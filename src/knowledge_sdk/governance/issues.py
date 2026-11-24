"""Manual issue actions only: no model calls or implicit retrieval tuning."""
from __future__ import annotations
from dataclasses import replace
import uuid
from .workflow import operation, now
from ..contracts.governance import IssueResolution, ReviewDecision
from ..contracts.events import OutboxEvent
from ..contracts.policy import Purpose, PolicyAction
from ..exceptions import ConflictError, PermissionDeniedError, ValidationError

class IssueMixin:
    @operation
    def resolve_evidence_issue(self,actor,issue_id,resolution_action,note,*,expected_version=None,agent=None,purpose=Purpose.READ,policy_context=None):
        # Validation before any write. The snapshot is part of the existing issue
        # record; no second issue or resolution table exists.
        issue=self.store.get_issue(actor.org_id,issue_id)
        resolution=IssueResolution(issue_id,actor.org_id,issue.doc_id,issue.version,resolution_action,note,actor.user_id,now())
        self.store.lock_document(issue.doc_id)
        issue=self.store.get_issue(actor.org_id,issue_id)
        if issue.status in ('resolved','dismissed') or expected_version is not None and expected_version!=issue.version:raise ConflictError('Issue conflict')
        decision=self.evaluate_policy(actor,issue.doc_id,action=PolicyAction.APPROVE_RELEASE,agent=agent,purpose=purpose,policy_context=policy_context)
        if not decision.allowed:raise PermissionDeniedError(decision.reason_code)
        d=self.store.get_document(issue.doc_id)
        v=self.store.get_version(d.doc_id,issue.version)
        if resolution_action=='keep_dissent':
            record=ReviewDecision(str(uuid.uuid4()),actor.org_id,d.doc_id,v.version,'dissent_recorded',actor_id=actor.user_id,
                                   comment=issue.anchor_id,dissent_note=note,created_at=now())
            self.store.put_review_decision(record)
        if resolution_action=='create_revision_draft' and self.store.get_kb(d.kb_id).governance_tier=='l2_controlled':
            latest=self.store.latest_version(d.doc_id)
            candidate=self.store.get_version(d.doc_id,latest)
            if candidate.lifecycle_state in ('draft','rejected'):
                # Link through immutable resolution; do not mutate someone's draft.
                revision_version=latest
            else:
                revision_version=latest+1
                draft=replace(v,version=revision_version,lifecycle_state='draft',author_id=actor.user_id,submitter_id='',reviewer_id='',publisher_id='',published_at='',source_issue_id=issue_id,created_at=now())
                chunks=[replace(c,version=revision_version) for c in self.store.get_chunks(d.doc_id,v.version)]
                self.store.put_version(draft,chunks)
                self.store.put_anchors([replace(a,version=revision_version) for a in self.store.get_anchors(actor.org_id,d.doc_id,v.version)])
            resolution=replace(resolution,revision_version=revision_version)
        result=replace(issue,status='dismissed' if resolution_action=='dismissed' else 'resolved',resolution=resolution)
        self.store.update_issue(result,expected_version=expected_version)
        stamp=now()
        self.store.enqueue_outbox(OutboxEvent(str(uuid.uuid4()),actor.org_id,'issue',issue_id,'issue.resolved',payload={'doc_id':d.doc_id,'version':issue.version},available_at=stamp,created_at=stamp))
        return result
