"""Dependency-free task runtime with commit-before-raise DENY and revocation.

Lock order is always client._lock -> store.transaction. Cross-connection PG
transactions use the store's conservative advisory serialization boundary.
"""
from __future__ import annotations
from dataclasses import replace
from datetime import datetime, timezone, timedelta
from functools import wraps
import uuid
import inspect
from ..contracts.runtime import (ContextBudget, AgentProfile, TaskContext, SnapshotItem,
                                 ContextSnapshot, MidTaskRevocation)
from ..contracts.models import KnowledgeScope
from ..contracts.policy import AgentIdentity, Purpose, PolicyContext, DecisionEffect, enum_value
from ..contracts.events import OutboxEvent
from ..contracts.impact import UsageEvent, ImpactAlert, ImpactReason
from ..exceptions import PermissionDeniedError, ValidationError, NotFoundError, ConflictError


def now(): return datetime.now(timezone.utc).isoformat()
def uid(): return str(uuid.uuid4())


def operation(fn):
    """Rejected security operations commit DENY/revocation before raising outside tx."""
    @wraps(fn)
    def run(self,actor,*args,**kwargs):
        failure=None;result=None
        with self._lock, self.store.runtime_transaction():
            try:result=fn(self,actor,*args,**kwargs)
            except PermissionDeniedError as exc:
                bound=inspect.signature(fn).bind(self,actor,*args,**kwargs).arguments
                task_id=bound.get('task_id','')
                self._audit_operation(actor,fn.__name__,{'policy_context':PolicyContext(task_id=task_id)},None,denied=True)
                failure=exc
        if failure is not None:raise failure
        return result
    return run


class RuntimeMixin:
    def _runtime_principal(self,actor):
        self._check_principal(actor)
        principal=self.store.get_principal(actor.org_id,actor.user_id)
        if principal is not None and (not principal.active or str(principal.policy_generation)!=actor.policy_generation):
            raise PermissionDeniedError('principal_session_stale')

    @staticmethod
    def _runtime_admin(actor):
        if not set(actor.org_roles)&{'admin','manage_org'}:raise PermissionDeniedError('profile_admin_required')

    @operation
    def register_agent_profile(self,actor,agent_id,display_name='',allowed_purposes=(Purpose.READ,Purpose.GROUND_INTERNAL_LLM),allowed_kb_ids=(),allowed_space_types=(),max_clearance_level='internal',default_budget=None):
        self._runtime_principal(actor);self._runtime_admin(actor)
        try:self.store.get_agent_profile(actor.org_id,agent_id)
        except NotFoundError:pass
        else:raise ConflictError('Profile already registered')
        profile=AgentProfile(actor.org_id,agent_id,display_name,allowed_purposes,allowed_kb_ids,allowed_space_types,max_clearance_level,default_budget if default_budget is not None else ContextBudget(),updated_at=now())
        self.store.upsert_agent_profile(profile);self._profile_event(actor,profile,'agent.profile_registered')
        return profile

    @operation
    def update_agent_profile(self,actor,agent_id,*,display_name=None,allowed_purposes=None,allowed_kb_ids=None,allowed_space_types=None,max_clearance_level=None,default_budget=None,active=None):
        self._runtime_principal(actor);self._runtime_admin(actor)
        old=self.store.get_agent_profile(actor.org_id,agent_id)
        values=locals();changes={n:values[n] for n in ('display_name','allowed_purposes','allowed_kb_ids','allowed_space_types','max_clearance_level','default_budget','active') if values[n] is not None}
        profile=replace(old,**changes,profile_generation=old.profile_generation+1,updated_at=now())
        self.store.upsert_agent_profile(profile);self._profile_event(actor,profile,'agent.profile_updated')
        return profile

    def _profile_event(self,actor,profile,event_type):
        t=now();event=OutboxEvent(uid(),actor.org_id,'agent_profile',profile.agent_id,event_type,
                    {'agent_id':profile.agent_id,'profile_generation':profile.profile_generation},available_at=t,created_at=t)
        self.store.enqueue_outbox(event);self._audit_operation(actor,event_type,{},profile)
        self._runtime_event(event)

    @operation
    def get_agent_profile(self,actor,agent_id):
        self._runtime_principal(actor);return self.store.get_agent_profile(actor.org_id,agent_id)

    @operation
    def list_agent_profiles(self,actor):
        self._runtime_principal(actor);return self.store.list_agent_profiles(actor.org_id)

    @operation
    def create_task_context(self,actor,agent_id,*,purpose=Purpose.GROUND_INTERNAL_LLM,budget=None,ttl_seconds=900,scope=None):
        self._runtime_principal(actor)
        profile=self.store.get_agent_profile(actor.org_id,agent_id);purpose=enum_value(Purpose,purpose)
        if not profile.active or purpose not in profile.allowed_purposes:raise PermissionDeniedError('agent_profile_denied')
        if type(ttl_seconds) is not int or ttl_seconds<0:raise ValidationError('Invalid ttl_seconds')
        if isinstance(budget,dict):budget=ContextBudget.from_dict(budget)
        budget=profile.default_budget.clamp(budget if budget is not None else profile.default_budget)
        if isinstance(scope,dict):scope=KnowledgeScope.from_dict(scope)
        scope=scope if scope is not None else KnowledgeScope()
        if not isinstance(scope,KnowledgeScope):raise ValidationError('Invalid task scope')
        from ..contracts.policy import parse_time
        stamp=now();expires=(parse_time(stamp)+timedelta(seconds=min(ttl_seconds,budget.max_ttl_seconds))).isoformat()
        try:generation=int(actor.policy_generation)
        except ValueError:raise PermissionDeniedError('invalid_principal_generation') from None
        task=TaskContext(uid(),actor.org_id,actor.user_id,agent_id,purpose,generation,profile.profile_generation,scope,budget,expires,stamp,stamp)
        self.store.put_task_context(task);self._audit_operation(actor,'create_task_context',{'purpose':purpose,'policy_context':PolicyContext(task_id=task.task_id)},task)
        return task

    def _runtime_owned(self,actor,task_id):
        try:task=self.store.get_task_context(actor.org_id,task_id)
        except NotFoundError:raise PermissionDeniedError('runtime_resource_unavailable') from None
        if task.actor_id!=actor.user_id:raise PermissionDeniedError('runtime_resource_unavailable')
        return task

    def _runtime_validate(self,actor,task_id,snapshot_id=None):
        from ..contracts.policy import parse_time
        task=self._runtime_owned(actor,task_id)
        if task.status!='active':raise PermissionDeniedError('mid_task_revocation:'+task.status)
        if parse_time(task.expires_at)<=datetime.now(timezone.utc):
            self.store.update_task_context_status(actor.org_id,task_id,'expired',stamp=now())
            raise PermissionDeniedError('mid_task_revocation:expired')
        reason=''
        try:self._runtime_principal(actor)
        except PermissionDeniedError:reason='principal_stale'
        principal=self.store.get_principal(actor.org_id,actor.user_id)
        if principal is not None and (not principal.active or principal.policy_generation!=task.policy_generation):reason='principal_stale'
        if str(task.policy_generation)!=actor.policy_generation:reason='principal_stale'
        try:profile=self.store.get_agent_profile(actor.org_id,task.agent_id)
        except NotFoundError:profile=None
        if profile is None or not profile.active or profile.profile_generation!=task.profile_generation or task.purpose not in profile.allowed_purposes:reason=reason or 'profile_disabled'
        if reason:
            self._runtime_revoke(task,reason);raise PermissionDeniedError('mid_task_revocation:'+reason)
        snapshots=self.store.list_context_snapshots(task.org_id,task.task_id)
        if snapshot_id is not None and not any(s.snapshot_id==snapshot_id for s in snapshots):raise PermissionDeniedError('runtime_resource_unavailable')
        for snapshot in snapshots:
            if snapshot.status!='valid':raise PermissionDeniedError('mid_task_revocation:revoked')
            for item in snapshot.items:
                try:
                    ref=self._runtime_reference(actor,task,profile,item.doc_id,item.version,item.anchor_id,item.chunk_ids)
                    # A newly tightened redactor must not expose the old unredacted text.
                    if not ref.excerpt.startswith(item.text):raise PermissionDeniedError('redaction_changed')
                except (PermissionDeniedError,NotFoundError):
                    self._runtime_revoke(task,'resource_unavailable',doc_id=item.doc_id,version=item.version,anchor_id=item.anchor_id)
                    raise PermissionDeniedError('mid_task_revocation:resource_unavailable') from None
        return task,profile

    def _runtime_identity(self,profile):
        return AgentIdentity(profile.agent_id,profile.org_id,allowed_purposes=profile.allowed_purposes,allowed_kb_ids=profile.allowed_kb_ids,max_clearance_level=profile.max_clearance_level,profile_version=str(profile.profile_generation))

    def _runtime_reference(self,actor,task,profile,doc_id,version=None,anchor_id='',chunk_ids=()):
        d=self.store.get_document(doc_id);kb=self.store.get_kb(d.kb_id)
        if d.org_id!=actor.org_id or not task.scope.contains(d,kb) or (profile.allowed_space_types and kb.space_type not in profile.allowed_space_types):raise PermissionDeniedError('runtime_scope_denied')
        if d.archived or d.lifecycle_state=='revoked' or (d.rights and d.rights.revoked):raise PermissionDeniedError('resource_revoked')
        if not isinstance(anchor_id,str):raise ValidationError('Invalid anchor_id')
        if anchor_id:
            bound=self.store.get_anchor(actor.org_id,doc_id,version or d.current_version,anchor_id)
            latest=self.store.get_anchor(actor.org_id,doc_id,d.current_version,anchor_id)
            if any(a.reanchor_status.value!='anchored' for a in (bound,latest)):raise PermissionDeniedError('anchor_unhealthy')
        from ..ingestion.fingerprint import normalize_text
        agent=self._runtime_identity(profile);context=PolicyContext(task_id=task.task_id)
        _,delivered,chunks,_,_=self._delivered_source(actor,doc_id,version,agent=agent,purpose=task.purpose,policy_context=context)
        if not isinstance(chunk_ids,(tuple,list)) or any(not isinstance(v,str) for v in chunk_ids):raise ValidationError('Invalid chunk selectors')
        if chunk_ids and set(chunk_ids)-{c.chunk_id for c in chunks}:raise PermissionDeniedError('runtime_resource_unavailable')
        body=normalize_text('\n'.join(c.text for c in chunks if c.chunk_id in chunk_ids) if chunk_ids else delivered.text)
        return self.reference(actor,doc_id,version,chunk_ids or None,excerpt='' if anchor_id else body,anchor_id=anchor_id or None,
                              agent=agent,purpose=task.purpose,policy_context=context)

    @operation
    def create_context_snapshot(self,actor,task_id,entries_or_query,*,rerank=False,reranker_id=None,calibrator_id=None,min_calibrated_score=None,rerank_top_k=None,reranker=None,calibrator=None):
        task,profile=self._runtime_validate(actor,task_id)
        from ..retrieval.strategies import resolve
        resolved=resolve(rerank,reranker_id,calibrator_id,min_calibrated_score,rerank_top_k,reranker,calibrator,self.reranker_registry,self.calibrator_registry)
        if not isinstance(entries_or_query,str) and any(v is not None for v in resolved):raise ValidationError('Ranking requires a query')
        if isinstance(entries_or_query,str):
            response=self.search(actor,entries_or_query,'keyword',max(1,min(task.budget.max_items,100)),agent=self._runtime_identity(profile),purpose=task.purpose,scope=task.scope,reranker=resolved[0],calibrator=resolved[1],min_calibrated_score=min_calibrated_score,rerank_top_k=rerank_top_k)
            entries=[{'doc_id':h.doc_id,'version':h.version} for h in response.hits]
        elif isinstance(entries_or_query,(list,tuple)):entries=entries_or_query
        else:raise ValidationError('Expected query or entries')
        items=[];documents=set();remaining=task.budget.max_total_chars
        for entry in entries:
            if len(items)>=task.budget.max_items or remaining<=0:break
            if not isinstance(entry,dict) or set(entry)-{'doc_id','version','anchor_id','chunk_ids'}:raise ValidationError('Invalid snapshot entry')
            doc_id=entry.get('doc_id');version=entry.get('version');anchor_id=entry.get('anchor_id','');chunks=entry.get('chunk_ids',())
            if not isinstance(doc_id,str) or not doc_id:raise ValidationError('Invalid doc_id')
            if version is not None and (type(version) is not int or version<1):raise ValidationError('Invalid version')
            if doc_id not in documents and len(documents)>=task.budget.max_documents:continue
            try:ref=self._runtime_reference(actor,task,profile,doc_id,version,anchor_id,chunks)
            except (PermissionDeniedError,NotFoundError):continue
            body=ref.excerpt[:min(remaining,task.budget.max_chars_per_item)]
            if not body:continue
            items.append(SnapshotItem(ref.doc_id,ref.version,body,ref.source_uri,ref.anchor_id or '',tuple(ref.chunk_ids)))
            documents.add(doc_id);remaining-=len(body)
        snapshots=self.store.list_context_snapshots(actor.org_id,task_id)
        snapshot=ContextSnapshot(uid(),task_id,actor.org_id,len(snapshots)+1,tuple(items),now(),item_count=len(items),total_chars=sum(len(i.text) for i in items))
        snapshot=replace(snapshot,snapshot_sha256=snapshot.digest());self.store.put_context_snapshot(snapshot)
        for item in items:
            usage=UsageEvent(uid(),actor.org_id,item.doc_id,item.version,item.anchor_id,'context_snapshot',snapshot.snapshot_id,task_id,actor.user_id,task.agent_id,task.purpose.value,snapshot.snapshot_sha256,now())
            self.store.put_usage_event(usage,actor=actor,agent=self._runtime_identity(profile))
        self._audit_operation(actor,'create_context_snapshot',{'purpose':task.purpose,'policy_context':PolicyContext(task_id=task_id)},snapshot)
        return snapshot

    @operation
    def read_task_snapshot(self,actor,task_id,snapshot_id):
        self._runtime_validate(actor,task_id,snapshot_id)
        return self.store.get_context_snapshot(actor.org_id,snapshot_id)

    @operation
    def complete_task_context(self,actor,task_id):
        self._runtime_validate(actor,task_id)
        task=self.store.update_task_context_status(actor.org_id,task_id,'completed',stamp=now())
        self._audit_operation(actor,'complete_task_context',{},task);return task

    @operation
    def list_task_revocations(self,actor,task_id):
        self._runtime_principal(actor);self._runtime_owned(actor,task_id)
        return self.store.list_task_revocations(actor.org_id,task_id)

    def _runtime_revoke(self,task,reason,event_id='',doc_id='',version=0,anchor_id=''):
        if task.status!='active':return
        stamp=now()
        if not event_id:
            event=OutboxEvent(uid(),task.org_id,'task_context',task.task_id,'task.revoked',{'task_id':task.task_id,'reason_code':reason},available_at=stamp,created_at=stamp)
            self.store.enqueue_outbox(event);event_id=event.event_id
        self.store.update_task_context_status(task.org_id,task.task_id,'revoked',reason=reason,stamp=stamp)
        snapshots=self.store.list_context_snapshots(task.org_id,task.task_id)
        self.store.mark_context_snapshots_revoked(task.org_id,task.task_id)
        for snapshot_id in [s.snapshot_id for s in snapshots] or ['']:
            self.store.put_task_revocation(MidTaskRevocation(uid(),task.org_id,task.task_id,reason,stamp,snapshot_id,event_id,doc_id,version,anchor_id))
        alert=ImpactAlert(uid(),task.org_id,event_id,doc_id,version,'task_context',task.task_id,ImpactReason.ACCESS_REVOKED,created_at=stamp)
        self.store.put_impact_alert(alert,actor_id=task.actor_id)

    def _runtime_event(self,event):
        kind=event.event_type
        if kind in ('agent.profile_updated','principal.policy_bumped'):
            tasks=self.store.find_active_tasks_referencing(event.org_id,**({'agent_id':event.payload['agent_id']} if kind.startswith('agent.') else {'actor_id':event.payload['user_id']}))
            for task in tasks:
                if kind=='principal.policy_bumped' and task.policy_generation>=event.payload['policy_generation']:continue
                if kind.startswith('agent.') and task.profile_generation>=event.payload['profile_generation']:continue
                self._runtime_revoke(task,'profile_disabled' if kind.startswith('agent.') else 'principal_stale',event.event_id)
        elif kind in ('doc.archived','doc.revoked','acl.updated','rights.updated','anchor.drifted','anchor.orphaned'):
            from ..contracts.policy import parse_time
            doc_id=event.payload['doc_id']
            for task in self.store.find_active_tasks_referencing(event.org_id,doc_id=doc_id):
                bound=[i for s in self.store.list_context_snapshots(task.org_id,task.task_id) if parse_time(s.created_at)<=parse_time(event.created_at) for i in s.items if i.doc_id==doc_id]
                if not bound:continue
                if kind.startswith('anchor.') and not any(i.anchor_id==event.payload.get('anchor_id') for s in self.store.list_context_snapshots(task.org_id,task.task_id) for i in s.items):continue
                self._runtime_revoke(task,'resource_unavailable',event.event_id,doc_id,event.payload['version'],event.payload.get('anchor_id',''))
        elif kind in ('doc.revised','doc.published'):
            for task in self.store.find_active_tasks_referencing(event.org_id,doc_id=event.payload['doc_id']):
                if any(i.doc_id==event.payload['doc_id'] and i.version<event.payload['version'] for s in self.store.list_context_snapshots(task.org_id,task.task_id) for i in s.items):
                    self.store.put_impact_alert(ImpactAlert(str(uuid.uuid5(uuid.NAMESPACE_URL,event.event_id+task.task_id)),task.org_id,event.event_id,event.payload['doc_id'],event.payload['version'],'task_context',task.task_id,ImpactReason.SUPERSEDED,created_at=now()),actor_id=task.actor_id)

    @operation
    def _runtime_mcp(self,actor,task_id,snapshot_id,name,arguments,context):
        from ..mcp.tools import EvidenceTools
        from ..client.local import LocalKnowledgeClient
        task,profile=self._runtime_validate(actor,task_id,snapshot_id)
        if context.purpose!=task.purpose:raise PermissionDeniedError('runtime_purpose_denied')
        if context.agent is not None and context.agent.agent_id!=task.agent_id:raise PermissionDeniedError('runtime_agent_denied')
        authority=self
        class Engine:
            def evaluate(self,a,agent,kb,document=None,*args,**kwargs):
                decision=authority.policy_engine.evaluate(a,agent,kb,document,*args,**kwargs)
                allowed=not profile.allowed_space_types or kb.space_type in profile.allowed_space_types
                if document is not None:allowed=allowed and task.scope.contains(document,kb)
                if not allowed:return replace(decision,effect=DecisionEffect.DENY,reason_code='runtime_scope_denied')
                return decision
        view=LocalKnowledgeClient(self.store,policy_engine=Engine(),redaction_registry=self.redaction_registry,vector_index=self.vector_index,embedder=self.embedder,require_principal=self.require_principal,reranker_registry=self.reranker_registry,calibrator_registry=self.calibrator_registry)
        view._lock=self._lock
        runtime_agent=self._runtime_identity(profile)
        if context.agent is not None:
            if task.purpose not in context.agent.allowed_purposes:raise PermissionDeniedError('runtime_agent_denied')
            if context.agent.allowed_kb_ids:
                ids=tuple(k for k in context.agent.allowed_kb_ids if not profile.allowed_kb_ids or k in profile.allowed_kb_ids)
                if not ids:raise PermissionDeniedError('runtime_agent_denied')
                runtime_agent=replace(runtime_agent,allowed_kb_ids=ids)
            if context.agent.max_clearance_level:
                levels=('','public','internal','confidential','restricted')
                runtime_agent=replace(runtime_agent,max_clearance_level=min((runtime_agent.max_clearance_level,context.agent.max_clearance_level),key=lambda v:levels.index(v) if v in levels else -1))
        from ..mcp.tools import plain
        params=dict(arguments)
        if name=='search_evidence':params['limit']=min(params.get('limit',5),task.budget.max_items,task.budget.max_documents)
        if name=='get_evidence_pack':params['max_chars']=min(params.get('max_chars',4000),task.budget.max_total_chars)
        if not all((task.budget.max_documents,task.budget.max_items,task.budget.max_chars_per_item,task.budget.max_total_chars)):raise PermissionDeniedError('runtime_budget_exceeded')
        if name=='search_evidence':params['task_id']=task_id
        result=plain(getattr(EvidenceTools(view),'_'+name)(replace(context,agent=runtime_agent),**params))
        material=result.get('hits',result.get('items',[]));texts=[i.get('excerpt',i.get('text','')) for i in material]
        if (len(material)>task.budget.max_items or len({i['doc_id'] for i in material})>task.budget.max_documents or any(len(text)>task.budget.max_chars_per_item for text in texts) or sum(map(len,texts))>task.budget.max_total_chars):raise PermissionDeniedError('runtime_budget_exceeded')
        return result
