"""Core Schema v7 T-01-T-27 formal-path suite against real storage.

Exercises src/knowledge_sdk/storage (SQLite always; live PostgreSQL when
KNOWLEDGE_SDK_TEST_PG_DSN is set) plus HTTP /v2 and MCP surfaces.
formal_t01_t27_accepted remains false; this is not official final acceptance.
scope is CORE_STORAGE_V7_ISOLATION_BRANCH.
"""
from __future__ import annotations

import importlib.util
import os
import unittest
from pathlib import Path

from knowledge_sdk.exceptions import ConflictError, ValidationError
from knowledge_sdk.storage.migration_v6 import require_v6, schema_version as schema_version_v6, upgrade_v6
from knowledge_sdk.storage.migration_v7 import (
    SCHEMA_V7_PROD_MIGRATION_AUTHORIZED,
    postgres_v7_ddl,
    rollback_v7,
    schema_version,
    upgrade_v7,
)
from knowledge_sdk.storage.schema_v7 import (
    CORE_V7_SPACES_PATH,
    EXPERIMENTAL_V3_ENABLED_DEFAULT,
    FORMAL_T01_T27_ACCEPTED,
    ISOLATION_RETENTION_SECONDS,
    OFFICIAL_ACTIONS,
    RESERVED_TITLES,
    CoreV7HttpSurface,
    DdlSemanticError,
    ProtocolError,
    SchemaV7,
    SchemaV7Error,
    candidate_mcp_policy_document,
    evaluate_mcp_tool,
    experimental_v3_enabled,
    read_frozen_contract_flags,
    validate_official_postgres_ddl,
    validate_postgres_ddl,
    validate_python_favorite_pointer,
    validate_python_kb,
    validate_python_space,
)
from knowledge_sdk.storage.sqlite_store import SQLiteStore

from tests.wave7.w7a2_report import SCOPE, build_report, report_json_bytes

REPO_ROOT = Path(__file__).resolve().parents[2]
LIVE_PG_REASON = (
    'Live PostgreSQL DSN not configured; CI unit-suite/pytest-suite provisions a '
    'disposable non-superuser pgvector role via KNOWLEDGE_SDK_TEST_PG_DSN. Locally, '
    '127.0.0.1:5432 had no response and no DSN was set, so only SQLite + DDL/FORCE '
    'RLS semantic checks ran. No production database was contacted.'
)


def _make_sqlite_v7():
    store = SQLiteStore(':memory:')
    upgrade_v6(store, owned_nonproduction=True)
    upgrade_v7(store, owned_nonproduction=True)
    engine = SchemaV7(store)
    engine.seed_standard()
    return store, engine


def _make_postgres_v7():
    from tests.pg_helpers import PgSandbox
    from knowledge_sdk.storage.postgres_store import PostgresStore
    sandbox = PgSandbox()
    store = PostgresStore(sandbox.dsn, enable_rls=True)
    upgrade_v6(store, owned_nonproduction=True)
    upgrade_v7(store, owned_nonproduction=True)
    engine = SchemaV7(store)
    engine.seed_standard()
    return sandbox, store, engine


class CoreV7SqliteT01T27Cases(unittest.TestCase):
    live_postgres = False

    def setUp(self):
        self.pg = validate_official_postgres_ddl()
        self.assertTrue(self.pg['ok'])
        self.assertFalse(self.pg['live_connection'])
        self._pg_sandbox = None
        if self.live_postgres:
            self._pg_sandbox, self.store, self.s = _make_postgres_v7()
            self.addCleanup(self.store.close)
            self.addCleanup(self._pg_sandbox.close)
        else:
            self.store, self.s = _make_sqlite_v7()
            self.addCleanup(self.store.close)
        self.assertEqual(schema_version(self.store), 7)
        self.assertFalse(FORMAL_T01_T27_ACCEPTED)
        self.assertFalse(SCHEMA_V7_PROD_MIGRATION_AUTHORIZED)

    def _external_assertion(self, **overrides):
        payload = dict(
            tenant_id='syn_org_a',
            subject_id='syn_admin',
            asset_id='syn_external_asset',
            valid_until=self.s.now() + 110,
            generation=1,
        )
        payload.update(overrides)
        return payload

    def _space_columns(self):
        if self.live_postgres:
            return [row[0] for row in self.store._execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema=current_schema() AND table_name=%s",
                ('ks_v7_space',),
            )]
        return [row[1] for row in self.store._execute('PRAGMA table_info(ks_v7_space)')]

    def test_t01_explicit_enterprise_tenant_and_tenant_boundary(self):
        self.assertEqual(RESERVED_TITLES['T-01'], 'Explicit enterprise tenant and tenant boundary')
        self.assertTrue(self.s.authorize('syn_org_a', 'syn_alice', 'syn_group_a_kb').allowed)
        decision = self.s.authorize('syn_org_a', 'syn_alice', 'syn_group_a_kb', claimed_tenant_id='syn_org_b')
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.layer, 'layer_0')
        # A KB that exists only in org_b is not visible when authorized in org_a.
        self.s.create_kb('syn_org_b', 'syn_org_b_only_kb', 'syn_enterprise')
        hidden = self.s.authorize('syn_org_a', 'syn_admin', 'syn_org_b_only_kb')
        self.assertFalse(hidden.allowed)
        # Foreign space cannot be referenced from the other tenant (FK / visibility).
        with self.assertRaises(Exception):
            self.s.create_kb('syn_org_a', 'syn_bad_kb', 'syn_missing_space')
        self.assertTrue(self.pg['force_rls'])

    def test_t02_flat_tenant_space_kb_no_parent(self):
        self.assertEqual(RESERVED_TITLES['T-02'], 'Flat Tenant-Space-KB, no parent')
        columns = self._space_columns()
        self.assertNotIn('parent_space_id', columns)
        bad = postgres_v7_ddl(include_semantic_role=True) + '\nALTER TABLE ks_v7_space ADD COLUMN parent_space_id TEXT;\n'
        with self.assertRaises(DdlSemanticError):
            validate_postgres_ddl(bad)

    def test_t03_same_org_composite_kb_binding(self):
        self.assertEqual(RESERVED_TITLES['T-03'], 'Same-org composite KB binding')
        kbs = self.s.sql(
            "SELECT kb_id FROM ks_v7_kb WHERE tenant_id=? AND home_space_id=?",
            ('syn_org_a', 'syn_enterprise'),
        )
        self.assertGreaterEqual(len(kbs), 2)
        # Cross-tenant home is refused.
        with self.assertRaises(Exception):
            self.s.sql(
                'INSERT INTO ks_v7_kb(tenant_id, kb_id, space_id, home_space_id, archived) VALUES(?,?,?,?,0)',
                ('syn_org_a', 'syn_cross', 'syn_group_a', 'syn_group_a_from_b'),
            )

    def test_t04_detach_not_archive_and_same_home_reattach(self):
        self.assertEqual(RESERVED_TITLES['T-04'], 'Detach not archive and same-home reattach')
        result = self.s.detach_kb('syn_org_a', 'syn_group_a_kb')
        self.assertIsNone(result['space_id'])
        self.assertEqual(result['archived'], 0)
        self.assertFalse(self.s.authorize('syn_org_a', 'syn_alice', 'syn_group_a_kb').allowed)
        with self.assertRaises(SchemaV7Error):
            self.s.attach_kb('syn_org_a', 'syn_group_a_kb', 'syn_group_b')
        self.s.attach_kb('syn_org_a', 'syn_group_a_kb', 'syn_group_a')
        self.assertTrue(self.s.authorize('syn_org_a', 'syn_alice', 'syn_group_a_kb').allowed)

    def test_t05_employee_personal_owner_boundary(self):
        self.assertEqual(RESERVED_TITLES['T-05'], 'Employee personal owner boundary')
        self.assertTrue(self.s.authorize('syn_org_a', 'syn_employee', 'syn_private_kb').allowed)
        denied = self.s.authorize('syn_org_a', 'syn_alice', 'syn_private_kb')
        self.assertFalse(denied.allowed)
        self.assertEqual(denied.layer, 'layer_2')

    def test_t06_enterprise_admin_no_private_content_shortcut(self):
        self.assertEqual(RESERVED_TITLES['T-06'], 'Enterprise admin no private-content shortcut')
        # Planting an admin grant must not open the personal space.
        self.s.grant('syn_org_a', 'syn_private', 'syn_admin', 'read', True)
        denied = self.s.authorize('syn_org_a', 'syn_admin', 'syn_private_kb')
        self.assertFalse(denied.allowed)
        self.assertEqual(denied.code, 'PERSONAL_OWNER_BOUNDARY')

    def test_t07_two_same_tenant_collaboration_groups_isolation(self):
        self.assertEqual(RESERVED_TITLES['T-07'], 'Two same-tenant collaboration groups isolation')
        self.assertTrue(self.s.authorize('syn_org_a', 'syn_alice', 'syn_group_a_kb').allowed)
        self.assertFalse(self.s.authorize('syn_org_a', 'syn_alice', 'syn_group_b_kb').allowed)
        self.assertTrue(self.s.authorize('syn_org_a', 'syn_bob', 'syn_group_b_kb').allowed)
        self.assertFalse(self.s.authorize('syn_org_a', 'syn_bob', 'syn_group_a_kb').allowed)

    def test_t08_eight_independent_action_grants(self):
        self.assertEqual(RESERVED_TITLES['T-08'], 'Eight independent action grants')
        self.assertEqual(len(OFFICIAL_ACTIONS), 8)
        for action in OFFICIAL_ACTIONS:
            self.assertTrue(self.s.authorize('syn_org_a', 'syn_alice', 'syn_group_a_kb', action=action).allowed)
        self.s.revoke('syn_org_a', 'syn_group_a', 'syn_alice', action='archive')
        for action in OFFICIAL_ACTIONS:
            allowed = self.s.authorize(
                'syn_org_a', 'syn_alice', 'syn_group_a_kb', action=action, policy_generation=2,
            ).allowed
            self.assertEqual(allowed, action != 'archive')
        self.assertFalse(self.s.authorize('syn_org_a', 'syn_alice', 'syn_group_a_kb', action='admin').allowed)

    def test_t09_explicit_deny_precedence(self):
        self.assertEqual(RESERVED_TITLES['T-09'], 'Explicit Deny precedence')
        self.s.add_deny('syn_org_a', 'user', 'syn_alice', 'kb', 'syn_group_a_kb', 'read')
        denied = self.s.authorize('syn_org_a', 'syn_alice', 'syn_group_a_kb', asset_id='syn_group_a_asset', agent_id='syn_agent')
        self.assertFalse(denied.allowed)
        self.assertEqual(denied.code, 'EXPLICIT_DENY')
        hidden = self.s.hydrate_favorites(
            'syn_org_a', 'syn_alice',
            [{'target_type': 'asset', 'target_id': 'syn_group_a_asset'}],
            agent_id='syn_agent',
        )
        self.assertEqual(hidden, [{'target_type': 'asset', 'target_id': 'syn_group_a_asset', 'state': 'unavailable'}])

    def test_t10_agent_space_ceiling(self):
        self.assertEqual(RESERVED_TITLES['T-10'], 'Agent Space ceiling')
        # Alice can read enterprise KB as a user, but the agent ceiling excludes nothing? 
        # Seed agent includes syn_enterprise. Narrow it to syn_group_a only.
        self.s.upsert_agent(
            'syn_org_a', 'syn_agent',
            allowed_space_ids=['syn_group_a'],
            allowed_kb_ids=['syn_group_a_kb', 'syn_enterprise_kb'],
            allowed_space_types=['team', 'enterprise'],
        )
        self.assertTrue(self.s.authorize('syn_org_a', 'syn_alice', 'syn_group_a_kb', agent_id='syn_agent').allowed)
        # Alice has a read grant on enterprise, but agent ceiling blocks it.
        self.assertTrue(self.s.authorize('syn_org_a', 'syn_alice', 'syn_enterprise_kb').allowed)
        ceiling = self.s.authorize('syn_org_a', 'syn_alice', 'syn_enterprise_kb', agent_id='syn_agent')
        self.assertFalse(ceiling.allowed)
        self.assertEqual(ceiling.code, 'AGENT_SPACE_CEILING')

    def test_t11_kb_fine_grained_consumption_scope(self):
        self.assertEqual(RESERVED_TITLES['T-11'], 'KB fine-grained consumption scope')
        self.s.upsert_agent(
            'syn_org_a', 'syn_agent',
            allowed_space_ids=['syn_enterprise'],
            allowed_kb_ids=['syn_enterprise_kb'],
            allowed_space_types=['enterprise'],
        )
        self.assertTrue(self.s.authorize('syn_org_a', 'syn_admin', 'syn_enterprise_kb', agent_id='syn_agent').allowed)
        denied = self.s.authorize('syn_org_a', 'syn_admin', 'syn_enterprise_kb_2', agent_id='syn_agent')
        self.assertFalse(denied.allowed)
        self.assertEqual(denied.code, 'AGENT_FINE_SCOPE_DENIED')

    def test_t12_knowledge_file_scope(self):
        self.assertEqual(RESERVED_TITLES['T-12'], 'Knowledge-file scope')
        self.s.upsert_agent(
            'syn_org_a', 'syn_agent',
            allowed_space_ids=['syn_group_a'],
            allowed_kb_ids=[],
            allowed_knowledge_file_ids=['syn_group_a_asset'],
            allowed_space_types=['team'],
        )
        self.assertTrue(self.s.authorize(
            'syn_org_a', 'syn_alice', 'syn_group_a_kb',
            asset_id='syn_group_a_asset', agent_id='syn_agent',
        ).allowed)
        self.s.create_asset('syn_org_a', 'syn_group_a_other_file', 'syn_group_a_kb', 'knowledge_file', folder_id='syn_folder')
        denied = self.s.authorize(
            'syn_org_a', 'syn_alice', 'syn_group_a_kb',
            asset_id='syn_group_a_other_file', agent_id='syn_agent',
        )
        self.assertFalse(denied.allowed)
        self.assertEqual(denied.code, 'AGENT_FINE_SCOPE_DENIED')

    def test_t13_deliverable_scope(self):
        self.assertEqual(RESERVED_TITLES['T-13'], 'Deliverable scope')
        self.s.upsert_agent(
            'syn_org_a', 'syn_agent',
            allowed_space_ids=['syn_enterprise'],
            allowed_kb_ids=[],
            allowed_deliverable_ids=['syn_external_asset'],
            allowed_space_types=['enterprise'],
        )
        self.assertTrue(self.s.authorize(
            'syn_org_a', 'syn_admin', 'syn_enterprise_kb',
            asset_id='syn_external_asset', agent_id='syn_agent',
            provider=lambda: self._external_assertion(),
        ).allowed)
        # Alice has only a generic enterprise read, but must still have current-user rights;
        # she does, via seed grant. Tighten: revoke alice enterprise read and the agent must not help.
        self.s.revoke('syn_org_a', 'syn_enterprise', 'syn_alice', action='read')
        denied = self.s.authorize(
            'syn_org_a', 'syn_alice', 'syn_enterprise_kb',
            asset_id='syn_external_asset', agent_id='syn_agent',
            provider=lambda: self._external_assertion(subject_id='syn_alice'),
            policy_generation=2,
        )
        self.assertFalse(denied.allowed)

    def test_t14_folder_scope(self):
        self.assertEqual(RESERVED_TITLES['T-14'], 'Folder scope')
        self.s.upsert_agent(
            'syn_org_a', 'syn_agent',
            allowed_space_ids=['syn_group_a'],
            allowed_folder_ids=['syn_folder'],
            allowed_space_types=['team'],
        )
        self.assertTrue(self.s.authorize(
            'syn_org_a', 'syn_alice', 'syn_group_a_kb',
            asset_id='syn_group_a_asset', agent_id='syn_agent',
        ).allowed)
        self.s.upsert_agent(
            'syn_org_a', 'syn_agent',
            allowed_space_ids=['syn_group_a'],
            allowed_folder_ids=['syn_other_folder'],
            allowed_space_types=['team'],
        )
        denied = self.s.authorize(
            'syn_org_a', 'syn_alice', 'syn_group_a_kb',
            asset_id='syn_group_a_asset', agent_id='syn_agent',
        )
        self.assertFalse(denied.allowed)
        self.assertEqual(denied.code, 'AGENT_FINE_SCOPE_DENIED')

    def test_t15_current_user_intersection_and_current_profile(self):
        self.assertEqual(RESERVED_TITLES['T-15'], 'Current User intersection and current profile')
        # Bob is not authorized on group A, even with an agent that includes group A.
        self.assertFalse(self.s.authorize(
            'syn_org_a', 'syn_bob', 'syn_group_a_kb',
            asset_id='syn_group_a_asset', agent_id='syn_agent',
        ).allowed)
        self.assertTrue(self.s.authorize(
            'syn_org_a', 'syn_alice', 'syn_group_a_kb',
            asset_id='syn_group_a_asset', agent_id='syn_agent',
            profile_generation=1,
        ).allowed)
        stale = self.s.authorize(
            'syn_org_a', 'syn_alice', 'syn_group_a_kb',
            asset_id='syn_group_a_asset', agent_id='syn_agent',
            profile_generation=2,
        )
        self.assertFalse(stale.allowed)
        self.assertEqual(stale.code, 'PROFILE_GENERATION_STALE')

    def test_t16_transactional_revocation_outbox_rollback(self):
        self.assertEqual(RESERVED_TITLES['T-16'], 'Transactional revocation/outbox rollback')
        with self.assertRaises(SchemaV7Error):
            self.s.revoke('syn_org_a', 'syn_group_a', 'syn_alice', inject_failure=True)
        self.assertTrue(self.s.authorize('syn_org_a', 'syn_alice', 'syn_group_a_kb').allowed)
        self.assertEqual(self.s.sql('SELECT count(*) FROM ks_v7_outbox WHERE tenant_id=?', ('syn_org_a',))[0][0], 0)
        generation = self.s.revoke('syn_org_a', 'syn_group_a', 'syn_alice')
        self.assertEqual(generation, 2)
        self.assertFalse(self.s.authorize('syn_org_a', 'syn_alice', 'syn_group_a_kb', policy_generation=2).allowed)
        self.assertEqual(
            self.s.sql('SELECT generation FROM ks_v7_outbox WHERE tenant_id=? AND kind=?', ('syn_org_a', 'revocation')),
            [(2,)],
        )

    def test_t17_current_policy_generation_strictness_staleness(self):
        self.assertEqual(RESERVED_TITLES['T-17'], 'Current policy generation strictness/staleness')
        self.assertTrue(self.s.authorize('syn_org_a', 'syn_alice', 'syn_group_a_kb', policy_generation=1).allowed)
        for generation in (None, True, 0, -1, 1.0, '1', 9007199254740992, 2):
            if generation is None:
                continue  # None means "do not present a generation claim"
            self.assertFalse(
                self.s.authorize('syn_org_a', 'syn_alice', 'syn_group_a_kb', policy_generation=generation).allowed
            )

    def test_t18_future_http_independent_version_compatibility(self):
        self.assertEqual(RESERVED_TITLES['T-18'], 'Future HTTP independent-version compatibility')
        self.assertFalse(EXPERIMENTAL_V3_ENABLED_DEFAULT)
        surface = CoreV7HttpSurface()
        self.assertFalse(surface.experimental_v3_enabled)
        v2 = surface.dispatch('GET', '/v2/spaces')
        self.assertEqual(v2['status'], 200)
        self.assertEqual(v2['baseline'], '9940818b962ccb186c0dfb0158de6bd9bd49057b')
        self.assertFalse(v2['mutable'])
        v7 = surface.dispatch('GET', '/v7-core/spaces')
        self.assertTrue(v7['distinct_from_v2'])
        with self.assertRaises(ProtocolError) as ctx:
            surface.redefine_v2_spaces({'new': True})
        self.assertEqual(ctx.exception.code, 'SILENT_V2_SEMANTIC_CHANGE_FORBIDDEN')
        with self.assertRaises(ProtocolError):
            surface.mount_production_http()
        with self.assertRaises(ProtocolError):
            surface.mount_v3()
        with self.assertRaises(ProtocolError):
            surface.dispatch('GET', '/v3/spaces')
        self.assertFalse(experimental_v3_enabled({'EXPERIMENTAL_V3_ENABLED': 'false'}))
        import re
        v2_src = (REPO_ROOT / 'src/knowledge_sdk/server/v2.py').read_text()
        routes = re.findall(r"\('(?:GET|POST|PUT|PATCH|DELETE)','(/[^']+)'\)", v2_src)
        if not routes:
            routes = re.findall(r"\('(?:GET|POST|PUT|PATCH|DELETE)',\s*'(/[^']+)'\)", v2_src)
        self.assertTrue(routes)
        self.assertTrue(all(path.startswith('/v2/') for path in routes))
        self.assertFalse(any(path.startswith('/v3/') for path in routes))
        self.assertIn('/v2/spaces', routes)
        self.assertEqual(CORE_V7_SPACES_PATH, '/v7-core/spaces')
        self.assertNotEqual(CORE_V7_SPACES_PATH, '/v2/spaces')

    def test_t19_future_python_candidate_protocol_compatibility(self):
        self.assertEqual(RESERVED_TITLES['T-19'], 'Future Python candidate protocol compatibility')
        self.assertTrue(validate_python_space({
            'tenant_id': 'syn_org_a', 'space_id': 'syn_group_a', 'space_type': 'team',
            'owner_id': 'syn_alice', 'status': 'active', 'policy_generation': 1,
        }))
        with self.assertRaises(ProtocolError):
            validate_python_space({
                'tenant_id': 'syn_org_a', 'space_id': 'syn_group_a', 'space_type': 'team',
                'owner_id': 'syn_alice', 'status': 'active', 'policy_generation': 1,
                'parent_space_id': 'syn_parent',
            })
        self.assertTrue(validate_python_kb({
            'tenant_id': 'syn_org_a', 'kb_id': 'syn_group_a_kb',
            'space_id': 'syn_group_a', 'home_space_id': 'syn_group_a', 'archived': 0,
        }))
        self.assertTrue(validate_python_favorite_pointer({
            'tenant_id': 'syn_org_a', 'user_id': 'syn_alice',
            'target_type': 'kb', 'target_id': 'syn_group_a_kb',
        }))
        with self.assertRaises(ProtocolError):
            validate_python_favorite_pointer({
                'tenant_id': 'syn_org_a', 'user_id': 'syn_alice',
                'target_type': 'kb', 'target_id': 'syn_group_a_kb',
                'body': 'secret',
            })
        flags = read_frozen_contract_flags(REPO_ROOT)
        self.assertEqual(flags['formal_t01_t27'], 'NOT_RUN_NOT_ACCEPTED')
        self.assertFalse(flags['schema_v7_ddl_authorized'])

    def test_t20_future_mcp_candidate_policy_compatibility(self):
        self.assertEqual(RESERVED_TITLES['T-20'], 'Future MCP candidate policy compatibility')
        policy = candidate_mcp_policy_document()
        self.assertTrue(policy['fail_closed'])
        self.assertFalse(policy['formal_acceptance'])
        self.assertFalse(evaluate_mcp_tool('text_to_sql', True, True)['allowed'])
        self.assertFalse(evaluate_mcp_tool('search', False, True)['allowed'])
        self.assertFalse(evaluate_mcp_tool('search', True, False)['allowed'])
        self.assertFalse(evaluate_mcp_tool('search', True, ['syn_group_a'], space_id='syn_group_b')['allowed'])
        self.assertTrue(evaluate_mcp_tool('search', True, ['syn_group_a'], space_id='syn_group_a')['allowed'])

    def test_t21_external_source_missing_assertion(self):
        self.assertEqual(RESERVED_TITLES['T-21'], 'External source missing assertion')
        self.assertFalse(self.s.authorize(
            'syn_org_a', 'syn_admin', 'syn_enterprise_kb', asset_id='syn_external_asset',
        ).allowed)
        self.s.sql('DELETE FROM ks_v7_external WHERE tenant_id=? AND ref_id=?', ('syn_org_a', 'syn_external'))
        denied = self.s.authorize(
            'syn_org_a', 'syn_admin', 'syn_enterprise_kb', asset_id='syn_external_asset',
            provider=lambda: self._external_assertion(),
        )
        self.assertFalse(denied.allowed)
        self.assertEqual(denied.code, 'EXTERNAL_ASSERTION_MISSING')

    def test_t22_external_expired_assertion(self):
        self.assertEqual(RESERVED_TITLES['T-22'], 'External expired assertion')
        self.s.upsert_external('syn_org_a', 'syn_external', valid_until=self.s.now() - 1, generation=1)
        denied = self.s.authorize(
            'syn_org_a', 'syn_admin', 'syn_enterprise_kb', asset_id='syn_external_asset',
            provider=lambda: self._external_assertion(valid_until=self.s.now() + 10),
        )
        self.assertFalse(denied.allowed)
        self.assertEqual(denied.code, 'EXTERNAL_EXPIRED')

    def test_t23_external_provider_outage(self):
        self.assertEqual(RESERVED_TITLES['T-23'], 'External provider outage')
        def unavailable():
            raise RuntimeError('PROVIDER_FAILURE')
        denied = self.s.authorize(
            'syn_org_a', 'syn_admin', 'syn_enterprise_kb', asset_id='syn_external_asset',
            provider=unavailable,
        )
        self.assertFalse(denied.allowed)
        self.assertEqual(denied.code, 'EXTERNAL_PROVIDER_OUTAGE')

    def test_t24_external_revocation_tombstone_cursor(self):
        self.assertEqual(RESERVED_TITLES['T-24'], 'External revocation/tombstone/cursor')
        self.assertTrue(self.s.authorize(
            'syn_org_a', 'syn_admin', 'syn_enterprise_kb', asset_id='syn_external_asset',
            provider=lambda: self._external_assertion(),
        ).allowed)
        self.s.upsert_external('syn_org_a', 'syn_external', valid_until=self.s.now() + 120, generation=2, revoked=True, tombstone=True, cursor='syn_cursor')
        denied = self.s.authorize(
            'syn_org_a', 'syn_admin', 'syn_enterprise_kb', asset_id='syn_external_asset',
            provider=lambda: self._external_assertion(generation=2),
        )
        self.assertFalse(denied.allowed)
        self.assertEqual(denied.code, 'EXTERNAL_REVOKED')
        self.assertFalse(evaluate_mcp_tool('sql', True, True)['allowed'])

    def test_t25_polymorphic_favorite_current_acl_hydration(self):
        self.assertEqual(RESERVED_TITLES['T-25'], 'Polymorphic favorite current-ACL hydration')
        with self.assertRaises(SchemaV7Error):
            self.s.add_favorite('syn_org_a', 'syn_alice', 'kb', 'syn_group_a_kb', body='secret', embedding=[0.1])
        targets = [
            {'target_type': 'kb', 'target_id': 'syn_group_a_kb'},
            {'target_type': 'asset', 'target_id': 'syn_group_a_asset'},
            {'target_type': 'kb', 'target_id': 'syn_private_kb'},
            {'target_type': 'asset', 'target_id': 'syn_private_asset'},
        ]
        result = self.s.hydrate_favorites('syn_org_a', 'syn_alice', targets)
        self.assertEqual([item['state'] for item in result], ['available', 'available', 'unavailable', 'unavailable'])
        for item in result[2:]:
            self.assertEqual(set(item), {'target_type', 'target_id', 'state'})
        self.s.revoke('syn_org_a', 'syn_group_a', 'syn_alice')
        later = self.s.hydrate_favorites('syn_org_a', 'syn_alice', targets)
        self.assertTrue(all(item['state'] == 'unavailable' for item in later))

    def test_t26_migration_rollback_drill_and_security_monotonicity(self):
        self.assertEqual(
            RESERVED_TITLES['T-26'],
            'Future reviewed migration/rollback drill and security monotonicity',
        )
        upgrade_v7(self.store, owned_nonproduction=True)
        self.assertEqual(schema_version(self.store), 7)
        with self.assertRaises(ValidationError):
            upgrade_v7(self.store)
        self.assertTrue(self.s.authorize('syn_org_a', 'syn_alice', 'syn_group_a_kb').allowed)
        self.assertEqual(self.s.rollback_schema(), 6)
        self.assertEqual(rollback_v7(self.store, owned_nonproduction=True), 6)
        self.assertEqual(schema_version(self.store), 6)
        require_v6(self.store)
        upgrade_v7(self.store, owned_nonproduction=True)
        self.s = SchemaV7(self.store)
        self.assertEqual(self.s.sql('SELECT count(*) FROM ks_v7_grant'), [(0,)])
        if self.live_postgres:
            other_sandbox, other_store, other = _make_postgres_v7()
            self.addCleanup(other_store.close)
            self.addCleanup(other_sandbox.close)
        else:
            other_store, other = _make_sqlite_v7()
            self.addCleanup(other_store.close)
        with self.assertRaises(SchemaV7Error) as ctx:
            other.restore_principal_active('syn_org_a', 'syn_alice')
        self.assertEqual(ctx.exception.code, 'SECURITY_STATE_MONOTONIC')
        with self.assertRaises(SchemaV7Error):
            other.restore_grants([])
        with self.assertRaises(SchemaV7Error):
            other.restore_policy_generation('syn_org_a', 'syn_group_a', 0)
        with self.assertRaises(SchemaV7Error):
            other.restore_share('syn_org_a', 'syn_share_private')
        stripped = postgres_v7_ddl(include_semantic_role=True).replace(
            'FORCE ROW LEVEL SECURITY', 'ENABLE ROW LEVEL SECURITY'
        )
        with self.assertRaises(DdlSemanticError):
            validate_postgres_ddl(stripped)
        bad = postgres_v7_ddl(include_semantic_role=True) + '\nALTER TABLE ks_v7_space ADD COLUMN parent_space_id TEXT;\n'
        with self.assertRaises(DdlSemanticError):
            validate_postgres_ddl(bad)

    def test_t27_personal_sharing_offboarding_approval_gating(self):
        self.assertEqual(
            RESERVED_TITLES['T-27'],
            'Personal-sharing/offboarding approval gating and full reviewed acceptance',
        )
        self.assertEqual(self.s.share_status('syn_org_a', 'syn_share_private'), 'active')
        result = self.s.resign('syn_org_a', 'syn_employee')
        self.assertEqual(result['frozen_within_seconds'], 0)
        self.assertLessEqual(result['frozen_within_seconds'], 60)
        self.assertEqual(result['isolation_until'], self.s.now() + ISOLATION_RETENTION_SECONDS)
        self.assertEqual(self.s.share_status('syn_org_a', 'syn_share_private'), 'invalidated')
        self.assertFalse(self.s.authorize('syn_org_a', 'syn_employee', 'syn_private_kb').allowed)
        # After 90 days the isolation window is expired (data still not auto-purged here).
        self.s.set_now(self.s.now() + ISOLATION_RETENTION_SECONDS)
        self.assertTrue(self.s.isolation_expired('syn_org_a', 'syn_employee'))
        with self.assertRaises(SchemaV7Error) as ctx:
            self.s.request_handover(
                'syn_org_a', 'syn_handover', 'syn_employee', 'syn_alice', include_private_body=True,
            )
        self.assertEqual(ctx.exception.code, 'PRIVATE_BODY_AUTO_INHERIT_FORBIDDEN')
        self.s.request_handover('syn_org_a', 'syn_handover', 'syn_employee', 'syn_alice')
        pending = self.s.approve_handover('syn_org_a', 'syn_handover', 'syn_approver_a')
        self.assertEqual(pending['status'], 'pending')
        with self.assertRaises(SchemaV7Error):
            self.s.approve_handover('syn_org_a', 'syn_handover', 'syn_employee')
        approved = self.s.approve_handover('syn_org_a', 'syn_handover', 'syn_approver_b')
        self.assertEqual(approved['status'], 'approved')
        self.assertTrue(approved['payload']['pointers_only'])
        self.assertFalse(approved['payload']['includes_private_body'])
        self.assertIsNone(approved['payload']['body'])
        # Report shape: always not formally accepted.
        report = build_report()
        self.assertEqual(report['scope'], SCOPE)
        self.assertIs(report['formal_t01_t27_accepted'], False)
        self.assertEqual(report['formal_t01_t27'], 'NOT_RUN_NOT_ACCEPTED')
        self.assertEqual(len(report['cases']), 27)



@unittest.skipUnless(os.environ.get('KNOWLEDGE_SDK_TEST_PG_DSN'), LIVE_PG_REASON)
class CoreV7PostgresT01T27Cases(CoreV7SqliteT01T27Cases):
    live_postgres = True

    def test_postgres_force_rls_hides_rows_without_tenant_scope(self):
        visible = self.s.sql('SELECT tenant_id FROM ks_v7_tenant WHERE tenant_id=?', ('syn_org_a',))
        self.assertEqual(visible, [('syn_org_a',)])
        hidden = self.store._execute('SELECT tenant_id FROM ks_v7_tenant')
        self.assertEqual(hidden, [])


class CoreV7CompatAndSurfaceCases(unittest.TestCase):
    def test_v6_callers_remain_compatible_after_v7_upgrade(self):
        store = SQLiteStore(':memory:')
        self.addCleanup(store.close)
        self.assertEqual(schema_version_v6(store), 5)
        from knowledge_sdk import Actor, LocalKnowledgeClient
        from knowledge_sdk.contracts.identity import IdentityPrincipal
        client = LocalKnowledgeClient(store)
        actor = Actor('owner', 'enterprise-a', org_roles=('admin',), clearance_level='internal', policy_generation='1')
        store.upsert_principal(IdentityPrincipal('enterprise-a', 'owner', org_roles=('admin',), clearance_level='internal'))
        kb = client.create_kb(actor, 'primary', 'private', kb_id='primary', space_type='personal', owner_user_id='owner')
        self.assertEqual(kb.kb_id, 'primary')
        upgrade_v6(store, owned_nonproduction=True)
        self.assertEqual(schema_version(store), 6)
        require_v6(store)
        loaded = client.get_kb(actor, 'primary')
        self.assertEqual(loaded.kb_id, 'primary')
        upgrade_v7(store, owned_nonproduction=True)
        self.assertEqual(schema_version(store), 7)
        require_v6(store)
        loaded = client.get_kb(actor, 'primary')
        self.assertEqual(loaded.kb_id, 'primary')
        listed = client.list_kbs(actor)
        self.assertEqual([item.kb_id for item in listed], ['primary'])

    def test_upgrade_v7_refuses_unowned_and_wrong_version(self):
        store = SQLiteStore(':memory:')
        self.addCleanup(store.close)
        with self.assertRaises(ConflictError):
            upgrade_v7(store, owned_nonproduction=True)
        upgrade_v6(store, owned_nonproduction=True)
        with self.assertRaises(ValidationError):
            upgrade_v7(store)

    def test_frozen_contract_flags_byte_stable(self):
        status = read_frozen_contract_flags(REPO_ROOT)
        self.assertEqual(status['formal_t01_t27'], 'NOT_RUN_NOT_ACCEPTED')
        self.assertIs(status['schema_v7_ddl_authorized'], False)
        self.assertIs(FORMAL_T01_T27_ACCEPTED, False)
        self.assertFalse(experimental_v3_enabled({}))

    def test_official_mcp_tools_have_no_text_to_sql(self):
        names = set()
        try:
            from knowledge_sdk.mcp.tools import tool_definitions
            names = {item['name'] for item in tool_definitions()}
        except Exception:
            import re
            text = (REPO_ROOT / 'src/knowledge_sdk/mcp/tools.py').read_text()
            names = set(re.findall(r"'([a-z_]+)'\s*:", text.split('_SCHEMAS=')[1].split('def tool_definitions')[0]))
        self.assertTrue(names)
        for forbidden in ('text_to_sql', 'sql', 'credential_vault', 'bypass_rls'):
            self.assertNotIn(forbidden, names)
        policy = candidate_mcp_policy_document()
        self.assertFalse(policy['formal_acceptance'])
        self.assertFalse(evaluate_mcp_tool('text_to_sql', True, True)['allowed'])

    def test_w7a2_report_contract(self):
        report = build_report()
        self.assertEqual(report['scope'], SCOPE)
        self.assertIs(report['formal_t01_t27_accepted'], False)
        self.assertEqual(report['formal_t01_t27'], 'NOT_RUN_NOT_ACCEPTED')
        self.assertFalse(report['schema_v7_prod_migration_authorized'])
        self.assertEqual(len(report['cases']), 27)
        self.assertEqual([c['id'] for c in report['cases']], ['T-%02d' % i for i in range(1, 28)])
        for case in report['cases']:
            self.assertEqual(case['result'], 'PASS')
            self.assertEqual(case['formal_status'], 'NOT_RUN_NOT_ACCEPTED')
            self.assertEqual(case['title'], RESERVED_TITLES[case['id']])
        committed = (REPO_ROOT / 'docs/acceptance/v21-wave7/W7A2_CORE_V7_T01_T27_REPORT.json').read_bytes()
        self.assertEqual(committed, report_json_bytes())


@unittest.skipUnless(
    importlib.util.find_spec('fastapi') is not None and importlib.util.find_spec('uvicorn') is not None,
    'fastapi/uvicorn not importable in this process (core python -S job); unit-suite and pytest-suite run the live /v2 path',
)
class CoreV7LiveHttpV2AndMcpCases(unittest.TestCase):
    def setUp(self):
        from contextlib import ExitStack
        import tempfile
        from knowledge_sdk import Actor, LocalKnowledgeClient
        from knowledge_sdk.contracts.identity import IdentityPrincipal
        from knowledge_sdk.server.app import create_app
        from tests.foundation.helpers import live
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        temp = self.stack.enter_context(tempfile.TemporaryDirectory())
        self.store = SQLiteStore(Path(temp) / 'v7.sqlite')
        self.stack.callback(self.store.close)
        self.client = LocalKnowledgeClient(self.store)
        self.secret = 'WAVE7-TEST-ONLY-PSEUDO-SECRET-DO-NOT-USE-REAL'
        self.issuer = 'https://gateway.example.invalid'
        for user in ('owner', 'reader'):
            self.store.upsert_principal(IdentityPrincipal('enterprise-a', user, org_roles=('admin',) if user == 'owner' else (), clearance_level='internal'))
        self.owner = Actor('owner', 'enterprise-a', org_roles=('admin',), clearance_level='internal', policy_generation='1')
        self.client.create_kb(self.owner, 'primary', 'private', kb_id='primary', space_type='personal', owner_user_id='owner')
        upgrade_v6(self.store, owned_nonproduction=True)
        upgrade_v7(self.store, owned_nonproduction=True)
        self.assertEqual(schema_version(self.store), 7)
        require_v6(self.store)
        self.app = create_app(
            self.client, auth_secret=self.secret, enable_ui=False,
            enable_v2=True, v2_issuer=self.issuer, enable_mcp=True,
        )
        self.base = self.stack.enter_context(live(self.app))

    def _wire(self, method, path, payload=None, expected=200):
        import json
        from urllib.request import Request, urlopen
        from urllib.error import HTTPError
        from knowledge_sdk.server.v2_auth import signed_v2_headers
        from tests.wave2.test_runtime import context
        ctx = context()
        raw = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode() if payload is not None else b''
        signed = signed_v2_headers(ctx, self.secret, method, path, raw)
        signed.update({'Content-Type': 'application/json'})
        request = Request(self.base + path, data=raw if method == 'POST' else None, method=method, headers=signed)
        try:
            response = urlopen(request, timeout=15)
        except HTTPError as exc:
            response = exc
        with response:
            status = response.status
            data = response.read()
        parsed = json.loads(data) if data else None
        self.assertEqual(status, expected, (path, status, parsed))
        return parsed

    def test_live_v2_spaces_on_schema_v7_store(self):
        listed = self._wire('GET', '/v2/spaces')
        self.assertIsInstance(listed, list)
        self.assertTrue(any(item.get('kb_id') == 'primary' for item in listed))
        from urllib.request import Request, urlopen
        from urllib.error import HTTPError
        try:
            urlopen(Request(self.base + '/v3/spaces', method='GET'), timeout=15)
            self.fail('/v3 must not be mounted')
        except HTTPError as exc:
            self.assertIn(exc.status, (404, 401, 403, 405))

    def test_live_mcp_tools_list(self):
        from knowledge_sdk.mcp.tools import tool_definitions
        names = [item['name'] for item in tool_definitions()]
        self.assertEqual(
            set(names),
            {'search_evidence', 'verify_citation', 'get_evidence_pack', 'report_evidence_issue'},
        )
        self.assertFalse(evaluate_mcp_tool('text_to_sql', True, True)['allowed'])
