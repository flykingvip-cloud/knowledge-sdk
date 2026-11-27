# T-01..T-27 Sandbox Dry-Run Tracking Matrix

**Label: `DRY_RUN_SANDBOX_NOT_FORMAL_ACCEPTANCE`**

This matrix is a Wave-V21-2 (W2A-2) in-process tracking aid only. It does **not** constitute formal T-01..T-27 acceptance.

- `contracts/v21-reuse-v1/status.json` `formal_t01_t27` remains **`NOT_RUN_NOT_ACCEPTED`** (this wave did not edit `status.json` or any other file under `contracts/v21-reuse-v1/`).
- Formal surfaces required by the reserved plan — SQLite, non-superuser PostgreSQL `FORCE RLS`, mounted HTTP `/v2`, Python SDK production clients, and MCP — were **not** run.
- All exercises listed here are offline stdlib loopback / sandbox tests under `sandbox/v21_reuse_v1/`. `EXPERIMENTAL_V3_ENABLED` stays default false. `mount_production_http()` remains forbidden. No implicit network and no secrets.
- Reserved titles are taken from the candidate allocation in `docs/acceptance/pre-v7-space-alignment/FORMAL_TEST_PLAN_NOT_RUN.md` (branch `feat/space-alignment-v1-design-proto@4bed2a1c`, blob `b0a2787d…`). That document itself marks every ID `NOT_RUN_NOT_ACCEPTED` and warns that numbering must be reconciled during formal review.

Status vocabulary used below:

| Sandbox column | Meaning |
|---|---|
| `IN_PROCESS_DRY_RUN_ONLY` | A related in-process analogue was exercised in this wave's sandbox or loopback tests. **Not** formal acceptance. |
| `TRACKED_NOT_EXERCISED_IN_THIS_SANDBOX` | The reserved formal scenario has no honest in-process analogue in the Wave-V21 zero-DDL sandbox (it needs Space / Favorites / `/v2` / PG RLS / MCP / production migration drill). Tracked only. |
| Formal status (every row) | `NOT_RUN_NOT_ACCEPTED` |

## Official required chaos paths (must-cover)

These five paths are required by `WAVE_V21_1_JOINT_CLOSURE_AND_WAVE2_LAUNCH_ORDER` §3.1 / §5.1 W2A-2. They are implemented as dedicated dry-run loopback tests in `sandbox/v21_reuse_v1/dry_run_cases.py` and also have earlier unit coverage in `sandbox_cases.py` where noted.

| Required path | Reserved tracking IDs | In-process dry-run test | Result in sandbox | Formal status |
|---|---|---|---|---|
| High-risk IKC blue/green rollback and a ban on `partial_available` | T-16 (revocation/outbox rollback analogue), T-26 (rollback drill analogue) | `test_t16_high_risk_blue_green_rollback_and_partial_available_ban`, `test_t16_rollback_fails_closed_without_prior_or_approval`, `IsolatedIkcRollbackCases.test_direct_ikc_rollback_is_pointer_only` | Live pointer rolls back to the previous fully published job; both jobs stay `visibility=published` (no `partial_available`); first-publish rollback and unapproved high-risk rollback fail closed; `partial_available=True` raises `PARTIAL_PUBLICATION_FORBIDDEN` | `NOT_RUN_NOT_ACCEPTED` |
| KSG-Lite Phase 0 unapproved publish intercept | T-27 (approval-gating analogue), T-17 (policy-generation strictness) | `test_t27_ksg_unapproved_publish_intercept`, `test_t17_stale_policy_generation_fail_closed` | High-risk `publish_blue_green(..., approved=False)` raises `APPROVAL_REQUIRED`; job stays `awaiting_approval` / `hidden`; stale `current_policy_generation` is denied | `NOT_RUN_NOT_ACCEPTED` |
| Four-channel partial revocation with `purged=false` | T-16, T-23 (timeout / outage analogue) | `test_t16_four_channel_partial_revocation_purged_false` | A failed or timed-out channel yields `purged=false` with a still-verifiable receipt; all four channel names are present | `NOT_RUN_NOT_ACCEPTED` |
| `RetrievalPlan` dual-view redaction with zero leak (`redacted_unauthorized_count`) | T-09 (explicit deny / side-channel analogue) | `test_t09_retrieval_plan_dual_view_zero_leak` | `end_user` / `agent` views expose only `redacted_unauthorized_count` and an opaque code; `syn_secret_doc` and `ACL_DENY` do not appear in the serialized view; audit view keeps precise exclusions | `NOT_RUN_NOT_ACCEPTED` |
| `ControlledDataBridge` tombstone / Text-to-SQL denial (Fail-Closed, no free Text-to-SQL) | T-24 | `test_t24_controlled_data_bridge_tombstone_and_text_to_sql_denied` | Active tombstone → `UNAUTHORIZED`; `sql` / `query_kind=text_to_sql` → `TEXT_TO_SQL_FORBIDDEN` | `NOT_RUN_NOT_ACCEPTED` |

## Full reserved T-01..T-27 tracking matrix

| ID | Reserved formal scenario | Required formal surfaces | Sandbox dry-run analogue (in-process only) | Evidence | Formal status |
|---|---|---|---|---|---|
| T-01 | Explicit enterprise tenant and tenant boundary | SQLite + non-superuser FORCE-RLS PostgreSQL; HTTP/Python/MCP where applicable | Cross-tenant `ResourceCapabilityBinding` is rejected. This is **not** PG `FORCE RLS` or `/v2` tenant isolation. | `dry_run_cases.T01T27SandboxDryRunCases.test_t01_cross_tenant_binding_rejected`; `sandbox_cases.ResourceCapabilityCases.test_cross_tenant_binding_rejected` — `IN_PROCESS_DRY_RUN_ONLY` | `NOT_RUN_NOT_ACCEPTED` |
| T-02 | Flat Tenant-Space-KB, no parent | same | No Tenant-Space-KB tree exists in the Wave-V21 sandbox. | `TRACKED_NOT_EXERCISED_IN_THIS_SANDBOX` | `NOT_RUN_NOT_ACCEPTED` |
| T-03 | Same-org composite KB binding | same | No composite KB / Space binding model in this sandbox. Resource != Capability binding is a weaker distinct-object check only (see T-01). | `TRACKED_NOT_EXERCISED_IN_THIS_SANDBOX` | `NOT_RUN_NOT_ACCEPTED` |
| T-04 | Detach not archive and same-home reattach | same | No detach/reattach Space-KB API in this sandbox. | `TRACKED_NOT_EXERCISED_IN_THIS_SANDBOX` | `NOT_RUN_NOT_ACCEPTED` |
| T-05 | Employee personal owner boundary | same | No personal Space / owner model in this sandbox. | `TRACKED_NOT_EXERCISED_IN_THIS_SANDBOX` | `NOT_RUN_NOT_ACCEPTED` |
| T-06 | Enterprise admin no private-content shortcut | same | No admin / private-content Space path in this sandbox. | `TRACKED_NOT_EXERCISED_IN_THIS_SANDBOX` | `NOT_RUN_NOT_ACCEPTED` |
| T-07 | Two same-tenant collaboration groups isolation | same | No collaboration-group / team Space isolation in this sandbox. | `TRACKED_NOT_EXERCISED_IN_THIS_SANDBOX` | `NOT_RUN_NOT_ACCEPTED` |
| T-08 | Eight independent action grants | same | No eight-grant action matrix in this sandbox. | `TRACKED_NOT_EXERCISED_IN_THIS_SANDBOX` | `NOT_RUN_NOT_ACCEPTED` |
| T-09 | Explicit Deny precedence | same | Unauthorized resources are excluded from end-user / agent `KnowledgeRetrievalPlan` views; only `redacted_unauthorized_count` is exposed. This is a dual-view deny analogue, not Layer-2 Space Gate + DocumentACL formal deny precedence. | `test_t09_retrieval_plan_dual_view_zero_leak`; `sandbox_cases.DualViewCases` — `IN_PROCESS_DRY_RUN_ONLY` | `NOT_RUN_NOT_ACCEPTED` |
| T-10 | Agent Space ceiling | same | No Agent `allowed_space_ids` ceiling is implemented here. `AIExecutionTraceContext` seven-key hops are a protocol analogue only (W2A-1 golden group G2) and do not enforce a Space ceiling. | `TRACKED_NOT_EXERCISED_IN_THIS_SANDBOX` (trace hops exist but are not a T-10 formal substitute) | `NOT_RUN_NOT_ACCEPTED` |
| T-11 | KB fine-grained consumption scope | same | No KB consumption-scope formal surface. | `TRACKED_NOT_EXERCISED_IN_THIS_SANDBOX` | `NOT_RUN_NOT_ACCEPTED` |
| T-12 | Knowledge-file scope | same | No knowledge-file ACL formal surface. | `TRACKED_NOT_EXERCISED_IN_THIS_SANDBOX` | `NOT_RUN_NOT_ACCEPTED` |
| T-13 | Deliverable scope | same | No deliverable-scope formal surface. | `TRACKED_NOT_EXERCISED_IN_THIS_SANDBOX` | `NOT_RUN_NOT_ACCEPTED` |
| T-14 | Folder scope | same | No folder-scope formal surface. | `TRACKED_NOT_EXERCISED_IN_THIS_SANDBOX` | `NOT_RUN_NOT_ACCEPTED` |
| T-15 | Current User intersection and current profile | same | No `User ∩ Agent` / current-profile formal intersection. | `TRACKED_NOT_EXERCISED_IN_THIS_SANDBOX` | `NOT_RUN_NOT_ACCEPTED` |
| T-16 | Transactional revocation/outbox rollback | same | Four-channel revocation (`purged=false` on partial failure) plus IKC blue/green pointer rollback with outbox events `blue_green` / `blue_green_rollback`. In-memory only; not a transactional PG outbox formal drill. | `test_t16_*`; `IsolatedIkcRollbackCases`; `sandbox_cases.RevocationCases` — `IN_PROCESS_DRY_RUN_ONLY` | `NOT_RUN_NOT_ACCEPTED` |
| T-17 | Current policy generation strictness/staleness | same | KSG-Lite rejects stale `current_policy_generation` and non-integer / out-of-range policy values. Not a mid-task HTTP `POLICY_GENERATION_STALE` formal suite. | `test_t17_stale_policy_generation_fail_closed`; `sandbox_cases.KSGLiteCases.test_stale_policy_denied` — `IN_PROCESS_DRY_RUN_ONLY` | `NOT_RUN_NOT_ACCEPTED` |
| T-18 | Future HTTP independent-version compatibility | same | Production HTTP `/v3` stays unmounted; `mount_production_http()` is forbidden even when the experimental flag is true. This is a boundary assertion, not a version-compat formal suite. | `sandbox_cases.LoopbackServiceCases.test_experimental_v3_defaults_false_and_never_mounts_http` — `IN_PROCESS_DRY_RUN_ONLY` (boundary only) | `NOT_RUN_NOT_ACCEPTED` |
| T-19 | Future Python candidate protocol compatibility | same | Frozen contract vectors (`validate.py` 51/51) and W2A-1 interop harness / golden fixture are protocol dry-runs, not a formal independent Python client-compat gate. | `interop_cases.GoldenInteropCases`; `python3 contracts/v21-reuse-v1/validate.py` — `IN_PROCESS_DRY_RUN_ONLY` | `NOT_RUN_NOT_ACCEPTED` |
| T-20 | Future MCP candidate policy compatibility | same | No MCP server or policy-compat suite is exercised in this sandbox. | `TRACKED_NOT_EXERCISED_IN_THIS_SANDBOX` | `NOT_RUN_NOT_ACCEPTED` |
| T-21 | External source missing assertion | same | Four-channel `status=missing` blocks `purged`; Mode C unknown `snapshot_id` fails closed with `VALIDATION_ERROR`. Not an external connector missing-assertion formal test. | `sandbox_cases.RevocationCases.test_missing_or_timeout_blocks_purged` — `IN_PROCESS_DRY_RUN_ONLY` (partial analogue) | `NOT_RUN_NOT_ACCEPTED` |
| T-22 | External expired assertion | same | No dedicated external-expiry / freshness formal assertion beyond tombstone `revoked_at` handling (covered under T-24). | `TRACKED_NOT_EXERCISED_IN_THIS_SANDBOX` | `NOT_RUN_NOT_ACCEPTED` |
| T-23 | External provider outage | same | Channel `timeout` blocks `purged=true`. Not a paid-provider or network-outage formal drill (transports stay in-process). | `test_t16_four_channel_partial_revocation_purged_false` — `IN_PROCESS_DRY_RUN_ONLY` (timeout analogue) | `NOT_RUN_NOT_ACCEPTED` |
| T-24 | External revocation/tombstone/cursor | same | Controlled Data Bridge active tombstone → `UNAUTHORIZED`; free Text-to-SQL / `sql` → `TEXT_TO_SQL_FORBIDDEN`. No cursor-pagination formal surface. | `test_t24_controlled_data_bridge_tombstone_and_text_to_sql_denied`; W2A-1 golden group G5 — `IN_PROCESS_DRY_RUN_ONLY` | `NOT_RUN_NOT_ACCEPTED` |
| T-25 | Polymorphic favorite current-ACL hydration | same | No Favorites / polymorphic ACL hydration in this sandbox. | `TRACKED_NOT_EXERCISED_IN_THIS_SANDBOX` | `NOT_RUN_NOT_ACCEPTED` |
| T-26 | Future reviewed migration/rollback drill and security monotonicity | same | IKC high-risk blue/green rollback (pointer only, no partial publication) plus the frozen Schema v6 / 709-file / M1-28 zero-drift gates. Not a reviewed Schema v7 / production migration drill. | `test_t16_high_risk_blue_green_rollback_and_partial_available_ban`; `scripts/verify_v21_boundaries.py`; `docs/acceptance/v2.2-align-wave2/verify_frozen.py` — `IN_PROCESS_DRY_RUN_ONLY` | `NOT_RUN_NOT_ACCEPTED` |
| T-27 | Personal-sharing/offboarding approval gating and full reviewed acceptance | same | KSG-Lite Phase 0 intercepts unapproved high-risk publish and unapproved high-risk rollback. This is not personal-sharing, offboarding, or full reviewed formal acceptance. | `test_t27_ksg_unapproved_publish_intercept`; `test_t16_rollback_fails_closed_without_prior_or_approval` — `IN_PROCESS_DRY_RUN_ONLY` (approval-gating analogue only) | `NOT_RUN_NOT_ACCEPTED` |

## Counts (sandbox dry-run only)

| Category | Count |
|---|---|
| Reserved formal IDs in this matrix | 27 |
| Rows with an honest in-process analogue (`IN_PROCESS_DRY_RUN_ONLY`) | 11 (T-01, T-09, T-16, T-17, T-18, T-19, T-21, T-23, T-24, T-26, T-27) |
| Rows tracked but not exercised in this sandbox | 16 (T-02..T-08, T-10..T-15, T-20, T-22, T-25) |
| Rows formally accepted | **0** |

How to run the dry-run tests (repo root on `PYTHONPATH`):

```
PYTHONPATH=src:. python -W error::ResourceWarning -m unittest discover -s sandbox/v21_reuse_v1 -p '*cases.py' -v
```
