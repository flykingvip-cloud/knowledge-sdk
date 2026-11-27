# sandbox/v21_reuse_v1 — zero-DDL Wave-V21 sandbox and loopback service

These modules are not mounted in the production HTTP app, do not add Schema v6/v7 tables, and do not claim T-01..T-27. `EXPERIMENTAL_V3_ENABLED` defaults to false; even when set true, `V21LoopbackService.mount_production_http()` stays forbidden.

Wave-V21-1 additions:
- `adapters.py`: injectable stdlib clients — `ModelAdapterClient`, `EmbeddingRerankAdapterClient`, `ControlledDataBridgeClient` (Mode A/B/C fail-closed, no Text-to-SQL), `CogniWeaveMemoryBridgeClient` (RevocationPurgeReceipt required), and `AIExecutionTraceContext` (seven-key propagation). Default transports are in-process loopbacks with no implicit network calls and no hardcoded credentials.
- `loopback_service.py`: in-process assembly of Resource != Capability, IKC blue/green publication, KSG-Lite Phase 0 hooks, four-channel revocation, and `KnowledgeRetrievalPlan` dual-view redaction.

Wave-V21-0 prototypes reused by the loopback service:
- `resources.py`: KnowledgeResource, DataCapabilityRef, ResourceCapabilityBinding must stay distinct.
- `ikc.py`: IntakeJob, KnowledgeProductionJob, PipelineVersion, and `active_published_production_id` blue-green switch. Reuses 9940818b idempotency/ingestion semantics in memory. High-risk/strong-compliance documents force `whole_document_atomic_publication=true` and forbid `partial_available`.
- `ksg_lite.py`: Phase 0 validation plugin mounted on existing `governance/workflow.py` and `governance/issues.py` operation names. No production table changes.
- `semantic_reference.py`: read-only `semantic_object_key` pointer plus concept/policy mappings. Writing connector/credential fields raises `SEMANTIC_WRITE_FORBIDDEN`.
- `revocation.py` / `retrieval_plan.py`: four-channel closed loop and M-04 dual-view redaction.

Wave-V21-2 additions (W2A-1; not formal T-01..T-27):
- `interop_harness.py`: offline stdlib harness for the five official interop groups (`models.embed`, `AIExecutionTrace` seven-key hops, `SemanticObjectCatalogReadAdapter`, CogniWeave `RevocationPurgeReceipt`, `ControlledDataBridge` Mode A/B/C fail-closed). No implicit network and no production HTTP mount.
- `fixtures/w2_interop_golden.json`: frozen inputs/outputs plus the canonical hash rule. `receipt_hash` reuses `revocation.canonical_json_bytes` (Python `json.dumps(..., sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')`, then SHA-256 as 64 lowercase hex). TypeScript must hash those exact UTF-8 bytes. Verify with `PYTHONPATH=src:. python -m sandbox.v21_reuse_v1.interop_harness`.

Run (must use repo root on PYTHONPATH):

`PYTHONPATH=src:. python -W error::ResourceWarning -m unittest discover -s sandbox/v21_reuse_v1 -p '*cases.py' -v`

`PYTHONPATH=src:. python -W error::ResourceWarning -m unittest discover -s sandbox/v21_reuse_v1 -p '*.py' -v`

`PYTHONPATH=src:. python -W error::ResourceWarning -m pytest sandbox/v21_reuse_v1/sandbox_cases.py sandbox/v21_reuse_v1/interop_cases.py -q`
