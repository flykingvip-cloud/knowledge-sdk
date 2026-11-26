# V21_WAVE0_TEAM_A_HANDOFF_REPORT

Status: **design/contract/sandbox handoff, not formal Wave-V21-0 acceptance**. This committed report does not predeclare a pending CI run green and does not embed its own final commit SHA. Literal SHA, run URL, and per-job durations are written after CI by `resolve_receipt.py` to an external receipt.

## 1. Branch, baseline, and authorization

- Branch: `feat/v21-wave0-contracts-and-adapters`, cut from exact Wave2 `9940818b962ccb186c0dfb0158de6bd9bd49057b`.
- Isolated worktree: `/workspace/knowledge-sdk-v21-wave0`. Frozen Pre-v7 checkout `feat/space-alignment-v1-design-proto@4bed2a1c86153035314815165f29d26a078fab50` was not modified.
- Owner authorization: t72u, directive `WAVE_V21_0_DUAL_TEAM_DIRECTIVES`, status `WAVE_V21_0_DISPATCHED_NON_DESTRUCTIVE`. Byte-original copy: `OWNER_WAVE_V21_0_DIRECTIVE.md` (SHA256 `f448592cdd3f6e7ec35e1887d27775abf4418fee251bb485d98a1eef28866738`).
- Flags remain false: `schema_v7_ddl_authorized`, `schema_v8_v9_ddl_authorized`, `final_alignment_frozen`, `prod_shadow_migration_cutover_authorized`. `semantic_object_dual_write_prohibited` and `duplicate_runtime_or_connector_build_prohibited` remain true.
- Resolve exact identity after CI:

`python docs/acceptance/v21-wave0/resolve_receipt.py --run-id <ID> --run-json <run.json> --jobs-json <jobs.json> --output /workspace/v21-wave0-task-inputs/FINAL_RESOLVED_RECEIPT.json`

The resolver requires this branch, merge-base `9940818b`, 37/37 successful jobs each under 1080 seconds, and unchanged protected remotes (main, Wave2, Pre-v7, Wave1.8, actual Wave1.5 `0d2f172c`, Wave1, v2.0.0).

## 2. CI

Wave2 baseline on `9940818b` is 36/36 green (run 45618122250). This branch preserves every previous workflow byte as an exact prefix and appends one independent job `v21-wave0-boundaries` (timeout 20 minutes, standard `ubuntu-24.04` runner). Existing job timeouts, steps, matrices, and assertions are unchanged.

Exact final run id, URL, and durations belong in the external receipt, not in a later self-referential commit. This report does not claim Wave-V21-0 formally accepted or Wave-V21-1 unlocked.

## 3. Raw gate commands

These commands are the source of the raw verifier outputs collected into CI artifact `v21-wave0-team-a-evidence` and copied next to the external receipt:

```
python docs/acceptance/v2.2-align-wave2/verify_frozen.py
python scripts/verify_v21_boundaries.py
PYTHONPATH=src:. python -W error::ResourceWarning -m unittest discover -s sandbox/v21_reuse_v1 -p 'sandbox_cases.py' -v
PYTHONPATH=src:. python -W error::ResourceWarning -m pytest sandbox/v21_reuse_v1/sandbox_cases.py -q
python contracts/v21-reuse-v1/validate.py
```

Local copies of the raw JSON are committed as `docs/acceptance/v21-wave0/verify_frozen.output.json` and `verify_v21_boundaries.output.json` after the last local regenerate. CI may reprint the same gates; treat the resolved commit receipt as authoritative for run identity.

`verify_v21_boundaries.py` re-runs the historical frozen guard, confirms `pyproject.toml` `dependencies == []` and Schema v6 production migration files are byte-identical to `9940818b`, scans new files for the 12 prohibited duplicate capabilities (with an explicit allowlist of pre-existing 9940818b knowledge-domain modules), and recomputes `v21-contract-manifest.json`.

## 4. Sandbox test inventory

File: `sandbox/v21_reuse_v1/sandbox_cases.py` (kept outside default pytest discovery so accepted SDK suites are unchanged). 25 cases, 0 skips, both unittest and pytest:

- ResourceCapabilityCases (5): distinct objects, collapsed payload rejected, secret handles rejected, bool/float policy_generation rejected, cross-tenant binding rejected.
- IKCCases (5): idempotent intake replay, payload conflict, high-risk atomic publication and `partial_available` forbidden, blue-green switch only after approval, illegal published-from-queued transition fail-closed.
- KSGLiteCases (5): mounts existing `governance/workflow.py` and `issues.py` operation names, high-risk publish requires approval plus atomic flag, partial publication denied, stale policy denied, proxy does not modify mixin classes.
- SemanticReferenceCases (2): read-only `semantic_object_key` binding; physical connector/credential write forbidden.
- RevocationCases (4): purged only when all four channels succeed; failed/missing/timeout channels block purged; receipt hash is tamper-evident.
- DualViewCases (3): audit/governance include `resources_excluded` and precise `permission_denied`; agent/end_user expose only `redacted_unauthorized_count` and an opaque code, with no unauthorized id side-channel.
- SourceShapeCases (1): Python 3.9 AST parse of sandbox modules.

Local contract vectors: 51 (18 positive / 33 negative) in Python and strict TypeScript/Node. Official OpenAPI 3.1 structural validation is executed in the new CI job with `openapi-spec-validator==0.9.0` as a job-only tool, not a core dependency.

## 5. Stream D/E (SDK-side) audit table — PROPOSED_PENDING_SOURCE_DOCUMENT

The official 10 field names from section 7 of 《Master Architecture v2.1 — OpenBot 既有能力清单与 Knowledge SDK 边界规范》 were not found (see `SOURCE_GAPS.md`). The columns below are a **proposed** mapping used so a code-backed SDK-side table can still be delivered. They are **not** claimed to be the official names.

Proposed columns and why: (1) capability_name — what is being reused or bounded; (2) authority_system_of_record — who may write; (3) public_contract — schema/API surface; (4) source_evidence — path/symbol actually inspected or added; (5) persistence_or_execution_depth — in-memory prototype vs production table; (6) identity_and_policy_generation — tenant/actor/generation rules; (7) fail_closed_behavior; (8) duplicate_build_status — against the 12 prohibited OpenBot capabilities; (9) test_evidence; (10) residual_gap.

| capability_name | authority_system_of_record | public_contract | source_evidence | persistence_or_execution_depth | identity_and_policy_generation | fail_closed_behavior | duplicate_build_status | test_evidence | residual_gap |
|---|---|---|---|---|---|---|---|---|---|
| D. Four-channel revocation + CogniWeave invalidation receipt | OpenBot/CogniWeave remains history-context authority; SDK only defines the receipt and orchestrates sandbox channels | `memory-resource-bridge.schema.json` `RevocationPurgeReceipt`, `/v3/revocations` draft | `sandbox/v21_reuse_v1/revocation.py` | In-memory sandbox only; no production table or CogniWeave network call | tenant_id + subject_id + policy_generation required | `purged` is false unless all four channel receipts are `success` | No new memory-distillation or agent-session runtime | RevocationCases (4) | Live CogniWeave `/v1` revocation wiring is Team B Stream D; not implemented here |
| D. Dual-view retrieval redaction (M-04) | SDK knowledge retrieval plan renderer (sandbox) | OpenAPI `AuditPlanView` / `RedactedPlanView` | `sandbox/v21_reuse_v1/retrieval_plan.py`; existing production redaction remains `src/knowledge_sdk/permissions/redaction.py` (unchanged) | Prototype only; production redaction hooks not modified | policy_generation strict integer | Unknown viewer rejected; user/agent views cannot echo unauthorized ids | No second policy engine | DualViewCases (3) | Production HTTP/MCP plan views are not mounted |
| E. Model / embed / rerank adapter | OpenBot public execution, Fallback, future `models.embed` / `models.rerank` proxy, or host-injected slot. SDK is not the credential vault | `model-adapter.schema.json` | `contracts/v21-reuse-v1/model-adapter.*`; baseline `openai_embedder.py` / lexical `reranker.py` allowlisted, unchanged | Contract + vectors only; no paid client | tenant + policy_generation; handles are `slot:*` | Credentials and implicit paid tracks rejected | No Model Provider/Vault/Fallback implementation added | 17 model-adapter vectors | Public OpenBot proxy does not exist yet (Team B Stream A) |
| E. Controlled Data Bridge Mode A/B/C | Tenant/user delegated handles; OpenBot remains enterprise data gateway authority | `controlled-data-bridge.schema.json` | contract pack + sandbox capability refs | Declaration validation only; no SQL engine, no connector vault | policy_generation, masking_receipt, freshness_ts, tombstone mandatory; Mode B requires row-level predicate | Unmatched mode Fail-Closed; Text-to-SQL forbidden; raw secrets forbidden | No DB/ERP/CRM connector or Data Capability execution engine added | 13 bridge vectors + capability secret tests | Mode A/B/C production unlock remains unauthorized |
| E. IKC / KSG-Lite / Resource Registry / EDKI | Knowledge SDK for IKC/KSG/registry prototypes; OpenBot is Semantic Object write authority | `/v3/*` draft (not mounted); `KnowledgeResource` ≠ `DataCapabilityRef`; read-only `semantic_object_key` | `sandbox/v21_reuse_v1/ikc.py`, `ksg_lite.py`, `resources.py`, `semantic_reference.py`; mounts existing `GovernanceMixin` / `IssueMixin` names | Zero production DDL; IKC reuses 9940818b idempotency/ingestion *semantics* in memory | High-risk forces atomic publication; stale policy denied | `partial_available` forbidden; semantic physical writes forbidden | No agent runtime, bandit, or workflow platform added | IKC/KSG/resource/semantic cases | `/v3` remains unmounted; Semantic Object catalog export is Team B VB-3 |

## 6. v21-contract-manifest inventory for Team B recomputation

Team B should run `python contracts/v21-reuse-v1/validate.py` on this exact commit and compare `contracts/v21-reuse-v1/v21-contract-manifest.json` plus the SHA-256 of that manifest file. Algorithm: POSIX relative path, stable sort, SHA-256 of raw bytes, manifest excludes itself, `node_modules/`, `ts-generated/`, `package-lock.json`, `__pycache__/`, `*.pyc`, and dotfiles. The exact file hashes are in the manifest generated with the commit; do not treat an older local copy as authoritative.

## 7. Explicit non-claims

- T-01 through T-27 are **not** passed and were not run as formal acceptance.
- `FINAL_SPACE_AND_FAVORITES_ALIGNMENT.md` was **not** written.
- Schema v7 / v8 / v9 production migrations and cutover were **not** started.
- `/v3/*` is a draft and is **not** mounted in the production HTTP app. `/v2/spaces` and Schema v6 are unchanged.
- Wave-V21-0 is **not** self-declared formally accepted. Wave-V21-1 is **not** unlocked.
- Team B was not contacted and was not nominated a SHA.
