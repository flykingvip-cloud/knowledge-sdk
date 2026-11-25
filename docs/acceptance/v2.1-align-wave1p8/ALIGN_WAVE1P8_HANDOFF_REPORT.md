# Align-Wave1.8 handoff — SDK-23 only

## 1. Branch, source baseline and protected refs

- Sole writable branch: `feat/align-wave1p8-pre-m2-foundation`.
- Exact semantic source baseline: `07f5d39f05ef4c7952be48b83025b9c86ea2458e`.
- Implementation revision before this evidence-only commit: `10d584f921135714af66e62247346fdee9cb7714`.
- Resolve the **final delivery revision**, exact matching run, job timings and statuses using the accompanying `FINAL_RESOLVED_RECEIPT.md`. They are deliberately resolved after this commit; a commit cannot contain its own hash. This report alone is **not** a CI-success certificate.
- The directive's old-branch SHA is historical, not current: earlier explicit owner authorization had already pushed the timeout-only commit `0d2f172c2ca1c79483257953b5388098b7cdacaf` before the subsequent stop/freeze instruction. This wave branches from **07f5d39f**, does not inherit that timeout change, and does not rewind or append to the old branch.

Read-only remote refs verified before push (CST / Asia/Shanghai):

| Protected ref | Actual immutable value |
|---|---|
| `feat/align-wave1p5-m1-readiness` | `0d2f172c2ca1c79483257953b5388098b7cdacaf` |
| `main` | `b953c9922cc1096e0e88455dab6746c01a9d27f9` |
| `v2.0.0` annotated tag object | `4afc1d71f9f5583d93c28f3f4380544a4e5fcc46` |
| `v2.0.0^{}` | `b953c9922cc1096e0e88455dab6746c01a9d27f9` |
| `feat/align-wave1-core-compat` | `60b6436ed9fccb4b49ae32e30f1664412e505888` |

```sh
git rev-parse HEAD
git log --reverse --format='%H %s' 07f5d39f..HEAD
git merge-base --is-ancestor 07f5d39f HEAD
git ls-remote origin refs/heads/main refs/heads/feat/align-wave1p5-m1-readiness refs/heads/feat/align-wave1-core-compat refs/tags/v2.0.0 'refs/tags/v2.0.0^{}'
```

## 2. CI: old four jobs → 22 independent standard-runner jobs

`CI_STEP_MAPPING.json` contains the **complete original step dictionaries**, command text, arguments, working directories, conditions, matrix, inherited environments and PostgreSQL service configuration, plus each destination. Programmatic comparison confirmed each unsplit old step dictionary is present exactly; all six split golden command lines are byte-identical as YAML values. No duplicate original gate was removed.

Both original matrix pairs remain **Python 3.9 / ubuntu-22.04** and **Python 3.12 / ubuntu-24.04**, `fail-fast: false`, `fetch-depth: 0`. Global `PYTHONPATH=src`; former HTTP jobs retain `PYTHONPATH=src:.`. Every job has `timeout-minutes: 30`, never 60. Every PG-bearing job gets its own pgvector:pg17 service and the original non-superuser / NOBYPASSRLS provisioning and isolated fixture database. In particular, **full optional unittest and pytest remain real-PG suites**, not silent SQLite substitutes.

| Old `http-and-package` step | New job family (each expands to two matrix jobs) |
|---|---|
| Full strict-warning unittest | `unit-suite` |
| Full strict-warning pytest | `pytest-suite` |
| `python -m build`, extracted-wheel/RECORD/AST/zero-dependency `verify_package.py dist/*.whl` | `package-suite` (no database consumed) |
| SQLite full115 / legacy75 / legacy100 | `golden-1` / `golden-2` / `golden-3` |
| PostgreSQL full115 / legacy75 / legacy100 | `golden-4` / `golden-5` / `golden-6` |
| Bare `validate_assets.py`, `validate_m1_manifest.py`, Node22, locked npm ci, both strict tsc commands, all303 Node assertions | `contracts-ts-and-docker-sandbox` |
| Actual dual-mode non-root sandbox probe, runtime image probe, both always-upload artifact steps | Same contracts job; original Python3.12 conditions unchanged |
| Old stdlib `core`: Python `-S -W error::ResourceWarning` full unittest and full115 golden | `core` unchanged, both matrix jobs |

The directive's `validate_alignment_contracts.py` is a conceptual name; the actual frozen executable is `contracts/validate_assets.py`. It is retained **bare and unchanged**, not replaced by a weaker wrapper. All Docker `--require` flags, signed authentication, readonly/non-root checks, all six golden modes, official OpenAPI validator, wheel verification and manifest checks remain.

Historical evidence:

- [45573187717](https://github.com/flykingvip-cloud/knowledge-sdk/actions/runs/45573187717), source `5775d424f112940199ff5cd292be1b9fc270d2bc`: four jobs success (earlier smaller contract scope).
- [45589941009](https://github.com/flykingvip-cloud/knowledge-sdk/actions/runs/45589941009), exact source07: core jobs **70s / 48s**, overloaded HTTP jobs **1816s / 1817s**, cancelled during combined golden step. Python3.9 full unittest was **532s**, pytest **533s**; later gates were not reached. Cancellation is not success, and no estimated 34-minute figure is represented as a measured completed job.
- Final exact-SHA CI link, all22 statuses, step coverage and actual measured durations are in `FINAL_RESOLVED_RECEIPT.md`. Exit gate: **all jobs success and each <1080s**, target <900s; any failure remains explicitly blocking. No paid runners, deployment, publishing, force push or added API polling loops.

## 3. Five task deliveries and zero-disturbance proof

1. **CI**: `.github/workflows/tests.yml`; original12 archived byte-for-byte at `docs/architecture/knowledge-sdk-alignment/12_WAVE1P8_PRE_M2_FOUNDATION_DIRECTIVE.md` (SHA256 `daa48b8853d0849b1df812ee0b87228ff57364e10ae41f90afb9fa330a096949`); complete step mapping above.
2. **Ingestion / isolation**: `ingestion/parsers/{__init__,builtin}.py` bounds raw parser input at existing32MiB; strict CSV rejects truncation/oversized fields as `ValidationError`; malformed UTF-8 including surrogate-string ingest is structured failure. `ingestion/chunkers/fixed.py` validates integral bounds and omits whitespace-only chunks without changing offsets. Tests cover large single paragraphs, nested Markdown tables/headings, multiline CSV, all Python29 whitespace points, internal U+FEFF, NFC mixed CJK/Latin, empty input and limit violations. Existing leading UTF-8 BOM parsing semantics are unchanged; semantic fingerprint normalization preserves U+FEFF.
3. **Pure internal primitives / resource close**: `contracts/idempotency.py` supplies strict sorted JSON UTF-8 SHA256, `(tenant, method, canonical_path, key)` claims, NEW / REPLAY_EXACT / CONFLICT_PAYLOAD_MISMATCH / IN_PROGRESS, isolated copies, atomic thread-safe memory TTL and expired-worker fencing. `contracts/ingestion_jobs.py` supplies all seven states, immutable payloads, explicit legal transitions, revision fencing, bounded explicit failed→queued retry, cancellation races and idempotent submission. No persistence or automatic write retry. `client/http_client.py` closes HTTPError streams even for malformed/non-object/error JSON and health failures; network exceptions allocate no response to close.
4. **Three-protocol security**: `tests/foundation/test_cross_protocol_parity.py` drives real Local client, signed loopback `/v1`, and **all four MCP tools**. Eight requested scenario families include User∩Agent / Purpose, scope and cross-tenant / robot binding, explicit Deny and failing redaction hook, stale generation, live task/snapshot revocation, excerpt tamper, L1 and L2 approval/publication/rollback, archive/restore with current ACL. Real profile/request budgets clamp snapshots and MCP pack delivery. Tamper's documented surface-specific vocabulary is preserved: Local/HTTP `TamperedExcerptError`, MCP `current_status=tampered`; no invented `/v2` wire evidence.
5. **Observability / E2E**: `audit/telemetry.py`, `client/local.py`, `server/{app,operations}.py`; core ingest/search/retrieve and HTTP emit fixed-schema JSON with generated request_id, **SHA256-pseudonymized tenant_id**, registered route/operation, status, latency and bounded error code. No URLs, queries, request IDs supplied by callers, raw identities, headers, content, exception text or tokens are serialized. Authenticated `/metrics` Prometheus counters add denial/revocation denials and search latency; exact old `/v1/metrics` JSON counters remain compatible. Existing principal / User∩Agent / metrics_admin authorization is retained. `/v1/ready` remains a real DB+Schema5 check and fails503 on closed storage or actual wrong version.

New tests / support (30 unittest methods, parameterized sub-assertions additional):

- `tests/foundation/test_primitives.py`:12 methods (all49 state-pairs, TTL, response copies, 16-way atomic claims, cancellation revision race, retries, strict JSON, HTTP error closes).
- `tests/foundation/test_ingestion.py`:3 methods.
- `tests/foundation/test_dual_engine.py`:5 methods, including **actual SQLite vs PostgreSQL** per-field equality of chunk IDs / boundaries / normalized hashes / anchor coordinates (only nondeterministic timestamps excluded), independent connections for **three tenants × three CRUD/update/rollback/reindex/search/archive/restore rounds**, WAL and non-superuser FORCE RLS assertions, plus two full lifecycle E2Es.
- `tests/foundation/test_cross_protocol_parity.py`:4 methods (two per engine).
- `tests/foundation/test_operations.py`:6 methods (two engines × full captured-log negatives, actual DB/schema probes, metrics current-actor authorization / denial / revocation / latency).
- `tests/foundation/helpers.py`: existing bounded ephemeral-loopback helper reuse; no fixed production ports.

`update_document` and `archive_document` are directive business names: the actual existing SDK methods are version-appending `ingest(..., doc_id=...)` and `archive(...)`, with `restore(...)`; no fictitious API was added.

```sh
python3 scripts/wave1p8/verify_scope.py
git diff 07f5d39f05ef4c7952be48b83025b9c86ea2458e -- src/knowledge_sdk/storage/migrations.py tests/benchmark docs/architecture/knowledge-sdk-alignment/contracts docs/architecture/knowledge-sdk-alignment/m1-freeze-manifest.json docs/architecture/knowledge-sdk-alignment/M1_DECISION_PACKAGE.md pyproject.toml
python3 docs/architecture/knowledge-sdk-alignment/validate_m1_manifest.py
python3 docs/architecture/knowledge-sdk-alignment/contracts/validate_assets.py
git diff --stat 07f5d39f..HEAD
```

Before final push: frozen diff **0 bytes**, all28 hashes verified, original00–10 unchanged, dependencies `[]`; manifest pending / freeze false. The complete file delta is reproducibly obtained by the last command and resolved in the final receipt. Tests generate old process-log artifacts; only this run's generated changes are preserved outside the repository then restored byte-for-byte, never committed. Pre-existing untracked `reports/` is left untouched.

## 4. Actual tests, protocol parity, lifecycle and observability evidence

Local box evidence is under `/workspace/align-wave1p8-task-inputs/` (durable files, not an ephemeral build cache):

- New foundation **30/30** passed with a real owned PostgreSQL17+pgvector, role NOSUPERUSER/NOBYPASSRLS, and SQLite. After final telemetry assertions, operations + parity **10/10** passed again; real revoked-task denial increments metrics.
- Python stdlib `python3 -S -W error::ResourceWarning -m unittest discover -s tests -t . -v`: **1017 run, 691 pass /326 optional skips**,0 failures. Unmodified stdlib golden **115/115**; security_assertion_failures0, implicit_model_calls0.
- Local full strict unittest: **1017 run,1009 pass /8 skips**,372.012s; pytest: **1009 pass /8 skips**,572 subtests,366.38s, **0 ResourceWarning**, one pre-existing third-party StarletteDeprecationWarning (not suppressed). All six unmodified golden modes pass: SQLite115/75/100 in6.239/5.720/6.076s; PostgreSQL115/75/100 in273.696/262.262/270.560s, security failures0 and implicit model calls0. Final exact-SHA CI remains authoritative and is resolved in the final receipt. Initial local full runs lacked the separate sandbox DSN, so the four sandbox tests were separately rerun **4/4 pass** against this wave's own initialized fixture DB. No live Qdrant or paid model was enabled; its three optional tests remain genuine skips.
- Bare asset validator: official OpenAPI validator **PASSED**,118 negative probes,23 paths,40 schemas,7 hash /4 HMAC /8 rollback /12 policy /10 minimum-slice vectors. Manifest **28/28**,0 signoffs, freeze false.
- Frozen TypeScript: real strict noEmit + strict executable compile + Node: **303 assertions**, all7 hash and4 HMAC vectors, Python29 whitespace and U+FEFF preservation passed.
- Actual wheel build and extracted-wheel RECORD/AST/zero-dependency selfcheck pass. Local `dist/` contained a pre-existing additional version; the local verifier used the explicit newly built1.2.0 wheel rather than deleting someone else's output. Clean CI preserves the original `dist/*.whl` command unchanged.
- Full captured root-log stream negatives test document body/excerpt markers, title, emails, tenant and actor PII, query/path sentinels, raw HMAC secret/signature and Bearer token. Every emitted record is parsed as JSON and allowlisted field-set checked, not merely selected fields inspected.
- Real ready tests mutate only isolated test-DB schema-version *data* / SQLite user_version then restore it; closed connection and mismatched version both503, restored healthy dependency200. This is fault injection, not a DDL/migration change.
- Protected Prometheus tests: unsigned401, insufficient role403, stale/inactive metrics administrator401, signed current actor200. No resource/tenant/query labels. Revocation metric counts HTTP revocation **denials**, not a claim that already-disclosed text can be erased.
- Actual Docker engines are unavailable in this box; **no local Docker pass is claimed**. The unmodified `--require` dual-engine non-root/readonly sandbox and actual runtime image probes must execute successfully on the final CI Python3.12 job; see receipt and CI artifacts.

Full lifecycle per engine is real: private space → member grant → ingest → search → reference verification → version update → content/filename-only rollback with current ACL/rights preserved → archive/no search → restore/current ACL → issue → evidence pack export → valid audit chain. Loopback uses fresh OS-assigned ports, offline hash embedding, owned temp databases only.

## 5. M1 governance and disclosed limits

**M1 remains pending_joint_signoff; freeze_authorized=false. This is Align-Wave1.8, NOT Wave2 / M2 Integration Ready.** No Schema6, table/column addition, physical job store, `/v2/*` runtime route, purge, P3 graph/ontology/vertical pack, enterprise or StratAI integration, deployment or package publishing is implemented or authorized here. Frozen docs/contracts and115 golden sources are untouched.

Initial split run45602151234 exposed the existing mandatory source-style gate: the new telemetry module lacked `from __future__ import annotations`. A scoped corrective commit adds that line, rechecks the unchanged isolation test, and strengthens all-four-tool L2 published/rollback parity plus 16-way idempotent job submission. No test is removed or suppressed; the failed initial run is not relabeled as success. The extra corrective commit is retained honestly rather than rewriting pushed history.

The new store protocols and in-memory reference implementations are internal preparation only: process restart loses state, TTL eviction is not durable exactly-once, no worker/scheduler or production persistence is claimed. Future canonical-path adapters must supply the trusted exact target; this primitive does not decode/reorder percent escapes or invent universal numeric cross-language canonicalization. No cross-request actor cache or retrieval-engine optimization was introduced.

Document11 was **not supplied**; none was fabricated and its absence is not treated as a blocker to the explicitly supplied12. Old branch at0d2 is accurately disclosed above and retained unchanged. SDK-21/22, all protected refs and unrelated working outputs remain untouched.

Delivery is accepted only with an accompanying exact final-SHA receipt proving all22 jobs success and each <18 minutes. Any failure, unexpected skip or ResourceWarning must be reported as a real exit blocker, not bypassed or retroactively relabeled as green.
