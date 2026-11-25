from __future__ import annotations
"""Immutable, tenant-bound authoritative identity and synchronization state."""
from dataclasses import dataclass, asdict
from typing import Tuple
from ..exceptions import ValidationError

@dataclass(frozen=True)
class IdentityPrincipal:
    org_id: str
    user_id: str
    external_id: str = ''
    username: str = ''
    active: bool = True
    policy_generation: int = 1
    roles: Tuple[str, ...] = ()
    department_ids: Tuple[str, ...] = ()
    org_roles: Tuple[str, ...] = ()
    clearance_level: str = ''
    clearance_tags: Tuple[str, ...] = ()
    updated_at: str = ''
    def __post_init__(self):
        for n in ('org_id','user_id'):
            v=getattr(self,n)
            if not isinstance(v,str) or not v or any(ord(c)<32 for c in v):raise ValidationError('Invalid principal identity')
        if type(self.active) is not bool or type(self.policy_generation) is not int or self.policy_generation<1:raise ValidationError('Invalid principal generation')
        if any(not isinstance(getattr(self,n),str) for n in ('external_id','username','updated_at')):raise ValidationError('Invalid principal attributes')
        if not isinstance(self.clearance_level,str):raise ValidationError('Invalid clearance')
        for n in ('roles','department_ids','org_roles','clearance_tags'):
            v=getattr(self,n)
            if not isinstance(v,(list,tuple)) or any(not isinstance(x,str) or not x for x in v):raise ValidationError('Invalid principal claims')
            object.__setattr__(self,n,tuple(v))

@dataclass(frozen=True)
class ConnectorSyncState:
    org_id: str
    connector_id: str
    cursor: str = ''
    updated_at: str = ''
    def __post_init__(self):
        if not self.org_id or not self.connector_id or not isinstance(self.cursor,str):raise ValidationError('Invalid connector state')
