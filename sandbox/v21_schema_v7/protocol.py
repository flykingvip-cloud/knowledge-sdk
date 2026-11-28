"""Sandbox analogues for future HTTP / Python / MCP compatibility (T-18–T-20).

In-process only. Does not mount production HTTP, does not start an MCP
server, and does not change /v2/spaces semantics. EXPERIMENTAL_V3_ENABLED
stays default false. These checks are not formal compatibility acceptance.
"""
from __future__ import annotations

import json
from pathlib import Path

from .constants import (
    FROZEN_V2_BASELINE,
    FROZEN_V2_SPACES_PATH,
    OFFICIAL_ACTIONS,
    SANDBOX_V7_SPACES_PATH,
)

EXPERIMENTAL_V3_ENABLED_DEFAULT = False
OPENBOT_KNOWLEDGE_SDK_V2_ENABLED_DEFAULT = False

# Candidate Python protocol required keys (sandbox only).
SPACE_PROTOCOL_KEYS = (
    'tenant_id', 'space_id', 'space_type', 'owner_id', 'status', 'policy_generation',
)
KB_PROTOCOL_KEYS = ('tenant_id', 'kb_id', 'space_id', 'home_space_id', 'archived')
FAVORITE_POINTER_KEYS = ('tenant_id', 'user_id', 'target_type', 'target_id')
MCP_FORBIDDEN_TOOLS = frozenset({
    'text_to_sql', 'sql', 'query_kind_text_to_sql', 'credential_vault',
    'model_credential_vault', 'bypass_rls',
})


class ProtocolError(RuntimeError):
    def __init__(self, code, message=None):
        self.code = code
        super().__init__(message or code)


class SandboxHttpSurface(object):
    """In-process HTTP path dispatcher. No sockets, no production mount."""

    def __init__(self):
        self.experimental_v3_enabled = EXPERIMENTAL_V3_ENABLED_DEFAULT
        self.openbot_v2_enabled = OPENBOT_KNOWLEDGE_SDK_V2_ENABLED_DEFAULT
        self._v2_frozen = {
            'path': FROZEN_V2_SPACES_PATH,
            'baseline': FROZEN_V2_BASELINE,
            'semantics': 'frozen_v2_spaces',
        }

    def mount_production_http(self):
        raise ProtocolError('MOUNT_PRODUCTION_HTTP_FORBIDDEN')

    def mount_v3(self):
        raise ProtocolError('MOUNT_V3_FORBIDDEN')

    def redefine_v2_spaces(self, _new_semantics):
        raise ProtocolError('SILENT_V2_SEMANTIC_CHANGE_FORBIDDEN')

    def dispatch(self, method, path, body=None):
        method = (method or 'GET').upper()
        if path.startswith('/v3/') or path == '/v3':
            raise ProtocolError('V3_UNMOUNTED')
        if path == FROZEN_V2_SPACES_PATH:
            if method in ('PUT', 'PATCH', 'DELETE') and body and body.get('rewrite_semantics'):
                raise ProtocolError('SILENT_V2_SEMANTIC_CHANGE_FORBIDDEN')
            return {
                'status': 200,
                'path': path,
                'baseline': FROZEN_V2_BASELINE,
                'semantics': self._v2_frozen['semantics'],
                'mutable': False,
            }
        if path == SANDBOX_V7_SPACES_PATH or path.startswith(SANDBOX_V7_SPACES_PATH + '/'):
            return {
                'status': 200,
                'path': path,
                'surface': 'sandbox_v7',
                'distinct_from_v2': True,
            }
        return {'status': 404, 'path': path, 'code': 'NOT_FOUND'}


def validate_python_space(payload):
    if type(payload) is not dict:
        raise ProtocolError('INVALID_PYTHON_SPACE')
    missing = [key for key in SPACE_PROTOCOL_KEYS if key not in payload]
    if missing:
        raise ProtocolError('INVALID_PYTHON_SPACE', 'missing ' + ','.join(missing))
    if payload.get('parent_space_id'):
        raise ProtocolError('PARENT_SPACE_FORBIDDEN')
    return True


def validate_python_kb(payload):
    if type(payload) is not dict:
        raise ProtocolError('INVALID_PYTHON_KB')
    missing = [key for key in KB_PROTOCOL_KEYS if key not in payload]
    if missing:
        raise ProtocolError('INVALID_PYTHON_KB', 'missing ' + ','.join(missing))
    if payload.get('tenant_id') and payload.get('org_id') and payload['tenant_id'] != payload.get('org_id', payload['tenant_id']):
        raise ProtocolError('ORG_MISMATCH')
    space_id = payload.get('space_id')
    home = payload.get('home_space_id')
    if space_id not in (None, home) and space_id != home:
        raise ProtocolError('ATTACH_HOME_MISMATCH')
    return True


def validate_python_favorite_pointer(payload):
    if type(payload) is not dict:
        raise ProtocolError('INVALID_FAVORITE')
    missing = [key for key in FAVORITE_POINTER_KEYS if key not in payload]
    if missing:
        raise ProtocolError('INVALID_FAVORITE', 'missing ' + ','.join(missing))
    for forbidden in ('body', 'chunk', 'embedding', 'evidence', 'body_text'):
        if payload.get(forbidden):
            raise ProtocolError('FAVORITE_BODY_FORBIDDEN')
    return True


def read_frozen_contract_flags(repo_root):
    """Read-only assertion that the frozen v21-reuse-v1 pack flags are unchanged."""
    path = Path(repo_root) / 'contracts' / 'v21-reuse-v1' / 'status.json'
    status = json.loads(path.read_text())
    required = {
        'schema_v7_ddl_authorized': False,
        'schema_v8_v9_ddl_authorized': False,
        'final_alignment_frozen': False,
        'prod_shadow_migration_cutover_authorized': False,
        'formal_t01_t27': 'NOT_RUN_NOT_ACCEPTED',
        'mounted_v3_runtime': False,
    }
    for key, expected in required.items():
        if status.get(key) != expected:
            raise ProtocolError(
                'FROZEN_CONTRACT_FLAG_DRIFT',
                '%s expected %r got %r' % (key, expected, status.get(key)),
            )
    return status


def evaluate_mcp_tool(tool_name, user_allowed, agent_allowed, space_id=None):
    """Candidate MCP policy: tool must stay inside User ∩ Agent, no free SQL."""
    if tool_name in MCP_FORBIDDEN_TOOLS or (tool_name or '').lower() in MCP_FORBIDDEN_TOOLS:
        return {'allowed': False, 'code': 'TEXT_TO_SQL_OR_CREDENTIAL_FORBIDDEN'}
    if not user_allowed:
        return {'allowed': False, 'code': 'USER_DENIED'}
    if not agent_allowed:
        return {'allowed': False, 'code': 'AGENT_CEILING'}
    if space_id and agent_allowed is not True:
        allowed_spaces = set(agent_allowed if isinstance(agent_allowed, (list, tuple, set)) else [])
        if allowed_spaces and space_id not in allowed_spaces:
            return {'allowed': False, 'code': 'AGENT_SPACE_CEILING'}
    return {'allowed': True, 'code': 'ALLOW', 'effective': 'user_intersect_agent'}


def candidate_mcp_policy_document():
    return {
        'version': 'sandbox-v7-mcp-candidate',
        'formal_acceptance': False,
        'allowed_actions': list(OFFICIAL_ACTIONS),
        'forbidden_tools': sorted(MCP_FORBIDDEN_TOOLS),
        'intersection': 'UserRights ∩ AgentProfile ∩ TaskScope',
        'fail_closed': True,
    }
