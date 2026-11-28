"""Additional Schema v7 sandbox cases (SPACE-C03, department ban, layers).

Discovered by *cases.py. These are not formal T-01–T-27 acceptance.
"""
from __future__ import annotations

import sqlite3
import unittest

from sandbox.v21_schema_v7.constants import FIVE_LAYERS, LAYER_IDS, OFFICIAL_ACTIONS
from sandbox.v21_schema_v7.engine import SandboxError, SandboxV7
from sandbox.v21_schema_v7.pg_ddl_semantics import DdlSemanticError, candidate_postgres_ddl, validate_postgres_ddl
from sandbox.v21_schema_v7.sqlite_sandbox import SchemaV6StoreRefused, migrate


class SchemaV7SandboxCases(unittest.TestCase):
    def setUp(self):
        self.s = SandboxV7()
        self.addCleanup(self.s.close)
        self.s.seed_standard()

    def test_official_five_layers_are_exactly_layer_0_to_4(self):
        self.assertEqual(len(FIVE_LAYERS), 5)
        self.assertEqual(LAYER_IDS, ('layer_0', 'layer_1', 'layer_2', 'layer_3', 'layer_4'))
        self.assertIn('Tenant + PG FORCE RLS', FIVE_LAYERS[0]['name'])
        self.assertIn('Identity & Revocation', FIVE_LAYERS[1]['name'])
        self.assertIn('Space Gate', FIVE_LAYERS[2]['name'])
        self.assertIn('KB & Document Gate', FIVE_LAYERS[3]['name'])
        self.assertIn('User ∩ Agent', FIVE_LAYERS[4]['name'])
        for layer in FIVE_LAYERS:
            self.assertFalse(layer['overridable'])

    def test_space_c03_one_org_team_one_team_space(self):
        with self.assertRaises(SandboxError) as ctx:
            self.s.bind_org_team('syn_org_a', 'syn_org_team_a', 'syn_group_b')
        self.assertEqual(ctx.exception.code, 'ORG_TEAM_ALREADY_BOUND')
        with self.assertRaises(SandboxError) as ctx:
            self.s.bind_org_team('syn_org_a', 'syn_org_team_extra', 'syn_group_a')
        self.assertEqual(ctx.exception.code, 'TEAM_SPACE_ALREADY_BOUND')
        with self.assertRaises(SandboxError):
            self.s.bind_org_team('syn_org_a', 'syn_org_team_ent', 'syn_enterprise')

    def test_department_auto_mapping_forbidden(self):
        with self.assertRaises(SandboxError) as ctx:
            self.s.map_department('syn_org_a', 'syn_dept_sales', 'syn_group_a')
        self.assertEqual(ctx.exception.code, 'DEPARTMENT_AUTO_MAPPING_FORBIDDEN')
        with self.assertRaises(SandboxError):
            self.s.bind_org_team('syn_org_a', 'dept:syn_sales', 'syn_group_b')
        with self.assertRaises(SandboxError):
            self.s.bind_org_team('syn_org_a', 'syn_department_ops', 'syn_group_b')

    def test_email_cannot_be_permanent_primary_key(self):
        with self.assertRaises(SandboxError) as ctx:
            self.s.create_principal('syn_org_a', 'syn_user@example.com')
        self.assertEqual(ctx.exception.code, 'EMAIL_PRIMARY_KEY_FORBIDDEN')
        denied = self.s.authorize('syn_org_a', 'syn_alice', 'syn_group_a_kb', email='syn_alice@example.com')
        self.assertFalse(denied.allowed)
        self.assertEqual(denied.layer, 'layer_1')

    def test_frozen_and_archived_spaces_fail_closed(self):
        for status, code in (('frozen', 'SPACE_FROZEN'), ('archived', 'SPACE_NOT_ACTIVE'), ('pending_purge', 'SPACE_NOT_ACTIVE')):
            self.s.set_space_status('syn_org_a', 'syn_group_a', status)
            denied = self.s.authorize('syn_org_a', 'syn_alice', 'syn_group_a_kb')
            self.assertFalse(denied.allowed)
            self.assertEqual(denied.code, code)
        self.s.set_space_status('syn_org_a', 'syn_group_a', 'active')

    def test_redaction_failure_fail_closed(self):
        denied = self.s.authorize(
            'syn_org_a', 'syn_alice', 'syn_group_a_kb',
            agent_id='syn_agent', redaction_ok=False,
        )
        self.assertFalse(denied.allowed)
        self.assertEqual(denied.code, 'REDACTION_FAILED')
        self.assertEqual(denied.layer, 'layer_4')

    def test_asset_and_kb_reject_body_fields(self):
        with self.assertRaises(SandboxError) as ctx:
            self.s.create_asset(
                'syn_org_a', 'syn_body_asset', 'syn_group_a_kb',
                body_text='secret', chunk='x', embedding=[1], evidence='e',
            )
        self.assertEqual(ctx.exception.code, 'ASSET_BODY_FORBIDDEN')

    def test_refuse_production_v6_like_tables(self):
        conn = sqlite3.connect(':memory:')
        self.addCleanup(conn.close)
        conn.execute('CREATE TABLE ingestion_jobs(id TEXT)')
        with self.assertRaises(SchemaV6StoreRefused):
            migrate(conn)

    def test_pg_ddl_rejects_missing_with_check_and_bypassrls(self):
        ddl = candidate_postgres_ddl()
        broken = ddl.replace('WITH CHECK (tenant_id = current_setting(\'app.current_org_id\', true))', '')
        with self.assertRaises(DdlSemanticError):
            validate_postgres_ddl(broken)
        bypass = ddl.replace(
            'CREATE ROLE sv7_sandbox_app_role LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;',
            'CREATE ROLE sv7_sandbox_app_role LOGIN SUPERUSER BYPASSRLS;',
        )
        with self.assertRaises(DdlSemanticError):
            validate_postgres_ddl(bypass)

    def test_official_actions_are_the_space_c05_eight(self):
        self.assertEqual(OFFICIAL_ACTIONS, (
            'read', 'upload', 'update', 'delete',
            'manage_members', 'manage_permissions', 'archive', 'transfer_ownership',
        ))
