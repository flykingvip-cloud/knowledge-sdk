"""Read-only SemanticReference bindings to OpenBot semantic_object_key.

Explicitly forbids writing physical connector fields or credentials.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple

FORBIDDEN_FIELDS = frozenset({
    'dsn', 'connection_string', 'jdbc_url', 'host', 'port', 'username', 'password',
    'api_key', 'api_token', 'credential', 'private_key', 'access_token', 'secret',
    'connector_config', 'physical_connector', 'database',
})


class SemanticReferenceWriteForbidden(ValueError):
    def __init__(self, code='SEMANTIC_WRITE_FORBIDDEN'):
        self.code = code
        super().__init__(code)


def _token(value, name):
    if type(value) is not str or not value or len(value) > 256:
        raise SemanticReferenceWriteForbidden('INVALID_' + name.upper())
    return value


@dataclass(frozen=True)
class SemanticReference:
    tenant_id: str
    semantic_object_key: str
    concept_ids: Tuple[str, ...]
    policy_clause_ids: Tuple[str, ...]

    def __post_init__(self):
        _token(self.tenant_id, 'tenant_id')
        _token(self.semantic_object_key, 'semantic_object_key')
        if not self.semantic_object_key.startswith('semobj:'):
            raise SemanticReferenceWriteForbidden('INVALID_SEMANTIC_OBJECT_KEY')
        if type(self.concept_ids) is not tuple or type(self.policy_clause_ids) is not tuple:
            raise SemanticReferenceWriteForbidden('INVALID_MAPPING')
        for item in self.concept_ids + self.policy_clause_ids:
            _token(item, 'mapping')


def from_payload(payload):
    if not isinstance(payload, dict):
        raise SemanticReferenceWriteForbidden('INVALID_PAYLOAD')
    illegal = set(payload) & FORBIDDEN_FIELDS
    if illegal:
        raise SemanticReferenceWriteForbidden('SEMANTIC_WRITE_FORBIDDEN')
    if payload.get('write') or payload.get('mutate') or 'connector' in {k.lower() for k in payload}:
        raise SemanticReferenceWriteForbidden('SEMANTIC_WRITE_FORBIDDEN')
    return SemanticReference(
        payload['tenant_id'],
        payload['semantic_object_key'],
        tuple(payload.get('concept_ids') or ()),
        tuple(payload.get('policy_clause_ids') or ()),
    )


def write_physical(*_a, **_k):
    raise SemanticReferenceWriteForbidden('SEMANTIC_WRITE_FORBIDDEN')
