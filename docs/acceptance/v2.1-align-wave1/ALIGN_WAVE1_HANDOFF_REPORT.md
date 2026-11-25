# Align-Wave1 / SDK-22 handoff — engineering evidence, NOT final acceptance

## 1. Branch, source and actual CI

Baseline `d1532951b08c8ef950dc604aa3427ceb9eab5d75`; branch
`feat/align-wave1-core-compat`. Explicit owner t56u LOCAL BOX override;
no CloudAgent. Implementation commits and measured source/CI receipts are
listed in `verification-summary.json` and `ci-source-verification.json`.
The latter is an explicitly timestamped historical status-at-archive, not a
claim that a pending fourth job passed. Final exact-SHA CI, including the actual
Docker receipt artifact `align-wave1-image-test`, must be verified separately;
the external final receipt is authoritative for that later run.
The final evidence/CI-only commit/CI receipt is retained outside the repo at
`/workspace/knowledge-sdk-align-wave1-artifacts/final-receipt.json` to avoid
self-referential SHAs. No PR, main/tag/version mutation, publication or deployment.

Status: **affected Task1 metadata requirement unresolved; independent review
pending. Do NOT declare Wave1 complete**, even if all automated gates pass.

## 2. Tasks 0–3: delivered code and assets

- Task0: six supplied UTF-8 originals archived byte-identically in
  `docs/architecture/knowledge-sdk-alignment/`. Original hashes and ZIP/source
  provenance are in PROVENANCE.json/.md. Independent 132-line directive is
  separately named OWNER_SUPPLEMENT_WAVE1_T56U_ORIGINAL.md; ZIP05 has 131 lines.
  Only literal numbered gutters/newline differ after normalization. No source
  was silently replaced. t56u is operational authority, not M1 joint signoff.
- Task1: client/compat.py adds get_kb, update_kb, list_kb_members,
  revoke_kb_member, list_document_versions, diff_document_versions,
  rollback_document, plan_sync. Local/HTTP reflected OPERATIONS now70 vs old62;
  old formats/signatures preserved except expressly additive archived_only=False.
  Source details: docs/agent-runtime-compat.md. Current identity, User ∩ Agent,
  explicit Deny, audited transactions, immutable intrinsic Owner, append-only
  rollback, L2 three-person publication, redaction-before-diff, uniform denials,
  immediate event-linked task revocation and independent PG-connection races
  covered. No DDL/table/column/schema-version changes.
- Connector planning uses shared pure preflight, never commit-and-rollback;
  custom consuming sync_since is never called. SQLite total_changes and actual
  PostgreSQL READ ONLY transactions prove no business/audit writes, in addition
  to cursor/source/outbox assertions. HTTP authentication replay/failed-auth
  auditing remains the separate pre-existing security boundary.
- Task2: actual pre-edit profiles identify authoritative metadata / tenant /
  savepoint overhead, not just scorer cost. Request-local bulk reads and title /
  chunk token reuse preserve exact candidate-pool order, policy checks, window,
  weights, threshold and quality. No cross-request/tenant/generation rank cache.
  New real same-identity Python/HTTP/MCP-four-tool permission suite covers both
  engines. ready checks a real connection and schema5; metrics exposes five fixed
  counters only behind signed current metrics_admin and agent checks. Health
  unchanged. Dockerfile/container.py are nonroot HTTP/MCP-only, mounted-secret,
  no insecure demo or UI; isolated test image is never published/deployed.
- Task3: contracts/ contains draft OpenAPI3.1 (JSON syntax, valid YAML1.2), exact
  schema-derived TS DTO, typed kb://↔ku:// mapping and six named JSON fixtures.
  Covers C01–C09, trusted gateway identity/tenant headers, security intersections,
  unified errors, refs/types/required/enums/bounds. Validator exercises actual
  policy intersection plus 37 negative probes; optional official validators and
  actual TypeScript typecheck are separate evidence. 23 paths / 28 schemas,
  x-contract-status=draft-pending-m1-freeze, runtime-v2-implemented=false.
  Future request details remain provisional; runtime canonical URIs unchanged.
- New tests: 48 unittest methods including dual-engine inherited cases;
  existing894 tests untouched; total942. No new golden group.

## 3. Quantitative verification and latency

See verification-summary.json, paired-performance-comparison.json, full logs,
wire-sqlite.json / wire-postgres.json, package-integrity.log and draft validation.
All 11 original benchmark source/data files (including every G1–G9 assertion)
match golden-before.json byte-for-byte; schema5 / dependencies=[] / package1.2.0
are preserved. Real local PostgreSQL17+pgvector fixture uses a NONSUPERUSER,
NOBYPASSRLS role; no existing service/database was used.

The frozen dataset has 4 train / 4 calibration / 24 evaluation families, disjoint.
Quality: candidate NDCG@3/MRR/recall1.0; correct refusal decisions24/24 (6 actual
refusal cases +18 evidence cases), false refusals0/18, ACL violations0, observed
implicit provider calls0. These are measured offline fixed-set results, NOT
production or online-provider claims. Explicit deterministic fixture embeddings
are not an online embedding provider. No query/evaluation-label tuning occurred.

Original before profiles/latencies were saved BEFORE source edits. Final paired
recheck runs exact detached baseline and feature on the SAME retained physical
snapshots and same machine, one warmup +five repeats,120 timed searches per arm.
Each entire pair runs real authorization/audit SQL inside an identical outer
measurement transaction and rolls back ONLY its fixture audit/usage writes to
retain the snapshot. This is benchmark isolation, NOT connector fake dry-run.
Actual index hashes and actual protected pool digests/order are compared;
instrumentation/wrapper overhead applies equally. Both baseline RRF and enhanced
candidate arms are reported, including any slower arm and noisy timings.

### Same-snapshot measured enhanced-search latency (ms)

| Engine | P50 before→after | P95 before→after | Mean before→after |
|---|---:|---:|---:|
| SQLite |17.840→16.969|19.125→18.718|13.203→12.757|
| PostgreSQL |146.320→80.210|168.564→95.123|110.537→62.158|

Enhanced P50 reduction: SQLite4.89%, PG45.18%. Plain RRF P50 **slowed**
1.873→1.916ms SQLite and9.628→10.106ms PG with current-principal transaction
checks; this is reported, not hidden. Both phases have161 identical observed
protected pools per engine and identical config/dataset/corpus/index hashes.
Baseline RRF NDCG remains0.774457(SQLite)/0.794961(PG), candidate1.0 before
and after; false-refusal/ACL/model counters unchanged. This is not a new M2
quality-gain claim, just preservation of the previously frozen offline result.

Local strict stdlib:942 collected,642 passed,300 optional skips; full unittest
and pytest:939 passed,3 online-Qdrant skips,0 failures. Pytest also ran252
subtests and emitted1 optional Starlette deprecation warning,0 ResourceWarnings.
Wave1 actual-wire groups111(SQLite)/114(PG), plus80 M2 and109 M1 groups per
engine; adapters' observed provider attempts0. Golden modes115/115,75/75,
100/100 each engine. Source tree and exact launch SHAs are in JSON; the stronger
physical-readonly assertions were also separately rerun after the full suite.

## 4. Uncovered items, contradictions and remaining risks

1. **Affected rollback requirement NOT complete**: schema-v5 DocumentVersion
   never retained historical arbitrary Document.metadata/title/ACL/rights/validity.
   Exact historical business metadata restoration cannot be fabricated, and new
   physical schema or changing existing version response contracts is prohibited.
   Implementation copies available target-version filename/text, retains current
   document/security metadata and lifecycle, never revives revoked rights/ACL.
   Requires owner/architect disposition. No hidden substitute or compliance claim.
2. Local Docker CLI/daemon/build tools absent: local status BUILD_NOT_RUN.
   Actual isolated CI image build/run is separately evidenced; never relabel a
   static check as an actual local build. No existing containers/network altered.
3. Source run45555859161 cancelled during its remaining3.12 golden stage;
   run45557895042 reached a real image build but failed on an uncaught transient
   ConnectionResetError before readiness. The sibling3.9 job was cancelled by
   matrix fail-fast. ci-container-startup-correction.json records the correction:
   bounded retry, unchanged real readiness/wire assertions, and independent matrix
   execution so a failed job cannot cancel remaining coverage. Neither run is
   claimed four-job green. The final receipt must verify the corrected run.
4. Three online-Qdrant tests intentionally skip; no live model/vector provider,
   paid calls or online quality/generalization claims. Optional pytest may report
   a FastAPI/Starlette deprecation warning; ResourceWarning gate remains strict.
5. Q3-M2 independent review remains historically pending. Owner t54u accepted
   M1 assumptions, NOT an invented M2 or M1 cross-repository joint freeze.
6. Package metadata1.2.0 vs annotated v2.0.0 tag is known historical DRIFT,
   unchanged by order. Upper strategy/protocol environment copies remain absent;
   supplied alignment sources are complete and preserved, not replaced by claims
   about inaccessible Governance Workbench publications.
7. No UI changes: L4 draft-asset/safety self-check only; NO_UI_CHANGES and
   NOT_RUN_NO_UI_CHANGES. No browser run performed; historical Q2 browser evidence
   is historical only. No v2 runtime/purge/schema6/physical jobs/Claim/graph/B09.

## 5. M1 freeze, Team B review and next authorization

L5 here is handoff compliance, **not self-awarded independent or architect
signoff**. Draft OpenAPI/DTO/fixtures are ready for the owner's/Team B's review,
not a claim that review occurred. No new recipient was contacted. Resolve the
historical-metadata contradiction, obtain independent Wave1 acceptance and M1
joint freeze before an explicitly issued Align-Wave2 taskbook. Do not start
Wave2/Q3-M3. Enterprise/StratAI production/system integration remains PAUSED;
no Mac/OpenBot edit, live service modification, migration or external deployment.
Owned fixture cluster/worktree cleanup and protected refs are recorded in the
external final receipt; existing reports/ remains untouched.
