"""Immutable connector protocol: source deltas are data, never executable adapters."""
from __future__ import annotations
from dataclasses import dataclass,field,asdict
from typing import Tuple,Optional,Any
from .policy import freeze_json,ResourceRights
from .models import DocumentACL
from ..exceptions import ValidationError


def _acl(value):
    if value is None:return None
    if isinstance(value,DocumentACL):value=asdict(value)
    if not isinstance(value,dict):raise ValidationError('Invalid connector ACL')
    DocumentACL(**value)
    return freeze_json(value)

@dataclass(frozen=True)
class ConnectorDocument:
    external_id: str
    doc_id: str
    kb_id: str
    content: Any
    filename: str = 'document.txt'
    title: str = ''
    metadata: dict = field(default_factory=dict)
    acl: Optional[dict] = None
    rights: Optional[ResourceRights] = None
    governance_tier: str = 'l1_agile'
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    source_sha256: str = ''
    updated_at: str = ''
    def __post_init__(self):
        if not all(isinstance(v,str) and v for v in (self.external_id,self.doc_id,self.kb_id)):raise ValidationError('Invalid source identity')
        if not isinstance(self.content,(str,bytes)):raise ValidationError('Invalid connector content')
        object.__setattr__(self,'metadata',freeze_json(dict(self.metadata)))
        object.__setattr__(self,'acl',_acl(self.acl))
        if isinstance(self.rights,dict):object.__setattr__(self,'rights',ResourceRights.from_dict(self.rights))
        if self.rights is not None and not isinstance(self.rights,ResourceRights):raise ValidationError('Invalid rights')

@dataclass(frozen=True)
class ConnectorACLUpdate:
    external_id: str
    doc_id: str
    acl: Optional[dict] = None
    rights: Optional[ResourceRights] = None
    def __post_init__(self):
        if not self.external_id or not self.doc_id:raise ValidationError('Invalid ACL update')
        object.__setattr__(self,'acl',_acl(self.acl))
        if isinstance(self.rights,dict):object.__setattr__(self,'rights',ResourceRights.from_dict(self.rights))

@dataclass(frozen=True)
class TombstoneRecord:
    external_id: str
    doc_id: str
    action: str = 'revoke'
    reason: str = ''
    occurred_at: str = ''
    def __post_init__(self):
        if self.action not in ('revoke','archive') or not self.external_id or not self.doc_id:raise ValidationError('Invalid tombstone')

@dataclass(frozen=True)
class ConnectorSyncBatch:
    upserts: Tuple[ConnectorDocument,...] = ()
    acl_updates: Tuple[ConnectorACLUpdate,...] = ()
    tombstones: Tuple[TombstoneRecord,...] = ()
    next_cursor: str = ''
    has_more: bool = False
    def __post_init__(self):
        for name,kind in (('upserts',ConnectorDocument),('acl_updates',ConnectorACLUpdate),('tombstones',TombstoneRecord)):
            values=getattr(self,name)
            if not isinstance(values,(tuple,list)) or any(not isinstance(v,kind) for v in values):raise ValidationError('Invalid batch')
            object.__setattr__(self,name,tuple(values))
        if not isinstance(self.next_cursor,str) or type(self.has_more) is not bool:raise ValidationError('Invalid cursor')

@dataclass(frozen=True)
class ConnectorSyncReport:
    connector_id: str
    org_id: str
    applied_upserts: int
    applied_acls: int
    applied_tombstones: int
    outbox_events: int
    previous_cursor: str
    next_cursor: str
