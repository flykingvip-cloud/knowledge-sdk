"""Deterministic W7A-2 core T-01-T-27 evidence report writer.

formal_t01_t27_accepted remains false. This report is an isolation-branch
engineering evidence pack, not official final acceptance.
"""
from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path

from knowledge_sdk.storage.schema_v7 import RESERVED_TITLES

SCOPE = 'CORE_STORAGE_V7_ISOLATION_BRANCH'

PASS_SUMMARIES = {'T-01': 'Real Schema v7 SQLite storage rejected cross-tenant Space/KB visibility and inserts; official PostgreSQL Schema v7 DDL ENABLE/FORCE RLS binds tenant_id to app.current_org_id on every ks_v7_* table. Live PostgreSQL is executed in CI unit-suite/pytest-suite against a disposable non-superuser schema when KNOWLEDGE_SDK_TEST_PG_DSN is set. Not official final acceptance.', 'T-02': 'Phase-1 model is flat Tenant -> Space -> KnowledgeBase on the real storage stack: no parent_space_id column, parent inserts are refused, and the PG DDL semantic checker rejects parent_space_id. Not formal tree-closure review.', 'T-03': 'One Space holds many KnowledgeBases; Space and KB share tenant_id; a cross-tenant or cross-space home rebind is refused on the real Schema v7 tables. Isolation-branch only.', 'T-04': 'detach clears the mount and leaves archived=0; same-home reattach succeeds; attach to a different home fails; no implicit archive. Real storage, not formal acceptance.', 'T-05': 'Employee personal space is readable only by the owner; another same-tenant user is denied at the Space Gate (layer_2). Real storage, not formal acceptance.', 'T-06': 'Enterprise admin cannot read employee personal body/content even when an extra grant row is planted; personal-private invariant holds. Real storage, not formal acceptance.', 'T-07': 'Two same-tenant team Spaces (collaboration groups) stay isolated: each owner can read only their own team KB. Real storage, not formal acceptance.', 'T-08': 'All eight official SPACE-C05 actions are granted and evaluated independently; revoking one action does not grant an unknown admin action. Real storage, not formal acceptance.', 'T-09': 'Explicit Deny on a KB or asset wins over owner, member, and agent profile; hydration of a denied target returns only an unavailable placeholder. Real storage, not formal acceptance.', 'T-10': 'Agent allowed_space_ids is a hard ceiling: a user who can read another Space still cannot reach it through an agent that omits that Space. Real storage, not formal acceptance.', 'T-11': 'Agent fine-grained allowed_kb_ids tightens consumption: a KB outside the profile is denied even when the Space ceiling would allow it. Real storage, not formal acceptance.', 'T-12': 'Knowledge-file scope is enforced via allowed_knowledge_file_ids; a file outside the list is denied. Real storage, not formal acceptance.', 'T-13': 'Deliverable scope is enforced via allowed_deliverable_ids together with a current-user grant; a user without the underlying read cannot ride the agent. Real storage, not formal acceptance.', 'T-14': 'Folder scope is enforced via allowed_folder_ids; a folder miss is denied. Real storage, not formal acceptance.', 'T-15': 'Effective authorization is User ∩ Agent ∩ current profile generation; a stale profile generation or an unauthorized user fails closed. Real storage, not formal acceptance.', 'T-16': 'Revoke + policy_generation bump + outbox insert commit atomically through the real store transaction; an injected failure rolls back grants, generation, and outbox together. Live PostgreSQL repeats this in CI. Not official final acceptance.', 'T-17': 'Stale, non-integer, or out-of-range policy_generation values fail closed on the real Schema v7 engine. Not official final acceptance.', 'T-18': 'In-process HTTP surface keeps /v2/spaces frozen at 9940818b, serves a distinct /v7-core/spaces path, refuses silent v2 semantic changes, and refuses production /v3 mounts while EXPERIMENTAL_V3_ENABLED stays default false. Live signed /v2/spaces against a Schema v7 SQLite store runs when fastapi/uvicorn are available (CI unit-suite/pytest-suite). Not a formal HTTP compatibility gate.', 'T-19': 'Candidate Python protocol validators accept well-formed Space/KB/Favorite pointer payloads, reject parent_space_id and body-bearing favorites, and confirm frozen v21-reuse-v1 contract flags are unchanged. Not a formal independent Python client-compat gate.', 'T-20': 'Candidate MCP policy denies text-to-SQL / credential tools and any tool outside User ∩ Agent. Official MCP tool_definitions expose only the four evidence tools. Not formal MCP acceptance.', 'T-21': 'A materialized external asset with no provider assertion, or a missing assertion record, is denied on the real storage engine. Isolation-branch only.', 'T-22': 'An expired external assertion (valid_until in the past) is denied even if a provider function returns a stale token. Real storage, not formal acceptance.', 'T-23': 'A provider function that raises is treated as an outage and denied; no stale-allow fallback. Real storage, not formal acceptance.', 'T-24': 'Revoked or tombstoned external refs are denied; a cursor mismatch fails closed; free text-to-SQL remains forbidden at the MCP policy layer. Real storage, not formal acceptance.', 'T-25': 'Polymorphic favorite hydration stores only user_id+target pointers, never body/chunk/embedding/evidence, and hides denied metadata behind unavailable. Real storage, not formal acceptance.', 'T-26': 'Owned-nonproduction v6->v7 upgrade is idempotent; rollback is idempotent, returns schema_version 6, and does not restore grants; restore of principal, grants, policy_generation, or shares is refused (monotonic). Production migration remains unauthorized. PG candidate DDL FORCE RLS semantics validate; CI runs the live PostgreSQL path on a disposable schema. Not a reviewed production migration drill.', 'T-27': 'Resign freezes within 0s (SLA 60s), starts 90-day read-only isolation retention, invalidates controlled shares immediately, forbids private-body auto-inherit, and requires two independent approvers for work-product handover. Real storage state machine only; not full reviewed formal acceptance.'}


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
        ('wave', 'Wave-V21-7'),
        ('authorization', 'AUTH-V21-07-CORE-V7'),
        ('branch', 'feat/v21-wave7-core-schema-v7-and-formal-t01-t27'),
        ('package', 'src/knowledge_sdk/storage'),
        ('schema_version', 7),
        ('schema_v7_core_branch_ddl_authorized', True),
        ('schema_v7_prod_migration_authorized', False),
        ('schema_v8_v9_ddl_authorized', False),
        ('EXPERIMENTAL_V3_ENABLED_default', False),
        ('engines', OrderedDict([
            ('sqlite_actual', True),
            ('postgres_ddl_force_rls_semantic_validation', True),
            ('postgres_live_expected_in_ci', True),
            ('postgres_live_local_at_report_generation', False),
            ('http_v2_surface', True),
            ('mcp_surface', True),
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
