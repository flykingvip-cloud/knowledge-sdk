"""T-01..T-27 sandbox dry-run cases. DRY_RUN_SANDBOX_NOT_FORMAL_ACCEPTANCE.

These in-process loopback tests exercise Wave-V21 sandbox analogues of the
reserved T-01..T-27 identifiers. They do not run SQLite / PostgreSQL FORCE
RLS / mounted HTTP / MCP formal surfaces and must not be reported as formal
acceptance. contracts/v21-reuse-v1/status.json formal_t01_t27 stays
NOT_RUN_NOT_ACCEPTED.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from knowledge_sdk.exceptions import ConflictError, ValidationError
from sandbox.v21_reuse_v1.adapters import AdapterError, ControlledDataBridgeClient
from sandbox.v21_reuse_v1.ikc import IKCSandbox
from sandbox.v21_reuse_v1.loopback_service import V21LoopbackService
from sandbox.v21_reuse_v1.resources import KnowledgeResource, DataCapabilityRef, ResourceCapabilityBinding, BoundaryError, validate_distinct
from sandbox.v21_reuse_v1.retrieval_plan import KnowledgeRetrievalPlan
from sandbox.v21_reuse_v1.revocation import CHANNELS

DRY_RUN_SANDBOX_NOT_FORMAL_ACCEPTANCE = True
FORMAL_T01_T27 = 'NOT_RUN_NOT_ACCEPTED'
ROOT = Path(__file__).resolve().parents[2]
STATUS_PATH = ROOT / 'contracts' / 'v21-reuse-v1' / 'status.json'


class DryRunBannerCases(unittest.TestCase):
    def test_explicit_dry_run_banner_and_unflipped_status(self):
        self.assertTrue(DRY_RUN_SANDBOX_NOT_FORMAL_ACCEPTANCE)
        self.assertEqual(FORMAL_T01_T27, 'NOT_RUN_NOT_ACCEPTED')
        status = json.loads(STATUS_PATH.read_text())
        self.assertEqual(status['formal_t01_t27'], 'NOT_RUN_NOT_ACCEPTED')
        self.assertIs(status['schema_v7_ddl_authorized'], False)
        self.assertIs(status['mounted_v3_runtime'], False)


class T01T27SandboxDryRunCases(unittest.TestCase):
    """Loopback / sandbox dry-run of the official required chaos paths.

    Labels are reserved T-IDs for tracking only. DRY_RUN_SANDBOX_NOT_FORMAL_ACCEPTANCE.
    """

    def setUp(self):
        self.service = V21LoopbackService(environ={})
        self.assertFalse(self.service.experimental_v3_enabled())
        self.assertFalse(self.service.production_v3_mounted())

    def _accepted_high_risk_intake(self, key):
        intake = self.service.submit_intake('syn_org', key, dict(source_kind='upload', compliance_class='high_risk'))
        return self.service.accept_intake('syn_org', intake)

    def _publish_high_risk(self, intake_key, prod_key, policy_generation=2):
        intake = self._accepted_high_risk_intake(intake_key)
        job = self.service.submit_production('syn_org', prod_key, dict(
            intake_job_id=intake.job_id, pipeline_id='pipe', pipeline_version='1', checksum='abc',
            compliance_class='high_risk', policy_generation=policy_generation,
        ))
        job = self.service.advance_production_to_approval('syn_org', job)
        return self.service.publish_blue_green('syn_org', job, policy_generation=policy_generation, approved=True)

    def test_t16_high_risk_blue_green_rollback_and_partial_available_ban(self):
        first = self._publish_high_risk('idem-dry-intake-a', 'idem-dry-prod-a', 2)
        second = self._publish_high_risk('idem-dry-intake-b', 'idem-dry-prod-b', 3)
        self.assertEqual(self.service.ikc.active_published_production_id, second.job_id)
        self.assertEqual(first.visibility, 'published')
        self.assertEqual(second.visibility, 'published')
        with self.assertRaises(ValidationError) as partial:
            self.service.ikc.submit_production('syn_org', 'idem-dry-partial', dict(
                intake_job_id=self._accepted_high_risk_intake('idem-dry-intake-partial').job_id,
                pipeline_id='pipe', pipeline_version='1', checksum='abc',
                compliance_class='high_risk', partial_available=True,
            ))
        self.assertEqual(str(partial.exception), 'PARTIAL_PUBLICATION_FORBIDDEN')
        restored = self.service.rollback_blue_green('syn_org', policy_generation=3, to_production_id=first.job_id, approved=True)
        self.assertEqual(restored.job_id, first.job_id)
        self.assertEqual(self.service.ikc.active_published_production_id, first.job_id)
        self.assertEqual(self.service.ikc.get_production('syn_org', first.job_id).visibility, 'published')
        self.assertEqual(self.service.ikc.get_production('syn_org', second.job_id).visibility, 'published')
        self.assertTrue(any(item[0] == 'blue_green_rollback' and item[2] == first.job_id for item in self.service.ikc.outbox))

    def test_t16_rollback_fails_closed_without_prior_or_approval(self):
        only = self._publish_high_risk('idem-dry-intake-solo', 'idem-dry-prod-solo', 4)
        with self.assertRaises(AdapterError) as no_target:
            self.service.rollback_blue_green('syn_org', policy_generation=4, approved=True)
        self.assertEqual(no_target.exception.code, 'NO_ROLLBACK_TARGET')
        second = self._publish_high_risk('idem-dry-intake-solo-2', 'idem-dry-prod-solo-2', 5)
        self.assertEqual(self.service.ikc.active_published_production_id, second.job_id)
        with self.assertRaises(AdapterError) as unapproved:
            self.service.rollback_blue_green('syn_org', policy_generation=5, to_production_id=only.job_id, approved=False)
        self.assertEqual(unapproved.exception.code, 'APPROVAL_REQUIRED')
        self.assertEqual(self.service.ikc.active_published_production_id, second.job_id)

    def test_t27_ksg_unapproved_publish_intercept(self):
        intake = self._accepted_high_risk_intake('idem-dry-intake-ksg')
        job = self.service.submit_production('syn_org', 'idem-dry-prod-ksg', dict(
            intake_job_id=intake.job_id, pipeline_id='pipe', pipeline_version='1', checksum='abc',
            compliance_class='high_risk', policy_generation=2,
        ))
        job = self.service.advance_production_to_approval('syn_org', job)
        with self.assertRaises(AdapterError) as ctx:
            self.service.publish_blue_green('syn_org', job, policy_generation=2, approved=False)
        self.assertEqual(ctx.exception.code, 'APPROVAL_REQUIRED')
        self.assertIsNone(self.service.ikc.active_published_production_id)
        self.assertEqual(self.service.ikc.get_production('syn_org', job.job_id).status, 'awaiting_approval')
        self.assertEqual(self.service.ikc.get_production('syn_org', job.job_id).visibility, 'hidden')

    def test_t16_four_channel_partial_revocation_purged_false(self):
        blocked = self.service.revoke(
            'syn_org', 'syn_mem_dry_1', 4, 'syn_task_dry_partial',
            failures={'vector_fts_index': 'failed'},
        )
        self.assertFalse(blocked['purged'])
        self.assertTrue(blocked.get('accepted'))
        self.assertEqual([item['channel'] for item in blocked['channels']], list(CHANNELS))
        self.assertEqual(blocked['channels'][1]['status'], 'failed')
        raw = dict(blocked)
        raw.pop('accepted', None)
        self.assertTrue(self.service.revocation.verify(raw))
        timeout = self.service.revoke(
            'syn_org', 'syn_mem_dry_2', 4, 'syn_task_dry_timeout',
            failures={'agent_history_cogniweave': 'timeout'},
        )
        self.assertFalse(timeout['purged'])
        self.assertEqual(timeout['channels'][3]['status'], 'timeout')

    def test_t09_retrieval_plan_dual_view_zero_leak(self):
        plan = self.service.retrieval_plan(
            'syn_org', 8, authorized=['syn_ok'],
            excluded=[dict(resource_id='syn_secret_doc', permission_denied='ACL_DENY')],
        )
        redacted = self.service.render_plan(plan, 'end_user')
        agent = self.service.render_plan(plan, 'agent')
        for view in (redacted, agent):
            self.assertEqual(view['redacted_unauthorized_count'], 1)
            dumped = json.dumps(view)
            self.assertNotIn('syn_secret_doc', dumped)
            self.assertNotIn('ACL_DENY', dumped)
            self.assertNotIn('resources_excluded', view)
        audit = self.service.render_plan(plan, 'audit')
        self.assertEqual(audit['resources_excluded'][0]['resource_id'], 'syn_secret_doc')
        self.assertEqual(audit['resources_excluded'][0]['permission_denied'], 'ACL_DENY')

    def test_t24_controlled_data_bridge_tombstone_and_text_to_sql_denied(self):
        client = ControlledDataBridgeClient()
        mask = dict(receipt_id='syn_mask_1', profile='standard', hash_algorithm='sha256', receipt_hash='a' * 64)
        mode_a = dict(
            mode='A', tenant_id='syn_org', policy_generation=3, freshness_ts='2026-11-27T00:00:00Z',
            masking_receipt=mask, tombstone=dict(active=False, revoked_at=None),
            user_delegation_handle='deleg:user_token_slot', query_kind='object_get',
        )
        with self.assertRaises(AdapterError) as tomb:
            client.execute(dict(mode_a, tombstone=dict(active=True, revoked_at='2026-11-27T00:00:00Z')))
        self.assertEqual(tomb.exception.code, 'UNAUTHORIZED')
        with self.assertRaises(AdapterError) as sql:
            client.execute(mode_a, query=dict(sql='SELECT * FROM t'))
        self.assertEqual(sql.exception.code, 'TEXT_TO_SQL_FORBIDDEN')
        with self.assertRaises(AdapterError) as kind:
            client.execute(dict(mode_a, query_kind='text_to_sql'))
        self.assertEqual(kind.exception.code, 'TEXT_TO_SQL_FORBIDDEN')

    def test_t17_stale_policy_generation_fail_closed(self):
        decision = self.service.ksg.validate(
            'publish_release',
            dict(
                policy_generation=2, current_policy_generation=9,
                compliance_class='high_risk', whole_document_atomic_publication=True, approved=True,
            ),
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason_code, 'POLICY_GENERATION_STALE')

    def test_t01_cross_tenant_binding_rejected(self):
        resource = KnowledgeResource('syn_org', 'syn_doc', 'document', 'syn label')
        other = DataCapabilityRef('syn_other', 'syn_cap', 'structured_select', 'svc:warehouse')
        binding = ResourceCapabilityBinding('syn_org', 'syn_doc', 'syn_cap', 3)
        with self.assertRaises(BoundaryError):
            validate_distinct(resource, other, binding)


class IsolatedIkcRollbackCases(unittest.TestCase):
    def test_direct_ikc_rollback_is_pointer_only(self):
        ikc = IKCSandbox()
        intake = ikc.submit_intake('syn_org', 'idem-ikc-a', dict(source_kind='upload', compliance_class='high_risk'))
        intake = ikc.transition_intake('syn_org', intake.job_id, 'validating', expected_revision=intake.revision)
        intake = ikc.transition_intake('syn_org', intake.job_id, 'accepted', expected_revision=intake.revision)
        first = ikc.submit_production('syn_org', 'prod-a', dict(
            intake_job_id=intake.job_id, pipeline_id='pipe', pipeline_version='1', checksum='a',
            compliance_class='high_risk',
        ))
        for state in ('parsing', 'chunking', 'indexing', 'awaiting_approval'):
            first = ikc.transition_production('syn_org', first.job_id, state, expected_revision=first.revision)
        first = ikc.publish_blue_green('syn_org', first.job_id, expected_revision=first.revision)
        intake_b = ikc.submit_intake('syn_org', 'idem-ikc-b', dict(source_kind='upload', compliance_class='high_risk'))
        intake_b = ikc.transition_intake('syn_org', intake_b.job_id, 'validating', expected_revision=intake_b.revision)
        intake_b = ikc.transition_intake('syn_org', intake_b.job_id, 'accepted', expected_revision=intake_b.revision)
        second = ikc.submit_production('syn_org', 'prod-b', dict(
            intake_job_id=intake_b.job_id, pipeline_id='pipe', pipeline_version='1', checksum='b',
            compliance_class='high_risk',
        ))
        for state in ('parsing', 'chunking', 'indexing', 'awaiting_approval'):
            second = ikc.transition_production('syn_org', second.job_id, state, expected_revision=second.revision)
        second = ikc.publish_blue_green('syn_org', second.job_id, expected_revision=second.revision)
        restored = ikc.rollback_blue_green('syn_org', to_production_id=first.job_id, expected_current=second.job_id)
        self.assertEqual(restored.job_id, first.job_id)
        self.assertEqual(ikc.active_published_production_id, first.job_id)
        with self.assertRaises(ConflictError) as stale:
            ikc.rollback_blue_green('syn_org', to_production_id=second.job_id, expected_current=second.job_id)
        self.assertEqual(str(stale.exception), 'STALE_BLUE_GREEN_POINTER')


if __name__ == '__main__':
    unittest.main()
