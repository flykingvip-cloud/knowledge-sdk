"""Schema-v5 additive v1 compatibility. No alternative authorization truth source."""
from __future__ import annotations
from dataclasses import replace
import difflib
from ..runtime.service import operation,now,uid
from ..contracts.policy import Purpose,PolicyAction,PolicyContext
from ..contracts.models import DocumentVersion
from ..contracts.events import OutboxEvent
from ..exceptions import PermissionDeniedError,NotFoundError,ValidationError,ConflictError


class CompatMixin:
    def _compat_kb(self,actor,kb_id,*,manage=False,agent=None,purpose=Purpose.READ,policy_context=None):
        if not isinstance(kb_id,str) or not kb_id or len(kb_id)>2000:raise ValidationError('Invalid resource id')
        self._runtime_principal(actor)
        try:
            kb=self.store.get_kb(kb_id)
            if kb.org_id!=actor.org_id:raise PermissionDeniedError()
            decision=self.evaluate_policy(actor,kb_id=kb_id,action=PolicyAction.MANAGE_SPACE if manage else PolicyAction.READ_CONTENT,agent=agent,purpose=purpose,policy_context=policy_context)
            if not decision.allowed:raise PermissionDeniedError()
            return kb
        except (NotFoundError,PermissionDeniedError):raise PermissionDeniedError('resource_unavailable') from None

    def _compat_version(self,actor,doc_id,version=None,**ctx):
        if not isinstance(doc_id,str) or not doc_id or len(doc_id)>2000:raise ValidationError('Invalid resource id')
        self._runtime_principal(actor)
        try:
            d=self.store.get_document(doc_id)
            if d.org_id!=actor.org_id:raise PermissionDeniedError()
            return self._delivered_source(actor,doc_id,version,**ctx)
        except (NotFoundError,PermissionDeniedError):raise PermissionDeniedError('resource_unavailable') from None

    @operation
    def get_kb(self,actor,kb_id,*,agent=None,purpose=Purpose.READ,policy_context=None):
        result=self._compat_kb(actor,kb_id,agent=agent,purpose=purpose,policy_context=policy_context)
        self._audit_operation(actor,'get_kb',{},result);return result

    @operation
    def update_kb(self,actor,kb_id,*,name=None,visibility=None,governance_tier=None,agent=None,purpose=Purpose.READ,policy_context=None):
        kb=self._compat_kb(actor,kb_id,manage=True,agent=agent,purpose=purpose,policy_context=policy_context)
        changes={}
        if name is not None:
            if not isinstance(name,str) or not name.strip() or len(name)>2000:raise ValidationError('Invalid space name')
            changes['name']=name
        if visibility is not None:
            self._visibility(visibility);changes.update(visibility=visibility,space_type={'private':'personal','team':'department','enterprise':'enterprise_public'}[visibility])
        if governance_tier is not None:
            if governance_tier not in ('l1_agile','l2_controlled'):raise ValidationError('Invalid governance tier')
            if kb.governance_tier=='l2_controlled' and governance_tier=='l1_agile' and any(d.kb_id==kb_id for d in self.store.list_documents(actor.org_id)):
                raise ConflictError('Controlled spaces with retained history cannot be downgraded')
            changes['governance_tier']=governance_tier
        result=replace(kb,**changes)
        decision=self.policy_engine.evaluate(actor,agent,result,member_role=self.store.member_role(kb_id,actor.user_id),action=PolicyAction.MANAGE_SPACE,purpose=purpose,context=policy_context)
        if not decision.allowed:raise PermissionDeniedError('resource_unavailable')
        self.store.put_kb(result)
        self._audit_operation(actor,'update_kb',{},result)
        # Space policy changes conservatively invalidate outstanding member tasks.
        if any(k in changes and getattr(kb,k)!=changes[k] for k in ('visibility','governance_tier')):
            for task in self.store.list_task_contexts(actor.org_id):
                if task.status=='active':self._runtime_revoke(task,'resource_unavailable')
        return result

    @operation
    def list_kb_members(self,actor,kb_id,*,agent=None,purpose=Purpose.READ,policy_context=None):
        self._compat_kb(actor,kb_id,manage=True,agent=agent,purpose=purpose,policy_context=policy_context)
        result=self.store.list_kb_members(actor.org_id,kb_id)
        self._audit_operation(actor,'list_kb_members',{},None);return result

    @operation
    def revoke_kb_member(self,actor,kb_id,user_id,*,agent=None,purpose=Purpose.READ,policy_context=None):
        kb=self._compat_kb(actor,kb_id,manage=True,agent=agent,purpose=purpose,policy_context=policy_context)
        if not isinstance(user_id,str) or not user_id or len(user_id)>2000:raise ValidationError('Invalid member')
        # v5 has one immutable intrinsic Owner, stored as an admin membership.
        # There is no owner-transfer API; deleting its row cannot transfer ownership.
        if user_id in (kb.owner_id,kb.owner_user_id):raise ConflictError('Cannot revoke the intrinsic space owner')
        self.store.remove_kb_member(actor.org_id,kb_id,user_id)
        stamp=now();event=OutboxEvent(uid(),actor.org_id,'kb',kb_id,'kb.member_revoked',{'kb_id':kb_id,'user_id':user_id},available_at=stamp,created_at=stamp)
        self.store.enqueue_outbox(event)
        # Include empty-snapshot tasks: absence of usage is not proof of no scope.
        for task in self.store.list_task_contexts(actor.org_id):
            if task.actor_id==user_id and task.status=='active':self._runtime_revoke(task,'resource_unavailable',event.event_id)
        from ..audit.ledger import append
        append(self.store,actor,'revoke_kb_member',agent=agent,purpose=purpose,resource_uri='kb:'+kb_id,details={'count':1})

    @operation
    def list_document_versions(self,actor,doc_id,*,agent=None,purpose=Purpose.READ,policy_context=None):
        ctx=dict(agent=agent,purpose=purpose,policy_context=policy_context)
        self._compat_version(actor,doc_id,**ctx);result=[]
        for n in range(1,self.store.latest_version(doc_id)+1):
            try:v=self._compat_version(actor,doc_id,n,**ctx)[1]
            except PermissionDeniedError:continue
            result.append(replace(v,text='',blob_key=None))
        self._audit_operation(actor,'list_document_versions',{'doc_id':doc_id},None);return result

    @operation
    def diff_document_versions(self,actor,doc_id,from_version,to_version,*,agent=None,purpose=Purpose.READ,policy_context=None):
        if any(type(v) is not int or v<1 for v in (from_version,to_version)):raise ValidationError('Invalid version')
        ctx=dict(agent=agent,purpose=purpose,policy_context=policy_context)
        a=self._compat_version(actor,doc_id,from_version,**ctx)[1]
        b=self._compat_version(actor,doc_id,to_version,**ctx)[1]
        # All offsets/counts are computed AFTER BOTH complete delivery/redaction gates.
        if len(a.text)+len(b.text)>1000000:raise ValidationError('Diff budget exceeded')
        lines_a=a.text.splitlines();lines_b=b.text.splitlines();changes=[]
        if len(lines_a)+len(lines_b)>10000:raise ValidationError('Diff budget exceeded')
        for tag,i,j,k,l in difflib.SequenceMatcher(None,lines_a,lines_b,autojunk=False).get_opcodes():
            if tag!='equal':changes.append({'operation':tag,'before':lines_a[i:j],'after':lines_b[k:l]})
        self._audit_operation(actor,'diff_document_versions',{'doc_id':doc_id},None)
        return {'doc_id':doc_id,'from_version':from_version,'to_version':to_version,'changes':changes}

    @operation
    def rollback_document(self,actor,doc_id,target_version,*,agent=None,purpose=Purpose.READ,policy_context=None):
        if type(target_version) is not int or target_version<1:raise ValidationError('Invalid version')
        ctx=dict(agent=agent,purpose=purpose,policy_context=policy_context)
        self._compat_version(actor,doc_id,target_version,**ctx)
        d=self.store.get_document(doc_id)
        decision=self.evaluate_policy(actor,doc_id,action=PolicyAction.WRITE_DOCUMENT,**ctx)
        if not decision.allowed:raise PermissionDeniedError('resource_unavailable')
        kb=self._compat_kb(actor,d.kb_id,**ctx);self.store.lock_document(doc_id)
        if self.store.latest_version(doc_id)!=d.current_version:raise ConflictError('Pending versions prevent append-at-current rollback')
        # Keep current ACL, rights, validity, archive and document metadata. v5 did
        # not persist historical business metadata: never invent an old value.
        source=self.store.get_version(doc_id,target_version)
        if source.lifecycle_state=='revoked':raise PermissionDeniedError('resource_unavailable')
        n=d.current_version+1
        from ..contracts.reanchor import merge_anchors_for_version
        from ..ingestion.fingerprint import sha256,normalize_text
        layout=self.parsers.parse_layout(source.text.encode(),'rollback.txt')
        chunks=self.chunker.split(source.text,doc_id,n)
        controlled=kb.governance_tier=='l2_controlled'
        v=DocumentVersion(doc_id,n,source.text,sha256(source.text),sha256(normalize_text(source.text)),now(),source.filename,lifecycle_state='draft' if controlled else d.lifecycle_state,author_id=actor.user_id)
        self.store.put_version(v,chunks)
        anchors=merge_anchors_for_version(actor.org_id,doc_id,n,layout,self.store.get_anchors(actor.org_id,doc_id,d.current_version))
        self.store.put_anchors(anchors)
        if not controlled:
            self.store.put_document(replace(d,current_version=n));self.store.refresh_fts(doc_id)
        self._emit_event(actor,'doc.draft_created' if controlled else 'doc.revised',doc_id,n,previous_version=d.current_version)
        if not controlled:
            from ..contracts.anchors import ReanchorStatus
            for anchor in anchors:
                if anchor.reanchor_status in (ReanchorStatus.DRIFT_PENDING,ReanchorStatus.ORPHANED):
                    self._emit_event(actor,'anchor.drifted' if anchor.reanchor_status==ReanchorStatus.DRIFT_PENDING else 'anchor.orphaned',doc_id,n,anchor_id=anchor.anchor_id)
        from ..audit.ledger import append
        append(self.store,actor,'rollback_document',agent=agent,purpose=purpose,doc_id=doc_id,details={'rollback_from_version':target_version,'previous_current_version':d.current_version,'created_version':n,'rollback_scope':'content_and_filename_only','security_metadata_preserved':True})
        if not controlled:self._sync_vector(doc_id)
        return self._ingested_response(actor,v,**ctx)

    def plan_sync(self,actor,connector_id,*,agent=None,purpose=Purpose.READ,policy_context=None):
        """Allowlisted connector preview; no source connector/callback is serialized."""
        from ..connectors.base import ConnectorSyncRunner
        if not isinstance(connector_id,str) or not connector_id:raise ValidationError('Invalid connector id')
        entry=self.connector_registry.get(connector_id)
        if entry is None:raise PermissionDeniedError('resource_unavailable')
        connector,kb_id=entry
        try:return ConnectorSyncRunner(self).plan_sync(actor,connector,org_id=actor.org_id,kb_id=kb_id,agent=agent,purpose=purpose,policy_context=policy_context)
        except (PermissionDeniedError,NotFoundError):raise PermissionDeniedError('resource_unavailable') from None
