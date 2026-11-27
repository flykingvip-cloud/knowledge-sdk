"""In-process / loopback assembly of the Wave-V21-0 sandbox model.

Protected by EXPERIMENTAL_V3_ENABLED defaulting to false. This service never
mounts /v3 on the production HTTP app and never touches Schema v6 migration tables.
"""
from __future__ import annotations
import os

from sandbox.v21_reuse_v1.adapters import (
    AdapterError, ModelAdapterClient, EmbeddingRerankAdapterClient,
    ControlledDataBridgeClient, CogniWeaveMemoryBridgeClient, AIExecutionTraceContext,
)
from sandbox.v21_reuse_v1.ikc import IKCSandbox, HIGH_RISK
from knowledge_sdk.exceptions import ConflictError, NotFoundError, ValidationError
from sandbox.v21_reuse_v1.ksg_lite import KSGLitePlugin
from sandbox.v21_reuse_v1.resources import (
    KnowledgeResource, DataCapabilityRef, ResourceCapabilityBinding,
    validate_distinct, reject_collapsed_payload,
)
from sandbox.v21_reuse_v1.retrieval_plan import KnowledgeRetrievalPlan
from sandbox.v21_reuse_v1.revocation import FourChannelRevocation
from sandbox.v21_reuse_v1.semantic_reference import from_payload as semantic_from_payload

EXPERIMENTAL_V3_ENV = 'EXPERIMENTAL_V3_ENABLED'
TRUTHY = frozenset({'1', 'true', 'yes', 'on'})


def experimental_v3_enabled(environ=None):
    value = (environ if environ is not None else os.environ).get(EXPERIMENTAL_V3_ENV, 'false')
    if value is None:
        return False
    return str(value).strip().lower() in TRUTHY


class V3ProductionMountForbidden(AdapterError):
    def __init__(self):
        super().__init__('V3_PRODUCTION_MOUNT_FORBIDDEN')


class V21LoopbackService(object):
    """Testable in-process facade. Production HTTP remains unmounted."""

    def __init__(self, environ=None, model_client=None, embed_client=None, data_bridge=None, memory_client=None, ikc=None, ksg=None, revocation=None):
        self.environ = dict(os.environ if environ is None else environ)
        self.flag_enabled = experimental_v3_enabled(self.environ)
        self.ikc = ikc or IKCSandbox()
        self.ksg = ksg or KSGLitePlugin()
        self.revocation = revocation or FourChannelRevocation()
        self.model = model_client or ModelAdapterClient()
        self.embed = embed_client or EmbeddingRerankAdapterClient()
        self.data_bridge = data_bridge or ControlledDataBridgeClient()
        self.memory = memory_client or CogniWeaveMemoryBridgeClient(verifier=self.revocation)
        self.resources = {}
        self.capabilities = {}
        self.bindings = {}

    def experimental_v3_enabled(self):
        return experimental_v3_enabled(self.environ)

    def production_v3_mounted(self):
        return False

    def mount_production_http(self):
        raise V3ProductionMountForbidden()

    def register_resource(self, resource):
        if not isinstance(resource, KnowledgeResource):
            raise AdapterError('COLLAPSED_RESOURCE_CAPABILITY')
        self.resources[resource.resource_id] = resource
        return resource

    def register_capability(self, capability):
        if not isinstance(capability, DataCapabilityRef):
            raise AdapterError('COLLAPSED_RESOURCE_CAPABILITY')
        self.capabilities[capability.capability_id] = capability
        return capability

    def bind_resource_capability(self, resource, capability, binding):
        reject_collapsed_payload(dict(resource_id=resource.resource_id))
        reject_collapsed_payload(dict(capability_id=capability.capability_id))
        validate_distinct(resource, capability, binding)
        self.register_resource(resource)
        self.register_capability(capability)
        self.bindings[(binding.tenant_id, binding.resource_id, binding.capability_id)] = binding
        return binding

    def bind_from_payloads(self, resource_payload, capability_payload, policy_generation):
        reject_collapsed_payload(resource_payload)
        reject_collapsed_payload(capability_payload)
        if set(resource_payload) & set(capability_payload) - {'tenant_id'}:
            # still allow only tenant overlap after separate payloads; collapse if mixed keys exist
            pass
        merged = dict(resource_payload)
        overlap = (set(resource_payload) & set(capability_payload)) - {'tenant_id'}
        if overlap:
            raise AdapterError('COLLAPSED_RESOURCE_CAPABILITY')
        resource = KnowledgeResource(
            resource_payload['tenant_id'], resource_payload['resource_id'],
            resource_payload['resource_type'], resource_payload.get('label'),
        )
        capability = DataCapabilityRef(
            capability_payload['tenant_id'], capability_payload['capability_id'],
            capability_payload['kind'], capability_payload['handle'],
        )
        binding = ResourceCapabilityBinding(resource.tenant_id, resource.resource_id, capability.capability_id, policy_generation)
        return self.bind_resource_capability(resource, capability, binding)

    def submit_intake(self, tenant_id, idempotency_key, payload):
        return self.ikc.submit_intake(tenant_id, idempotency_key, payload)

    def accept_intake(self, tenant_id, job):
        job = self.ikc.transition_intake(tenant_id, job.job_id, 'validating', expected_revision=job.revision)
        return self.ikc.transition_intake(tenant_id, job.job_id, 'accepted', expected_revision=job.revision)

    def submit_production(self, tenant_id, idempotency_key, payload):
        compliance = payload.get('compliance_class', 'standard')
        if compliance in HIGH_RISK:
            decision = self.ksg.validate('submit_for_review', dict(
                policy_generation=payload.get('policy_generation', 1),
                compliance_class=compliance,
                whole_document_atomic_publication=payload.get('whole_document_atomic_publication', True),
                visibility=payload.get('visibility'),
                partial_available=payload.get('partial_available'),
            ))
            if not decision.allowed:
                raise AdapterError(decision.reason_code)
        return self.ikc.submit_production(tenant_id, idempotency_key, payload)

    def advance_production_to_approval(self, tenant_id, job):
        for state in ('parsing', 'chunking', 'indexing', 'awaiting_approval'):
            job = self.ikc.transition_production(tenant_id, job.job_id, state, expected_revision=job.revision)
        return job

    def publish_blue_green(self, tenant_id, job, *, policy_generation, approved=False):
        context = dict(
            policy_generation=policy_generation,
            compliance_class=job.compliance_class,
            whole_document_atomic_publication=job.whole_document_atomic_publication,
            approved=approved,
        )
        decision = self.ksg.validate('publish_release', context)
        if not decision.allowed:
            raise AdapterError(decision.reason_code)
        return self.ikc.publish_blue_green(tenant_id, job.job_id, expected_revision=job.revision)

    def rollback_blue_green(self, tenant_id, *, policy_generation, to_production_id=None, approved=False):
        current_id = self.ikc.active_published_production_id
        if current_id is None:
            raise AdapterError('NO_ACTIVE_PUBLICATION')
        current = self.ikc.get_production(tenant_id, current_id)
        targets = [current]
        if to_production_id:
            targets.append(self.ikc.get_production(tenant_id, to_production_id))
        for job in targets:
            if job.compliance_class in HIGH_RISK:
                decision = self.ksg.validate('publish_release', dict(
                    policy_generation=policy_generation,
                    compliance_class=job.compliance_class,
                    whole_document_atomic_publication=job.whole_document_atomic_publication,
                    approved=approved,
                ))
                if not decision.allowed:
                    raise AdapterError(decision.reason_code)
        try:
            return self.ikc.rollback_blue_green(
                tenant_id, to_production_id=to_production_id, expected_current=current_id,
            )
        except (ConflictError, NotFoundError, ValidationError) as exc:
            raise AdapterError(exc.args[0] if exc.args else 'ROLLBACK_REJECTED') from exc

    def revoke(self, tenant_id, subject_id, policy_generation, task_id, *, failures=None):
        receipt = self.revocation.run(tenant_id, subject_id, policy_generation, task_id, failures=failures)
        return self.memory.apply_purge(receipt)

    def retrieval_plan(self, tenant_id, policy_generation, authorized, excluded):
        return KnowledgeRetrievalPlan(tenant_id, policy_generation, authorized, excluded)

    def render_plan(self, plan, viewer):
        return plan.render(viewer)

    def semantic_reference(self, payload):
        return semantic_from_payload(payload)

    def invoke_model(self, payload, trace=None):
        if trace is not None and not isinstance(trace, AIExecutionTraceContext):
            trace = AIExecutionTraceContext.from_payload(trace)
        return self.model.invoke(payload, trace=trace)
