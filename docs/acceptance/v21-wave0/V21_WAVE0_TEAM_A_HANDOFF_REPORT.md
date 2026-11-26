# V21_WAVE0_TEAM_A_HANDOFF_REPORT

Status: **design/contract/sandbox handoff, not formal Wave-V21-0 acceptance**. This committed report does not predeclare a pending CI run green and does not embed its own final commit SHA. Literal SHA, run URL, and per-job durations are written after CI by `resolve_receipt.py` to an external receipt.

This revision is a docs-only remap of Stream D/E. It maps the SDK-side Stream D audit onto the official section-7 field names from 《Master Architecture v2.1 — OpenBot 既有能力清单与 Knowledge SDK 边界规范》(SHA-256 `c5196ff1d050ac6477cc064390a708a4d10121cf7fe300bb24764a87a2a5b1c2`). The full architecture document is cited, not committed. The document's `signoff_status` remains `READY_FOR_OWNER_SIGNOFF_AND_STREAM_A_E_AUDIT_CLOSURE`. Owner providing the source document is **not** baseline signoff, does **not** start Schema v7/v8/v9, and does **not** unlock Wave-V21-1.

The previous English proposed column names (`capability_name`, `authority_system_of_record`, `public_contract`, `source_evidence`, `persistence_or_execution_depth`, `identity_and_policy_generation`, `fail_closed_behavior`, `duplicate_build_status`, `test_evidence`, `residual_gap`) are retired. They were a Team A holding mapping labeled `PROPOSED_PENDING_SOURCE_DOCUMENT` and were **never** official. Contract files under `contracts/v21-reuse-v1/` are unchanged from `02bf58738986bc7e22dfeafcb2911970d14f2588`.

## 1. Branch, baseline, and authorization

- Branch: `feat/v21-wave0-contracts-and-adapters`, cut from exact Wave2 `9940818b962ccb186c0dfb0158de6bd9bd49057b`.
- Isolated worktree: `/workspace/knowledge-sdk-v21-wave0`. Frozen Pre-v7 checkout `feat/space-alignment-v1-design-proto@4bed2a1c86153035314815165f29d26a078fab50` was not modified.
- Owner authorization: t72u, directive `WAVE_V21_0_DUAL_TEAM_DIRECTIVES`, status `WAVE_V21_0_DISPATCHED_NON_DESTRUCTIVE`. Byte-original copy: `OWNER_WAVE_V21_0_DIRECTIVE.md` (SHA256 `f448592cdd3f6e7ec35e1887d27775abf4418fee251bb485d98a1eef28866738`).
- Flags remain false: `schema_v7_ddl_authorized`, `schema_v8_v9_ddl_authorized`, `final_alignment_frozen`, `prod_shadow_migration_cutover_authorized`. `semantic_object_dual_write_prohibited` and `duplicate_runtime_or_connector_build_prohibited` remain true.
- Resolve exact identity after CI:

`python docs/acceptance/v21-wave0/resolve_receipt.py --run-id <ID> --run-json <run.json> --jobs-json <jobs.json> --output /workspace/v21-wave0-task-inputs/FINAL_RESOLVED_RECEIPT.json`

The resolver requires this branch, merge-base `9940818b`, 37/37 successful jobs each under 1080 seconds, and unchanged protected remotes (main, Wave2, Pre-v7, Wave1.8, actual Wave1.5 `0d2f172c`, Wave1, v2.0.0).

### 1.1 Team B VB-4 report (attributed, not formal acceptance)

Team B (B团队-知识库对齐) reported that VB-4 independent recomputation on `02bf58738986bc7e22dfeafcb2911970d14f2588` is complete. They cited: the commit is on `feat/v21-wave0-contracts-and-adapters` and is a descendant of `9940818b962ccb186c0dfb0158de6bd9bd49057b`; `python3 contracts/v21-reuse-v1/validate.py` exited 0 with `formal_acceptance` false and `status` `DRAFT_CONTRACTS_VALIDATED_NOT_FORMAL_ACCEPTANCE`; manifest file SHA-256 `6da567e0f376fee7b6b2b033e6666cbd5eba7bc3d67b93089e49e6edb759906d`; all 18 manifest files matched; no contract-hash `V21-DELTA`; and a read-only check of GitHub Actions run `45908411136` as `completed`/`success` with `head_sha=02bf5873` and 37/37 jobs success (they did not rerun locally or review every command log). Team A records these as **Team B's VB-4 report**, not as formal Wave-V21-0 acceptance, and does not unlock Wave-V21-1.

Locally, on this worktree at `02bf58738986bc7e22dfeafcb2911970d14f2588`, Team A reconfirmed the previously published contract identity: the commit is on this branch and is a descendant of `9940818b962ccb186c0dfb0158de6bd9bd49057b`; `python3 contracts/v21-reuse-v1/validate.py` exits 0 with `formal_acceptance` false and `status` `DRAFT_CONTRACTS_VALIDATED_NOT_FORMAL_ACCEPTANCE`; the manifest file SHA-256 is `6da567e0f376fee7b6b2b033e6666cbd5eba7bc3d67b93089e49e6edb759906d`, matching both the previously published handoff identity and the hash Team B cited. This remap does not re-verify the GitHub Actions run.

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

## 5. Stream D (SDK-side) — official section-7 10-field audit

Source of the field names: section 7 of 《Master Architecture v2.1 — OpenBot 既有能力清单与 Knowledge SDK 边界规范》, SHA-256 `c5196ff1d050ac6477cc064390a708a4d10121cf7fe300bb24764a87a2a5b1c2`. The official 10 names are used as the Stream D table columns. For readability, each SDK-side topic is rendered as a field/value table whose `字段` values are exactly those column names.

This is the Team A / Knowledge SDK side of Stream D (Memory & Knowledge Boundary), backed by the zero-DDL sandbox and already delivered contracts. It is not a Stream A/B/C OpenBot audit, and it does not invent Owner rulings. Field `保留/扩展/迁移/废弃裁定` only restates what Wave-V21-0 and the v2.1 document already authorize (sandbox/prototype, `/v3` unmounted, no production DDL, OpenBot remains authority where already stated, no duplicate build of the 12 prohibited capabilities). Any forward-looking recommendation is labeled pending Owner signoff.

The Stream D extra requirement「给出 OpenBot 本地知识模块向 SDK 委派收口清单，与 Space Pre-v7 B2-2 124 项实审完全对齐」is Team B / OpenBot work. Team A did **not** produce that list. It is recorded as a residual in section 5.7.

Cross-system contract packs, `validate.py`, the 51 vectors, the OpenAPI draft, and the `v21-wave0-boundaries` job are inventoried in Stream E (section 6), not as a 10-field table.

### 5.1 Four-channel revocation + CogniWeave invalidation receipt

| 字段 | 内容 |
|---|---|
| 文件路径与代码入口 | `sandbox/v21_reuse_v1/revocation.py` (`ChannelStore`, `FourChannelRevocation.run` / `verify`). Draft HTTP entry: `contracts/v21-reuse-v1/openapi-v3-draft.yaml` path `/v3/revocations` (`operationId: startRevocation`). Not mounted in the production HTTP app. |
| 核心对象与数据表/存储文件 | In-memory `ChannelStore.records` for `primary_storage_acl`, `vector_fts_index`, `cache_materialized_snapshot`, `agent_history_cogniweave`. Receipt object: `task_id`, `tenant_id`, `subject_id`, `policy_generation`, `channels`, `purged`, `hash_algorithm`, `receipt_hash`. No production table and no CogniWeave network call. |
| API / RPC / Event 契约 | `memory-resource-bridge.schema.json` `RevocationPurgeReceipt`; OpenAPI draft `/v3/revocations`. Related vectors: `MEM-POS-CH4`, `MEM-POS-RECEIPT`, `MEM-NEG-THREE-CHANNELS`, `MEM-NEG-PURGED-WITH-FAIL`. The pack itself is listed in Stream E. |
| 当前权威写主 | OpenBot/CogniWeave remains history-context / agent-history authority. The SDK defines the receipt and orchestrates sandbox channels only. |
| 已实现且稳定功能 | Sandbox closed loop only: `purged` is true only when all four channel receipts are `success`; the receipt hash is tamper-evident (SHA-256). This is not a production-stable service. |
| 仅有接口/原型/默认关闭/Fail-Closed 功能 | The module is an unmounted prototype. Failed, missing, or timeout channels leave `purged` false. Live CogniWeave `/v1` revocation wiring is not implemented. |
| 已完成的测试证据 | `RevocationCases` (4) in `sandbox/v21_reuse_v1/sandbox_cases.py`; memory-resource-bridge vectors above; also executed by `validate.py` and CI job `v21-wave0-boundaries`. |
| 未覆盖的测试场景 | Live CogniWeave network revocation, production four-channel orchestration, and OpenBot-side integration tests are out of Team A scope. |
| 与另一仓库的重复点 | No new agent-memory distillation or agent-session runtime was added. Channel name `agent_history_cogniweave` is a sandbox label, not a CogniWeave SDK reimplementation. |
| 保留/扩展/迁移/废弃裁定 | Authorized scope only: keep as a Wave-V21-0 sandbox/prototype; `/v3` remains unmounted; no production DDL; no duplicate build of the 12 prohibited capabilities. Live CogniWeave wiring is a Team B residual and is pending Owner signoff — not an Owner ruling in this table. |

### 5.2 Dual-view retrieval redaction (M-04)

| 字段 | 内容 |
|---|---|
| 文件路径与代码入口 | `sandbox/v21_reuse_v1/retrieval_plan.py` (`KnowledgeRetrievalPlan.render`). Existing production redaction remains `src/knowledge_sdk/permissions/redaction.py` and was not modified this wave. Draft HTTP entry: OpenAPI `/v3/krdr/plans` (`operationId: createRetrievalPlan`), unmounted. |
| 核心对象与数据表/存储文件 | In-memory plan with `authorized` and `excluded` lists. Audit/governance viewers: `audit`, `governance`. Redacted viewers: `agent`, `end_user`. No new production table. |
| API / RPC / Event 契约 | OpenAPI draft `AuditPlanView` / `RedactedPlanView`. Related vectors: `V3-POS-REDACTED-VIEW`, `V3-POS-AUDIT-VIEW`, `V3-NEG-USER-LEAK`. Pack inventory is in Stream E. |
| 当前权威写主 | SDK sandbox plan renderer for this prototype. Production redaction hooks were not modified and are not claimed as transferred authority. |
| 已实现且稳定功能 | Sandbox only: audit/governance views include `resources_excluded` and precise `permission_denied`; agent/end_user views expose only `redacted_unauthorized_count` and an opaque `redaction_code`, with no unauthorized id side-channel. |
| 仅有接口/原型/默认关闭/Fail-Closed 功能 | Prototype only; production HTTP/MCP plan views are not mounted. Unknown viewer rejected (`INVALID_VIEWER`). Non-integer or out-of-range `policy_generation` rejected (`INVALID_POLICY_GENERATION`). |
| 已完成的测试证据 | `DualViewCases` (3); OpenAPI draft vectors above; CI job `v21-wave0-boundaries`. |
| 未覆盖的测试场景 | Production HTTP/MCP plan views, end-to-end MCP tool redaction, and live authorization-source integration. |
| 与另一仓库的重复点 | No second policy engine was added. The existing production redaction module was left unchanged rather than forked. |
| 保留/扩展/迁移/废弃裁定 | Authorized scope only: keep as a sandbox prototype; `/v3` remains unmounted; production redaction stays as already implemented. Any decision to mount or replace production views is pending Owner signoff. |

### 5.3 IKC (intake / knowledge production prototype)

| 字段 | 内容 |
|---|---|
| 文件路径与代码入口 | `sandbox/v21_reuse_v1/ikc.py` (`IKCSandbox.submit_intake`, `submit_production`, `transition_*`, `publish_blue_green`). Draft OpenAPI: `/v3/ikc/intake-jobs`, `/v3/ikc/production-jobs`, `/v3/ikc/production-jobs/{job_id}/publish`. Unmounted. |
| 核心对象与数据表/存储文件 | In-memory `IntakeJob`, `KnowledgeProductionJob`, `PipelineVersion`, and `active_published_production_id` (blue-green). Reuses 9940818b idempotency/ingestion *semantics* in memory. Zero production DDL; no new Schema v6/v7 tables. |
| API / RPC / Event 契约 | OpenAPI draft IKC paths; write operations carry the draft `Idempotency-Key` rule described in `openapi-v3-draft.yaml`. Related vector: `V3-NEG-PARTIAL`. Pack inventory is in Stream E. |
| 当前权威写主 | Knowledge SDK is the write surface of this IKC *prototype only*. OpenBot remains Semantic Object write authority. No transfer of that authority is claimed. |
| 已实现且稳定功能 | Sandbox: idempotent intake replay, payload-conflict rejection, high-risk/strong-compliance forcing `whole_document_atomic_publication`, blue-green switch only after approval, illegal published-from-queued transition fail-closed. |
| 仅有接口/原型/默认关闭/Fail-Closed 功能 | Entire `/v3` IKC surface is an unmounted draft. `partial_available` is forbidden. High-risk / strong-compliance publication is atomic or denied. |
| 已完成的测试证据 | `IKCCases` (5) in `sandbox_cases.py`; related OpenAPI draft vector; CI job `v21-wave0-boundaries`. |
| 未覆盖的测试场景 | Production persistence, real pipeline workers, mounted HTTP, and formal T-01–T-27. |
| 与另一仓库的重复点 | No agent runtime, Bandit selector, or workflow platform was added. The prototype mounts existing ingestion semantics rather than a second production IKC. |
| 保留/扩展/迁移/废弃裁定 | Authorized scope only: keep as a zero-DDL sandbox/prototype; `/v3` unmounted; no Schema v7/v8/v9. Any production IKC migration or cutover is pending Owner signoff and is not authorized in this wave. |

### 5.4 KSG-Lite (Phase 0 validation plugin)

| 字段 | 内容 |
|---|---|
| 文件路径与代码入口 | `sandbox/v21_reuse_v1/ksg_lite.py` (`KSGLitePlugin.validate` / `bind`). Inspects existing `src/knowledge_sdk/governance/workflow.py` (`GovernanceMixin`) and `src/knowledge_sdk/governance/issues.py` (`IssueMixin`) operation names (`submit_for_review`, `approve_release`, `reject_release`, `publish_release`, `resolve_evidence_issue`) without editing those modules. Draft OpenAPI: `/v3/ksg/validations`. Unmounted. |
| 核心对象与数据表/存储文件 | In-memory `KSGDecision` (`allowed`, `reason_code`). No new production governance table. Production mixin classes are not modified. |
| API / RPC / Event 契约 | OpenAPI draft `/v3/ksg/validations`. Validation is a sandbox hook, not a new workflow event bus. Pack inventory is in Stream E. |
| 当前权威写主 | Existing Knowledge SDK governance mixins remain the production operation surface. KSG-Lite is a fail-closed validation plugin and does not execute governance writes by default. |
| 已实现且稳定功能 | Sandbox: operation-name mounting against the existing mixins; high-risk publish requires approval plus the atomic flag; stale `policy_generation` denied; optional proxy does not modify mixin classes. |
| 仅有接口/原型/默认关闭/Fail-Closed 功能 | Phase 0 plugin / unmounted `/v3` draft. Partial publication (`partial_available`) is denied. The plugin does not itself perform release writes. |
| 已完成的测试证据 | `KSGLiteCases` (5) in `sandbox_cases.py`; CI job `v21-wave0-boundaries`. |
| 未覆盖的测试场景 | Production governance persistence, end-to-end approval UI/API, and mounted `/v3/ksg` tests. |
| 与另一仓库的重复点 | No second workflow platform was added. The plugin binds to already-present operation names instead of reimplementing governance. |
| 保留/扩展/迁移/废弃裁定 | Authorized scope only: keep as a Phase 0 sandbox plugin; no production table changes; `/v3` unmounted. Promoting KSG-Lite into the production HTTP app is pending Owner signoff. |

### 5.5 Resource Registry (KnowledgeResource vs DataCapabilityRef)

| 字段 | 内容 |
|---|---|
| 文件路径与代码入口 | `sandbox/v21_reuse_v1/resources.py` (`KnowledgeResource`, `DataCapabilityRef`, `ResourceCapabilityBinding`, `validate_distinct`). Draft OpenAPI: `/v3/resources`, `/v3/resources/{resource_id}/bindings`. Unmounted. |
| 核心对象与数据表/存储文件 | In-memory dataclasses only. Resource types: `document`, `knowledge_base`, `agent_memory`, `materialized_snapshot`. Capability kinds: `structured_select`, `object_get`, `snapshot_read`. Handles must be `slot:`, `deleg:`, or `svc:` prefixes. No production registry table. |
| API / RPC / Event 契约 | OpenAPI draft resource and binding paths; `KnowledgeResource` is not `DataCapabilityRef`. Related contract surface also appears in the Controlled Data Bridge pack, inventoried in Stream E. |
| 当前权威写主 | Knowledge SDK is the write surface of this registry *prototype only*. OpenBot remains the enterprise data-gateway / Semantic Object authority. Tenant/user delegated handles do not move that authority to the SDK. |
| 已实现且稳定功能 | Sandbox: objects stay distinct; collapsed payloads rejected; secret handles rejected; bool/float `policy_generation` rejected; cross-tenant binding rejected. |
| 仅有接口/原型/默认关闭/Fail-Closed 功能 | Unmounted `/v3` prototype. Raw secrets, DSN-like handles, and unmatched capability shapes are rejected. Mode A/B/C production unlock is not authorized (see Stream E). |
| 已完成的测试证据 | `ResourceCapabilityCases` (5); related Controlled Data Bridge secret/mode vectors are in Stream E. |
| 未覆盖的测试场景 | Production registry persistence, live capability execution, and connector-backed bindings. |
| 与另一仓库的重复点 | No DB/ERP/CRM connector, Connector Vault, or Data Capability execution engine was added (12 prohibited capabilities). |
| 保留/扩展/迁移/废弃裁定 | Authorized scope only: keep the distinct-object prototype; no production DDL; no connector/execution-engine build. Production Controlled Data Bridge unlock remains unauthorized and pending Owner signoff. |

### 5.6 EDKI SemanticReference (read-only semantic_object_key)

| 字段 | 内容 |
|---|---|
| 文件路径与代码入口 | `sandbox/v21_reuse_v1/semantic_reference.py` (`SemanticReference`, `from_payload`, `write_physical`). Draft OpenAPI: `/v3/edki/semantic-references`. Unmounted. |
| 核心对象与数据表/存储文件 | In-memory `SemanticReference`: `tenant_id`, `semantic_object_key` (must start with `semobj:`), `concept_ids`, `policy_clause_ids`. No local Semantic Object catalog table and no dual-write store. |
| API / RPC / Event 契约 | OpenAPI draft EDKI semantic-reference paths; read-only `semantic_object_key` pointer plus concept/policy mappings. Pack inventory is in Stream E. |
| 当前权威写主 | OpenBot remains Semantic Object write authority. `semantic_object_dual_write_prohibited` remains true. The SDK prototype stores only a read-only reference. |
| 已实现且稳定功能 | Sandbox: accept a well-formed read-only binding; reject physical connector/credential fields (`SEMANTIC_WRITE_FORBIDDEN`). |
| 仅有接口/原型/默认关闭/Fail-Closed 功能 | `write_physical` always raises. Connector, DSN, host, credential, and similar fields in the payload are forbidden. `/v3` is unmounted. |
| 已完成的测试证据 | `SemanticReferenceCases` (2) in `sandbox_cases.py`; CI job `v21-wave0-boundaries`. |
| 未覆盖的测试场景 | Semantic Object catalog export (Team B VB-3), live OpenBot catalog sync, and any authorized migration of write authority (not authorized). |
| 与另一仓库的重复点 | No second Semantic Object store and no dual-write path were added. |
| 保留/扩展/迁移/废弃裁定 | Authorized scope only: keep as a read-only prototype; OpenBot remains write authority; dual-write remains prohibited; `/v3` unmounted; no Schema v7/v8/v9 or cutover. Any later migration of write authority is pending Owner signoff and is not authorized now. |

### 5.7 Stream D residuals not produced by Team A

- 「OpenBot 本地知识模块向 SDK 委派收口清单，与 Space Pre-v7 B2-2 124 项实审完全对齐」: Team B / OpenBot work. Team A did not invent or draft that list.
- Stream B extras (逐连接器区分生产可用驱动 vs Demo/Mock; 明确解锁 `knowledge-object-only` 所需的安全门禁) and Stream C extras (核实 AOR Stage 4 真实测试状态; 区分确定性探针 vs LLM-as-Judge 缺口): Team B. Team A did not write Stream B/C audit reports.
- Live CogniWeave `/v1` revocation wiring, Semantic Object catalog export (VB-3), and OpenBot-side Stream A–D reports remapped to official fields: Team B residuals. Team B stated they will re-issue Stream A/B reports after VB-4.

## 6. Stream E — 冻结版《跨系统接口契约清单》与兼容性测试矩阵

Stream E is **not** a section-7 10-field table. Per section 7 of the same v2.1 document, Stream E requires a frozen-form 《跨系统接口契约清单》 and a compatibility test matrix, to be brought under dual-repo CI gating.

Team A publishes that inventory from the already delivered tree `contracts/v21-reuse-v1/` at `02bf58738986bc7e22dfeafcb2911970d14f2588` (5 packs + `validate.py` + 51 vectors + OpenAPI draft + CI job `v21-wave0-boundaries`). The pack's own committed status remains `DRAFT_WAVE_V21_0_NOT_FROZEN` in `status.json`, and `validate.py` reports `DRAFT_CONTRACTS_VALIDATED_NOT_FORMAL_ACCEPTANCE` with `formal_acceptance: false`. This section is **not** a formal joint freeze with OpenBot. knowledge-sdk CI already runs `validate.py` and job `v21-wave0-boundaries`. OpenBot-side CI gating of these contracts is a Team B residual and is **not** claimed here.

`status.json` flags on that tree remain: `schema_v7_ddl_authorized=false`, `schema_v8_v9_ddl_authorized=false`, `final_alignment_frozen=false`, `prod_shadow_migration_cutover_authorized=false`, `semantic_object_dual_write_prohibited=true`, `duplicate_runtime_or_connector_build_prohibited=true`, `mounted_v3_runtime=false`, `formal_t01_t27=NOT_RUN_NOT_ACCEPTED`. Core `pyproject.toml` `dependencies` remain `[]`.

### 6.1 跨系统接口契约清单（已交付草稿；非双方正式冻结）

| 契约包 | 模式 / 草稿 | 向量（accept / reject） | 覆盖的跨系统表面 | 说明 |
|---|---|---|---|---|
| model-adapter | `model-adapter.schema.json` | 17 (8 / 9) | LLM / embed / rerank request and response; injection handles `slot:` / `deleg:` / `svc:`; `policy_generation` | OpenBot public execution, Fallback, future `models.embed` / `models.rerank` proxy, or a host-injected slot is the intended runtime. SDK is not the credential vault. Baseline `openai_embedder.py` / lexical `reranker.py` are allowlisted and unchanged. No paid client and no Model Provider/Vault/Fallback implementation were added. Public OpenBot proxy does not exist yet (Team B Stream A residual). |
| controlled-data-bridge | `controlled-data-bridge.schema.json` | 13 (3 / 10) | Mode A/B/C declarations; mandatory `policy_generation`, `masking_receipt`, `freshness_ts`, `tombstone`; Mode B row-level predicate | Tenant/user delegated handles only. OpenBot remains enterprise data gateway authority. Declaration validation only: no SQL engine, no connector vault. Unmatched mode Fail-Closed; Text-to-SQL forbidden; raw secrets forbidden. Mode A/B/C production unlock remains unauthorized. |
| memory-resource-bridge | `memory-resource-bridge.schema.json` | 8 (3 / 5) | Read-only memory discovery (`resource_type=agent_memory`); four-channel `RevocationPurgeReceipt` | Complements the Stream D sandbox revocation loop. Discovery is read-only. `purged` requires four success channel receipts. |
| ai-execution-trace | `ai-execution-trace.schema.json` | 6 (1 / 5) | Unified trace identity: `tenant_id`, `user_id`, `agent_id`, `trace_id`, `run_id`, `plan_id`, `policy_generation`, `cost_attribution` | Contract + vectors only. No new agent runtime was added. |
| openapi-v3-draft | `openapi-v3-draft.yaml` (OpenAPI 3.1) | 7 (3 / 4) | Draft `/v3/ikc/*`, `/v3/ksg/validations`, `/v3/resources`, `/v3/krdr/plans`, `/v3/edki/semantic-references`, `/v3/revocations`; `AuditPlanView` / `RedactedPlanView` | `/v3/*` is a draft and **must not** be mounted in the production HTTP app. Space APIs stay on `/v2/spaces`. Schema v6 is unchanged. |

Shared supporting files in the same pack (also in `v21-contract-manifest.json`): `validate.py`, `dto.py`, `dto.ts`, `check.ts`, `package.json`, `tsconfig.json`, `status.json`, `README.md`, plus the five `*.vectors.json` files and two schema/OpenAPI files above. Manifest algorithm: POSIX relative path, stable sort, SHA-256 of raw bytes; the manifest excludes itself, `node_modules/`, `ts-generated/`, `package-lock.json`, `__pycache__/`, `*.pyc`, and dotfiles. File count: 18. Manifest file SHA-256: `6da567e0f376fee7b6b2b033e6666cbd5eba7bc3d67b93089e49e6edb759906d`.

### 6.2 Compatibility test matrix

| 门禁 | 执行位置 | 断言 | 范围与限制 |
|---|---|---|---|
| `python contracts/v21-reuse-v1/validate.py` | Local and knowledge-sdk CI job `v21-wave0-boundaries` | 51 vectors (18 accept / 33 reject); manifest recomputed and compared; exits 0 with `formal_acceptance: false` and `status: DRAFT_CONTRACTS_VALIDATED_NOT_FORMAL_ACCEPTANCE` | Validates the isolated pack. Does **not** constitute formal Wave-V21-0 acceptance. |
| `openapi-spec-validator==0.9.0 --schema 3.1` on `openapi-v3-draft.yaml` | knowledge-sdk CI job `v21-wave0-boundaries` only | OpenAPI 3.1 structural validation | Job-only tool; not a core `pyproject.toml` dependency. |
| `npm ci --ignore-scripts` + `tsc -p tsconfig.json` + `node ts-generated/check.js` | knowledge-sdk CI job `v21-wave0-boundaries` | Strict TypeScript/Node vector check against the same 51 cases | `ts-generated/` and `package-lock.json` are excluded from the contract manifest. |
| unittest + pytest `sandbox/v21_reuse_v1/sandbox_cases.py` | knowledge-sdk CI job `v21-wave0-boundaries` | 25 cases, 0 skips: resources, IKC, KSG-Lite, semantic reference, revocation, dual-view, source shape | Sandbox closed loops, not T-01–T-27, and not a mounted `/v3` runtime test. |
| `python scripts/verify_v21_boundaries.py` | knowledge-sdk CI job `v21-wave0-boundaries` | `dependencies == []`; Schema v6 production migrations byte-identical to `9940818b`; 12 prohibited-capability scan; manifest recomputation; frozen M1 guard | Boundary / non-duplication gate, not functional acceptance of T-01–T-27. |
| `python docs/acceptance/v2.2-align-wave2/verify_frozen.py` | knowledge-sdk CI job `v21-wave0-boundaries` (and historical Wave2 jobs) | M1 frozen 28-asset tree unchanged | The v21 pack is isolated and must not rewrite those hashes. |
| OpenBot-side CI gating of `contracts/v21-reuse-v1/` | **Not delivered by Team A** | — | Team B residual. Do not read knowledge-sdk job `v21-wave0-boundaries` as dual-repo CI. |

## 7. v21-contract-manifest inventory for Team B recomputation

Team B should run `python contracts/v21-reuse-v1/validate.py` on the contract tree at `02bf58738986bc7e22dfeafcb2911970d14f2588` (this docs-only remap does not change those files) and compare `contracts/v21-reuse-v1/v21-contract-manifest.json` plus the SHA-256 of that manifest file. Algorithm: POSIX relative path, stable sort, SHA-256 of raw bytes, manifest excludes itself, `node_modules/`, `ts-generated/`, `package-lock.json`, `__pycache__/`, `*.pyc`, and dotfiles. The exact file hashes are in the manifest generated with that commit; do not treat an older local copy as authoritative. The published manifest file SHA-256 remains `6da567e0f376fee7b6b2b033e6666cbd5eba7bc3d67b93089e49e6edb759906d`.

## 8. Explicit non-claims

- T-01 through T-27 are **not** passed and were not run as formal acceptance.
- `FINAL_SPACE_AND_FAVORITES_ALIGNMENT.md` was **not** written.
- Schema v7 / v8 / v9 production migrations and cutover were **not** started.
- `/v3/*` is a draft and is **not** mounted in the production HTTP app. `/v2/spaces` and Schema v6 are unchanged.
- Wave-V21-0 is **not** self-declared formally accepted. Wave-V21-1 is **not** unlocked.
- The v2.1 baseline is **not** Owner-signed. `signoff_status` remains `READY_FOR_OWNER_SIGNOFF_AND_STREAM_A_E_AUDIT_CLOSURE`.
- Stream E is **not** a formal joint freeze, and OpenBot-side CI is **not** claimed to already gate these contracts.
- Team A did not write Stream B/C OpenBot audits and did not produce the B2-2 124-item delegation list.
