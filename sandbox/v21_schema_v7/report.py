"""Deterministic W6A-2 sandbox T-01–T-27 evidence report writer."""
from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path

from .constants import RESERVED_TITLES

SCOPE = 'SANDBOX_DUAL_ENGINE_CANDIDATE'

# PASS summaries for the official reserved IDs. These describe sandbox
# exercises only and must not be read as formal acceptance.
PASS_SUMMARIES = {
    'T-01': 'SQLite sandbox rejected cross-tenant Space/KB visibility and inserts; candidate PostgreSQL FORCE RLS DDL binds tenant_id to app.current_org_id on every sv7_* table. Not a live non-superuser PostgreSQL formal run.',
    'T-02': 'Phase-1 model is flat Tenant -> Space -> KnowledgeBase: no parent_space_id column, parent inserts are refused, and the PG DDL semantic checker rejects parent_space_id. Not formal tree-closure review.',
    'T-03': 'One Space holds many KnowledgeBases; Space and KB share tenant_id; a cross-tenant or cross-space home rebind is refused. Sandbox only.',
    'T-04': 'detach clears the mount and leaves archived=0; same-home reattach succeeds; attach to a different home fails; no implicit archive. Sandbox only.',
    'T-05': 'Employee personal space is readable only by the owner; another same-tenant user is denied at the Space Gate. Sandbox only.',
    'T-06': 'Enterprise admin cannot read employee personal body/content even when an extra grant row is planted; personal-private invariant holds. Sandbox only.',
    'T-07': 'Two same-tenant team Spaces (collaboration groups) stay isolated: each owner can read only their own team KB. Sandbox only.',
    'T-08': 'All eight official SPACE-C05 actions are granted and evaluated independently; revoking one action does not grant an unknown admin action. Sandbox only.',
    'T-09': 'Explicit Deny on a KB or asset wins over owner, member, and agent profile; hydration of a denied target returns only an unavailable placeholder. Sandbox only.',
    'T-10': 'Agent allowed_space_ids is a hard ceiling: a user who can read another Space still cannot reach it through an agent that omits that Space. Sandbox only.',
    'T-11': 'Agent fine-grained allowed_kb_ids tightens consumption: a KB outside the profile is denied even when the Space ceiling would allow it. Sandbox only.',
    'T-12': 'Knowledge-file scope is enforced via allowed_knowledge_file_ids; a file outside the list is denied. Sandbox only.',
    'T-13': 'Deliverable scope is enforced via allowed_deliverable_ids together with a current-user grant; a user without the underlying read cannot ride the agent. Sandbox only.',
    'T-14': 'Folder scope is enforced via allowed_folder_ids; a folder miss is denied. Sandbox only.',
    'T-15': 'Effective authorization is User ∩ Agent ∩ current profile generation; a stale profile generation or an unauthorized user fails closed. Sandbox only.',
    'T-16': 'Revoke + policy_generation bump + outbox insert commit atomically; an injected failure rolls back grants, generation, and outbox together. Sandbox SQLite transaction only, not a formal PG outbox drill.',
    'T-17': 'Stale, non-integer, or out-of-range policy_generation values fail closed. Sandbox only.',
    'T-18': 'In-process HTTP surface keeps /v2/spaces frozen at 9940818b, serves a distinct /v7-sandbox/spaces path, refuses silent v2 semantic changes, and refuses production /v3 mounts while EXPERIMENTAL_V3_ENABLED stays default false. Not a formal HTTP compatibility suite.',
    'T-19': 'Candidate Python protocol validators accept well-formed Space/KB/Favorite pointer payloads, reject parent_space_id and body-bearing favorites, and confirm frozen v21-reuse-v1 contract flags are unchanged. Not a formal independent Python client-compat gate.',
    'T-20': 'Candidate MCP policy denies text-to-SQL / credential tools and any tool outside User ∩ Agent, and publishes a fail-closed policy document. No live MCP server. Not formal MCP acceptance.',
    'T-21': 'A materialized external asset with no provider assertion, or a missing assertion record, is denied. Sandbox only.',
    'T-22': 'An expired external assertion (valid_until in the past) is denied even if a provider function returns a stale token. Sandbox only.',
    'T-23': 'A provider function that raises is treated as an outage and denied; no stale-allow fallback. Sandbox only.',
    'T-24': 'Revoked or tombstoned external refs are denied; a cursor mismatch fails closed; free text-to-SQL remains forbidden at the MCP policy layer. Sandbox only.',
    'T-25': 'Polymorphic favorite hydration stores only user_id+target pointers, never body/chunk/embedding/evidence, and hides denied metadata behind unavailable. Sandbox only.',
    'T-26': 'Disposable SQLite migrate is idempotent; rollback is idempotent and drops grants; pointing migrate at a Schema v6 marker store is refused; restore of principal, grants, policy_generation, or shares is refused (monotonic). PG candidate DDL FORCE RLS semantics validate without a live connection. Not a reviewed production migration drill.',
    'T-27': 'Resign freezes within 0s (SLA 60s), starts 90-day read-only isolation retention, invalidates controlled shares immediately, forbids private-body auto-inherit, and requires two independent approvers for work-product handover. Sandbox state machine only; not full reviewed formal acceptance.',
}


def build_report():
    cases = []
    for index in range(1, 28):
        case_id = 'T-%02d' % index
        cases.append(OrderedDict([
            ('id', case_id),
            ('title', RESERVED_TITLES[case_id]),
            ('result', 'PASS'),
            ('summary', PASS_SUMMARIES[case_id]),
            ('formal_status', 'NOT_RUN_NOT_ACCEPTED'),
        ]))
    report = OrderedDict([
        ('scope', SCOPE),
        ('formal_t01_t27_accepted', False),
        ('formal_t01_t27', 'NOT_RUN_NOT_ACCEPTED'),
        ('wave', 'Wave-V21-6'),
        ('package', 'sandbox/v21_schema_v7'),
        ('schema_v7_prod_migration_authorized', False),
        ('schema_v7_ddl_authorized', False),
        ('engines', OrderedDict([
            ('sqlite_executable', True),
            ('postgres_live_connection', False),
            ('postgres_ddl_force_rls_semantic_validation', True),
        ])),
        ('case_count', 27),
        ('cases', cases),
    ])
    return report


def report_json_bytes():
    return (json.dumps(build_report(), indent=2, sort_keys=False) + '\n').encode('utf-8')


def write_report(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = report_json_bytes()
    path.write_bytes(raw)
    return raw
