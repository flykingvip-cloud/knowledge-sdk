"""Strict KnowledgeResource vs DataCapabilityRef separation. Stdlib only."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

RESOURCE_TYPES = frozenset({'document', 'knowledge_base', 'agent_memory', 'materialized_snapshot'})
CAPABILITY_KINDS = frozenset({'structured_select', 'object_get', 'snapshot_read'})


class BoundaryError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _id(value, name='id'):
    if type(value) is not str or not value or value != value.strip() or '/' in value:
        raise BoundaryError('INVALID_' + name.upper())
    return value


@dataclass(frozen=True)
class KnowledgeResource:
    tenant_id: str
    resource_id: str
    resource_type: str
    label: Optional[str] = None

    def __post_init__(self):
        _id(self.tenant_id, 'tenant_id')
        _id(self.resource_id, 'resource_id')
        if self.resource_type not in RESOURCE_TYPES:
            raise BoundaryError('INVALID_RESOURCE_TYPE')
        if self.label is not None and (type(self.label) is not str or len(self.label) > 64):
            raise BoundaryError('INVALID_LABEL')


@dataclass(frozen=True)
class DataCapabilityRef:
    tenant_id: str
    capability_id: str
    kind: str
    handle: str

    def __post_init__(self):
        _id(self.tenant_id, 'tenant_id')
        _id(self.capability_id, 'capability_id')
        if self.kind not in CAPABILITY_KINDS:
            raise BoundaryError('INVALID_CAPABILITY_KIND')
        if type(self.handle) is not str or not (self.handle.startswith('svc:') or self.handle.startswith('deleg:') or self.handle.startswith('slot:')):
            raise BoundaryError('INVALID_CAPABILITY_HANDLE')
        lowered = self.handle.lower()
        if any(token in lowered for token in ('password', 'secret', 'apikey', 'api_key', 'dsn=')):
            raise BoundaryError('CREDENTIAL_FORBIDDEN')


@dataclass(frozen=True)
class ResourceCapabilityBinding:
    tenant_id: str
    resource_id: str
    capability_id: str
    policy_generation: int

    def __post_init__(self):
        _id(self.tenant_id, 'tenant_id')
        _id(self.resource_id, 'resource_id')
        _id(self.capability_id, 'capability_id')
        if type(self.policy_generation) is not int or isinstance(self.policy_generation, bool) or not 1 <= self.policy_generation <= 9007199254740991:
            raise BoundaryError('INVALID_POLICY_GENERATION')


def validate_distinct(resource, capability, binding=None):
    if not isinstance(resource, KnowledgeResource) or not isinstance(capability, DataCapabilityRef):
        raise BoundaryError('COLLAPSED_RESOURCE_CAPABILITY')
    if set(resource.__dataclass_fields__) & set(capability.__dataclass_fields__) - {'tenant_id'}:
        # shared tenant_id is the only allowed overlap of field names
        pass
    if hasattr(resource, 'capability_id') or hasattr(capability, 'resource_id') and 'resource_id' in getattr(capability, '__dict__', {}):
        raise BoundaryError('COLLAPSED_RESOURCE_CAPABILITY')
    if isinstance(resource, DataCapabilityRef) or isinstance(capability, KnowledgeResource):
        raise BoundaryError('COLLAPSED_RESOURCE_CAPABILITY')
    if resource.tenant_id != capability.tenant_id:
        raise BoundaryError('TENANT_MISMATCH')
    if binding is not None:
        if not isinstance(binding, ResourceCapabilityBinding):
            raise BoundaryError('INVALID_BINDING')
        if binding.tenant_id != resource.tenant_id or binding.resource_id != resource.resource_id or binding.capability_id != capability.capability_id:
            raise BoundaryError('BINDING_MISMATCH')
    return True


def reject_collapsed_payload(payload):
    if not isinstance(payload, dict):
        raise BoundaryError('INVALID_PAYLOAD')
    has_resource = 'resource_id' in payload or 'resource_type' in payload
    has_capability = 'capability_id' in payload or 'kind' in payload
    if has_resource and has_capability:
        raise BoundaryError('COLLAPSED_RESOURCE_CAPABILITY')
    return payload
