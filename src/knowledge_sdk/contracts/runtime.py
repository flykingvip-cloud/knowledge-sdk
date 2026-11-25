"""Q3-M1 frozen runtime contracts.

Supplemental defaults are implementation choices: protocol spec was not supplied.
Empty profile whitelists mean unrestricted; explicit task scope ``none`` means deny all.
"""
from __future__ import annotations
from dataclasses import dataclass, field, fields
import hashlib
import json
import re
from typing import Tuple
from .policy import PolicyContract, Purpose, enum_value, sequence, text, parse_time
from ..exceptions import ValidationError


def integer(value, name, minimum=0):
    if type(value) is not int or value < minimum: raise ValidationError('Invalid '+name)


class RuntimeContract(PolicyContract):
    def to_dict(self):
        def convert(value):
            if isinstance(value, PolicyContract) or hasattr(value, 'to_dict'): return value.to_dict()
            if isinstance(value, (tuple, list)): return [convert(v) for v in value]
            if isinstance(value, dict): return {k:convert(v) for k,v in value.items()}
            return value.value if isinstance(value, Purpose) else value
        return {f.name:convert(getattr(self,f.name)) for f in fields(self)}


@dataclass(frozen=True)
class ContextBudget(RuntimeContract):
    max_documents: int = 5
    max_items: int = 20
    max_chars_per_item: int = 2000
    max_total_chars: int = 8000
    max_ttl_seconds: int = 900
    def __post_init__(self):
        for f in fields(self): integer(getattr(self,f.name),f.name)
    def clamp(self, other):
        if not isinstance(other,ContextBudget): raise ValidationError('Expected ContextBudget')
        return ContextBudget(**{f.name:min(getattr(self,f.name),getattr(other,f.name)) for f in fields(self)})


@dataclass(frozen=True)
class AgentProfile(RuntimeContract):
    org_id: str
    agent_id: str
    display_name: str = ''
    allowed_purposes: Tuple[Purpose,...] = (Purpose.READ, Purpose.GROUND_INTERNAL_LLM)
    allowed_kb_ids: Tuple[str,...] = ()
    allowed_space_types: Tuple[str,...] = ()
    max_clearance_level: str = 'internal'
    default_budget: ContextBudget = field(default_factory=ContextBudget)
    active: bool = True
    profile_generation: int = 1
    updated_at: str = ''
    def __post_init__(self):
        for n in ('org_id','agent_id'):text(getattr(self,n),n,True)
        text(self.display_name,'display_name')
        for n in ('allowed_kb_ids','allowed_space_types'):
            object.__setattr__(self,n,sequence(getattr(self,n),n))
        object.__setattr__(self,'allowed_purposes',sequence(self.allowed_purposes,'allowed_purposes',Purpose))
        if set(self.allowed_space_types)-{'enterprise_public','department','personal'}:raise ValidationError('Invalid space types')
        if self.max_clearance_level not in ('public','internal','confidential','restricted'):raise ValidationError('Invalid clearance')
        if isinstance(self.default_budget,dict):object.__setattr__(self,'default_budget',ContextBudget.from_dict(self.default_budget))
        if not isinstance(self.default_budget,ContextBudget):raise ValidationError('Invalid default budget')
        if type(self.active) is not bool:raise ValidationError('Invalid active')
        integer(self.profile_generation,'profile_generation',1)
        text(self.updated_at,'updated_at')
        if self.updated_at:parse_time(self.updated_at)


@dataclass(frozen=True)
class TaskContext(RuntimeContract):
    task_id: str
    org_id: str
    actor_id: str
    agent_id: str
    purpose: Purpose
    policy_generation: int
    profile_generation: int
    scope: object
    budget: ContextBudget
    expires_at: str
    created_at: str
    updated_at: str
    status: str = 'active'
    revoked_reason: str = ''
    revoked_at: str = ''
    def __post_init__(self):
        from .models import KnowledgeScope
        for n in ('task_id','org_id','actor_id','agent_id'):text(getattr(self,n),n,True)
        object.__setattr__(self,'purpose',enum_value(Purpose,self.purpose))
        integer(self.policy_generation,'policy_generation');integer(self.profile_generation,'profile_generation',1)
        if isinstance(self.scope,dict):object.__setattr__(self,'scope',KnowledgeScope.from_dict(self.scope))
        if not isinstance(self.scope,KnowledgeScope):raise ValidationError('Invalid scope')
        if isinstance(self.budget,dict):object.__setattr__(self,'budget',ContextBudget.from_dict(self.budget))
        if not isinstance(self.budget,ContextBudget):raise ValidationError('Invalid budget')
        if self.status not in ('active','completed','expired','revoked'):raise ValidationError('Invalid task status')
        for n in ('expires_at','created_at','updated_at'):parse_time(getattr(self,n))
        for n in ('revoked_reason','revoked_at'):text(getattr(self,n),n)
        if self.revoked_at:parse_time(self.revoked_at)


@dataclass(frozen=True)
class SnapshotItem(RuntimeContract):
    doc_id: str
    version: int
    text: str
    source_uri: str
    anchor_id: str = ''
    chunk_ids: Tuple[str,...] = ()
    excerpt_hash: str = ''
    def __post_init__(self):
        for n in ('doc_id','source_uri'):text(getattr(self,n),n,True)
        text(self.text,'text');text(self.anchor_id,'anchor_id')
        integer(self.version,'version',1)
        object.__setattr__(self,'chunk_ids',sequence(self.chunk_ids,'chunk_ids'))
        text(self.excerpt_hash,'excerpt_hash')
        expected=hashlib.sha256(self.text.encode()).hexdigest()
        if self.excerpt_hash and self.excerpt_hash!=expected:raise ValidationError('Invalid excerpt hash')
        object.__setattr__(self,'excerpt_hash',expected)


@dataclass(frozen=True)
class ContextSnapshot(RuntimeContract):
    snapshot_id: str
    task_id: str
    org_id: str
    snapshot_seq: int
    items: Tuple[SnapshotItem,...]
    created_at: str
    snapshot_sha256: str = ''
    status: str = 'valid'
    item_count: int = 0
    total_chars: int = 0
    def __post_init__(self):
        for n in ('snapshot_id','task_id','org_id'):text(getattr(self,n),n,True)
        integer(self.snapshot_seq,'snapshot_seq',1);parse_time(self.created_at)
        if not isinstance(self.items,(tuple,list)):raise ValidationError('Invalid items')
        values=tuple(SnapshotItem.from_dict(v) if isinstance(v,dict) else v for v in self.items)
        if any(not isinstance(v,SnapshotItem) for v in values):raise ValidationError('Invalid item')
        object.__setattr__(self,'items',values)
        if self.status not in ('valid','revoked'):raise ValidationError('Invalid snapshot status')
        integer(self.item_count,'item_count');integer(self.total_chars,'total_chars')
        if self.item_count!=len(values) or self.total_chars!=sum(len(v.text) for v in values):raise ValidationError('Invalid snapshot counts')
        text(self.snapshot_sha256,'snapshot_sha256')
        if self.snapshot_sha256 and not re.fullmatch('[0-9a-f]{64}',self.snapshot_sha256):raise ValidationError('Invalid snapshot hash')
    def digest(self):
        data=self.to_dict();data.pop('snapshot_sha256');data.pop('status')
        return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


@dataclass(frozen=True)
class MidTaskRevocation(RuntimeContract):
    revocation_id: str
    org_id: str
    task_id: str
    reason_code: str
    created_at: str
    snapshot_id: str = ''
    trigger_event_id: str = ''
    affected_doc_id: str = ''
    affected_version: int = 0
    affected_anchor_id: str = ''
    def __post_init__(self):
        for n in ('revocation_id','org_id','task_id','reason_code'):text(getattr(self,n),n,True)
        for n in ('snapshot_id','trigger_event_id','affected_doc_id','affected_anchor_id'):text(getattr(self,n),n)
        integer(self.affected_version,'affected_version');parse_time(self.created_at)
