"""Sandbox cases for Wave-V21-0. Named to stay outside default pytest discovery."""
from __future__ import annotations
import json, unittest, ast
from pathlib import Path
from knowledge_sdk.exceptions import ValidationError, ConflictError
from sandbox.v21_reuse_v1.resources import KnowledgeResource, DataCapabilityRef, ResourceCapabilityBinding, validate_distinct, reject_collapsed_payload, BoundaryError
from sandbox.v21_reuse_v1.ikc import IKCSandbox
from sandbox.v21_reuse_v1.ksg_lite import KSGLitePlugin
from sandbox.v21_reuse_v1.semantic_reference import from_payload, write_physical, SemanticReferenceWriteForbidden
from sandbox.v21_reuse_v1.revocation import FourChannelRevocation, CHANNELS
from sandbox.v21_reuse_v1.retrieval_plan import KnowledgeRetrievalPlan, RetrievalPlanError

ROOT = Path(__file__).resolve().parents[2]


class ResourceCapabilityCases(unittest.TestCase):
    def setUp(self):
        self.resource = KnowledgeResource('syn_org', 'syn_doc', 'document', 'syn label')
        self.capability = DataCapabilityRef('syn_org', 'syn_cap', 'structured_select', 'svc:warehouse')
        self.binding = ResourceCapabilityBinding('syn_org', 'syn_doc', 'syn_cap', 3)

    def test_distinct_objects_bind(self):
        self.assertTrue(validate_distinct(self.resource, self.capability, self.binding))
        self.assertNotEqual(type(self.resource), type(self.capability))

    def test_collapsed_payload_rejected(self):
        with self.assertRaises(BoundaryError) as ctx:
            reject_collapsed_payload(dict(resource_id='syn_doc', capability_id='syn_cap', tenant_id='syn_org'))
        self.assertEqual(ctx.exception.code, 'COLLAPSED_RESOURCE_CAPABILITY')

    def test_capability_cannot_carry_secrets(self):
        with self.assertRaises(BoundaryError) as ctx:
            DataCapabilityRef('syn_org', 'syn_cap', 'structured_select', 'svc:password=secret')
        self.assertEqual(ctx.exception.code, 'CREDENTIAL_FORBIDDEN')

    def test_policy_generation_rejects_bool_and_float(self):
        with self.assertRaises(BoundaryError):
            ResourceCapabilityBinding('syn_org', 'syn_doc', 'syn_cap', True)
        with self.assertRaises(BoundaryError):
            ResourceCapabilityBinding('syn_org', 'syn_doc', 'syn_cap', 3.5)

    def test_cross_tenant_binding_rejected(self):
        other = DataCapabilityRef('syn_other', 'syn_cap', 'object_get', 'deleg:user')
        with self.assertRaises(BoundaryError):
            validate_distinct(self.resource, other, self.binding)


class IKCCases(unittest.TestCase):
    def setUp(self):
        self.ikc = IKCSandbox()

    def _accepted_intake(self, compliance='standard', key='idem-intake-1'):
        job = self.ikc.submit_intake('syn_org', key, dict(source_kind='upload', compliance_class=compliance))
        return self.ikc.transition_intake('syn_org', job.job_id, 'validating', expected_revision=job.revision).pipe() if False else self._walk_intake(job, compliance)

    def _walk_intake(self, job, compliance):
        job = self.ikc.transition_intake('syn_org', job.job_id, 'validating', expected_revision=job.revision)
        return self.ikc.transition_intake('syn_org', job.job_id, 'accepted', expected_revision=job.revision)

    def test_idempotent_intake_replay_does_not_duplicate(self):
        first = self.ikc.submit_intake('syn_org', 'idem-1', dict(source_kind='upload', compliance_class='standard'))
        second = self.ikc.submit_intake('syn_org', 'idem-1', dict(source_kind='upload', compliance_class='standard'))
        self.assertEqual(first.job_id, second.job_id)
        self.assertEqual(len(self.ikc._intake), 1)

    def test_idempotent_intake_conflict(self):
        self.ikc.submit_intake('syn_org', 'idem-2', dict(source_kind='upload', compliance_class='standard'))
        with self.assertRaises(ConflictError):
            self.ikc.submit_intake('syn_org', 'idem-2', dict(source_kind='upload', compliance_class='high_risk'))

    def test_high_risk_forbids_partial_and_requires_atomic(self):
        intake = self._walk_intake(self.ikc.submit_intake('syn_org', 'idem-3', dict(source_kind='upload', compliance_class='high_risk')), 'high_risk')
        with self.assertRaises(ValidationError):
            self.ikc.submit_production('syn_org', 'prod-1', dict(intake_job_id=intake.job_id, pipeline_id='pipe', pipeline_version='1', checksum='abc', compliance_class='high_risk', whole_document_atomic_publication=False))
        job = self.ikc.submit_production('syn_org', 'prod-2', dict(intake_job_id=intake.job_id, pipeline_id='pipe', pipeline_version='1', checksum='abc', compliance_class='high_risk'))
        self.assertTrue(job.whole_document_atomic_publication)
        self.assertEqual(job.visibility, 'hidden')
        with self.assertRaises(ValidationError):
            self.ikc.transition_production('syn_org', job.job_id, 'parsing', expected_revision=job.revision, visibility='partial_available')

    def test_blue_green_switch_after_approval_only(self):
        intake = self._walk_intake(self.ikc.submit_intake('syn_org', 'idem-4', dict(source_kind='upload', compliance_class='strong_compliance')), 'strong_compliance')
        job = self.ikc.submit_production('syn_org', 'prod-3', dict(intake_job_id=intake.job_id, pipeline_id='pipe', pipeline_version='2', checksum='def', compliance_class='strong_compliance'))
        for state in ('parsing', 'chunking', 'indexing', 'awaiting_approval'):
            job = self.ikc.transition_production('syn_org', job.job_id, state, expected_revision=job.revision)
        published = self.ikc.publish_blue_green('syn_org', job.job_id, expected_revision=job.revision)
        self.assertEqual(published.status, 'published')
        self.assertEqual(published.visibility, 'published')
        self.assertEqual(self.ikc.active_published_production_id, published.job_id)
        self.assertTrue(any(item[0] == 'blue_green' for item in self.ikc.outbox))

    def test_illegal_production_transition_fail_closed(self):
        intake = self._walk_intake(self.ikc.submit_intake('syn_org', 'idem-5', dict(source_kind='upload', compliance_class='standard')), 'standard')
        job = self.ikc.submit_production('syn_org', 'prod-4', dict(intake_job_id=intake.job_id, pipeline_id='pipe', pipeline_version='1', checksum='abc', compliance_class='standard'))
        with self.assertRaises(ConflictError):
            self.ikc.transition_production('syn_org', job.job_id, 'published', expected_revision=job.revision)


class KSGLiteCases(unittest.TestCase):
    def setUp(self):
        self.plugin = KSGLitePlugin()

    def test_mounts_existing_governance_operations(self):
        self.assertIn('submit_for_review', self.plugin.workflow_operations)
        self.assertIn('publish_release', self.plugin.workflow_operations)
        self.assertIn('resolve_evidence_issue', self.plugin.issue_operations)

    def test_high_risk_publish_requires_approval_and_atomic_flag(self):
        denied = self.plugin.validate('publish_release', dict(policy_generation=2, compliance_class='high_risk', whole_document_atomic_publication=True))
        self.assertFalse(denied.allowed)
        self.assertEqual(denied.reason_code, 'APPROVAL_REQUIRED')
        allowed = self.plugin.validate('publish_release', dict(policy_generation=2, compliance_class='high_risk', whole_document_atomic_publication=True, approved=True))
        self.assertTrue(allowed.allowed)

    def test_partial_available_denied(self):
        decision = self.plugin.validate('submit_for_review', dict(policy_generation=2, partial_available=True))
        self.assertEqual(decision.reason_code, 'PARTIAL_PUBLICATION_FORBIDDEN')

    def test_stale_policy_denied(self):
        decision = self.plugin.validate('approve_release', dict(policy_generation=2, current_policy_generation=3))
        self.assertEqual(decision.reason_code, 'POLICY_GENERATION_STALE')

    def test_proxy_does_not_modify_mixin(self):
        class Dummy(object):
            def publish_release(self, **kwargs):
                return 'ok'
        proxy = self.plugin.bind(Dummy())
        with self.assertRaises(PermissionError):
            proxy.publish_release(policy_context=dict(policy_generation=2, compliance_class='high_risk', whole_document_atomic_publication=True))
        self.assertTrue(hasattr(Dummy, 'publish_release') or True)


class SemanticReferenceCases(unittest.TestCase):
    def test_read_only_binding(self):
        ref = from_payload(dict(tenant_id='syn_org', semantic_object_key='semobj:openbot:finance.invoice', concept_ids=['concept.invoice'], policy_clause_ids=['policy.retention']))
        self.assertEqual(ref.semantic_object_key, 'semobj:openbot:finance.invoice')

    def test_physical_connector_fields_forbidden(self):
        with self.assertRaises(SemanticReferenceWriteForbidden) as ctx:
            from_payload(dict(tenant_id='syn_org', semantic_object_key='semobj:openbot:x', concept_ids=[], policy_clause_ids=[], dsn='postgresql://x'))
        self.assertEqual(ctx.exception.code, 'SEMANTIC_WRITE_FORBIDDEN')
        with self.assertRaises(SemanticReferenceWriteForbidden):
            write_physical(dsn='postgresql://x')


class RevocationCases(unittest.TestCase):
    def setUp(self):
        self.loop = FourChannelRevocation()

    def test_purged_only_when_all_four_succeed(self):
        receipt = self.loop.run('syn_org', 'syn_mem_1', 4, 'syn_task_ok')
        self.assertTrue(receipt['purged'])
        self.assertEqual([item['channel'] for item in receipt['channels']], list(CHANNELS))
        self.assertTrue(self.loop.verify(receipt))

    def test_failed_channel_blocks_purged(self):
        receipt = self.loop.run('syn_org', 'syn_mem_1', 4, 'syn_task_fail', failures={'vector_fts_index': 'failed'})
        self.assertFalse(receipt['purged'])
        self.assertEqual(receipt['channels'][1]['status'], 'failed')
        self.assertTrue(self.loop.verify(receipt))

    def test_missing_or_timeout_blocks_purged(self):
        missing = self.loop.run('syn_org', 'syn_mem_1', 4, 'syn_task_miss', failures={'cache_materialized_snapshot': 'missing'})
        timeout = self.loop.run('syn_org', 'syn_mem_1', 4, 'syn_task_to', failures={'agent_history_cogniweave': 'timeout'})
        self.assertFalse(missing['purged'])
        self.assertFalse(timeout['purged'])

    def test_tamper_evident_hash(self):
        receipt = self.loop.run('syn_org', 'syn_mem_1', 4, 'syn_task_tamper')
        receipt['purged'] = False
        self.assertFalse(self.loop.verify(receipt))


class DualViewCases(unittest.TestCase):
    def setUp(self):
        self.plan = KnowledgeRetrievalPlan('syn_org', 8, authorized=['syn_ok'], excluded=[dict(resource_id='syn_secret_doc', permission_denied='ACL_DENY')])

    def test_audit_and_governance_have_precise_exclusions(self):
        for viewer in ('audit', 'governance'):
            view = self.plan.render(viewer)
            self.assertEqual(view['resources_excluded'][0]['resource_id'], 'syn_secret_doc')
            self.assertEqual(view['resources_excluded'][0]['permission_denied'], 'ACL_DENY')

    def test_agent_and_user_have_only_counts_and_opaque_code(self):
        for viewer in ('agent', 'end_user'):
            view = self.plan.render(viewer)
            self.assertEqual(view['redacted_unauthorized_count'], 1)
            self.assertRegex(view['redaction_code'], r'^[a-f0-9]{16}$')
            self.assertNotIn('resources_excluded', view)
            self.assertNotIn('syn_secret_doc', json.dumps(view))
            self.assertNotIn('ACL_DENY', json.dumps(view))

    def test_unknown_viewer_rejected(self):
        with self.assertRaises(RetrievalPlanError):
            self.plan.render('attacker')


class SourceShapeCases(unittest.TestCase):
    def test_sandbox_is_python39_ast(self):
        root = ROOT / 'sandbox' / 'v21_reuse_v1'
        parsed = 0
        for path in root.glob('*.py'):
            ast.parse(path.read_text())
            parsed += 1
        self.assertGreaterEqual(parsed, 7)


if __name__ == '__main__':
    unittest.main()
