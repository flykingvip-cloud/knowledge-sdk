"""Memory-only internal job model. No database schema, worker or HTTP routes."""
from __future__ import annotations
from dataclasses import dataclass, replace
from enum import Enum
import threading
import uuid
from typing import Optional, Protocol
from ..exceptions import ValidationError, ConflictError, NotFoundError
from .idempotency import request_fingerprint


class IngestionJobState(str, Enum):
    QUEUED = 'queued'
    PARSING = 'parsing'
    CHUNKING = 'chunking'
    INDEXING = 'indexing'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


ALLOWED_TRANSITIONS = {
    IngestionJobState.QUEUED: frozenset(('parsing', 'cancelled', 'failed')),
    IngestionJobState.PARSING: frozenset(('chunking', 'cancelled', 'failed')),
    IngestionJobState.CHUNKING: frozenset(('indexing', 'cancelled', 'failed')),
    IngestionJobState.INDEXING: frozenset(('completed', 'cancelled', 'failed')),
    IngestionJobState.FAILED: frozenset(),  # explicit retry only
    IngestionJobState.COMPLETED: frozenset(),
    IngestionJobState.CANCELLED: frozenset(),
}
_PROGRESS = dict(queued=0, parsing=10, chunking=40, indexing=70, completed=100, failed=0, cancelled=0)


@dataclass(frozen=True)
class IngestionJob:
    job_id: str
    tenant_id: str
    idempotency_key: str
    fingerprint: str
    status: IngestionJobState = IngestionJobState.QUEUED
    attempts: int = 1
    max_attempts: int = 3
    revision: int = 0
    chunks_total: int = 0
    chunks_indexed: int = 0
    anchors_created: int = 0
    error_code: Optional[str] = None

    @property
    def progress_pct(self): return _PROGRESS[self.status.value]

    def payload(self):
        return dict(job_id=self.job_id, tenant_id=self.tenant_id, status=self.status.value,
                    progress_pct=self.progress_pct, attempts=self.attempts,
                    stats=dict(chunks_total=self.chunks_total, chunks_indexed=self.chunks_indexed,
                               anchors_created=self.anchors_created), error_code=self.error_code,
                    error_message=None)


class IngestionJobStore(Protocol):
    def submit(self, tenant_id: str, idempotency_key: str, payload, *, max_attempts: int = 3) -> IngestionJob: ...
    def get(self, tenant_id: str, job_id: str) -> IngestionJob: ...
    def transition(self, tenant_id: str, job_id: str, state, *, expected_revision: int, **stats) -> IngestionJob: ...
    def retry(self, tenant_id: str, job_id: str, *, expected_revision: int) -> IngestionJob: ...


class InMemoryIngestionJobStore:
    def __init__(self):
        self._lock = threading.RLock()
        self._jobs = {}
        self._submissions = {}

    def submit(self, tenant_id, idempotency_key, payload, *, max_attempts=3):
        if any(type(v) is not str or not v.strip() for v in (tenant_id, idempotency_key)) or type(max_attempts) is not int or max_attempts < 1:
            raise ValidationError('INVALID_JOB_SUBMISSION')
        fingerprint = request_fingerprint(dict(payload=payload, max_attempts=max_attempts))
        with self._lock:
            key = (tenant_id, idempotency_key)
            if key in self._submissions:
                job = self._jobs[self._submissions[key]]
                if job.fingerprint != fingerprint: raise ConflictError('IDEMPOTENCY_CONFLICT')
                return job
            job = IngestionJob(uuid.uuid4().hex, tenant_id, idempotency_key, fingerprint, max_attempts=max_attempts)
            self._jobs[job.job_id] = job
            self._submissions[key] = job.job_id
            return job

    def get(self, tenant_id, job_id):
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.tenant_id != tenant_id: raise NotFoundError('JOB_NOT_FOUND')
            return job

    def _checked(self, tenant_id, job_id, revision):
        job = self.get(tenant_id, job_id)
        if type(revision) is not int or revision != job.revision: raise ConflictError('STALE_JOB_REVISION')
        return job

    def transition(self, tenant_id, job_id, state, *, expected_revision, **stats):
        try: state = IngestionJobState(state)
        except (TypeError, ValueError) as exc: raise ValidationError('INVALID_JOB_STATE') from exc
        with self._lock:
            job = self._checked(tenant_id, job_id, expected_revision)
            if state not in ALLOWED_TRANSITIONS[job.status]: raise ConflictError('INVALID_JOB_TRANSITION')
            if set(stats) - {'chunks_total', 'chunks_indexed', 'anchors_created', 'error_code'}:
                raise ValidationError('INVALID_JOB_PROGRESS')
            values = {k: stats.get(k, getattr(job, k)) for k in ('chunks_total', 'chunks_indexed', 'anchors_created')}
            if any(type(v) is not int or v < 0 or v < getattr(job, k) for k, v in values.items()) or values['chunks_indexed'] > values['chunks_total']:
                raise ValidationError('INVALID_JOB_PROGRESS')
            error = stats.get('error_code')
            # Never carry arbitrary exception text, content, credentials or PII.
            if state == IngestionJobState.FAILED:
                if error not in ('PARSE_FAILED', 'CHUNK_FAILED', 'INDEX_FAILED', 'CANCEL_FAILED', 'BACKEND_UNAVAILABLE'):
                    raise ValidationError('INVALID_JOB_ERROR_CODE')
            elif error is not None: raise ValidationError('UNEXPECTED_JOB_ERROR')
            if state == IngestionJobState.COMPLETED and values['chunks_total'] != values['chunks_indexed']:
                raise ValidationError('INCOMPLETE_JOB_PROGRESS')
            result = replace(job, status=state, revision=job.revision+1, error_code=error, **values)
            self._jobs[job_id] = result
            return result

    def retry(self, tenant_id, job_id, *, expected_revision):
        with self._lock:
            job = self._checked(tenant_id, job_id, expected_revision)
            if job.status != IngestionJobState.FAILED or job.attempts >= job.max_attempts:
                raise ConflictError('JOB_RETRY_NOT_ALLOWED')
            result = replace(job, status=IngestionJobState.QUEUED, revision=job.revision+1,
                             attempts=job.attempts+1, error_code=None, chunks_total=0,
                             chunks_indexed=0, anchors_created=0)
            self._jobs[job_id] = result
            return result
