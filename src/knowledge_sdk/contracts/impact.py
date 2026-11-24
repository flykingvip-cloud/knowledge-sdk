"""Immutable usage lineage and identifier-only impact metadata."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import re
from .policy import PolicyContract, Purpose, enum_value, parse_time, text
from ..exceptions import ValidationError


class ImpactReason(str, Enum):
    ACCESS_REVOKED = 'access_revoked'
    RESOURCE_ARCHIVED = 'resource_archived'
    SUPERSEDED = 'superseded'
    ANCHOR_DRIFTED = 'anchor_drifted'
    ANCHOR_ORPHANED = 'anchor_orphaned'


@dataclass(frozen=True)
class UsageEvent(PolicyContract):
    usage_id: str
    org_id: str
    doc_id: str
    version: int
    anchor_id: str = ''
    consumer_type: str = ''
    consumer_id: str = ''
    task_id: str = ''
    actor_id: str = ''
    agent_id: str = ''
    purpose: str = 'read'
    receipt_hash: str = ''
    created_at: str = ''

    def __post_init__(self):
        for name in ('usage_id','org_id','doc_id','actor_id'):text(getattr(self,name),name,True)
        for name in ('anchor_id','consumer_type','consumer_id','task_id','agent_id'):text(getattr(self,name),name)
        if type(self.version) is not int or self.version<1:raise ValidationError('Invalid usage version')
        object.__setattr__(self,'purpose',enum_value(Purpose,self.purpose).value)
        if not isinstance(self.receipt_hash,str) or not re.fullmatch('[0-9a-f]{64}',self.receipt_hash):
            raise ValidationError('Invalid receipt hash')
        parse_time(self.created_at)


@dataclass(frozen=True)
class ImpactAlert(PolicyContract):
    alert_id: str
    org_id: str
    source_event_id: str
    doc_id: str
    source_version: int
    target_type: str
    target_id: str
    impact_reason: ImpactReason
    status: str = 'open'
    created_at: str = ''
    summary: str = ''

    def __post_init__(self):
        for name in ('alert_id','org_id','source_event_id','doc_id','target_id'):text(getattr(self,name),name,True)
        if type(self.source_version) is not int or self.source_version<1:raise ValidationError('Invalid source_version')
        if self.target_type not in ('consumer_binding','usage_event','evidence_pack'):raise ValidationError('Invalid target_type')
        if self.status not in ('open','acknowledged','resolved'):raise ValidationError('Invalid impact status')
        object.__setattr__(self,'impact_reason',enum_value(ImpactReason,self.impact_reason))
        parse_time(self.created_at)
        # Always derive this metadata from identifiers, never trust a stored title
        # or a caller-supplied free-text summary.
        object.__setattr__(self,'summary',impact_summary(self))


def impact_summary(alert):
    import json
    return json.dumps({'doc_id':alert.doc_id,'version':alert.source_version,
                       'target_type':alert.target_type,'target_id':alert.target_id,
                       'impact_reason':alert.impact_reason.value},sort_keys=True,separators=(',',':'))
