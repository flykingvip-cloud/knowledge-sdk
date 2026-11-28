"""Automated sandbox suite covering reserved T-01–T-27 IDs.

Official reserved titles are taken from FORMAL_TEST_PLAN_NOT_RUN.md.
Every case exercises the disposable SQLite Schema v7 engine and the
PostgreSQL DDL / FORCE RLS semantic checker. formal_t01_t27_accepted
remains false; these tests are not formal acceptance.
"""
from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path

from sandbox.v21_schema_v7.constants import (
    ISOLATION_RETENTION_SECONDS,
    OFFICIAL_ACTIONS,
    RESERVED_TITLES,
)
from sandbox.v21_schema_v7.engine import SandboxError, SandboxV7
from sandbox.v21_schema_v7.pg_ddl_semantics import (
    DdlSemanticError,
    candidate_postgres_ddl,
    validate_official_candidate,
    validate_postgres_ddl,
)
from sandbox.v21_schema_v7.protocol import (
    EXPERIMENTAL_V3_ENABLED_DEFAULT,
    ProtocolError,
    SandboxHttpSurface,
    candidate_mcp_policy_document,
    evaluate_mcp_tool,
    read_frozen_contract_flags,
    validate_python_favorite_pointer,
    validate_python_kb,
    validate_python_space,
)
from sandbox.v21_schema_v7.report import SCOPE, build_report
from sandbox.v21_schema_v7.sqlite_sandbox import (
    DisposableSQLite,
    SchemaV6StoreRefused,
    migrate,
    rollback,
    sandbox_version,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


class T01T27SandboxCases(unittest.TestCase):
    def setUp(self):
        self.pg = validate_official_candidate()
        self.assertTrue(self.pg['ok'])
        self.assertFalse(self.pg['live_connection'])
        self.s = SandboxV7()
        self.addCleanup(self.s.close)
        self.s.seed_standard()

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
        columns = [row[1] for row in self.s.sql('PRAGMA table_info(sv7_space)')]
        self.assertNotIn('parent_space_id', columns)
        bad = candidate_postgres_ddl() + '\nALTER TABLE sv7_space ADD COLUMN parent_space_id TEXT;\n'
        with self.assertRaises(DdlSemanticError):
            validate_postgres_ddl(bad)

    def test_t03_same_org_composite_kb_binding(self):
        self.assertEqual(RESERVED_TITLES['T-03'], 'Same-org composite KB binding')
        kbs = self.s.sql(
            "SELECT kb_id FROM sv7_kb WHERE tenant_id=? AND home_space_id=?",
            ('syn_org_a', 'syn_enterprise'),
        )
        self.assertGreaterEqual(len(kbs), 2)
        # Cross-tenant home is refused.
        with self.assertRaises(Exception):
            self.s.sql(
                'INSERT INTO sv7_kb(tenant_id, kb_id, space_id, home_space_id, archived) VALUES(?,?,?,?,0)',
                ('syn_org_a', 'syn_cross', 'syn_group_a', 'syn_group_a_from_b'),
            )

    def test_t04_detach_not_archive_and_same_home_reattach(self):
        self.assertEqual(RESERVED_TITLES['T-04'], 'Detach not archive and same-home reattach')
        result = self.s.detach_kb('syn_org_a', 'syn_group_a_kb')
        self.assertIsNone(result['space_id'])
        self.assertEqual(result['archived'], 0)
        self.assertFalse(self.s.authorize('syn_org_a', 'syn_alice', 'syn_group_a_kb').allowed)
        with self.assertRaises(SandboxError):
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
        with self.assertRaises(SandboxError):
            self.s.revoke('syn_org_a', 'syn_group_a', 'syn_alice', inject_failure=True)
        self.assertTrue(self.s.authorize('syn_org_a', 'syn_alice', 'syn_group_a_kb').allowed)
        self.assertEqual(self.s.sql('SELECT count(*) FROM sv7_outbox WHERE tenant_id=?', ('syn_org_a',))[0][0], 0)
        generation = self.s.revoke('syn_org_a', 'syn_group_a', 'syn_alice')
        self.assertEqual(generation, 2)
        self.assertFalse(self.s.authorize('syn_org_a', 'syn_alice', 'syn_group_a_kb', policy_generation=2).allowed)
        self.assertEqual(
            self.s.sql('SELECT generation FROM sv7_outbox WHERE tenant_id=? AND kind=?', ('syn_org_a', 'revocation')),
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
        surface = SandboxHttpSurface()
        self.assertFalse(surface.experimental_v3_enabled)
        v2 = surface.dispatch('GET', '/v2/spaces')
        self.assertEqual(v2['status'], 200)
        self.assertEqual(v2['baseline'], '9940818b962ccb186c0dfb0158de6bd9bd49057b')
        self.assertFalse(v2['mutable'])
        v7 = surface.dispatch('GET', '/v7-sandbox/spaces')
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
        self.s.sql('DELETE FROM sv7_external WHERE tenant_id=? AND ref_id=?', ('syn_org_a', 'syn_external'))
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
        with self.assertRaises(SandboxError):
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
        # Idempotent migrate on an already-migrated disposable DB.
        from sandbox.v21_schema_v7.sqlite_sandbox import migrate as remigrate
        self.assertEqual(remigrate(self.s.conn), 7)
        self.assertEqual(sandbox_version(self.s.conn), 7)
        # Refuse Schema v6 stores.
        v6 = sqlite3.connect(':memory:')
        self.addCleanup(v6.close)
        v6.execute('CREATE TABLE schema_migrations(version INTEGER)')
        v6.execute('INSERT INTO schema_migrations VALUES(6)')
        with self.assertRaises(SchemaV6StoreRefused):
            migrate(v6)
        # Rollback is idempotent and does not restore grants.
        self.assertTrue(self.s.authorize('syn_org_a', 'syn_alice', 'syn_group_a_kb').allowed)
        self.assertIsNone(self.s.rollback_schema())
        self.assertIsNone(self.s.rollback_schema())
        # Recreate empty schema: previous grants must not come back.
        remigrate(self.s.conn)
        self.assertEqual(
            self.s.sql("SELECT count(*) FROM sv7_grant"),
            [(0,)],
        )
        with self.assertRaises(SandboxError) as ctx:
            # new engine methods still refuse restore APIs
            other = SandboxV7()
            self.addCleanup(other.close)
            other.seed_standard()
            other.restore_principal_active('syn_org_a', 'syn_alice')
        self.assertEqual(ctx.exception.code, 'SECURITY_STATE_MONOTONIC')
        other = SandboxV7()
        self.addCleanup(other.close)
        other.seed_standard()
        with self.assertRaises(SandboxError):
            other.restore_grants([])
        with self.assertRaises(SandboxError):
            other.restore_policy_generation('syn_org_a', 'syn_group_a', 0)
        with self.assertRaises(SandboxError):
            other.restore_share('syn_org_a', 'syn_share_private')
        # Throwaway file migrate/rollback path.
        with DisposableSQLite.throwaway_file() as tmp:
            self.assertEqual(sandbox_version(tmp.conn), 7)
            rollback(tmp.conn)
            self.assertIsNone(sandbox_version(tmp.conn))
        # Official PG DDL still validates (already in setUp) and negative FORCE miss fails.
        stripped = candidate_postgres_ddl().replace('FORCE ROW LEVEL SECURITY', 'ENABLE ROW LEVEL SECURITY')
        with self.assertRaises(DdlSemanticError):
            validate_postgres_ddl(stripped)

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
        with self.assertRaises(SandboxError) as ctx:
            self.s.request_handover(
                'syn_org_a', 'syn_handover', 'syn_employee', 'syn_alice', include_private_body=True,
            )
        self.assertEqual(ctx.exception.code, 'PRIVATE_BODY_AUTO_INHERIT_FORBIDDEN')
        self.s.request_handover('syn_org_a', 'syn_handover', 'syn_employee', 'syn_alice')
        pending = self.s.approve_handover('syn_org_a', 'syn_handover', 'syn_approver_a')
        self.assertEqual(pending['status'], 'pending')
        with self.assertRaises(SandboxError):
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


class ReportContractCases(unittest.TestCase):
    def test_reserved_titles_cover_t01_t27(self):
        self.assertEqual(list(RESERVED_TITLES), ['T-%02d' % i for i in range(1, 28)])
        report = build_report()
        self.assertIs(report['formal_t01_t27_accepted'], False)
        self.assertEqual(report['scope'], 'SANDBOX_DUAL_ENGINE_CANDIDATE')
        self.assertFalse(report['schema_v7_prod_migration_authorized'])
        self.assertFalse(report['engines']['postgres_live_connection'])
        self.assertTrue(report['engines']['sqlite_executable'])
        self.assertTrue(report['engines']['postgres_ddl_force_rls_semantic_validation'])
        from sandbox.v21_schema_v7.report import report_json_bytes
        committed = (REPO_ROOT / 'docs/acceptance/v21-wave6/W6A2_SANDBOX_T01_T27_REPORT.json').read_bytes()
        self.assertEqual(committed, report_json_bytes())
