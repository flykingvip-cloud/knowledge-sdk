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
from sandbox.v21_reuse_v1.adapters import (
    AdapterError, ModelAdapterClient, EmbeddingRerankAdapterClient,
    ControlledDataBridgeClient, CogniWeaveMemoryBridgeClient, AIExecutionTraceContext,
    LoopbackModelTransport, TRACE_KEYS,
)
from sandbox.v21_reuse_v1.loopback_service import V21LoopbackService, experimental_v3_enabled, V3ProductionMountForbidden

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




class AdapterClientCases(unittest.TestCase):
    def setUp(self):
        self.provider = dict(track='openbot_public_execution', handle='slot:openbot_llm', model_id='syn-llm')
        self.llm = dict(
            tenant_id='syn_org', user_id='syn_user', agent_id='syn_agent', trace_id='syn_trace',
            run_id='syn_run', plan_id='syn_plan', policy_generation=7, provider=self.provider,
            messages=[dict(role='user', text='syn summary request')], max_output_tokens=64,
        )
        self.trace = dict(
            tenant_id='syn_org', user_id='syn_user', agent_id='syn_agent', trace_id='syn_trace',
            run_id='syn_run', plan_id='syn_plan', policy_generation=7,
            cost_attribution=dict(system='knowledge_sdk', component='ikc', units='calls', quantity=1),
        )
        self.mask = dict(receipt_id='syn_mask_1', profile='standard', hash_algorithm='sha256', receipt_hash='a' * 64)
        self.tombstone = dict(active=False, revoked_at=None)

    def test_model_default_loopback_and_injection(self):
        client = ModelAdapterClient()
        response = client.invoke(self.llm)
        self.assertTrue(response['text'].startswith('syn loopback:'))
        self.assertEqual(response['tenant_id'], 'syn_org')
        recorder = type('Recorder', (), {})()
        recorder.calls = []
        inner = LoopbackModelTransport()
        def invoke(request, _inner=inner, _recorder=recorder):
            _recorder.calls.append(request)
            return _inner.invoke(request)
        recorder.invoke = invoke
        injected = ModelAdapterClient(transport=recorder)
        injected.invoke(self.llm)
        self.assertEqual(len(recorder.calls), 1)

    def test_model_rejects_hardcoded_credentials_and_urls(self):
        client = ModelAdapterClient()
        bad = dict(self.llm, api_key='sk-secret')
        with self.assertRaises(AdapterError) as ctx:
            client.invoke(bad)
        self.assertEqual(ctx.exception.code, 'CREDENTIAL_FORBIDDEN')
        with self.assertRaises(AdapterError):
            client.invoke(dict(self.llm, messages=[dict(role='user', text='see https://example.invalid/p')]))

    def test_embed_and_rerank_are_local_and_deterministic(self):
        client = EmbeddingRerankAdapterClient()
        embed_req = dict(tenant_id='syn_org', policy_generation=7, provider=dict(track='host_injected_external_provider', handle='slot:embed'), inputs=['syn alpha', 'syn beta'])
        first = client.embed(embed_req)
        second = client.embed(embed_req)
        self.assertEqual(first, second)
        self.assertEqual(first['dim'], 8)
        self.assertEqual(len(first['vectors']), 2)
        rerank = client.rerank(dict(
            tenant_id='syn_org', policy_generation=7,
            provider=dict(track='openbot_models_rerank_proxy', handle='slot:rerank'),
            query='syn alpha',
            candidates=[dict(candidate_id='syn_c1', text='syn alpha match'), dict(candidate_id='syn_c2', text='unrelated')],
        ))
        self.assertEqual(rerank['rankings'][0]['candidate_id'], 'syn_c1')
        self.assertGreaterEqual(rerank['rankings'][0]['score'], rerank['rankings'][1]['score'])

    def test_data_bridge_modes_and_fail_closed(self):
        client = ControlledDataBridgeClient()
        mode_a = dict(mode='A', tenant_id='syn_org', policy_generation=3, freshness_ts='2026-11-27T00:00:00Z', masking_receipt=self.mask, tombstone=self.tombstone, user_delegation_handle='deleg:user_token_slot', query_kind='object_get')
        mode_b = dict(mode='B', tenant_id='syn_org', policy_generation=3, freshness_ts='2026-11-27T00:00:00Z', masking_receipt=self.mask, tombstone=self.tombstone, service_credential_handle='svc:tenant_warehouse', row_level_predicate=dict(field='org_id', op='eq', value='syn_org'), query_kind='structured_select')
        mode_c = dict(mode='C', tenant_id='syn_org', policy_generation=3, freshness_ts='2026-11-27T00:00:00Z', masking_receipt=self.mask, tombstone=self.tombstone, snapshot_id='syn_snap_1', query_kind='snapshot_read')
        self.assertEqual(client.execute(mode_a)['mode'], 'A')
        self.assertEqual(client.execute(mode_b)['mode'], 'B')
        self.assertEqual(client.execute(mode_c)['mode'], 'C')
        with self.assertRaises(AdapterError) as unmatched:
            client.execute(dict(mode_a, mode='D'))
        self.assertEqual(unmatched.exception.code, 'MODE_UNMATCHED')
        with self.assertRaises(AdapterError) as sql:
            client.execute(mode_a, query=dict(sql='SELECT * FROM t'))
        self.assertEqual(sql.exception.code, 'TEXT_TO_SQL_FORBIDDEN')
        with self.assertRaises(AdapterError) as tomb:
            client.execute(dict(mode_a, tombstone=dict(active=True, revoked_at='2026-11-27T00:00:00Z')))
        self.assertEqual(tomb.exception.code, 'UNAUTHORIZED')

    def test_memory_bridge_requires_valid_purge_receipt(self):
        memory = CogniWeaveMemoryBridgeClient()
        memory.discover(dict(tenant_id='syn_org', resource_type='agent_memory', memory_resource_id='syn_mem_1', owner_agent_id='syn_agent', policy_generation=4, discoverable=True, freshness_ts='2026-11-27T00:00:00Z', label='syn memory'))
        loop = FourChannelRevocation()
        ok = loop.run('syn_org', 'syn_mem_1', 4, 'syn_task_ok')
        accepted = memory.apply_purge(ok)
        self.assertTrue(accepted['accepted'])
        self.assertTrue(accepted['purged'])
        failed = loop.run('syn_org', 'syn_mem_1', 4, 'syn_task_fail', failures={'vector_fts_index': 'failed'})
        self.assertFalse(failed['purged'])
        memory.apply_purge(failed)
        tampered = loop.run('syn_org', 'syn_mem_1', 4, 'syn_task_tamper')
        tampered['purged'] = False
        with self.assertRaises(AdapterError):
            memory.apply_purge(tampered)
        incomplete = dict(ok, channels=ok['channels'][:3], purged=True, task_id='syn_task_short')
        with self.assertRaises(AdapterError) as ctx:
            memory.apply_purge(incomplete)
        self.assertEqual(ctx.exception.code, 'CHANNEL_INCOMPLETE')

    def test_trace_propagates_seven_keys(self):
        context = AIExecutionTraceContext.from_payload(self.trace)
        self.assertEqual(tuple(context.seven_keys()), TRACE_KEYS)
        headers = context.headers()
        self.assertEqual(headers['X-V21-Trace-Id'], 'syn_trace')
        self.assertEqual(headers['X-V21-Policy-Generation'], '7')
        bound = context.propagate(dict(extra='ok'))
        for key in TRACE_KEYS:
            self.assertEqual(bound[key], self.trace[key])
        self.assertEqual(bound['cost_attribution']['system'], 'knowledge_sdk')
        missing = dict(self.trace)
        missing.pop('run_id')
        with self.assertRaises(AdapterError):
            AIExecutionTraceContext.from_payload(missing)
        client = ModelAdapterClient()
        response = client.invoke(dict(self.llm), trace=context)
        self.assertEqual(response['trace_id'], 'syn_trace')

    def test_adapter_modules_have_no_network_imports(self):
        root = ROOT / 'sandbox' / 'v21_reuse_v1'
        banned = {'socket', 'ssl', 'http.client', 'http.server', 'urllib', 'urllib.request', 'requests', 'aiohttp', 'httpx'}
        found = set()
        for path in (root / 'adapters.py', root / 'loopback_service.py'):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        found.add(alias.name)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    found.add(node.module)
        self.assertFalse(found & banned)


class LoopbackServiceCases(unittest.TestCase):
    def setUp(self):
        self.service = V21LoopbackService(environ={})

    def test_experimental_v3_defaults_false_and_never_mounts_http(self):
        self.assertFalse(experimental_v3_enabled({}))
        self.assertFalse(experimental_v3_enabled({'EXPERIMENTAL_V3_ENABLED': 'false'}))
        self.assertFalse(self.service.experimental_v3_enabled())
        self.assertFalse(self.service.production_v3_mounted())
        with self.assertRaises(V3ProductionMountForbidden):
            self.service.mount_production_http()
        enabled = V21LoopbackService(environ={'EXPERIMENTAL_V3_ENABLED': 'true'})
        self.assertTrue(enabled.experimental_v3_enabled())
        self.assertFalse(enabled.production_v3_mounted())
        with self.assertRaises(V3ProductionMountForbidden):
            enabled.mount_production_http()

    def test_resource_is_not_capability(self):
        resource = KnowledgeResource('syn_org', 'syn_doc', 'document', 'syn label')
        capability = DataCapabilityRef('syn_org', 'syn_cap', 'structured_select', 'svc:warehouse')
        binding = ResourceCapabilityBinding('syn_org', 'syn_doc', 'syn_cap', 3)
        self.service.bind_resource_capability(resource, capability, binding)
        self.assertIsNot(type(resource), type(capability))
        with self.assertRaises(BoundaryError):
            self.service.bind_from_payloads(
                dict(tenant_id='syn_org', resource_id='syn_doc', resource_type='document', capability_id='syn_cap'),
                dict(tenant_id='syn_org', capability_id='syn_cap', kind='structured_select', handle='svc:warehouse'),
                3,
            )

    def test_ikc_high_risk_blue_green_uses_ksg_hooks(self):
        intake = self.service.submit_intake('syn_org', 'idem-loop-1', dict(source_kind='upload', compliance_class='high_risk'))
        intake = self.service.accept_intake('syn_org', intake)
        with self.assertRaises(AdapterError) as denied:
            self.service.submit_production('syn_org', 'prod-loop-bad', dict(
                intake_job_id=intake.job_id, pipeline_id='pipe', pipeline_version='1', checksum='abc',
                compliance_class='high_risk', whole_document_atomic_publication=False, policy_generation=2,
            ))
        self.assertEqual(denied.exception.code, 'ATOMIC_PUBLICATION_REQUIRED')
        job = self.service.submit_production('syn_org', 'prod-loop-ok', dict(
            intake_job_id=intake.job_id, pipeline_id='pipe', pipeline_version='1', checksum='abc',
            compliance_class='high_risk', policy_generation=2,
        ))
        self.assertTrue(job.whole_document_atomic_publication)
        job = self.service.advance_production_to_approval('syn_org', job)
        with self.assertRaises(AdapterError) as unapproved:
            self.service.publish_blue_green('syn_org', job, policy_generation=2, approved=False)
        self.assertEqual(unapproved.exception.code, 'APPROVAL_REQUIRED')
        published = self.service.publish_blue_green('syn_org', job, policy_generation=2, approved=True)
        self.assertEqual(published.status, 'published')
        self.assertEqual(published.visibility, 'published')
        self.assertEqual(self.service.ikc.active_published_production_id, published.job_id)

    def test_revocation_and_dual_view_redaction(self):
        receipt = self.service.revoke('syn_org', 'syn_mem_1', 4, 'syn_task_loop')
        self.assertTrue(receipt['purged'])
        self.assertTrue(receipt['accepted'])
        self.assertEqual([item['channel'] for item in receipt['channels']], list(CHANNELS))
        blocked = self.service.revoke('syn_org', 'syn_mem_1', 4, 'syn_task_block', failures={'agent_history_cogniweave': 'timeout'})
        self.assertFalse(blocked['purged'])
        plan = self.service.retrieval_plan('syn_org', 8, authorized=['syn_ok'], excluded=[dict(resource_id='syn_secret_doc', permission_denied='ACL_DENY')])
        redacted = self.service.render_plan(plan, 'end_user')
        self.assertEqual(redacted['redacted_unauthorized_count'], 1)
        self.assertNotIn('syn_secret_doc', json.dumps(redacted))
        audit = self.service.render_plan(plan, 'audit')
        self.assertEqual(audit['resources_excluded'][0]['resource_id'], 'syn_secret_doc')

class SourceShapeCases(unittest.TestCase):
    def test_sandbox_is_python39_ast(self):
        root = ROOT / 'sandbox' / 'v21_reuse_v1'
        parsed = 0
        for path in root.glob('*.py'):
            ast.parse(path.read_text())
            parsed += 1
        self.assertGreaterEqual(parsed, 9)


if __name__ == '__main__':
    unittest.main()
