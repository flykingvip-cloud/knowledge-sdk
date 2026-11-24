"""Strict queue-only evidence feedback contracts; no document mutation semantics."""
from __future__ import annotations
from dataclasses import dataclass, fields
from datetime import datetime, timedelta
from enum import Enum
import unicodedata
from .policy import PolicyContract, enum_value, parse_time
from .anchors import integer
from .uri import parse_uri_v2
from ..exceptions import ValidationError

class IssueType(str,Enum):
    OUTDATED='outdated'
    ANCHOR_DRIFT='anchor_drift'
    CONFLICT='conflict'
    INACCURACY='inaccuracy'

ISSUE_STATUSES=('open','triaged','resolved','dismissed')
def issue_text(value,name,required=False):
    if not isinstance(value,str) or any(unicodedata.category(c).startswith('C') for c in value) or required and not value.strip():
        raise ValidationError('Invalid '+name)
    return value

@dataclass(frozen=True)
class EvidenceIssue(PolicyContract):
    issue_id:str
    org_id:str
    doc_id:str
    version:int
    anchor_id:str=''
    issue_type:IssueType=IssueType.INACCURACY
    description:str=''
    conflicting_uri:str=''
    reported_by_user_id:str=''
    reported_by_agent_id:str=''
    status:str='open'
    created_at:str=''
    def __post_init__(self):
        for f in fields(self):
            if f.name not in ('version','issue_type'):issue_text(getattr(self,f.name),f.name,f.name in ('issue_id','org_id','doc_id','description','created_at'))
        integer(self.version,'version',1)
        object.__setattr__(self,'issue_type',enum_value(IssueType,self.issue_type))
        if not 1<=len(self.description)<=4000 or self.status not in ISSUE_STATUSES:raise ValidationError('Invalid evidence issue')
        parse_time(self.created_at)
        raw=datetime.fromisoformat(self.created_at[:-1]+'+00:00' if self.created_at.endswith('Z') else self.created_at)
        if raw.utcoffset()!=timedelta(0):raise ValidationError('Issue timestamp must be UTC')
        if self.conflicting_uri:parse_uri_v2(self.conflicting_uri)
