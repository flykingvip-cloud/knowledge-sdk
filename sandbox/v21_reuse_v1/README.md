# sandbox/v21_reuse_v1 — zero-DDL Wave-V21-0 prototypes

DRAFT only. These modules are not mounted in the production HTTP app, do not add Schema v6/v7 tables, and do not claim T-01..T-27.

- `resources.py`: KnowledgeResource, DataCapabilityRef, ResourceCapabilityBinding must stay distinct.
- `ikc.py`: IntakeJob, KnowledgeProductionJob, PipelineVersion, and `active_published_production_id` blue-green switch. Reuses 9940818b idempotency/ingestion semantics in memory. High-risk/strong-compliance documents force `whole_document_atomic_publication=true` and forbid `partial_available`.
- `ksg_lite.py`: Phase 0 validation plugin mounted on existing `governance/workflow.py` and `governance/issues.py` operation names. No production table changes.
- `semantic_reference.py`: read-only `semantic_object_key` pointer plus concept/policy mappings. Writing connector/credential fields raises `SEMANTIC_WRITE_FORBIDDEN`.
- `revocation.py` / `retrieval_plan.py`: four-channel closed loop and M-04 dual-view redaction.

Run (must use repo root on PYTHONPATH):

`PYTHONPATH=src:. python -W error::ResourceWarning -m unittest discover -s sandbox/v21_reuse_v1 -p 'sandbox_cases.py' -v`

`PYTHONPATH=src:. python -W error::ResourceWarning -m pytest sandbox/v21_reuse_v1/sandbox_cases.py -q`
