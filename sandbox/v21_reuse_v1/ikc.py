"""IKC async knowledge-production state machine. In-memory only, zero production DDL.

Reuses 9940818b IngestionJob / idempotency_records / outbox_events *semantics*
via the existing stdlib contract modules. It does not alter production tables.
"""
from __future__ import annotations
from dataclasses import dataclass, replace
from enum import Enum
import threading, uuid
from typing import Optional
from knowledge_sdk.contracts.idempotency import request_fingerprint, InMemoryIdempotencyStore, IdempotencyDecision
from knowledge_sdk.exceptions import ValidationError, ConflictError, NotFoundError

INTAKE_TRANSITIONS = {
    'queued': frozenset({'validating', 'cancelled', 'rejected'}),
    'validating': frozenset({'accepted', 'rejected', 'cancelled'}),
    'accepted': frozenset(),
    'rejected': frozenset(),
    'cancelled': frozenset(),
}
PRODUCTION_TRANSITIONS = {
    'queued': frozenset({'parsing', 'cancelled', 'failed'}),
    'parsing': frozenset({'chunking', 'cancelled', 'failed'}),
    'chunking': frozenset({'indexing', 'cancelled', 'failed'}),
    'indexing': frozenset({'awaiting_approval', 'cancelled', 'failed'}),
    'awaiting_approval': frozenset({'published', 'cancelled', 'failed'}),
    'published': frozenset(),
    'failed': frozenset(),
    'cancelled': frozenset(),
}
HIGH_RISK = frozenset({'high_risk', 'strong_compliance'})


class Visibility(str, Enum):
    HIDDEN = 'hidden'
    PUBLISHED = 'published'


@dataclass(frozen=True)
class PipelineVersion:
    pipeline_id: str
    version: str
    checksum: str


@dataclass(frozen=True)
class IntakeJob:
    job_id: str
    tenant_id: str
    status: str
    compliance_class: str
    fingerprint: str
    revision: int = 0


@dataclass(frozen=True)
class KnowledgeProductionJob:
    job_id: str
    tenant_id: str
    intake_job_id: str
    pipeline: PipelineVersion
    status: str
    compliance_class: str
    whole_document_atomic_publication: bool
    visibility: str
    fingerprint: str
    revision: int = 0
    published_production_id: Optional[str] = None


class IKCSandbox:
    """In-memory IKC prototype. No SQLite/PG schema changes."""

    def __init__(self):
        self._lock = threading.RLock()
        self._intake = {}
        self._intake_keys = {}
        self._prod = {}
        self._prod_keys = {}
        self.active_published_production_id = None
        self.idempotency = InMemoryIdempotencyStore()
        self.outbox = []

    def _atomic(self, compliance_class):
        if compliance_class not in ('standard', 'high_risk', 'strong_compliance'):
            raise ValidationError('INVALID_COMPLIANCE_CLASS')
        return compliance_class in HIGH_RISK

    def submit_intake(self, tenant_id, idempotency_key, payload):
        if type(tenant_id) is not str or not tenant_id or type(idempotency_key) is not str or not idempotency_key:
            raise ValidationError('INVALID_JOB_SUBMISSION')
        compliance = payload.get('compliance_class', 'standard')
        self._atomic(compliance)
        fingerprint = request_fingerprint(dict(payload=payload))
        decision, record = self.idempotency.begin(tenant_id, 'POST', '/v3/ikc/intake-jobs', idempotency_key, payload)
        if decision is IdempotencyDecision.CONFLICT_PAYLOAD_MISMATCH:
            raise ConflictError('IDEMPOTENCY_CONFLICT')
        with self._lock:
            key = (tenant_id, idempotency_key)
            if key in self._intake_keys:
                job = self._intake[self._intake_keys[key]]
                if job.fingerprint != fingerprint:
                    raise ConflictError('IDEMPOTENCY_CONFLICT')
                return job
            job = IntakeJob(uuid.uuid4().hex, tenant_id, 'queued', compliance, fingerprint)
            self._intake[job.job_id] = job
            self._intake_keys[key] = job.job_id
            if decision is IdempotencyDecision.NEW:
                self.idempotency.complete(record, dict(job_id=job.job_id, status=job.status))
            return job

    def transition_intake(self, tenant_id, job_id, status, *, expected_revision):
        with self._lock:
            job = self._intake.get(job_id)
            if job is None or job.tenant_id != tenant_id:
                raise NotFoundError('JOB_NOT_FOUND')
            if expected_revision != job.revision:
                raise ConflictError('STALE_JOB_REVISION')
            if status not in INTAKE_TRANSITIONS[job.status]:
                raise ConflictError('INVALID_JOB_TRANSITION')
            job = replace(job, status=status, revision=job.revision + 1)
            self._intake[job_id] = job
            self.outbox.append(('intake', job.job_id, status))
            return job

    def submit_production(self, tenant_id, idempotency_key, payload):
        intake_id = payload.get('intake_job_id')
        pipeline = PipelineVersion(payload['pipeline_id'], payload['pipeline_version'], payload['checksum'])
        compliance = payload.get('compliance_class', 'standard')
        atomic = True if self._atomic(compliance) else bool(payload.get('whole_document_atomic_publication', False))
        if compliance in HIGH_RISK and payload.get('whole_document_atomic_publication') is False:
            raise ValidationError('ATOMIC_PUBLICATION_REQUIRED')
        if payload.get('visibility') == 'partial_available' or payload.get('partial_available') is True:
            raise ValidationError('PARTIAL_PUBLICATION_FORBIDDEN')
        fingerprint = request_fingerprint(dict(payload=payload))
        decision, record = self.idempotency.begin(tenant_id, 'POST', '/v3/ikc/production-jobs', idempotency_key, payload)
        if decision is IdempotencyDecision.CONFLICT_PAYLOAD_MISMATCH:
            raise ConflictError('IDEMPOTENCY_CONFLICT')
        with self._lock:
            intake = self._intake.get(intake_id)
            if intake is None or intake.tenant_id != tenant_id or intake.status != 'accepted':
                raise ValidationError('INTAKE_NOT_ACCEPTED')
            key = (tenant_id, idempotency_key)
            if key in self._prod_keys:
                job = self._prod[self._prod_keys[key]]
                if job.fingerprint != fingerprint:
                    raise ConflictError('IDEMPOTENCY_CONFLICT')
                return job
            job = KnowledgeProductionJob(uuid.uuid4().hex, tenant_id, intake_id, pipeline, 'queued', compliance, atomic, Visibility.HIDDEN.value, fingerprint)
            self._prod[job.job_id] = job
            self._prod_keys[key] = job.job_id
            if decision is IdempotencyDecision.NEW:
                self.idempotency.complete(record, dict(job_id=job.job_id, status=job.status))
            return job

    def transition_production(self, tenant_id, job_id, status, *, expected_revision, visibility=None):
        with self._lock:
            job = self._prod.get(job_id)
            if job is None or job.tenant_id != tenant_id:
                raise NotFoundError('JOB_NOT_FOUND')
            if expected_revision != job.revision:
                raise ConflictError('STALE_JOB_REVISION')
            if status not in PRODUCTION_TRANSITIONS[job.status]:
                raise ConflictError('INVALID_JOB_TRANSITION')
            if visibility == 'partial_available' or status == 'partial_available':
                raise ValidationError('PARTIAL_PUBLICATION_FORBIDDEN')
            if job.whole_document_atomic_publication and visibility not in (None, Visibility.HIDDEN.value, Visibility.PUBLISHED.value):
                raise ValidationError('PARTIAL_PUBLICATION_FORBIDDEN')
            if status == 'published':
                if job.status != 'awaiting_approval':
                    raise ConflictError('INVALID_JOB_TRANSITION')
                vis = Visibility.PUBLISHED.value
                production_id = job.job_id
            else:
                vis = Visibility.HIDDEN.value
                production_id = job.published_production_id
            job = replace(job, status=status, revision=job.revision + 1, visibility=vis, published_production_id=production_id)
            self._prod[job_id] = job
            self.outbox.append(('production', job.job_id, status))
            return job

    def publish_blue_green(self, tenant_id, job_id, *, expected_revision):
        job = self.transition_production(tenant_id, job_id, 'published', expected_revision=expected_revision)
        with self._lock:
            if job.visibility != Visibility.PUBLISHED.value:
                raise ValidationError('PARTIAL_PUBLICATION_FORBIDDEN')
            previous = self.active_published_production_id
            self.active_published_production_id = job.job_id
            self.outbox.append(('blue_green', previous, job.job_id))
            return job
