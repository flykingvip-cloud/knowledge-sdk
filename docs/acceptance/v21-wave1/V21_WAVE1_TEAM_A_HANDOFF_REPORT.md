# V21_WAVE1_TEAM_A_HANDOFF_REPORT

Status: **Team A Wave-V21-1 implementation handoff (W1A-1 through W1A-4 local suite), not formal T-01–T-27 acceptance**. This report does not claim Space Gate 3/4 MET, Schema v7 authorization, official VB-1 lock changes, or production cutover. `formal_acceptance` remains false.

Order: `WAVE_V21_0_JOINT_CLOSURE_AND_WAVE1_LAUNCH_ORDER` (SHA-256 `450108ec3b9e8ca5d04bbfe0718d2ce4712acd485a8c4eafb1a6286ce7b943da`). Verdict already recorded as `WAVE_V21_0_JOINT_CLEAN_ACCEPT` with `wave_v21_1_unlocked=true`. Still false and unchanged here: `schema_v7_ddl_authorized`, `schema_v8_v9_ddl_authorized`, `final_alignment_frozen`, `prod_shadow_migration_cutover_authorized`. Official VB-1 lock remains `111/13/0`. AUTH-V21-04 remains HOLD.

## 1. Branch and commits

- Repository: `knowledge-sdk`
- Isolated branch: `feat/v21-wave1-runtime-adapters`
- Isolated worktree: `/workspace/knowledge-sdk-v21-wave1`
- Frozen Wave-V21-0 tip (parent of W1A-1, unmodified): `9d25ea96b75b5ab528a2d2670b5419d9a217e39e`
- W1A-1 commit (contract pack promotion, unmodified ancestor): `116877f0e837a3c3cfc96327e9ae05c22feb2a0a`
- W1A-2 / W1A-3 implementation commit: `39052a9c7011983e17864de24b0e2ef7fba066e7`
- This report is a follow-on docs commit on the same isolated branch. The exact branch-tip SHA after that commit, and the remote SHA after `git push -u`, belong in the external receipt `/workspace/v21-wave1-task-inputs/W1A234_RECEIPT.md`.
- Existing Wave-V21-0 worktree `/workspace/knowledge-sdk-v21-wave0` was left untouched at `9d25ea96`. `/workspace/knowledge-sdk` was not used as the Wave-V21-1 working tree.
- No PR, no merge to `main`, no force-push, no amend, no tag, no release.

## 2. Frozen contract identity (unchanged in W1A-2/W1A-3/W1A-4)

- Pack status: `FROZEN_V21_REUSE_V1`
- Deterministic manifest SHA-256: `212537fd41bd4cc4d9d7343cacafaea225ee98b6586df716bf036a397cb2a382`
- File count: 18
- Draft-era SHA (comparison only): `6da567e0f376fee7b6b2b033e6666cbd5eba7bc3d67b93089e49e6edb759906d`
- Five schema groups and 51 vectors remain byte-identical to `9d25ea96` / `116877f0`. W1A-2 and W1A-3 did not edit `contracts/v21-reuse-v1/` files, so the frozen SHA did not change.
- `scripts/verify_v21_boundaries.py` still hard-locks the SHA above. The only verifier edit in this wave after W1A-1 is allowing the new prefix `docs/acceptance/v21-wave1/`.

This is the SHA Team B should recompute for Sync-W1-1 / W1B-4.

## 3. What Team A delivered

### W1A-1 (already landed at `116877f0`)

Promoted `contracts/v21-reuse-v1/status.json` and the manifest from `DRAFT_WAVE_V21_0_NOT_FROZEN` to `FROZEN_V21_REUSE_V1`, and locked the new manifest SHA in `verify_v21_boundaries.py`. Receipt: `/workspace/v21-wave1-task-inputs/W1A1_MANIFEST_RECEIPT.md`.

### W1A-2 — protocol-level adapter clients

All clients live under `sandbox/v21_reuse_v1/adapters.py` (not `src/knowledge_sdk/`, not a duplicate OpenBot/CogniWeave runtime). Stdlib only. Default transports are in-process loopbacks: no sockets, no hardcoded credentials, no implicit outbound calls. Hosts may inject a transport.

- `ModelAdapterClient` — validates `LLMInvokeRequest` / `LLMInvokeResponse` against the frozen schema; default `LoopbackModelTransport`.
- `EmbeddingRerankAdapterClient` — deterministic hash embeddings and lexical rerank; validates `EmbedRequest` / `RerankRequest` and responses.
- `ControlledDataBridgeClient` — Mode A/B/C only, fail-closed; rejects unmatched modes, free-form Text-to-SQL, and active tombstones; Mode B requires `row_level_predicate`.
- `CogniWeaveMemoryBridgeClient` — read-only `MemoryDiscoveryMetadata`; requires a contract-valid, integrity-checked `RevocationPurgeReceipt` (`purged` only when all four channels succeed).
- `AIExecutionTraceContext` — official seven-key propagation (`tenant_id`, `user_id`, `agent_id`, `trace_id`, `run_id`, `plan_id`, `policy_generation`) plus the required `cost_attribution` envelope.

### W1A-3 — in-process / loopback service layer

`sandbox/v21_reuse_v1/loopback_service.py` assembles the Wave-V21-0 sandbox model:

- `EXPERIMENTAL_V3_ENABLED` defaults false; `production_v3_mounted()` is always false; `mount_production_http()` raises `V3_PRODUCTION_MOUNT_FORBIDDEN` even if the flag is true.
- Resource != Capability (`KnowledgeResource` / `DataCapabilityRef` / `ResourceCapabilityBinding`).
- IKC three-stage intake → production → blue/green publish; high-risk / strong-compliance requires `whole_document_atomic_publication=true` and forbids `partial_available`.
- KSG-Lite Phase 0 hooks run before high-risk submit/publish (approval required to publish).
- Four-channel revocation orchestrated through the memory client's receipt check.
- `KnowledgeRetrievalPlan` dual-view redaction with `redacted_unauthorized_count` for agent / end_user views.

No Schema v6 production migration tables were touched. `/v3` was not mounted on the production HTTP app. `pyproject.toml` core `dependencies` remains `[]`.

## 4. Local verification (W1A-4)

Commands run in `/workspace/knowledge-sdk-v21-wave1` after the implementation commit `39052a9c7011983e17864de24b0e2ef7fba066e7` (and re-run after this docs commit as needed):

```
python3 contracts/v21-reuse-v1/validate.py
python3 scripts/verify_v21_boundaries.py
python3 docs/acceptance/v2.2-align-wave2/verify_frozen.py
PYTHONPATH=src:. python3 -W error::ResourceWarning -m unittest discover -s sandbox/v21_reuse_v1 -p 'sandbox_cases.py' -v
```

Results:

- `validate.py`: exit 0; 51/51 vectors (18 accept / 33 reject); `manifest_sha256=212537fd41bd4cc4d9d7343cacafaea225ee98b6586df716bf036a397cb2a382`; `formal_acceptance=false`.
- `verify_v21_boundaries.py`: `passed=true`; `v21_contract_status=FROZEN_V21_REUSE_V1`; same manifest SHA; `schema_version=6`; 709 baseline files, 0 drift; `formal_acceptance=false`.
- `verify_frozen.py`: `passed=true`; M1 `contract_asset_count=28`; architecture and `pyproject.toml` byte diffs 0.
- unittest `sandbox_cases.py`: 36/36 OK (25 Wave-V21-0 cases plus 11 new adapter / loopback cases). `pytest` is not installed in the local executor environment; CI still runs the same file under both runners.

## 5. GitHub Actions

Push of `feat/v21-wave1-runtime-adapters` is a W1A-4 step and is performed only after this local suite is green. The GitHub Actions Run ID is **not available until that push starts a workflow**.

- Placeholder: `GH_ACTIONS_RUN_ID=PENDING_AFTER_PUSH`
- After push, record the actual Run ID (if the workflow starts) in `/workspace/v21-wave1-task-inputs/W1A234_RECEIPT.md`. If remote CI is blocked (for example by billing limits), do not treat a missing Run ID as formal acceptance, and do not open a PR to work around it.

This report does not predeclare a pending CI run green.

## 6. Residual notes (not claimed as closed)

- Formal T-01–T-27 remains `NOT_RUN_NOT_ACCEPTED`.
- Space Gate 3/4 remain `NOT_MET`. Official VB-1 lock stays `111/13/0`.
- Schema v7/v8/v9 DDL remains unauthorized. Production shadow migration / cutover remains unauthorized.
- `/v3/*` stays an unmounted draft; `EXPERIMENTAL_V3_ENABLED` stays default false.
- Schema/OpenAPI file-level metadata in the frozen pack still says `DRAFT_WAVE_V21_0_NOT_FROZEN` so those bytes stay backward-compatible; pack freeze is authoritative in `status.json`, the manifest, and the boundary lock.
- Historical Wave-V21-0 handoff docs still archive the draft-era SHA `6da567e0...`.
- Sync-W1-1 still needs Team B to recompute the frozen SHA `212537fd41bd4cc4d9d7343cacafaea225ee98b6586df716bf036a397cb2a382`.
