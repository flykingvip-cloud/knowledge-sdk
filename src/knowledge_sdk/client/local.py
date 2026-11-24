from __future__ import annotations
import knowledge_sdk
from datetime import datetime, timezone
from functools import wraps
import threading
import uuid
import math
from typing import Optional, Sequence
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
    @wraps(method)
    def wrapped(self,*args,**kwargs):
        with self._lock: return method(self,*args,**kwargs)
    return wrapped

class LocalKnowledgeClient:
    """Trusted in-process API. Caller supplies an authenticated Actor, not user input."""
    def __init__(self,store=None,blob_store=None,parsers=None,chunker=None,vector_index=None,embedder=None,excerpt_policy=None,*,policy_engine:Optional[KnowledgePolicyEngine]=None,redaction_registry:Optional[RedactionRegistry]=None,policy_rules:Sequence[PolicyRule]=()):
        self.policy_engine = policy_engine if policy_engine is not None else DefaultPolicyEngine(policy_rules)
        self.redaction_registry = redaction_registry if redaction_registry is not None else RedactionRegistry()
        self.store=store if store is not None else SQLiteStore()
        self.blob_store=blob_store; self.parsers=parsers or ParserRegistry.defaults(); self.chunker=chunker or HierarchicalChunker()
        if (vector_index is None)!=(embedder is None): raise ValidationError("Provide both vector_index and embedder")
        self.vector_index=vector_index; self.embedder=embedder; self.excerpt_policy=excerpt_policy or ExcerptPolicy()
        self._lock=threading.RLock()
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
        self.store.put_document(d)
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
        with self.store.transaction():
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
        if not d.archived:
            chunks=self.store.get_chunks(doc_id,d.current_version)
            vectors=self.embedder.embed([c.text for c in chunks])
            if len(vectors)!=len(chunks): raise ValidationError("Embedder returned wrong number of vectors")
            self.vector_index.upsert([(VectorHit(c.doc_id,c.version,c.chunk_id,0),v) for c,v in zip(chunks,vectors)])
        self.store.mark_pending(doc_id,False)
    @serialized
    def ingest(self,actor,kb_id,content,filename="document.txt",title=None,visibility=None,doc_id=None,metadata=None,acl=None,*,rights=None,lifecycle_state=None,valid_from=None,valid_to=None,agent=None,purpose=Purpose.READ,policy_context=None):
        ctx=dict(agent=agent,purpose=purpose,policy_context=policy_context)
        kb=self._kb(actor,kb_id,write=True,**ctx)
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
                self._read(actor,doc_id,**ctx)
                previous=self.store.get_version(doc_id,d.current_version)
        changes={name:value for name,value in (("rights",rights),("lifecycle_state",lifecycle_state),("valid_from",valid_from),("valid_to",valid_to)) if value is not None}
        if classify(previous,raw_hash,semantic_hash)!="new_semantic_version":
            updated=replace(d,**changes)
            # Dataclass validation precedes updates; return is separately read-gated.
            if changes: self.store.put_document(updated)
            if acl is not None: self.store.set_acl(doc_id,acl)
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
        if kb.governance_tier == "l2_controlled" and lifecycle_state is None:
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
        v=DocumentVersion(doc_id,version,text,raw_hash,semantic_hash,datetime.now(timezone.utc).isoformat(),filename,blob_key)
        anchors=merge_anchors_for_version(actor.org_id,doc_id,version,layout,
                    self.store.get_anchors(actor.org_id,doc_id,previous.version) if previous else ())
        with self.store.transaction():
            # Separate processes can race; the unique version key prevents lost history.
            if previous and self.store.get_document(doc_id).current_version!=previous.version: raise ConflictError("Concurrent version update")
            if previous is None:
                try: self.store.get_document(doc_id)
                except NotFoundError: pass
                else: raise ConflictError("Document identity already exists")
            self.store.put_document(d); self.store.put_version(v,chunks); self.store.put_anchors(anchors); self.store.refresh_fts(doc_id)
            if acl is not None: self.store.set_acl(doc_id,acl)
            if self.vector_index is not None: self.store.mark_pending(doc_id)
        self._sync_vector(doc_id)
        return self._ingested_response(actor,v,**ctx)
    @serialized
    def list_documents(self,actor,kb_id=None,include_archived=False,*,agent=None,purpose=Purpose.READ,policy_context=None):
        ctx=dict(agent=agent,purpose=purpose,policy_context=replace(policy_context or PolicyContext(),include_archived=True) if include_archived else policy_context)
        if kb_id: self._kb(actor,kb_id,**ctx)
        result=[]
        for d in self.store.list_documents(actor.org_id):
            if kb_id and d.kb_id!=kb_id: continue
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
        with self.store.transaction():
            d.archived=True; self.store.put_document(d); self.store.refresh_fts(doc_id)
            if self.vector_index is not None: self.store.mark_pending(doc_id)
        self._sync_vector(doc_id)
    @serialized
    def restore(self,actor,doc_id,*,agent=None,purpose=Purpose.READ,policy_context=None):
        ctx=dict(agent=agent,purpose=purpose,policy_context=policy_context)
        d=self._read(actor,doc_id,True,**ctx); self._kb(actor,d.kb_id,write=True,**ctx)
        with self.store.transaction():
            d.archived=False; self.store.put_document(d); self.store.refresh_fts(doc_id)
            if self.vector_index is not None: self.store.mark_pending(doc_id)
        self._sync_vector(doc_id)
    @serialized
    def set_document_acl(self,actor,doc_id,acl,*,agent=None,purpose=Purpose.READ,policy_context=None):
        d=self.store.get_document(doc_id); self._kb(actor,d.kb_id,admin=True,agent=agent,purpose=purpose,policy_context=policy_context)
        if not isinstance(acl,DocumentACL): raise ValidationError("Expected DocumentACL")
        self.store.set_acl(doc_id,acl)
    @serialized
    def search(self,actor,query,mode="keyword",limit=20,filters=None,scope=None,*,agent=None,purpose=Purpose.READ,policy_context=None):
        ctx=dict(agent=agent,purpose=purpose,policy_context=policy_context)
        if scope is not None: scope = self.validate_scope(actor, scope,**ctx)
        return run_search(self.store,actor,query,mode,limit,filters,self.vector_index,self.embedder,self.excerpt_policy,scope=scope,
                          policy_engine=self.policy_engine,redaction_registry=self.redaction_registry,**ctx)
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
        return d,v,decision

    @serialized
    def report_evidence_issue(self,actor,source_uri,issue_type,description,*,conflicting_uri="",agent=None,purpose=Purpose.READ,policy_context=None):
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
        with self.store.transaction():
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
        return issue

    @serialized
    def list_evidence_issues(self,actor,*,doc_id=None,status=None,agent=None,purpose=Purpose.READ,policy_context=None):
        ctx=dict(agent=agent,purpose=purpose,policy_context=policy_context);result=[]
        for issue in self.store.list_issues(actor.org_id,doc_id=doc_id,status=status):
            try:
                if not isinstance(issue,EvidenceIssue):continue
                decision=self.evaluate_policy(actor,issue.doc_id,**ctx)
                if not decision.allowed:continue
                if issue.conflicting_uri:
                    other=parse_uri_v2(issue.conflicting_uri)
                    if other.org_id!=actor.org_id or not self.evaluate_policy(actor,other.doc_id,**ctx).allowed:continue
                delivered=issue
                if decision.effect==DecisionEffect.ALLOW_WITH_REDACTION:
                    masked=self.redaction_registry.apply(issue.description,decision.redaction_profile,purpose,{'doc_id':issue.doc_id})[0]
                    delivered=replace(issue,description=masked,conflicting_uri='',reported_by_user_id='',reported_by_agent_id='',anchor_id='')
                if self.evaluate_policy(actor,issue.doc_id,**ctx)!=decision:continue
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
        with self.store.transaction():
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
    def consume(self,actor,ref,*,agent=None,purpose=Purpose.READ,policy_context=None): return consume(self,actor,ref,agent=agent,purpose=purpose,policy_context=policy_context)
    @serialized
    def batch_consume(self,actor,refs,*,agent=None,purpose=Purpose.READ,policy_context=None): return batch_consume(self,actor,refs,agent=agent,purpose=purpose,policy_context=policy_context)
    @serialized
    def reindex(self,actor,kb_id,*,agent=None,purpose=Purpose.READ,policy_context=None):
        self._kb(actor,kb_id,admin=True,agent=agent,purpose=purpose,policy_context=policy_context)
        for d in self.store.list_documents(actor.org_id):
            if d.kb_id==kb_id:
                with self.store.transaction(): self.store.refresh_fts(d.doc_id)
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
        self.store.put_binding(actor, binding)
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
        receipt = self.verify_ref(actor, ref,agent=agent,purpose=purpose,policy_context=policy_context)
        if receipt.status not in ("consumed", "partial"): raise PermissionDeniedError(receipt.reason_code or "Reference unavailable or denied")
        if binding is not None:
            binding = self.validate_binding(actor, binding,agent=agent,purpose=purpose,policy_context=policy_context)
            document = self._read(actor, ref.doc_id,agent=agent,purpose=purpose,policy_context=policy_context)
            if not binding.default_scope.contains(document, self.store.get_kb(document.kb_id)):
                raise PermissionDeniedError("Reference outside consumer scope")
            receipt = replace(receipt, consumer_type=binding.consumer_type, consumer_id=binding.consumer_id, used_by_stage=binding.stage)
        return Attachment(ref, receipt)

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
