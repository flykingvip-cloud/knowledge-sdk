"""Append-only governance snapshots. Mutations belong to the workflow service."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple
from .policy import PolicyContract, sequence, text
from .anchors import integer
from ..exceptions import ValidationError

@dataclass(frozen=True)
class ReviewDecision(PolicyContract):
    decision_id: str
    org_id: str
    doc_id: str
    version: int
    stage: str
    actor_id: str = ''
    reviewer_id: str = ''
    submitter_id: str = ''
    expected_version: Optional[int] = None
    comment: str = ''
    dissent_note: str = ''
    conditions: str = ''
    created_at: str = ''
    def __post_init__(self):
        integer(self.version,'version',1)
        if self.expected_version is not None:integer(self.expected_version,'expected_version',1)
        if self.stage not in ('submitted','approved','rejected','published','dissent_recorded'):raise ValidationError('Invalid review stage')
        for name in ('decision_id','org_id','doc_id','actor_id','reviewer_id','submitter_id','comment','dissent_note','conditions','created_at'):text(getattr(self,name),name)

@dataclass(frozen=True)
class ReleaseManifest(PolicyContract):
    doc_id: str
    org_id: str
    version: int
    lifecycle_state: str
    submitter_id: str = ''
    reviewer_id: str = ''
    publisher_id: str = ''
    published_at: str = ''
    dissent_notes: Tuple[str, ...] = ()
    resolved_issue_ids: Tuple[str, ...] = ()
    def __post_init__(self):
        integer(self.version,'version',1)
        for n in ('dissent_notes','resolved_issue_ids'):object.__setattr__(self,n,sequence(getattr(self,n),n))

@dataclass(frozen=True)
class IssueResolution(PolicyContract):
    issue_id: str
    org_id: str
    doc_id: str
    version: int
    resolution_action: str
    note: str
    actor_id: str
    created_at: str
    revision_version: Optional[int] = None
    def __post_init__(self):
        if self.resolution_action not in ('create_revision_draft','retrieval_tuning','keep_dissent','dismissed'):raise ValidationError('Invalid resolution action')
        integer(self.version,'version',1)
        text(self.note,'note',True)
