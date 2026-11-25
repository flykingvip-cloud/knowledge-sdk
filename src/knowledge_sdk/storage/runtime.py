"""Shared parameterized v5 persistence. PostgreSQL wraps every public method in tenant_method.

SQL columns are redundant integrity checks, never an independent authority.
Snapshot payloads are insert-only; only their external revocation status changes.
"""
from __future__ import annotations
import json
from dataclasses import replace
from contextlib import contextmanager
from ..contracts.models import encode, decode
from ..contracts.runtime import ContextSnapshot
from ..exceptions import ConflictError, NotFoundError, ValidationError

_COLUMNS={
 'agent_profiles':('org_id','agent_id','display_name','allowed_purposes_json','allowed_kb_ids_json','allowed_space_types_json','max_clearance_level','default_budget_json','active','profile_generation','updated_at'),
 'task_contexts':('task_id','org_id','actor_id','agent_id','purpose','policy_generation','profile_generation','scope_json','budget_json','status','revoked_reason','revoked_at','expires_at','created_at','updated_at'),
 'context_snapshots':('snapshot_id','task_id','org_id','snapshot_seq','item_count','total_chars','snapshot_sha256','status','created_at'),
 'task_revocations':('revocation_id','org_id','task_id','snapshot_id','trigger_event_id','reason_code','affected_doc_id','affected_version','affected_anchor_id','created_at')}


def values(table,obj):
    data=obj.to_dict()
    out=[]
    for col in _COLUMNS[table]:
        key=col[:-5] if col.endswith('_json') else col
        value=data[key]
        if col.endswith('_json'):value=json.dumps(value,sort_keys=True,separators=(',',':'))
        elif isinstance(value,bool):value=int(value)
        out.append(value)
    return tuple(out)


class RuntimeStoreMixin:
    @contextmanager
    def runtime_transaction(self):
        # Serialize policy/resource decisions and their writes across PG clients,
        # not outbox claims: SKIP LOCKED must remain independently concurrent.
        with self.transaction():
            if hasattr(self,'_pg'):self._execute('SELECT pg_advisory_xact_lock(5855462191)')
            yield

    def _rt_execute(self,sql,args=()):
        return self._execute(sql.replace('?', '%s') if hasattr(self,'_pg') else sql,args)

    def _rt_write(self,table,obj,keys,upsert=False):
        columns=_COLUMNS[table]+('data',)
        data=values(table,obj)+(self._dump(obj),)
        sql='INSERT INTO '+table+' ('+','.join(columns)+') VALUES ('+','.join('?' for _ in columns)+')'
        if upsert:sql+=' ON CONFLICT('+','.join(keys)+') DO UPDATE SET '+','.join(c+'=excluded.'+c for c in columns if c not in keys)
        self._rt_execute(sql,data)

    def _rt_read(self,table,org_id,where='',args=()):
        columns=_COLUMNS[table]
        rows=self._rt_execute('SELECT '+','.join(columns)+',data FROM '+table+' WHERE org_id=?'+where,(org_id,)+tuple(args))
        result=[]
        for row in rows:
            try:obj=decode(json.loads(row[-1]));expected=values(table,obj)
            except (ValueError,TypeError,KeyError,AttributeError,ValidationError) as exc:raise ConflictError('Runtime metadata integrity failure') from exc
            actual=tuple(row[:-1])
            if table=='context_snapshots':
                # Status is separately mutable, sealed content is not.
                index=columns.index('status')
                if actual[index] not in ('valid','revoked'):raise ConflictError('Invalid snapshot status')
                expected=expected[:index]+(actual[index],)+expected[index+1:]
                if not isinstance(obj,ContextSnapshot) or obj.status!='valid' or not obj.snapshot_sha256 or obj.digest()!=obj.snapshot_sha256:raise ConflictError('Snapshot seal mismatch')
                obj=replace(obj,status=actual[index])
            # JSON semantic comparison (not whitespace) for cross-driver stability.
            for col,a,b in zip(columns,actual,expected):
                if (json.loads(a)!=json.loads(b)) if col.endswith('_json') else (a!=b):raise ConflictError('Runtime SQL/JSON mismatch')
            result.append(obj)
        return result

    def upsert_agent_profile(self,profile):
        with self.runtime_transaction():self._rt_write('agent_profiles',profile,('org_id','agent_id'),True)

    def get_agent_profile(self,org_id,agent_id):
        rows=self._rt_read('agent_profiles',org_id,' AND agent_id=?',(agent_id,))
        if not rows:raise NotFoundError('Runtime resource unavailable')
        return rows[0]

    def list_agent_profiles(self,org_id):
        return sorted(self._rt_read('agent_profiles',org_id),key=lambda p:p.agent_id)

    def put_task_context(self,task):
        self._rt_write('task_contexts',task,('task_id',))

    def get_task_context(self,org_id,task_id):
        rows=self._rt_read('task_contexts',org_id,' AND task_id=?',(task_id,))
        if not rows:raise NotFoundError('Runtime resource unavailable')
        return rows[0]

    def list_task_contexts(self,org_id,*,actor_id=None,status=None):
        sql='';args=[]
        for col,value in (('actor_id',actor_id),('status',status)):
            if value is not None:sql+=' AND '+col+'=?';args.append(value)
        return self._rt_read('task_contexts',org_id,sql,args)

    def update_task_context_status(self,org_id,task_id,status,*,reason='',stamp=''):
        old=self.get_task_context(org_id,task_id)
        if old.status!='active' and status!=old.status:raise ConflictError('Terminal task cannot be revived')
        if status=='active':raise ConflictError('Task transition must be terminal')
        obj=replace(old,status=status,revoked_reason=reason,revoked_at=stamp if status=='revoked' else old.revoked_at,updated_at=stamp or old.updated_at)
        columns=_COLUMNS['task_contexts']
        self._rt_execute('UPDATE task_contexts SET '+','.join(c+'=?' for c in columns)+',data=? WHERE org_id=? AND task_id=?',values('task_contexts',obj)+(self._dump(obj),org_id,task_id))
        return obj

    def put_context_snapshot(self,snapshot):
        if snapshot.status!='valid' or snapshot.digest()!=snapshot.snapshot_sha256:raise ConflictError('Invalid snapshot seal')
        self._rt_write('context_snapshots',snapshot,('snapshot_id',))

    def get_context_snapshot(self,org_id,snapshot_id):
        rows=self._rt_read('context_snapshots',org_id,' AND snapshot_id=?',(snapshot_id,))
        if not rows:raise NotFoundError('Runtime resource unavailable')
        return rows[0]

    def list_context_snapshots(self,org_id,task_id):
        return sorted(self._rt_read('context_snapshots',org_id,' AND task_id=?',(task_id,)),key=lambda s:s.snapshot_seq)

    def mark_context_snapshots_revoked(self,org_id,task_id):
        self._rt_execute("UPDATE context_snapshots SET status='revoked' WHERE org_id=? AND task_id=?",(org_id,task_id))

    def put_task_revocation(self,revocation):
        self._rt_write('task_revocations',revocation,('revocation_id',))

    def list_task_revocations(self,org_id,task_id):
        return self._rt_read('task_revocations',org_id,' AND task_id=?',(task_id,))

    def find_active_tasks_referencing(self,org_id,*,doc_id=None,actor_id=None,agent_id=None):
        where=" AND status='active'";args=[]
        for col,value in (('actor_id',actor_id),('agent_id',agent_id)):
            if value is not None:where+=' AND '+col+'=?';args.append(value)
        if doc_id is not None:
            where+=' AND task_id IN (SELECT task_id FROM usage_events WHERE org_id=? AND doc_id=?)'
            args.extend((org_id,doc_id))
        return self._rt_read('task_contexts',org_id,where,args)
