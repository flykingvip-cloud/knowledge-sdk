from __future__ import annotations
import knowledge_sdk
from datetime import datetime, timezone
from functools import wraps
import threading
import inspect
import uuid
import math
from typing import Optional, Sequence, List
from ..contracts.policy import (ResourceRights, PolicyContext, PolicyAction, Purpose, DecisionEffect, PolicyRule, enum_value)
from ..permissions.engine import KnowledgePolicyEngine, DefaultPolicyEngine, intersect_decisions
from ..permissions.redaction import RedactionRegistry
from ..contracts.issues import EvidenceIssue, IssueType
from ..contracts.models import Actor
from dataclasses import replace
from ..contracts.models import (KnowledgeScope, ConsumerBinding, KnowledgeAnswer, GeneratedAnswer, Attachment, MaterialReceipt)
from ..retrieval.answers import AnswerGenerator, ExtractiveAnswerGenerator
from ..permissions.policy import can_manage_kb, can_upload_to_kb
from ..contracts.models import (KnowledgeBase, Document, DocumentVersion, DocumentACL, KnowledgeRef, RetrieveResponse, ExcerptPolicy)
from ..contracts.uri import build_uri, parse_uri_v2
from ..contracts.anchors import ReanchorStatus, integer, identifier
from ..contracts.reanchor import merge_anchors_for_version
from .compat import CompatMixin
from ..runtime.service import RuntimeMixin
from ..governance.workflow import GovernanceMixin
from ..governance.issues import IssueMixin
from ..packs.service import PackMixin
from .anchors import deliver as deliver_anchor, validate_source as validate_anchor_source, validate_identity as validate_anchor_identity
from ..contracts.receipts import consume, batch_consume, validate_excerpt
from ..exceptions import PermissionDeniedError, NotFoundError, ValidationError, ConflictError, TamperedExcerptError
from ..permissions.policy import can_admin, can_read, can_write
from ..storage.sqlite_store import SQLiteStore
from ..ingestion.parsers import ParserRegistry
from ..ingestion.chunkers import HierarchicalChunker
from ..ingestion.fingerprint import fingerprints, classify, normalize_text, sha256
from ..retrieval.base import VectorHit
from ..retrieval.hybrid import search as run_search
from ..retrieval.excerpt import make_excerpt

def serialized(method):
    signature = inspect.signature(method)
    audited = method.__name__ in {
        'ingest','archive','restore','set_document_acl','set_document_rights',
        'search','retrieve','consume','attach','confirm_anchor_reanchor',
        'submit_for_review','approve_release','reject_release','publish_release','record_dissent',
        'resolve_evidence_issue','create_evidence_pack','get_evidence_pack','verify_evidence_pack','export_evidence_pack',
        'report_evidence_issue','get_document','reference','query_audit_events',
        'list_impact_alerts','acknowledge_impact_alert','drain_outbox','ask','batch_consume','verify_ref'}
    @wraps(method)
    def wrapped(self,*args,**kwargs):
        with self._lock:
            values=signature.bind(self,*args,**kwargs).arguments
            actor=values.get('actor')
            frame={'action':method.__name__,'values':values,'recorded':False}
            self._audit_frames.append(frame)
            try:
                try:
                    if actor is not None:self._check_principal(actor)
                    result=method(self,*args,**kwargs)
                except PermissionDeniedError:
                    if actor is not None:self._audit_operation(actor,method.__name__,values,None,denied=True)
                    raise
                if audited and actor is not None and not frame['recorded']:
                    self._audit_operation(actor,method.__name__,values,result)
                return result
            finally:self._audit_frames.pop()

    return wrapped

class _AuditedEngine:
    """Capture decisions made by retrieval too, not just direct evaluate_policy."""
    def __init__(self, client, delegate):
        self.client=client;self.delegate=delegate
    def __getattr__(self,name):return getattr(self.delegate,name)
    def evaluate(self, actor, agent, kb, document=None, acl=None, member_role=None,
                 action=PolicyAction.READ_CONTENT, purpose=Purpose.READ, context=None):
        try:self.client._check_principal(actor)
        except PermissionDeniedError:
            self.client._audit_operation(actor,'evaluate_policy',{},None,denied=True)
            raise
        decision=self.delegate.evaluate(actor,agent,kb,document,acl,member_role,action,purpose,context)
        self.client._audit_operation(actor,'evaluate_policy',
                    {'agent':agent,'purpose':purpose,'doc_id':document.doc_id if document else '', 'policy_context':context},decision)
        return decision


class LocalKnowledgeClient(CompatMixin,RuntimeMixin, GovernanceMixin, IssueMixin, PackMixin):
    """Trusted in-process API. Caller supplies an authenticated Actor, not user input."""
    def __init__(self,store=None,blob_store=None,parsers=None,chunker=None,vector_index=None,embedder=None,excerpt_policy=None,*,policy_engine:Optional[KnowledgePolicyEngine]=None,redaction_registry:Optional[RedactionRegistry]=None,policy_rules:Sequence[PolicyRule]=(),identity_resolver=None,allow_insecure_local_webhook=False,require_principal=False,reranker_registry=None,calibrator_registry=None,connector_registry=None):
        self.policy_engine = policy_engine if policy_engine is not None else DefaultPolicyEngine(policy_rules)
        self.redaction_registry = redaction_registry if redaction_registry is not None else RedactionRegistry()
        self.store=store if store is not None else SQLiteStore()
        self.blob_store=blob_store; self.parsers=parsers or ParserRegistry.defaults(); self.chunker=chunker or HierarchicalChunker()
        if (vector_index is None)!=(embedder is None): raise ValidationError("Provide both vector_index and embedder")
        self.vector_index=vector_index; self.embedder=embedder; self.excerpt_policy=excerpt_policy or ExcerptPolicy()
        self._lock=threading.RLock()
        from ..retrieval.strategies import registries
        self.reranker_registry,self.calibrator_registry=registries(reranker_registry,calibrator_registry)
        self.connector_registry=dict(connector_registry or {})
        self._audit_frames=[]
        self.require_principal=require_principal
        self.identity_resolver=identity_resolver
        self.allow_insecure_local_webhook=allow_insecure_local_webhook
    @property
    def policy_engine(self): return self._policy_engine
    @policy_engine.setter
    def policy_engine(self, value): self._policy_engine=_AuditedEngine(self,value)

    def _check_principal(self,actor):
        from ..permissions.identity import check_principal
        check_principal(self.store,actor,required=self.require_principal)

    def _audit_operation(self, actor, action, values, result, denied=False):
        from ..audit.ledger import append
        # Legacy host adapters may not yet implement the new optional ledger.
        if not hasattr(self.store,'append_audit_event'): return
        ref=values.get('ref')
        doc_id=values.get('doc_id') or getattr(ref,'doc_id','') or getattr(result,'doc_id','')
        effect=DecisionEffect.DENY if denied else DecisionEffect.ALLOW
        reason='permission_denied' if denied else 'ok'
        profile=''
        if action=='evaluate_policy' and result is not None:
            effect=result.effect;reason=result.reason_code;profile=result.redaction_profile
        elif isinstance(result,MaterialReceipt) and result.status not in ('consumed','partial'):
            effect=DecisionEffect.DENY;reason=result.reason_code or 'unavailable'
        context=values.get('policy_context')
        audit_purpose=values.get('purpose') or (Purpose.GROUND_INTERNAL_LLM if values.get('generator') is not None else Purpose.READ)
        append(self.store,actor,action,agent=values.get('agent'),
               purpose=audit_purpose,doc_id=doc_id,
               effect=effect,reason=reason,redaction_profile=profile,
               request_id=context.request_id if context else '',task_id=context.task_id if context else '',
               policy_generation=str(getattr(result,"policy_generation",(context.policy_generation if context and context.policy_generation else actor.policy_generation))))

    @staticmethod
    def _audit_admin(actor):
        return bool(set(actor.org_roles).intersection(('admin','manage_org','auditor')))

    @serialized
    def query_audit_events(self,actor,*,doc_id=None,actor_id=None,action=None,since=None,until=None,limit=100,agent=None,purpose=Purpose.READ,policy_context=None):
        if not self._audit_admin(actor):
            if actor_id is not None and actor_id!=actor.user_id:
                raise PermissionDeniedError('audit_scope_denied')
            actor_id=actor.user_id
        events=self.store.list_audit_events(actor.org_id,doc_id=doc_id,actor_id=actor_id,
                    action=action,since=since,until=until,limit=limit)
        result=[]
        for event in events:
            if event.doc_id:
                try:
                    decision=self.evaluate_policy(actor,event.doc_id,agent=agent,purpose=purpose,policy_context=policy_context)
                    if not decision.allowed: continue
                    if decision.effect==DecisionEffect.ALLOW_WITH_REDACTION:
                        self.redaction_registry.apply('',decision.redaction_profile,purpose)
                except (NotFoundError,PermissionDeniedError): continue
            result.append(event)
        return result

    @staticmethod
    def _org_agent(actor,agent,purpose):
        purpose=enum_value(Purpose,purpose)
        if agent is not None:
            if agent.org_id!=actor.org_id or purpose not in agent.allowed_purposes or agent.allowed_kb_ids:
                raise PermissionDeniedError('org_agent_scope_denied')

    @serialized
    def verify_audit_chain(self,actor,*,from_seq=1,to_seq=None,agent=None,purpose=Purpose.READ,policy_context=None):
        from ..audit.ledger import verify_audit_chain
        self._org_agent(actor,agent,purpose)
        if not set(actor.org_roles).intersection(('admin','manage_org')):
            raise PermissionDeniedError('audit_admin_required')
        return verify_audit_chain(self.store,actor.org_id,from_seq=from_seq,to_seq=to_seq)

    def _visible_impact(self,actor,alert,*,agent=None,purpose=Purpose.READ,policy_context=None):
        if alert.org_id!=actor.org_id:return False
        if alert.target_type=='task_context':
            try:return self._runtime_owned(actor,alert.target_id).org_id==actor.org_id
            except PermissionDeniedError:return False
        document=self.store.get_document(alert.doc_id)
        if document.org_id!=actor.org_id:return False
        owner=self.store.impact_owner(actor.org_id,alert.alert_id)==actor.user_id
        boundary=self.evaluate_policy(actor,kb_id=document.kb_id,agent=agent,purpose=purpose,policy_context=policy_context)
        if not boundary.allowed:return False
        # Permission to know an alert exists is distinct from permission to read
        # its revoked source. Only owners/managers get identifier-only metadata.
        management=self.evaluate_policy(actor,kb_id=document.kb_id,action=PolicyAction.MANAGE_SPACE,
                    agent=agent,purpose=purpose,policy_context=policy_context)
        admin=bool(set(actor.org_roles).intersection(('admin','manage_org')))
        if not (owner or admin or management.allowed):return False
        decision=self.evaluate_policy(actor,alert.doc_id,agent=agent,purpose=purpose,policy_context=policy_context)
        profiles=','.join(dict.fromkeys(p for value in (decision.redaction_profile,
                   document.rights.redaction_profile if document.rights else '') for p in value.split(',') if p))
        if profiles:self.redaction_registry.apply('',profiles,purpose)
        # Even after DENY, no content, title, excerpt, claim snapshot or receipt
        # escapes: ImpactAlert.summary is regenerated from five opaque fields.
        return True

    @serialized
    def list_impact_alerts(self,actor,*,doc_id=None,status=None,target_id=None,agent=None,purpose=Purpose.READ,policy_context=None):
        result=[]
        for alert in self.store.list_impact_alerts(actor.org_id,doc_id=doc_id,status=status,target_id=target_id):
            try:
                if self._visible_impact(actor,alert,agent=agent,purpose=purpose,policy_context=policy_context):result.append(alert)
            except (NotFoundError,PermissionDeniedError):continue
        return result

    @serialized
    def acknowledge_impact_alert(self,actor,alert_id,*,status='acknowledged',agent=None,purpose=Purpose.READ,policy_context=None):
        if status not in ('acknowledged','resolved'):raise ValidationError('Invalid acknowledgement status')
        with self.store._write_scope():
            alerts=[a for a in self.store.list_impact_alerts(actor.org_id) if a.alert_id==alert_id]
            if not alerts:raise NotFoundError('Impact alert not found')
            alert=alerts[0]
            if not self._visible_impact(actor,alert,agent=agent,purpose=purpose,policy_context=policy_context):
                raise PermissionDeniedError('impact_scope_denied')
            self.store.update_impact_alert_status(actor.org_id,alert_id,status)
            return replace(alert,status=status)

    @serialized
    def drain_outbox(self,actor,*,limit=50,agent=None,purpose=Purpose.READ,policy_context=None):
        from ..events.outbox import OutboxDispatcher
        from ..impact.radar import ImpactRadar
        from ..impact.webhook import WebhookDispatcher
        self._org_agent(actor,agent,purpose)
        if not set(actor.org_roles).intersection(('admin','manage_org')):raise PermissionDeniedError('outbox_admin_required')
        worker=OutboxDispatcher(self.store,radar=ImpactRadar(self),webhook=WebhookDispatcher(self.store,
                                  allow_insecure_local_webhook=self.allow_insecure_local_webhook))
        return worker.drain_outbox(limit=limit,org_id=actor.org_id)

    def _record_usage(self,actor,ref,receipt,*,agent=None,purpose=Purpose.READ,policy_context=None):
        from ..contracts.impact import UsageEvent
        from ..contracts.models import encode
        import json
        if receipt.status not in ('consumed','partial'):return
        event=UsageEvent(str(uuid.uuid4()),actor.org_id,ref.doc_id,ref.version,
                         anchor_id=ref.anchor_id,consumer_type=receipt.consumer_type,
                         consumer_id=receipt.consumer_id,
                         task_id=(policy_context.task_id if policy_context else '') or receipt.used_by_stage,
                         actor_id=actor.user_id,agent_id=agent.agent_id if agent else '',
                         purpose=enum_value(Purpose,purpose).value,
                         receipt_hash=sha256(json.dumps(encode(receipt),sort_keys=True,separators=(',',':'))),
                         created_at=datetime.now(timezone.utc).isoformat())
        self.store.put_usage_event(event,actor=actor,agent=agent)

    def _audit_current_write(self,actor,doc_id,result=None):
        writes={'ingest','archive','restore','set_document_acl','set_document_rights',
                'confirm_anchor_reanchor','report_evidence_issue','consume','attach'}
        for frame in reversed(self._audit_frames):
            if frame['action'] not in writes:continue
            if not frame['recorded']:
                values=dict(frame['values']);values['doc_id']=doc_id
                self._audit_operation(actor,frame['action'],values,result)
                frame['recorded']=True
            break

    def _emit_event(self, actor, event_type, doc_id, version, *, anchor_id='', previous_version=0):
        from ..contracts.events import OutboxEvent
        stamp=datetime.now(timezone.utc).isoformat()
        payload={'doc_id':doc_id,'version':version,'previous_version':previous_version}
        if anchor_id: payload['anchor_id']=anchor_id
        event=OutboxEvent(str(uuid.uuid4()),actor.org_id,'anchor' if anchor_id else
                          'acl' if event_type=='acl.updated' else 'document',
                          anchor_id or doc_id,event_type,payload=payload,
                          available_at=stamp,created_at=stamp)
        self.store.enqueue_outbox(event)
        self._runtime_event(event)
        self._audit_current_write(actor,doc_id)

    @serialized
    def register_webhook_subscription(self,actor,url,secret,event_types,*,allow_insecure_local=False):
        from ..contracts.events import WebhookSubscription
        from ..impact.webhook import validate_webhook_url
        if not set(actor.org_roles).intersection(('admin','manage_org')):
            raise PermissionDeniedError('webhook_admin_required')
        validate_webhook_url(url,allow_insecure_local=allow_insecure_local)
        sub=WebhookSubscription(str(uuid.uuid4()),actor.org_id,url,secret,event_types,
                                allow_insecure_local=allow_insecure_local)
        self.store.put_webhook_subscription(sub)
        return sub.public_dict()

    def _kb(self,actor,kb_id,write=False,admin=False,*,agent=None,purpose=Purpose.READ,policy_context=None):
        kb=self.store.get_kb(kb_id)
        action = PolicyAction.MANAGE_SPACE if admin else PolicyAction.WRITE_DOCUMENT if write else PolicyAction.READ_CONTENT
        decision = self.evaluate_policy(actor,kb_id=kb_id,action=action,agent=agent,purpose=purpose,policy_context=policy_context)
        if not decision.allowed: raise PermissionDeniedError(decision.reason_code)
        return kb

    def _read(self,actor,doc_id,include_archived=False,*,agent=None,purpose=Purpose.READ,policy_context=None):
        if include_archived:
            policy_context = replace(policy_context or PolicyContext(), include_archived=True)
        decision = self.evaluate_policy(actor,doc_id,agent=agent,purpose=purpose,policy_context=policy_context)
        if not decision.allowed: raise PermissionDeniedError(decision.reason_code)
        return self.store.get_document(doc_id)

    @serialized
    def evaluate_policy(self,actor,doc_id=None,*,kb_id=None,action=PolicyAction.READ_CONTENT,purpose=Purpose.READ,agent=None,policy_context=None):
        document = self.store.get_document(doc_id) if doc_id is not None else None
        if document is not None:
            if kb_id is not None and document.kb_id != kb_id: raise PermissionDeniedError("space_boundary_denied")
            kb_id = document.kb_id
        if kb_id is None: raise ValidationError("Expected document or space")
        kb = self.store.get_kb(kb_id)
        return self.policy_engine.evaluate(actor,agent,kb,document,self.store.get_acl(doc_id) if document else None,
                                          self.store.member_role(kb_id,actor.user_id),action,purpose,policy_context)

    def _delivered_source(self,actor,doc_id,version=None,*,agent=None,purpose=Purpose.READ,policy_context=None):
        decision = self.evaluate_policy(actor,doc_id,agent=agent,purpose=purpose,policy_context=policy_context)
        if not decision.allowed: raise PermissionDeniedError(decision.reason_code)
        if version is not None and (type(version) is not int or version < 1): raise ValidationError("Invalid version")
        d = self.store.get_document(doc_id)
        v = self.store.get_version(doc_id,version if version is not None else d.current_version)
        self._published_version(d,v)
        chunks = self.store.get_chunks(doc_id,v.version)
        if decision.effect != DecisionEffect.ALLOW_WITH_REDACTION: return d,v,chunks,decision,""
        def mask(value):
            return self.redaction_registry.apply(value,decision.redaction_profile,purpose,{"doc_id":doc_id,"version":v.version})
        body, summary = mask(v.text)
        # These are detached delivery views, not changes to the source versions.
        delivered = replace(v,text=body,raw_hash=sha256(body),semantic_hash=sha256(normalize_text(body)),blob_key=None,filename=mask(v.filename)[0])
        safe_chunks=[]; cursor=0
        for chunk in chunks:
            body=mask(chunk.text)[0]
            safe_chunks.append(replace(chunk,text=body,chunk_hash=sha256(body),start_offset=cursor,end_offset=cursor+len(body),
                                       heading=mask(chunk.heading)[0],section_path=[mask(t)[0] for t in chunk.section_path]))
            cursor += len(body)
        def safe(value):
            if isinstance(value,str): return mask(value)[0]
            if isinstance(value,dict): return {k:safe(v) for k,v in value.items()}
            if isinstance(value,list): return [safe(v) for v in value]
            return value
        return replace(d,title=mask(d.title)[0],metadata=safe(d.metadata)),delivered,safe_chunks,decision,summary

    def _published_version(self,d,v):
        if self.store.get_kb(d.kb_id).governance_tier=='l2_controlled' and v.lifecycle_state!='published':
            raise PermissionDeniedError('lifecycle_not_published')

    def _ingested_response(self,actor,v,**context):
        try: return self.get_document(actor,v.doc_id,v.version,**context)
        except PermissionDeniedError:
            # Upload is not an implicit read grant. Preserve a useful write
            # receipt without returning any original body/blob/hash/filename.
            return replace(v,text="",raw_hash="",semantic_hash="",filename="",blob_key=None)

    @serialized
    def set_document_rights(self,actor,doc_id,rights,*,agent=None,purpose=Purpose.READ,policy_context=None):
        d=self.store.get_document(doc_id)
        self._kb(actor,d.kb_id,admin=True,agent=agent,purpose=purpose,policy_context=policy_context)
        if not isinstance(rights,ResourceRights): raise ValidationError("Expected ResourceRights")
        d=replace(d,rights=rights)
        with self.store.runtime_transaction():
            self.store.put_document(d)
            self._emit_event(actor,'doc.revoked' if rights.revoked else 'rights.updated',doc_id,d.current_version)
        # A management operation is not a grant to read a personal/denied body
        # or its user-provided descriptive metadata.
        return replace(d,title="",metadata={})

    @staticmethod
    def _visibility(value):
        if value not in ("private","team","enterprise"): raise ValidationError("Invalid visibility")
    @serialized
    def create_kb(self,actor,name,visibility="private",kb_id=None,*,space_type=None,owner_department_id="",owner_user_id="",governance_tier="l1_agile",agent=None,purpose=Purpose.READ,policy_context=None):
        self._visibility(visibility)
        if space_type is not None and space_type not in ("enterprise_public", "department", "personal"):
            raise ValidationError("Invalid explicit space type")
        if not isinstance(name,str) or not name.strip(): raise ValidationError("KB name required")
        kb_id=kb_id or str(uuid.uuid4())
        try: self.store.get_kb(kb_id)
        except NotFoundError: pass
        else: raise ConflictError("KB identity already exists")
        kb=KnowledgeBase(kb_id,actor.org_id,name,actor.user_id,visibility,space_type or "",owner_department_id,owner_user_id,governance_tier=governance_tier)
        if space_type is not None:
            if space_type == "department" and not owner_department_id: raise ValidationError("Department space requires owner_department_id")
            if not can_manage_kb(actor,kb): raise PermissionDeniedError("Space creation denied")
        decision=self.policy_engine.evaluate(actor,agent,kb,action=PolicyAction.MANAGE_SPACE,purpose=purpose,context=policy_context)
        if not decision.allowed: raise PermissionDeniedError(decision.reason_code)
        with self.store.runtime_transaction():
            try:self.store.get_kb(kb_id)
            except NotFoundError:pass
            else:raise ConflictError("KB identity already exists")
            self.store.put_kb(kb); self.store.grant_member(kb_id,actor.user_id,"admin")
        return kb
    @serialized
    def list_kbs(self,actor,*,agent=None,purpose=Purpose.READ,policy_context=None):
        return [k for k in self.store.list_kbs(actor.org_id) if self.evaluate_policy(actor,kb_id=k.kb_id,agent=agent,purpose=purpose,policy_context=policy_context).allowed]
    @serialized
    def grant_kb_member(self,actor,kb_id,user_id,role,*,agent=None,purpose=Purpose.READ,policy_context=None):
        self._kb(actor,kb_id,admin=True,agent=agent,purpose=purpose,policy_context=policy_context)
        if role not in ("viewer","editor","admin") or not user_id: raise ValidationError("Invalid member/role")
        self.store.grant_member(kb_id,user_id,role)
    def _sync_vector(self,doc_id):
        if self.vector_index is None: return
        # Durable dirty marker is cleared only after the remote index acknowledges all writes.
        self.store.mark_pending(doc_id)
        d=self.store.get_document(doc_id)
        self.vector_index.delete_document(doc_id)
        if not d.archived and d.lifecycle_state=="published":
            chunks=self.store.get_chunks(doc_id,d.current_version)
            vectors=self.embedder.embed([c.text for c in chunks])
            if len(vectors)!=len(chunks): raise ValidationError("Embedder returned wrong number of vectors")
            self.vector_index.upsert([(VectorHit(c.doc_id,c.version,c.chunk_id,0),v) for c,v in zip(chunks,vectors)])
        self.store.mark_pending(doc_id,False)
    @serialized
    def ingest(self,actor,kb_id,content,filename="document.txt",title=None,visibility=None,doc_id=None,metadata=None,acl=None,*,rights=None,lifecycle_state=None,valid_from=None,valid_to=None,agent=None,purpose=Purpose.READ,policy_context=None):
        ctx=dict(agent=agent,purpose=purpose,policy_context=policy_context)
        kb=self._kb(actor,kb_id,write=True,**ctx)
        controlled=kb.governance_tier=='l2_controlled'
        if controlled and lifecycle_state not in (None,'draft'):raise PermissionDeniedError('Controlled ingest must create a draft')
        if any(v is not None for v in (rights,lifecycle_state,valid_from,valid_to)):
            self._kb(actor,kb_id,admin=True,**ctx)
        if rights is not None and not isinstance(rights,ResourceRights): raise ValidationError("Expected ResourceRights")
        if not isinstance(content,(str,bytes)): raise ValidationError("content must be UTF-8 text or bytes")
        if acl is not None:
            self._kb(actor,kb_id,admin=True,**ctx)
            if not isinstance(acl,DocumentACL): raise ValidationError("Expected DocumentACL")
        raw=content.encode("utf-8") if isinstance(content,str) else content
        if len(raw)>32*1024*1024: raise ValidationError("Document exceeds 32 MiB limit")
        layout=self.parsers.parse_layout(raw,filename);text=layout.full_text
        if not text.strip(): raise ValidationError("Empty document")
        raw_hash,semantic_hash=fingerprints(raw,text); previous=None; d=None
        if doc_id:
            try: d=self.store.get_document(doc_id)
            except NotFoundError: pass
            if d:
                if d.kb_id!=kb_id or d.org_id!=actor.org_id: raise PermissionDeniedError("Access denied")
                write_decision=self.evaluate_policy(actor,doc_id,action=PolicyAction.WRITE_DOCUMENT,**ctx)
                if not write_decision.allowed: raise PermissionDeniedError(write_decision.reason_code)
                if not controlled:self._read(actor,doc_id,**ctx)
                previous=self.store.get_version(doc_id,self.store.latest_version(doc_id) if controlled else d.current_version)
        changes={name:value for name,value in (("rights",rights),("lifecycle_state",lifecycle_state),("valid_from",valid_from),("valid_to",valid_to)) if value is not None}
        if classify(previous,raw_hash,semantic_hash)!="new_semantic_version" and not (controlled and previous and previous.author_id=="legacy_unknown"):
            if controlled:return self._ingested_response(actor,previous,**ctx)
            updated=replace(d,**changes)
            # Dataclass validation precedes updates; return is separately read-gated.
            with self.store.runtime_transaction():
                if changes:
                    self.store.put_document(updated)
                    self._emit_event(actor,'doc.revoked' if updated.rights and updated.rights.revoked else 'rights.updated',doc_id,previous.version)
                if acl is not None:
                    self.store.set_acl(doc_id,acl)
                    self._emit_event(actor,'acl.updated',doc_id,previous.version)
            return self._ingested_response(actor,previous,**ctx)
        visibility=visibility or (d.visibility if d else kb.visibility); self._visibility(visibility)
        doc_id=doc_id or str(uuid.uuid4()); version=previous.version+1 if previous else 1
        metadata=metadata if metadata is not None else (d.metadata if d else {})
        # JSON serializability is checked before writing any blob or DB rows.
        import json
        json.dumps(metadata)
        if not isinstance(metadata,dict): raise ValidationError("metadata must be an object")
        chunks=self.chunker.split(text,doc_id,version)
        blob_key=None
        live_document=d
        if controlled:
            changes["lifecycle_state"]="draft"
        security = {name:getattr(d,name) for name in ("rights","lifecycle_state","valid_from","valid_to")} if d else {}
        security.update(changes)
        d=Document(doc_id,actor.org_id,kb_id,d.owner_id if d else actor.user_id,title or (d.title if d else filename),visibility,version,False,metadata,**security)
        if previous is None:
            # No existing resource state/rights to override: evaluate the new
            # identity's write boundary before persisting the proposed controls.
            identity=Document(doc_id,actor.org_id,kb_id,actor.user_id,"",visibility)
            write_decision=self.policy_engine.evaluate(actor,agent,kb,identity,acl,self.store.member_role(kb_id,actor.user_id),
                                                       PolicyAction.WRITE_DOCUMENT,purpose,policy_context)
            if not write_decision.allowed: raise PermissionDeniedError(write_decision.reason_code)
        blob_key=self.blob_store.put(actor.org_id,doc_id,raw_hash,raw) if self.blob_store else None
        v=DocumentVersion(doc_id,version,text,raw_hash,semantic_hash,datetime.now(timezone.utc).isoformat(),filename,blob_key,lifecycle_state="draft" if controlled else d.lifecycle_state,author_id=actor.user_id)
        anchors=merge_anchors_for_version(actor.org_id,doc_id,version,layout,
                    self.store.get_anchors(actor.org_id,doc_id,previous.version) if previous else ())
        with self.store.runtime_transaction():
            # Separate processes can race; the unique version key prevents lost history.
            if previous:
                self.store.lock_document(doc_id)
                if self.store.latest_version(doc_id)!=previous.version:raise ConflictError("Concurrent version update")
                if self.store.get_document(doc_id)!=live_document:raise ConflictError('Concurrent live document change')
            if previous is None:
                try: self.store.get_document(doc_id)
                except NotFoundError: pass
                else: raise ConflictError("Document identity already exists")
            serving_old=controlled and live_document is not None and live_document.lifecycle_state=='published'
            self.store.put_document(live_document if serving_old else d)
            self.store.put_version(v,chunks); self.store.put_anchors(anchors)
            if not controlled:self.store.refresh_fts(doc_id)
            self._emit_event(actor,'doc.draft_created' if controlled else 'doc.revised' if previous else 'doc.ingested',doc_id,version,previous_version=previous.version if previous else 0)
            for anchor in (() if controlled else anchors):
                if anchor.reanchor_status in (ReanchorStatus.DRIFT_PENDING,ReanchorStatus.ORPHANED):
                    self._emit_event(actor,'anchor.drifted' if anchor.reanchor_status==ReanchorStatus.DRIFT_PENDING else 'anchor.orphaned',doc_id,version,anchor_id=anchor.anchor_id)
            if changes and not controlled:
                self._emit_event(actor,'doc.revoked' if d.rights and d.rights.revoked else 'rights.updated',doc_id,version)
            if acl is not None:
                self.store.set_acl(doc_id,acl)
                self._emit_event(actor,'acl.updated',doc_id,version)
            if self.vector_index is not None and not controlled: self.store.mark_pending(doc_id)
        if not controlled:self._sync_vector(doc_id)
        return self._ingested_response(actor,v,**ctx)
    @serialized
    def list_documents(self,actor,kb_id=None,include_archived=False,*,archived_only=False,agent=None,purpose=Purpose.READ,policy_context=None):
        if type(archived_only) is not bool:raise ValidationError('Invalid archived_only')
        ctx=dict(agent=agent,purpose=purpose,policy_context=replace(policy_context or PolicyContext(),include_archived=True) if include_archived or archived_only else policy_context)
        if kb_id:
            if archived_only:self._compat_kb(actor,kb_id,**ctx)
            else:self._kb(actor,kb_id,**ctx)
        result=[]
        for d in self.store.list_documents(actor.org_id):
            if kb_id and d.kb_id!=kb_id: continue
            if archived_only:
                if not d.archived:continue
                decision=self.evaluate_policy(actor,d.doc_id,action=PolicyAction.MANAGE_SPACE,**ctx)
                if not decision.allowed:continue
            try: result.append(self._delivered_source(actor,d.doc_id,**ctx)[0])
            except PermissionDeniedError: pass
        return result
    @serialized
    def get_document(self,actor,doc_id,version=None,*,agent=None,purpose=Purpose.READ,policy_context=None):
        d,v,_,_,_=self._delivered_source(actor,doc_id,version,agent=agent,purpose=purpose,policy_context=policy_context)
        return v if version is not None else d
    @serialized
    def inspect_document(self, actor, doc_id, version=None,*,agent=None,purpose=Purpose.READ,policy_context=None):
        """Permission-checked workbench detail; no storage objects escape the API."""
        ctx=dict(agent=agent,purpose=purpose,policy_context=policy_context)
        document,selected,chunks,_,_=self._delivered_source(actor,doc_id,version,**ctx)
        if version is not None and (type(version) is not int or version < 1): raise ValidationError("Invalid version")
        # Metadata only for the history rail; content is returned for the selected version.
        versions = [{"version": v.version, "created_at": v.created_at, "filename": v.filename,
                     "raw_hash": v.raw_hash}
                    for v in (self._delivered_source(actor,doc_id,n,**ctx)[1] for n in range(1, document.current_version + 1))]
        return {"document": document, "versions": versions, "selected": selected,
                "chunks": chunks,
                "acl": self.store.get_acl(doc_id),
                "can_manage": self.can_manage_kb(actor, document.kb_id,**ctx),
                "can_upload": self.can_upload_to_kb(actor, document.kb_id,**ctx)}

    @serialized
    def list_consumer_bindings(self, actor,*,agent=None,purpose=Purpose.READ,policy_context=None):
        # Revalidate after permission changes; stale bindings must not leak selectors.
        result = []
        for binding in self.store.list_bindings(actor):
            try: result.append(self.validate_binding(actor, binding,agent=agent,purpose=purpose,policy_context=policy_context))
            except (PermissionDeniedError, NotFoundError): pass
        return result

    @serialized
    def preview(self,actor,doc_id,version=None,limit=800,*,agent=None,purpose=Purpose.READ,policy_context=None):
        return self.retrieve(actor,doc_id,version,offset=0,limit=limit,agent=agent,purpose=purpose,policy_context=policy_context)
    @serialized
    def archive(self,actor,doc_id,*,agent=None,purpose=Purpose.READ,policy_context=None):
        ctx=dict(agent=agent,purpose=purpose,policy_context=policy_context)
        d=self._read(actor,doc_id,True,**ctx); self._kb(actor,d.kb_id,write=True,**ctx)
        with self.store.runtime_transaction():
            d.archived=True; self.store.put_document(d); self.store.refresh_fts(doc_id)
            self._emit_event(actor,'doc.archived',doc_id,d.current_version)
            if self.vector_index is not None: self.store.mark_pending(doc_id)
        self._sync_vector(doc_id)
    @serialized
    def restore(self,actor,doc_id,*,agent=None,purpose=Purpose.READ,policy_context=None):
        ctx=dict(agent=agent,purpose=purpose,policy_context=policy_context)
        d=self._read(actor,doc_id,True,**ctx); self._kb(actor,d.kb_id,write=True,**ctx)
        with self.store.runtime_transaction():
            d.archived=False; self.store.put_document(d); self.store.refresh_fts(doc_id)
            self._emit_event(actor,'doc.restored',doc_id,d.current_version)
            if self.vector_index is not None: self.store.mark_pending(doc_id)
        self._sync_vector(doc_id)
    @serialized
    def set_document_acl(self,actor,doc_id,acl,*,agent=None,purpose=Purpose.READ,policy_context=None):
        d=self.store.get_document(doc_id); self._kb(actor,d.kb_id,admin=True,agent=agent,purpose=purpose,policy_context=policy_context)
        if not isinstance(acl,DocumentACL): raise ValidationError("Expected DocumentACL")
        with self.store.runtime_transaction():
            self.store.set_acl(doc_id,acl)
            self._emit_event(actor,'acl.updated',doc_id,d.current_version)
    @serialized
    def search(self,actor,query,mode="keyword",limit=20,filters=None,scope=None,*,agent=None,purpose=Purpose.READ,policy_context=None,rerank=False,reranker_id=None,calibrator_id=None,min_calibrated_score=None,rerank_top_k=None,reranker=None,calibrator=None):
        from ..retrieval.strategies import resolve
        reranker,calibrator=resolve(rerank,reranker_id,calibrator_id,min_calibrated_score,rerank_top_k,reranker,calibrator,self.reranker_registry,self.calibrator_registry)
        with self.store.runtime_transaction():
            self._check_principal(actor)
            ctx=dict(agent=agent,purpose=purpose,policy_context=policy_context)
            if scope is not None: scope = self.validate_scope(actor, scope,**ctx)
            return run_search(self.store,actor,query,mode,limit,filters,self.vector_index,self.embedder,self.excerpt_policy,scope=scope,
                              policy_engine=self.policy_engine,redaction_registry=self.redaction_registry,reranker=reranker,calibrator=calibrator,min_calibrated_score=min_calibrated_score,rerank_top_k=rerank_top_k,**ctx)
    @serialized
    def retrieve(self,actor,doc_id,version=None,chunk_ids=None,offset=0,limit=8000,*,agent=None,purpose=Purpose.READ,policy_context=None):
        d,v,chunks,decision,summary=self._delivered_source(actor,doc_id,version,agent=agent,purpose=purpose,policy_context=policy_context)
        version=v.version
        if not isinstance(version,int) or version<1 or not isinstance(offset,int) or not isinstance(limit,int) or offset<0 or not 1<=limit<=100000:
            raise ValidationError("Invalid version/pagination")
        if chunk_ids:
            selected=[c for c in chunks if c.chunk_id in chunk_ids]
            if len(set(chunk_ids))!=len(selected): raise NotFoundError("Chunk not found")
            text="\n".join(c.text for c in selected)
        else: text=v.text
        page=text[offset:offset+limit]; end=offset+len(page); truncated=end<len(text)
        return RetrieveResponse(doc_id,version,page,offset,limit,len(text),truncated,end if truncated else None,build_uri(d.org_id,doc_id,version),list(chunk_ids or []),summary)
    def _anchor_authority(self,actor,doc_id,version=None,*,agent=None,purpose=Purpose.READ,policy_context=None):
        decision=self.evaluate_policy(actor,doc_id,agent=agent,purpose=purpose,policy_context=policy_context)
        if not decision.allowed:raise PermissionDeniedError(decision.reason_code)
        d=self.store.get_document(doc_id)
        if version is not None:integer(version,'version',1)
        v=self.store.get_version(doc_id,d.current_version if version is None else version)
        self._published_version(d,v)
        return d,v,decision

    @serialized
    def report_evidence_issue(self,actor,source_uri,issue_type,description,*,conflicting_uri="",agent=None,purpose=Purpose.READ,policy_context=None) -> EvidenceIssue:
        """Queue data for human review. Never update document/version/ACL/rights."""
        if (issue_type not in ('outdated','anchor_drift','conflict','inaccuracy') or not isinstance(issue_type,str)
            or not isinstance(description,str) or not description.strip() or len(description)>4000):
            raise ValidationError('Invalid issue parameters')
        ctx=dict(agent=agent,purpose=purpose,policy_context=policy_context)
        snapshots=[]
        def authorize(uri):
            if not isinstance(uri,str) or not 1<=len(uri)<=2048:raise ValidationError('Invalid issue parameters')
            parsed=parse_uri_v2(uri)
            if parsed.org_id!=actor.org_id:raise PermissionDeniedError('access_denied')
            # Separate feedback authority and READ/redaction gate. Do not consume
            # a pending anchor to report its drift; it is an authorized impact view.
            decision=self.evaluate_policy(actor,parsed.doc_id,action=PolicyAction.REPORT_ISSUE,**ctx)
            if not decision.allowed:raise PermissionDeniedError('access_denied')
            d,v,chunks,read,_=self._delivered_source(actor,parsed.doc_id,parsed.version,**ctx)
            if d.org_id!=parsed.org_id:raise PermissionDeniedError('access_denied')
            if parsed.anchor_id:self.get_anchor(actor,parsed.doc_id,parsed.anchor_id,parsed.version,**ctx)
            if parsed.chunk_id and parsed.chunk_id not in {c.chunk_id for c in chunks}:raise PermissionDeniedError('access_denied')
            obligations=intersect_decisions((read,decision))
            if not obligations.allowed:raise PermissionDeniedError('access_denied')
            if obligations.effect==DecisionEffect.ALLOW_WITH_REDACTION:
                self.redaction_registry.apply('',obligations.redaction_profile,purpose)
            snapshots.append((parsed.doc_id,obligations))
            return parsed
        with self.store.runtime_transaction():
            try:
                parsed=authorize(source_uri)
                if conflicting_uri:authorize(conflicting_uri)
                # Hooks can re-enter trusted clients. Recheck both sources only
                # AFTER every hook, immediately before writing the review queue.
                for identity,previous in snapshots:
                    final=intersect_decisions((self.evaluate_policy(actor,identity,**ctx),self.evaluate_policy(actor,identity,action=PolicyAction.REPORT_ISSUE,**ctx)))
                    if final!=previous or not final.allowed:raise PermissionDeniedError('access_denied')
            except NotFoundError:raise PermissionDeniedError('access_denied') from None
            issue=EvidenceIssue(str(uuid.uuid4()),actor.org_id,parsed.doc_id,parsed.version,
                anchor_id=parsed.anchor_id or '',issue_type=issue_type,description=description,conflicting_uri=conflicting_uri,
                reported_by_user_id=actor.user_id,reported_by_agent_id=agent.agent_id if agent else '',
                created_at=datetime.now(timezone.utc).isoformat())
            self.store.put_issue(issue)
            self._audit_current_write(actor,issue.doc_id,issue)
        return issue

    @serialized
    def list_evidence_issues(self,actor,*,doc_id=None,status=None,agent=None,purpose=Purpose.READ,policy_context=None) -> List[EvidenceIssue]:
        ctx=dict(agent=agent,purpose=purpose,policy_context=policy_context);result=[]
        for issue in self.store.list_issues(actor.org_id,doc_id=doc_id,status=status):
            try:
                if not isinstance(issue,EvidenceIssue):continue
                decision=self.evaluate_policy(actor,issue.doc_id,**ctx)
                if not decision.allowed:continue
                conflict=None
                if issue.conflicting_uri:
                    other=parse_uri_v2(issue.conflicting_uri)
                    if other.org_id!=actor.org_id:continue
                    conflict=self.evaluate_policy(actor,other.doc_id,**ctx)
                    if not conflict.allowed:continue
                delivered=issue
                if decision.effect==DecisionEffect.ALLOW_WITH_REDACTION:
                    masked=self.redaction_registry.apply(issue.description,decision.redaction_profile,purpose,{'doc_id':issue.doc_id})[0]
                    delivered=replace(issue,description=masked,conflicting_uri='',reported_by_user_id='',reported_by_agent_id='',anchor_id='',resolution=replace(issue.resolution,note=self.redaction_registry.apply(issue.resolution.note,decision.redaction_profile,purpose)[0]) if issue.resolution else None)
                if self.evaluate_policy(actor,issue.doc_id,**ctx)!=decision:continue
                if conflict is not None and self.evaluate_policy(actor,other.doc_id,**ctx)!=conflict:continue
                result.append(delivered)
            except (NotFoundError,PermissionDeniedError,ValidationError):continue
        return result

    @serialized
    def list_anchors(self,actor,doc_id,version=None,*,agent=None,purpose=Purpose.READ,policy_context=None):
        d,v,decision=self._anchor_authority(actor,doc_id,version,agent=agent,purpose=purpose,policy_context=policy_context)
        anchors=self.store.get_anchors(d.org_id,doc_id,v.version);result=[]
        # Even an empty anchor list cannot silently bypass a required hook.
        if decision.effect==DecisionEffect.ALLOW_WITH_REDACTION:self.redaction_registry.apply('',decision.redaction_profile,purpose)
        for anchor in anchors:
            validate_anchor_identity(anchor,d.org_id,doc_id,v.version)
            if anchor.reanchor_status==ReanchorStatus.ANCHORED:validate_anchor_source(anchor,v)
            result.append(deliver_anchor(self,anchor,decision,purpose))
        return result

    @serialized
    def get_anchor(self,actor,doc_id,anchor_id,version=None,*,agent=None,purpose=Purpose.READ,policy_context=None):
        identifier(anchor_id,'anchor_id')
        d,v,decision=self._anchor_authority(actor,doc_id,version,agent=agent,purpose=purpose,policy_context=policy_context)
        anchor=self.store.get_anchor(d.org_id,doc_id,v.version,anchor_id)
        validate_anchor_identity(anchor,d.org_id,doc_id,v.version,anchor_id)
        if anchor.reanchor_status==ReanchorStatus.ANCHORED:validate_anchor_source(anchor,v)
        return deliver_anchor(self,anchor,decision,purpose)

    @serialized
    def confirm_anchor_reanchor(self,actor,doc_id,version,anchor_id,*,agent=None,purpose=Purpose.READ,policy_context=None):
        ctx=dict(agent=agent,purpose=purpose,policy_context=policy_context)
        # Source check, permissions and state update share the same SQLite writer
        # lock across workers. Read authority is independent of write authority.
        with self.store.runtime_transaction():
            d,v,decision=self._anchor_authority(actor,doc_id,version,**ctx)
            write=self.evaluate_policy(actor,doc_id,action=PolicyAction.WRITE_DOCUMENT,**ctx)
            if not write.allowed:raise PermissionDeniedError(write.reason_code)
            anchor=self.store.get_anchor(d.org_id,doc_id,v.version,anchor_id)
            validate_anchor_identity(anchor,d.org_id,doc_id,v.version,anchor_id)
            if anchor.reanchor_status!=ReanchorStatus.DRIFT_PENDING:raise ValidationError('Only drift_pending anchors can be confirmed')
            validate_anchor_source(anchor,v)
            confirmed=replace(anchor,reanchor_status=ReanchorStatus.ANCHORED)
            delivered=deliver_anchor(self,confirmed,decision,purpose)
            self.store.update_anchor(confirmed)
            self._emit_event(actor,'anchor.reanchored',doc_id,version,anchor_id=anchor_id)
        return delivered

    @serialized
    def reference(self,actor,doc_id,version=None,chunk_ids=None,excerpt="",*,anchor_id=None,agent=None,purpose=Purpose.READ,policy_context=None):
        d,v,chunks,decision,_=self._delivered_source(actor,doc_id,version,agent=agent,purpose=purpose,policy_context=policy_context)
        version=v.version; chunk_ids=list(chunk_ids or [])
        if anchor_id is not None:
            identifier(anchor_id,'anchor_id')
            if chunk_ids:raise ValidationError('Chunk and anchor selectors are mutually exclusive')
            anchor=self.get_anchor(actor,doc_id,anchor_id,version,agent=agent,purpose=purpose,policy_context=policy_context)
            if anchor.reanchor_status!=ReanchorStatus.ANCHORED:raise PermissionDeniedError('anchor_drift_pending' if anchor.reanchor_status==ReanchorStatus.DRIFT_PENDING else 'anchor_orphaned')
            if not isinstance(excerpt,str):raise ValidationError('Invalid excerpt')
            if not excerpt:excerpt=anchor.quote.exact
            # Accept only actual delivered text; never sign arbitrary surrounding text.
            if anchor.quote.exact not in excerpt or (excerpt!=anchor.quote.exact and excerpt not in v.text):raise TamperedExcerptError('Anchor excerpt mismatch')
            return KnowledgeRef(d.org_id,doc_id,version,build_uri(d.org_id,doc_id,version,anchor_id=anchor_id),[],excerpt,sha256(excerpt),anchor_id=anchor_id)
        if decision.effect == DecisionEffect.ALLOW_WITH_REDACTION:
            if excerpt:
                probe=KnowledgeRef(d.org_id,doc_id,version,build_uri(d.org_id,doc_id,version,chunk_ids[0] if len(chunk_ids)==1 else None),chunk_ids,excerpt,sha256(excerpt))
                try: validate_excerpt(probe,v,chunks,allow_combined=True)
                except TamperedExcerptError:
                    excerpt=normalize_text(self.redaction_registry.apply(excerpt,decision.redaction_profile,purpose,{"doc_id":doc_id,"version":version})[0])
            else:
                excerpt=normalize_text("\n".join(c.text for c in chunks if c.chunk_id in chunk_ids) if chunk_ids else v.text)
        ref=KnowledgeRef(d.org_id,doc_id,version,build_uri(d.org_id,doc_id,version,chunk_ids[0] if len(chunk_ids)==1 else None),chunk_ids,excerpt,sha256(excerpt))
        validate_excerpt(ref,v,chunks,allow_combined=decision.effect == DecisionEffect.ALLOW_WITH_REDACTION); return ref
    @serialized
    def consume(self,actor,ref,*,agent=None,purpose=Purpose.READ,policy_context=None):
        with self.store._write_scope():
            receipt=consume(self,actor,ref,agent=agent,purpose=purpose,policy_context=policy_context)
            self._record_usage(actor,ref,receipt,agent=agent,purpose=purpose,policy_context=policy_context)
            self._audit_current_write(actor,ref.doc_id,receipt)
            return receipt
    @serialized
    def batch_consume(self,actor,refs,*,agent=None,purpose=Purpose.READ,policy_context=None):
        if len(refs)>100:raise ValidationError('At most 100 references per batch')
        return [self.consume(actor,ref,agent=agent,purpose=purpose,policy_context=policy_context) for ref in refs]
    @serialized
    def reindex(self,actor,kb_id,*,agent=None,purpose=Purpose.READ,policy_context=None):
        self._kb(actor,kb_id,admin=True,agent=agent,purpose=purpose,policy_context=policy_context)
        for d in self.store.list_documents(actor.org_id):
            if d.kb_id==kb_id:
                with self.store.runtime_transaction(): self.store.refresh_fts(d.doc_id)
                self._sync_vector(d.doc_id)
    @serialized
    def health(self):
        pending=self.store.pending_documents()
        return {"status":"degraded" if pending else "ok","version":knowledge_sdk.__version__,"pending_index_count":len(pending)}

    def can_manage_kb(self, actor: Actor, kb_id: str,*,agent=None,purpose=Purpose.READ,policy_context=None) -> bool:
        return self.evaluate_policy(actor,kb_id=kb_id,action=PolicyAction.MANAGE_SPACE,agent=agent,purpose=purpose,policy_context=policy_context).allowed

    def can_upload_to_kb(self, actor: Actor, kb_id: str,*,agent=None,purpose=Purpose.READ,policy_context=None) -> bool:
        return self.evaluate_policy(actor,kb_id=kb_id,action=PolicyAction.WRITE_DOCUMENT,agent=agent,purpose=purpose,policy_context=policy_context).allowed

    @serialized
    def validate_scope(self, actor: Actor, scope: KnowledgeScope,*,agent=None,purpose=Purpose.READ,policy_context=None) -> KnowledgeScope:
        """Validate explicit identities, never expand them into additional grants."""
        if isinstance(scope, dict): scope = KnowledgeScope.from_dict(scope)
        if not isinstance(scope, KnowledgeScope): raise ValidationError("Expected KnowledgeScope")
        for kb_id in scope.kb_ids: self._kb(actor, kb_id,agent=agent,purpose=purpose,policy_context=policy_context)
        for doc_id in scope.doc_ids: self._read(actor, doc_id,agent=agent,purpose=purpose,policy_context=policy_context)
        return scope

    @serialized
    def validate_binding(self, actor: Actor, binding: ConsumerBinding,*,agent=None,purpose=Purpose.READ,policy_context=None) -> ConsumerBinding:
        if isinstance(binding, dict): binding = ConsumerBinding.from_dict(binding)
        if not isinstance(binding, ConsumerBinding): raise ValidationError("Expected ConsumerBinding")
        self.validate_scope(actor, binding.default_scope,agent=agent,purpose=purpose,policy_context=policy_context)
        return binding

    @serialized
    def bind_consumer(self, actor: Actor, binding: ConsumerBinding,*,agent=None,purpose=Purpose.READ,policy_context=None) -> ConsumerBinding:
        binding = self.validate_binding(actor, binding,agent=agent,purpose=purpose,policy_context=policy_context)
        self.store.put_binding(actor,binding,agent=agent,purpose=enum_value(Purpose,purpose).value)
        return binding

    @serialized
    def get_consumer_binding(self, actor: Actor, consumer_type: str, consumer_id: str,*,agent=None,purpose=Purpose.READ,policy_context=None) -> ConsumerBinding:
        return self.validate_binding(actor, self.store.get_binding(actor, consumer_type, consumer_id),agent=agent,purpose=purpose,policy_context=policy_context)

    @serialized
    def create_ref(self, actor: Actor, doc_id: str, version=None, chunk_ids=None, excerpt: str = "",*,anchor_id=None,agent=None,purpose=Purpose.READ,policy_context=None) -> KnowledgeRef:
        return self.reference(actor, doc_id, version, chunk_ids, excerpt,anchor_id=anchor_id,agent=agent,purpose=purpose,policy_context=policy_context)

    @serialized
    def verify_ref(self, actor: Actor, ref: KnowledgeRef,*,agent=None,purpose=Purpose.READ,policy_context=None) -> MaterialReceipt:
        """Re-authorize and verify version, URI, chunks, excerpt and digest now."""
        return self.consume(actor, ref,agent=agent,purpose=purpose,policy_context=policy_context)

    @serialized
    def verify_receipt(self, actor: Actor, ref: KnowledgeRef, receipt: MaterialReceipt, binding=None,*,agent=None,purpose=Purpose.READ,policy_context=None) -> bool:
        if not isinstance(receipt, MaterialReceipt): raise ValidationError("Expected MaterialReceipt")
        try:
            if binding is not None:
                binding = self.validate_binding(actor, binding,agent=agent,purpose=purpose,policy_context=policy_context)
                if (receipt.consumer_type, receipt.consumer_id, receipt.used_by_stage) != (binding.consumer_type, binding.consumer_id, binding.stage): return False
                document = self._read(actor, ref.doc_id,agent=agent,purpose=purpose,policy_context=policy_context)
                if not binding.default_scope.contains(document, self.store.get_kb(document.kb_id)): return False
            current = self.verify_ref(actor, ref,agent=agent,purpose=purpose,policy_context=policy_context)
            fields = ("status", "source_uri", "evidence_kind", "chunk_ids", "reason_code", "excerpt_hash")
            return current.status in ("partial", "consumed") and all(getattr(current,k) == getattr(receipt,k) for k in fields)
        except (PermissionDeniedError,NotFoundError):
            return False

    @serialized
    def attach(self, actor: Actor, ref: KnowledgeRef, binding=None,*,agent=None,purpose=Purpose.READ,policy_context=None) -> Attachment:
        with self.store._write_scope():
            receipt=consume(self,actor,ref,agent=agent,purpose=purpose,policy_context=policy_context)
            if receipt.status not in ('consumed','partial'):raise PermissionDeniedError(receipt.reason_code or 'Reference unavailable or denied')
            if binding is not None:
                binding=self.validate_binding(actor,binding,agent=agent,purpose=purpose,policy_context=policy_context)
                document=self._read(actor,ref.doc_id,agent=agent,purpose=purpose,policy_context=policy_context)
                if not binding.default_scope.contains(document,self.store.get_kb(document.kb_id)):
                    raise PermissionDeniedError('Reference outside consumer scope')
                receipt=replace(receipt,consumer_type=binding.consumer_type,consumer_id=binding.consumer_id,used_by_stage=binding.stage)
            self._record_usage(actor,ref,receipt,agent=agent,purpose=purpose,policy_context=policy_context)
            self._audit_current_write(actor,ref.doc_id,receipt)
            return Attachment(ref,receipt)

    @serialized
    def ask(self, actor: Actor, question: str, scope: Optional[KnowledgeScope] = None, top_k: int = 5, mode: str = "keyword",
            generator: Optional[AnswerGenerator] = None, excerpt_policy: Optional[ExcerptPolicy] = None, min_score: float = 0.0,
            binding=None,*,agent=None,purpose=None,policy_context=None) -> KnowledgeAnswer:
        """Only this explicit operation may invoke a supplied answer generator.

        Scores are fused reciprocal ranks, not probability/confidence values.
        A host should set a calibrated min_score for its retrieval backend.
        """
        purpose=enum_value(Purpose,purpose if purpose is not None else Purpose.GROUND_INTERNAL_LLM if generator is not None else Purpose.READ)
        ctx=dict(agent=agent,purpose=purpose,policy_context=policy_context)
        if not isinstance(top_k, int) or isinstance(top_k, bool) or not 1 <= top_k <= 100:
            raise ValidationError("Invalid top_k")
        if not isinstance(min_score, (int, float)) or isinstance(min_score, bool) or not math.isfinite(min_score) or min_score < 0:
            raise ValidationError("Invalid evidence threshold")
        if excerpt_policy is not None and not isinstance(excerpt_policy, ExcerptPolicy):
            raise ValidationError("Expected ExcerptPolicy")
        # ask selectors are narrowing filters, never grants. Unauthorized explicit
        # selectors produce a uniform refusal rather than an identity oracle.
        if isinstance(binding, dict): binding = ConsumerBinding.from_dict(binding)
        if binding is not None and not isinstance(binding, ConsumerBinding): raise ValidationError("Expected ConsumerBinding")
        scope = scope if scope is not None else (binding.default_scope if binding else KnowledgeScope())
        if isinstance(scope, dict): scope = KnowledgeScope.from_dict(scope)
        if not isinstance(scope, KnowledgeScope): raise ValidationError("Expected KnowledgeScope")
        hits = run_search(self.store, actor, question, mode, top_k,
                          vector_index=self.vector_index, embedder=self.embedder,
                          policy=excerpt_policy or self.excerpt_policy, scope=scope,
                          additional_scope=binding.default_scope if binding else None,policy_engine=self.policy_engine,
                          redaction_registry=self.redaction_registry,**ctx).hits
        hits = [h for h in hits if h.score >= min_score and h.excerpt.strip()]
        if not hits:
            return KnowledgeAnswer(refusal_reason="no_authorized_evidence_above_threshold", scope_applied=scope, binding_applied=binding)
        # Re-read current SQLite authority AND redaction before any generator.
        decisions=[]; safe_hits=[]; attachments=[]
        try:
            for hit in hits:
                read=self.evaluate_policy(actor,hit.doc_id,**ctx)
                indexed=self.evaluate_policy(actor,hit.doc_id,action=PolicyAction.SEARCH_INDEX,**ctx)
                merged=intersect_decisions((read,indexed)); decisions.append(merged)
                if not merged.allowed: raise PermissionDeniedError("evidence_access_changed")
                d=self.store.get_document(hit.doc_id)
                if d.current_version != hit.version: raise PermissionDeniedError("evidence_access_changed")
                raw=next(c for c in self.store.get_chunks(hit.doc_id,hit.version) if c.chunk_id==hit.chunk_id)
                text=raw.text; title=d.title; summary=""
                if merged.effect == DecisionEffect.ALLOW_WITH_REDACTION:
                    text,summary=self.redaction_registry.apply(text,merged.redaction_profile,purpose,{"doc_id":hit.doc_id})
                    title=self.redaction_registry.apply(title,merged.redaction_profile,purpose,{"doc_id":hit.doc_id})[0]
                view=make_excerpt(text,excerpt_policy or self.excerpt_policy,d.visibility=="enterprise",query=question,masking_summary=summary)
                safe_hit=replace(hit,title=title,**view)
                # If SEARCH and READ have incompatible delivery representations,
                # reference validation refuses instead of dropping an obligation.
                ref=self.reference(actor,hit.doc_id,hit.version,[hit.chunk_id],safe_hit.excerpt,**ctx)
                attachment=self.attach(actor,ref,**ctx)
                if binding:
                    attachment.receipt=replace(attachment.receipt,consumer_type=binding.consumer_type,consumer_id=binding.consumer_id,used_by_stage=binding.stage)
                safe_hits.append(safe_hit); attachments.append(attachment)
            combined=intersect_decisions(decisions)
            if not combined.allowed: raise PermissionDeniedError("evidence_access_changed")
            # Hooks are trusted but can re-enter the client. Check again AFTER
            # hooks/receipts, immediately before handing off any evidence text.
            final=[intersect_decisions((self.evaluate_policy(actor,h.doc_id,**ctx),self.evaluate_policy(actor,h.doc_id,action=PolicyAction.SEARCH_INDEX,**ctx))) for h in hits]
            if final != decisions or not intersect_decisions(final).allowed:
                raise PermissionDeniedError("evidence_access_changed")
            hits=safe_hits
        except (PermissionDeniedError,NotFoundError,ValidationError,StopIteration):
            return KnowledgeAnswer(refusal_reason="evidence_access_changed",scope_applied=scope,binding_applied=binding)
        result = (generator or ExtractiveAnswerGenerator()).generate(question, hits, scope, actor)
        if not isinstance(result, GeneratedAnswer) or not isinstance(result.answer, str) or not result.answer.strip() or not isinstance(result.model_called, bool):
            raise ValidationError("Generator must return a nonempty GeneratedAnswer")
        # A local plugin may re-enter this client and revoke access during generate().
        for item in attachments:
            if not self.verify_receipt(actor, item.reference, item.receipt,**ctx):
                return KnowledgeAnswer(refusal_reason="evidence_access_changed", model_called=result.model_called, scope_applied=scope, binding_applied=binding)
        return KnowledgeAnswer(result.answer, "answered", "", [a.reference for a in attachments],
                               [a.receipt for a in attachments], hits, result.model_called, scope, binding)
