"""Tenant-bound stdlib adapters for the Wave1.8 protocols, on explicit schema v6.

The caller owns the MetadataStore connection. execute() is the mutation boundary:
claim, durable side effect and exact response snapshot commit in ONE transaction.
A process killed before commit rolls all three back. Replays still require a fresh
authorization callback, including current User intersect Agent and explicit Deny.
"""
from __future__ import annotations
from contextlib import contextmanager
from dataclasses import asdict
import json
import time
from ..contracts.idempotency import (IdempotencyDecision as Decision,
    IdempotencyRecord, InMemoryIdempotencyStore, request_fingerprint)
from ..contracts.ingestion_jobs import (IngestionJob, IngestionJobState,
    InMemoryIngestionJobStore)
from ..exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from .migration_v6 import require_v6


def _job_json(job):
    data=asdict(job)
    data["status"]=job.status.value
    return _json(data)


def _json(value):
    # Reuse strict JSON validation; no pickle, model markers or exception payloads.
    request_fingerprint(value)
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)


class _Bound:
    def __init__(self,store,tenant_id):
        if type(tenant_id) is not str or not tenant_id or tenant_id!=tenant_id.strip():
            raise ValidationError('EXPLICIT_ENTERPRISE_TENANT_REQUIRED')
        require_v6(store)
        self.store=store
        self.tenant_id=tenant_id
        self.pg=hasattr(store,'_pg')

    def _tenant(self,tenant):
        if tenant!=self.tenant_id:
            raise PermissionDeniedError('TENANT_MISMATCH')

    def _sql(self,sql,args=()):
        return self.store._execute(sql.replace('?','%s') if self.pg else sql,args)

    @contextmanager
    def _transaction(self,lock=None):
        with self.store.transaction():
            if self.pg:
                with self.store.tenant_scope(self.tenant_id):
                    if lock is not None:
                        self._sql('SELECT pg_advisory_xact_lock(hashtextextended(?,0))',(lock,))
                    yield
            else:
                yield


class PersistentIdempotencyStore(_Bound):
    def __init__(self,store,tenant_id,ttl_seconds=300,*,clock=time.time):
        # Memory protocol is the validation oracle, not the persistence backend.
        InMemoryIdempotencyStore(ttl_seconds)
        super().__init__(store,tenant_id)
        self.ttl_seconds=ttl_seconds
        self._clock=clock  # durable epoch, deliberately not process-monotonic time

    def _record(self,row):
        return IdempotencyRecord(tuple(row[:4]),row[4],row[5],row[6],bool(row[7]),
                                 json.loads(row[8]) if row[8] is not None else None)

    def _find(self,key):
        rows=self._sql('SELECT org_id,method,canonical_path,idempotency_key,fingerprint,claim_id,expires_at,completed,response_snapshot FROM idempotency_records WHERE org_id=? AND method=? AND canonical_path=? AND idempotency_key=?',key)
        return self._record(rows[0]) if rows else None

    def begin(self,tenant_id,method,canonical_path,idempotency_key,payload):
        self._tenant(tenant_id)
        # Exact key validation and fingerprint semantics from the original protocol.
        _,candidate=InMemoryIdempotencyStore(self.ttl_seconds).begin(tenant_id,method,canonical_path,idempotency_key,payload)
        key=candidate.key
        with self._transaction(_json(list(key))):
            self._sql('DELETE FROM idempotency_records WHERE org_id=? AND method=? AND canonical_path=? AND idempotency_key=? AND expires_at<=?',key+(self._clock(),))
            record=self._find(key)
            if record is None:
                self._sql('INSERT INTO idempotency_records(org_id,method,canonical_path,idempotency_key,fingerprint,expires_at) VALUES(?,?,?,?,?,?)',key+(candidate.fingerprint,self._clock()+self.ttl_seconds))
                return Decision.NEW,self._find(key)
            if record.fingerprint!=candidate.fingerprint:
                return Decision.CONFLICT_PAYLOAD_MISMATCH,record
            return (Decision.REPLAY_EXACT if record.completed else Decision.IN_PROGRESS),record

    def complete(self,record,result):
        self._tenant(record.key[0])
        encoded=_json(result)
        with self._transaction(_json(list(record.key))):
            current=self._find(record.key)
            if current is None or current.expires_at<=self._clock() or current.claim_id!=record.claim_id or current.fingerprint!=record.fingerprint:
                raise ConflictError('STALE_IDEMPOTENCY_CLAIM')
            if current.completed:
                if _json(current.result)!=encoded:
                    raise ConflictError('IDEMPOTENCY_RESULT_CONFLICT')
                return current
            self._sql('UPDATE idempotency_records SET completed=1,response_snapshot=? WHERE org_id=? AND method=? AND canonical_path=? AND idempotency_key=? AND claim_id=?',(encoded,)+record.key+(record.claim_id,))
            return self._find(record.key)

    def cleanup(self):
        with self._transaction():
            rows=self._sql('SELECT claim_id FROM idempotency_records WHERE org_id=? AND expires_at<=?',(self.tenant_id,self._clock()))
            self._sql('DELETE FROM idempotency_records WHERE org_id=? AND expires_at<=?',(self.tenant_id,self._clock()))
            return len(rows)

    def execute(self,method,canonical_path,idempotency_key,payload,*,authorize,mutate):
        """No authorization cache. mutate must use THIS store/transaction only.

        External services or independently committed connections are not supported
        transactional side effects. There is no automatic unkeyed mutation retry.
        """
        # Global runtime transaction precedes key lock, matching LocalClient's lock
        # ordering. RLock serializes this connection; PG serializes DB transactions.
        with self.store.runtime_transaction(),self._transaction():
            authorize()
            decision,record=self.begin(self.tenant_id,method,canonical_path,idempotency_key,payload)
            if decision==Decision.CONFLICT_PAYLOAD_MISMATCH:
                raise ConflictError('IDEMPOTENCY_CONFLICT')
            if decision==Decision.IN_PROGRESS:
                raise ConflictError('IDEMPOTENCY_IN_PROGRESS')
            if decision==Decision.REPLAY_EXACT:
                return record.result
            result=mutate()
            return self.complete(record,result).result


class PersistentIngestionJobStore(_Bound):
    """Durable CAS and idempotent submission; no scheduler or background worker."""
    def _decode(self,row):
        data=json.loads(row[-1])
        data['status']=IngestionJobState(data['status'])
        job=IngestionJob(**data)
        if (job.tenant_id,job.job_id,job.idempotency_key,job.fingerprint,job.revision,job.status.value)!=tuple(row[:-1]):
            raise ConflictError('JOB_INTEGRITY_FAILURE')
        return job

    def submit(self,tenant_id,idempotency_key,payload,*,max_attempts=3):
        self._tenant(tenant_id)
        candidate=InMemoryIngestionJobStore().submit(tenant_id,idempotency_key,payload,max_attempts=max_attempts)
        with self._transaction(_json(['job',tenant_id,idempotency_key])):
            rows=self._sql('SELECT org_id,job_id,idempotency_key,fingerprint,revision,status,data FROM ingestion_jobs WHERE org_id=? AND idempotency_key=?',(tenant_id,idempotency_key))
            if rows:
                job=self._decode(rows[0])
                if job.fingerprint!=candidate.fingerprint:
                    raise ConflictError('IDEMPOTENCY_CONFLICT')
                return job
            self._sql('INSERT INTO ingestion_jobs(org_id,job_id,idempotency_key,fingerprint,revision,status,data) VALUES(?,?,?,?,?,?,?)',(tenant_id,candidate.job_id,idempotency_key,candidate.fingerprint,0,candidate.status.value,_job_json(candidate)))
            return candidate

    def get(self,tenant_id,job_id):
        if tenant_id!=self.tenant_id:raise NotFoundError('JOB_NOT_FOUND')
        with self._transaction():
            rows=self._sql('SELECT org_id,job_id,idempotency_key,fingerprint,revision,status,data FROM ingestion_jobs WHERE org_id=? AND job_id=?',(tenant_id,job_id))
            if not rows:
                raise NotFoundError('JOB_NOT_FOUND')
            return self._decode(rows[0])

    def _change(self,tenant_id,job_id,method,**kwargs):
        if tenant_id!=self.tenant_id:raise NotFoundError('JOB_NOT_FOUND')
        with self._transaction(_json(['job-id',tenant_id,job_id])):
            current=self.get(tenant_id,job_id)
            core=InMemoryIngestionJobStore()
            core._jobs[job_id]=current
            result=getattr(core,method)(tenant_id,job_id,**kwargs)
            self._sql('UPDATE ingestion_jobs SET revision=?,status=?,data=? WHERE org_id=? AND job_id=? AND revision=?',(result.revision,result.status.value,_job_json(result),tenant_id,job_id,current.revision))
            return self.get(tenant_id,job_id)

    def transition(self,tenant_id,job_id,state,*,expected_revision,**stats):
        return self._change(tenant_id,job_id,'transition',state=state,expected_revision=expected_revision,**stats)

    def retry(self,tenant_id,job_id,*,expected_revision):
        return self._change(tenant_id,job_id,'retry',expected_revision=expected_revision)
