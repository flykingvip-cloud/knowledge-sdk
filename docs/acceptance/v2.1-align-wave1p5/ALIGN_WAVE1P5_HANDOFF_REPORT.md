# SDK-22 Align-Wave1p5 M1 Readiness — Handoff

## 1. Scope and implemented deliverables

Owner t58u authorizes readiness work only, not joint M1 freeze, Wave2 or any
production/Enterprise/StratAI integration. Baseline is exact
`60b6436ed9fccb4b49ae32e30f1664412e505888`; feature branch is
`feat/align-wave1p5-m1-readiness`. No main/tag/version/schema/production change.

- Task0: rollback audit explicitly states content+filename-only and preserved
  current security. Runtime v1 return fields unchanged. Historical ACL/rights,
  arbitrary old metadata and L2 publication are never resurrected. See
  TASK0_ROLLBACK_AUDIT_PROVENANCE.json and dual-engine regressions.
- Task1: M1_DECISION_PACKAGE.md and pending m1-freeze-manifest.json cover D1–D7
  with options/tradeoffs/migration/dissent/owner/evidence fields. Checker success
  means WELL_FORMED_PENDING, freeze_authorized:false, zero signatures—not approval.
- Task2: SDK-only SQLite/PG sandbox, two fake tenants/three space classes,
  explicit Deny, versions/archive, human-vs-Agent intersection counterexample.
  Nonroot/read-only app, mounted ephemeral0600 key, no dev/demo/auth bypass.
  Seed rejects unknown/nonempty/diverged/forged-receipt schemas before migration;
  idempotence reads only. PG role is NOSUPERUSER/NOBYPASSRLS with FORCE RLS;
  current-v5 bootstrap inherits fixture-schema ownership, NOT DML-only least
  privilege. URI reference mapping has no runtime dependencies or authority
  grants: strict typed IDs/escaping, two-way uniqueness, retained section metadata.
- Task3: identity-only single-request memo under the existing lock+transaction,
  fresh entry/vector/rerank/calibration/final checks, principal-write invalidation;
  policy/redaction/profile/task/rank decisions remain uncached. Real independent
  PG connections/reentrant mutation/task-purpose+org tests fail closed. KB archive
  is analysis only: no current lifecycle field; JSON storage means a physical
  column is not logically inevitable, but any reviewed column/index design is
  future Wave2/Schema6. No secret JSON marker or archive-all-children workaround.

## 2. Actual validation and evidence

- Full strict stdlib: **966 total,654 passed,312 optional skips,0 failures/ResourceWarnings**.
- Full optional unittest: **966 total,962 passed,4 skips,0 failures/ResourceWarnings**.
- Full pytest: **962 passed,4 skipped,264 subtests**,0 failures/ResourceWarnings;
  one pre-existing optional Starlette TestClient deprecation (not hidden).
- **24 new readiness tests** beyond Wave1's942; final additional assertions cover
  same-user reentrant task purpose/tenant binding and real fixture store cleanup.
- Both actual SQLite and owned PostgreSQL17/pgvector/RLS: **115/115**, legacy
  **75/75 and100/100**, no golden/source/assertion changes. All12 tracked
  benchmark files hashed, including g6/g7_g8/g9 and the60 original runner cases.
- Actual Python/HTTP/MCP Wave1 groups111/114, M2 runtime9-variant groups80 per
  engine and M1 HMAC/OIDC six-family groups109 per engine. Known provider
  boundaries instrumented:0 attempts; PG non-superuser/RLS verified.
- Real locked TypeScript5.9.3: noEmit typecheck + compile + executed Node tests,
  **44 assertions**. Official OpenAPI3.1 validator passed;29 schemas,23 paths,
  six fixtures,37 negative probes. Pending manifest is not freeze authorization.
- Build, all inherited/current wheel RECORD checks, AST Python3.9 and extracted
  `-S -W error::ResourceWarning` audit/request-lifetime smoke passed. Wheel
  contents match current core source byte-for-byte; mandatory dependencies=[].
- All physical schema columns/indexes/RLS/policies digests unchanged at5.
  See VALIDATION_SUMMARY.json plus the copied actual logs/JSON receipts.
- Full-suite start revision is recorded in VALIDATION_SUMMARY.json; subsequent
  fixture replay-initialization refusal cleanup has real dual-engine focused
  evidence. Final CI at exact delivered HEAD is required for all later fixture
  routing changes. Local Docker is **BUILD_NOT_RUN**, never a fabricated pass.

L4 is draft-asset selfcheck + NO_UI_CHANGES; no new browser run claimed.
L5 is handoff compliance only; independent review remains PENDING.
Original benchmark sources/assertions, dependencies=[], v5 DDL, package1.2.0
and protected refs are unchanged. No G10, /v2 runtime or schema6 work.

## 3. Fixed-set performance/quality — honest mixed latency

Same physical SQLite corpus/index and retained PG/pgvector schema, frozen M2
24 evaluation families/config/window100/threshold0.6. One warmup/five repeats,
120 samples per arm/engine; protected pool/order/hash, corpus/index/config and
all repeated quality aggregates identical. Before evidence predates first
extension commit. Actual original file-completion wallclock timestamps and
per-search perf_counter durations are disclosed separately; the inherited
harness did not capture wallclock start/end, so none are fabricated.

| Engine/arm | P50 before→after ms | P95 before→after ms | Mean before→after ms |
|---|---:|---:|---:|
| SQLite plain RRF |1.9081→1.9462|2.2122→2.4843|1.6662→1.7728|
| PG plain RRF |9.1808→9.3666|13.5552→13.4263|9.2051→9.2061|
| SQLite enhanced |16.2855→16.6667|18.6098→19.6041|12.2733→12.9984|
| PG enhanced |75.5429→63.0749|84.4657→70.8976|56.9013→48.4227|

Plain-P50 recovery is NOT demonstrated (+.0381/.1858ms); SQLite enhanced also
slightly slower (+2.34%). PG enhanced improves16.50%. No repeated metric chase,
quality/threshold/window tuning or reduced security/candidate work. Profile
principal checks1913→962, policy audits1580 unchanged. Small fixed-set timings
are noisy, not production SLA claims. Candidate NDCG/MRR1.0 and refusal24/24,
false-refusal0, ACL0, instrumented model-boundary attempts0 on both engines.
Baseline NDCG SQLite.774457/PG.794961; all quality is unchanged vs Wave1.

## 4. Commits, CI and residual decision gates

Runtime/performance-tested source: `841f67ed610205889fc56c7185d3b53eab1e7173`
(the later commits change fixture/contract/test/evidence assets, not core source).
Frozen final local full-suite revision: `4b59d48cec5c9bead6073b1f9fb45fa2f19cbb8b`.
Logical commits are visible in branch history: audit semantics, seven pending
M1 decisions, sandbox+locked TS assets, request-only identity reuse, strict
bidirectional URI fix,0600-key compatibility, startup/shutdown cleanup, explicit
reentrant task tests and actual-CI network fix. No history rewrite.

Initial CI `45569559720` on841f67e is **NOT_GREEN**: both core jobs passed;
3.12 HTTP unit/pytest/golden/contracts passed, then actual sandbox host readiness
failed. Its downloaded runtime artifact proves seed success and uvicorn startup,
not host reachability. The new frontend fixes the observed routing boundary;
only a real later image run can confirm it. No control or test was disabled.

The final full commit SHA and actual four-job CI run URL/status are supplied in
`/workspace/knowledge-sdk-align-wave1p5-artifacts/final-receipt.json` alongside this
handoff, and must match `git rev-parse HEAD` and the remote feature ref. This
committed report cannot embed its own future commit hash/run identifier without
changing that identifier. CI_PROVENANCE.json retains the failed first run
honestly; it is never substituted for the final matching-head receipt. A missing
or non-green final receipt means CI acceptance remains incomplete.

Protected refs: main `b953c9922cc1096e0e88455dab6746c01a9d27f9`;
v2.0.0 annotated object `4afc1d71f9f5583d93c28f3f4380544a4e5fcc46`, peeled main;
Wave1 baseline60b6436, M2d153295, M169b6c98 remain untouched.

- Joint M1 signoff is pending; no invented architect/TeamB/owner signatures.
  t58u scope authorization is not joint freeze. Q3-M2 independent review remains
  historical PENDING, distinct from owner-provided Q3-M1 t54u review.
- Upper strategy/protocol copies are not handed to this environment; no new
  service, grant or external contact was sought. Supplied alignment source docs
  remain original bytes. Do not claim absent upper-spec compliance.
- D6 package1.2.0 vs annotated v2.0.0 drift is documented, not silently changed.
- Plain RRF latency is honestly not recovered; reviewers decide acceptability.
- Local Docker unavailable; CI proof is a separate actual result, never a local
  pass. No production deployment, live model/embedding or paid call occurred.

## 5. Reviewer handoff and safety closure

All box fixtures use the new owned socket-only PG17 cluster at55479 and
unique schemas; no existing DB/service/container was touched. Cleanup status
and exact final remote refs are recorded in the accompanying final receipt;
absence of cleanup confirmation must not be read as complete. CI scripts always
remove only their own UUID projects/containers/networks/images, not shared base
images or unrelated resources. Docker PG publishes no host port; the signed
adapter is127.0.0.1-only on its fresh frontend bridge (not an egress firewall),
with no external provider configured. All new ephemeral keys are0600 and never
printed/committed; source app remains nonroot and read-only. No key, token or
DSN password is included in evidence. `reports/` is preserved; only the two
test-generated historical Q2 process logs were restored byte-for-byte from the
baseline after preserving current-run copies in this new evidence directory.

Use deploy/openbot-sandbox/README.md for fresh UUID-scoped fixture-only setups.
Run validate_m1_manifest.py to check shape, not to authorize freeze; run the
locked contracts npm ci/tsc/noEmit/compiled tests and official OpenAPI validator.
Golden115/75/100, current full strict suites, real wire probes and inherited+
readiness wheel checks are reproducible from repository source. No TeamB
message, OpenBot edit, Enterprise/StratAI resume, main/tag mutation, PR, release,
publication, production migration/deploy or Wave2/M3 start is authorized here.
