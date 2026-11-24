"""L2 dual-track workflow: serialized, transaction-locked and append-only."""
from __future__ import annotations
from dataclasses import replace
from datetime import datetime, timezone
from functools import wraps
import inspect
import uuid
from ..contracts.governance import ReviewDecision, ReleaseManifest
from ..contracts.policy import PolicyAction, Purpose
from ..exceptions import ConflictError, PermissionDeniedError, ValidationError

def now():return datetime.now(timezone.utc).isoformat()

def operation(fn):
    signature=inspect.signature(fn)
    @wraps(fn)
    def run(self,*args,**kwargs):
        values=signature.bind(self,*args,**kwargs).arguments
        actor=values['actor']
        with self._lock:
            try:
                with self.store.transaction():
                    result=fn(self,*args,**kwargs)
                    self._audit_operation(actor,fn.__name__,values,result)
                    return result
            except PermissionDeniedError:
                self._audit_operation(actor,fn.__name__,values,None,denied=True)
                raise
    return run

class GovernanceMixin:
    def _governance_version(self,actor,doc_id,version,expected_version,action,*,require_expected=False,**ctx):
        self.store.lock_document(doc_id)
        d=self.store.get_document(doc_id)
        if d.org_id!=actor.org_id:raise PermissionDeniedError('access_denied')
        if self.store.get_kb(d.kb_id).governance_tier!='l2_controlled':raise ValidationError('Controlled space required')
        decision=self.evaluate_policy(actor,doc_id,action=action,**ctx)
        if not decision.allowed:raise PermissionDeniedError(decision.reason_code)
        version=self.store.latest_version(doc_id) if version is None else version
        if type(version) is not int or version<1:raise ValidationError('Invalid version')
        if require_expected and expected_version is None or expected_version is not None and (type(expected_version) is not int or expected_version!=version):raise ConflictError('Expected version conflict')
        return d,self.store.get_version(doc_id,version)

    def _review(self,actor,d,v,stage,expected=None,comment='',conditions='',dissent=''):
        record=ReviewDecision(str(uuid.uuid4()),d.org_id,d.doc_id,v.version,stage,actor.user_id,v.reviewer_id,
                              v.submitter_id,expected,comment,dissent,conditions,now())
        self.store.put_review_decision(record)
        return record

    def _manifest(self,d,v):
        reviews=self.store.list_review_decisions(d.org_id,d.doc_id,v.version)
        issues=self.store.list_issues(d.org_id,doc_id=d.doc_id)
        return ReleaseManifest(d.doc_id,d.org_id,v.version,v.lifecycle_state,v.submitter_id,v.reviewer_id,
                               v.publisher_id,v.published_at,tuple(r.dissent_note for r in reviews if r.stage=='dissent_recorded'),
                               tuple(i.issue_id for i in issues if i.version==v.version and i.status=='resolved'))

    @operation
    def submit_for_review(self,actor,doc_id,*,version=None,expected_version=None,note='',agent=None,purpose=Purpose.READ,policy_context=None):
        d,v=self._governance_version(actor,doc_id,version,expected_version,PolicyAction.WRITE_DOCUMENT,agent=agent,purpose=purpose,policy_context=policy_context)
        if v.lifecycle_state not in ('draft','rejected'):raise ConflictError('Version not draft/rejected')
        v=self.store.update_version_state(doc_id,v.version,'in_review',submitter_id=actor.user_id,reviewer_id='',publisher_id='',published_at='')
        return self._review(actor,d,v,'submitted',expected_version,comment=note)

    def _review_authority(self,actor,d,v):
        if actor.user_id in (v.submitter_id,v.author_id):raise PermissionDeniedError('self_review_forbidden')
        if v.lifecycle_state!='in_review':raise ConflictError('Version not in review')

    @operation
    def approve_release(self,actor,doc_id,*,version,expected_version,comment='',conditions='',agent=None,purpose=Purpose.READ,policy_context=None):
        d,v=self._governance_version(actor,doc_id,version,expected_version,PolicyAction.APPROVE_RELEASE,require_expected=True,agent=agent,purpose=purpose,policy_context=policy_context)
        self._review_authority(actor,d,v)
        v=self.store.update_version_state(doc_id,version,'approved',reviewer_id=actor.user_id)
        return self._review(actor,d,v,'approved',expected_version,comment,conditions)

    @operation
    def reject_release(self,actor,doc_id,*,version,expected_version,reason,agent=None,purpose=Purpose.READ,policy_context=None):
        if not isinstance(reason,str) or not reason.strip():raise ValidationError('Rejection reason required')
        d,v=self._governance_version(actor,doc_id,version,expected_version,PolicyAction.APPROVE_RELEASE,require_expected=True,agent=agent,purpose=purpose,policy_context=policy_context)
        self._review_authority(actor,d,v)
        v=self.store.update_version_state(doc_id,version,'rejected',reviewer_id=actor.user_id)
        return self._review(actor,d,v,'rejected',expected_version,comment=reason)

    @operation
    def publish_release(self,actor,doc_id,*,version,expected_version,agent=None,purpose=Purpose.READ,policy_context=None):
        d,v=self._governance_version(actor,doc_id,version,expected_version,PolicyAction.PUBLISH_RELEASE,require_expected=True,agent=agent,purpose=purpose,policy_context=policy_context)
        if v.lifecycle_state!='approved':raise ConflictError('Version not approved')
        if actor.user_id==v.reviewer_id:raise PermissionDeniedError('reviewer_cannot_publish')
        if actor.user_id in (v.author_id,v.submitter_id):raise PermissionDeniedError('author_cannot_publish')
        if d.lifecycle_state=='published' and version<=d.current_version:raise ConflictError('Release must advance live version')
        previous=d.current_version if d.lifecycle_state=='published' else 0
        v=self.store.update_version_state(doc_id,version,'published',publisher_id=actor.user_id,published_at=now())
        self.store.update_document_lifecycle(doc_id,'published',current_version=version)
        self.store.refresh_fts(doc_id)
        self._review(actor,d,v,'published',expected_version)
        self._emit_event(actor,'doc.published',doc_id,version,previous_version=previous)
        for anchor in self.store.get_anchors(d.org_id,doc_id,version):
            if anchor.reanchor_status.value in ('drift_pending','orphaned'):
                self._emit_event(actor,'anchor.drifted' if anchor.reanchor_status.value=='drift_pending' else 'anchor.orphaned',doc_id,version,anchor_id=anchor.anchor_id)
        # Native PG vector index shares this transaction. Other indexes retain
        # their durable pending marker on a failed sync; never index drafts.
        self._sync_vector(doc_id)
        return self._manifest(d,v)

    @operation
    def record_dissent(self,actor,doc_id,*,version,note,stance='dissent',target_anchor_id='',agent=None,purpose=Purpose.READ,policy_context=None):
        if not isinstance(note,str) or not note.strip():raise ValidationError('Dissent required')
        self.store.lock_document(doc_id)
        d=self._read(actor,doc_id,agent=agent,purpose=purpose,policy_context=policy_context)
        if not self.evaluate_policy(actor,doc_id,action=PolicyAction.WRITE_DOCUMENT,agent=agent,purpose=purpose,policy_context=policy_context).allowed:raise PermissionDeniedError('dissent_role_required')
        v=self.store.get_version(doc_id,version)
        if v.lifecycle_state not in ('in_review','approved','published'):raise ConflictError('Dissent requires review or published version')
        if target_anchor_id and not any(a.anchor_id==target_anchor_id for a in self.store.get_anchors(actor.org_id,doc_id,version)):raise ValidationError('Unknown anchor')
        return self._review(actor,d,v,'dissent_recorded',comment=stance+(':'+target_anchor_id if target_anchor_id else ''),dissent=note)

    @operation
    def get_release_manifest(self,actor,doc_id,*,version=None,agent=None,purpose=Purpose.READ,policy_context=None):
        d=self.store.get_document(doc_id)
        decision=self.evaluate_policy(actor,doc_id,action=PolicyAction.APPROVE_RELEASE,agent=agent,purpose=purpose,policy_context=policy_context)
        if not decision.allowed:raise PermissionDeniedError(decision.reason_code)
        return self._manifest(d,self.store.get_version(doc_id,version or self.store.latest_version(doc_id)))
