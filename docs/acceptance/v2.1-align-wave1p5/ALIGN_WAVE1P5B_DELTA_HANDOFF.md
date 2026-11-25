# SDK-22 Align-Wave1.5b — source-verified DRAFT engineering handoff

M1 status: **pending_joint_signoff**, freeze_authorized:false, approvals:[],
no self-awarded independent acceptance. Owner-provided original06/10 document
prior Wave1/Wave1.5 acceptance and the ordinary-RRF Accept with Waiver; the waiver
is not new-contract acceptance, a production SLA, M1 freeze or Wave2 permission.
This delta changes docs/contracts/validators/tests only; no runtime implementation.

## 1. Final40SHA and relative diff — single-commit resolver

Parent baseline:5775d424f112940199ff5cd292be1b9fc270d2bc.
Same feature:feat/align-wave1p5-m1-readiness. Exactly ONE normal new commit is
reserved for this complete delta. No amend after push, force, tag/main mutation,
PR, package/release publication or deployment.

A commit cannot embed its own future SHA/CI run ID without changing that SHA.
Therefore this committed report deliberately provides resolvers; the final rendered
external report/receipt and final handoff message supply actual resolved values.
On the delivered checkout:

```sh
DELIVERED_SHA=$(git log -1 --format=%H -- docs/acceptance/v2.1-align-wave1p5/ALIGN_WAVE1P5B_DELTA_HANDOFF.md)
git rev-parse "$DELIVERED_SHA^"
git rev-list --count 5775d424f112940199ff5cd292be1b9fc270d2bc.."$DELIVERED_SHA"
git diff --stat 5775d424f112940199ff5cd292be1b9fc270d2bc.."$DELIVERED_SHA"
```

Expected parent is the baseline above and count is1. The external rendered
handoff stores the ACTUAL diffstat, final40SHA and complete changed-file hash map,
not an invented future SHA placeholder. Receipt:
/workspace/align-wave1p5b-task-inputs/final-receipt.json
Rendered final handoff:
/workspace/align-wave1p5b-task-inputs/ALIGN_WAVE1P5B_DELTA_HANDOFF_FINAL.md

## 2. Exact-SHA four-job CI binding

After the sole push, use the actual run whose head_sha equals DELIVERED_SHA:
`gh run list --workflow tests.yml --commit "$DELIVERED_SHA" --json databaseId,headSha,status,conclusion,url`.
The external receipt records the native GitHub result and all4job IDs/conclusions:
Python3.9/ubuntu22.04 and3.12/ubuntu24.04 × core/http-and-package. Existing CI runs
full strict unittest/pytest, actual disposable PG17/pgvector/RLS golden modes,
locked TypeScript/Node, official OpenAPI checks and real isolated Docker sandboxes.
No new workflow/deployment or live provider is added. Baseline run45573187717 is
historical evidence for5775d424 ONLY; it is NOT final delta CI. This report makes
no advance CI-success claim; final result is resolved after push outside Git.

## 3. Complete contract file SHA-256 list (no circular self-hash)

All28 required assets below are validated against exact current bytes. Coverage
includes EVERY contract root file (including validators, generator, locked dev
files, evidence metadata/checklist), ALL11 fixture JSON, M1 decision package,
manifest validator and source provenance. Removing ANY entry fails. Deleted
mandatory files cannot disappear from coverage; extra entries, malformed digests,
traversal, outside-root symlinks and actual mismatches fail. The manifest itself
is excluded to avoid a digest self-cycle. Hashing the generic validator is NOT a
cycle: its source does not contain the manifest's hash. These are integrity pins,
not authenticated signatures or permission to freeze.

| Repo-relative asset | Bare lowercase SHA-256 |
|---|---|
| `docs/architecture/knowledge-sdk-alignment/M1_DECISION_PACKAGE.md` | `45d017cda4038718c7f12c0d89d2aa4cbc406e40ab45e8051f0a21a8129a9c73` |
| `docs/architecture/knowledge-sdk-alignment/WAVE1P5B_SOURCE_PROVENANCE.json` | `4ecf13191c87f362bf4c5cfe878ad914742c9e55789feaea53f7b886895a92d3` |
| `docs/architecture/knowledge-sdk-alignment/contracts/.gitignore` | `4d56952b0fb13bf8f9b6c13a6d4c34a075bac3af447636a1df4335d7576e2f97` |
| `docs/architecture/knowledge-sdk-alignment/contracts/README.md` | `14144e90a621b3d5dc3eadeefbb3b4e8a312b82d0b7ea9dd74390ca3d2d17830` |
| `docs/architecture/knowledge-sdk-alignment/contracts/contract-fixtures/agent-intersection-deny.json` | `d535a70749500fd903c4e27d7024d270557af6c88cbdc1864456a74b415a3f10` |
| `docs/architecture/knowledge-sdk-alignment/contracts/contract-fixtures/calibrated-search-response.json` | `ffbc876db333ee0fdbfe219b4e9db442173c665c0f41ab98f1495fcd777c11e2` |
| `docs/architecture/knowledge-sdk-alignment/contracts/contract-fixtures/dual-uri-evidence.json` | `4d62459fed7ed4da4dabf6604cdf06e59d318f78485f8de15b08e17f2c495791` |
| `docs/architecture/knowledge-sdk-alignment/contracts/contract-fixtures/error-envelope.json` | `f1c0538c45f9323383e4ce9e0fe1ebda0f8faabafc8bdf0e9d88cc47eedccef6` |
| `docs/architecture/knowledge-sdk-alignment/contracts/contract-fixtures/hash-vectors-utf8.json` | `c350210a595ede70f6a7d420069fc4a1fda5409783f9225550706b44842119ca` |
| `docs/architecture/knowledge-sdk-alignment/contracts/contract-fixtures/identity-context.json` | `16588221f0d1a2366f735266dd7ecd7d594408544601d8eb8025f7c6dece4f34` |
| `docs/architecture/knowledge-sdk-alignment/contracts/contract-fixtures/identity-lifecycle-fixtures.json` | `9ee7ff9148341f4f80405525c2366d0ca665f727cbc38e9b1dd6f1149eb6be3d` |
| `docs/architecture/knowledge-sdk-alignment/contracts/contract-fixtures/kb-lifecycle.json` | `500ec24e25bcd20755ffeecc61cda98f2349e0eb19b4bd2becd03c833173ce10` |
| `docs/architecture/knowledge-sdk-alignment/contracts/contract-fixtures/policy-generation-cases.json` | `18b4d60a1c9e3e4817f34cd44300bc00e1efcfe4bfe73924c700a68480fbce7f` |
| `docs/architecture/knowledge-sdk-alignment/contracts/contract-fixtures/rollback-activation-cases.json` | `cf32b61bce87c131eed6285011a3a99d0ba0840676be8e9bb94c7f7e82b9c9c8` |
| `docs/architecture/knowledge-sdk-alignment/contracts/contract-fixtures/signed-request-canonicalization.json` | `84e95ce2534838e050a11fb08c33f96c24e6dd927764e72584399c15eaa27fc6` |
| `docs/architecture/knowledge-sdk-alignment/contracts/delta_contracts.py` | `07e86adb06b84854995f3d2d2b564860379282c4b1ede5da91b4746554396271` |
| `docs/architecture/knowledge-sdk-alignment/contracts/fixture-evidence-boundaries.json` | `a024b8066ae0edd5ed3575e516027c160da86f29aa7a930981fc80b410c3cbd9` |
| `docs/architecture/knowledge-sdk-alignment/contracts/fixture-schemas.json` | `17a454d94398f8aef26858d2c02e87c8919bb489c33e475ddc857be8a3a132f5` |
| `docs/architecture/knowledge-sdk-alignment/contracts/generate_assets.py` | `0a3f689e760e1ea278749b137e4f5b6c046e0fb76bf5ac2ecb8b94a0e0790247` |
| `docs/architecture/knowledge-sdk-alignment/contracts/minimum-slice-checklist.json` | `b789df23561b9bb2f9a5f17bd90d29ba1b2677248ad05e7a3929eb91cdd5e3f9` |
| `docs/architecture/knowledge-sdk-alignment/contracts/openapi-v2-draft.yaml` | `824b74a3bcb44dcda63938624779d4f32b361ea2567d471690f751e6afcaf12b` |
| `docs/architecture/knowledge-sdk-alignment/contracts/openbot-adapter-dto.d.ts` | `815f447d9c1ac6d5e9b614caa427941f14b780ac2c37fb67f8552705005e3d26` |
| `docs/architecture/knowledge-sdk-alignment/contracts/package-lock.json` | `529ef0f02a19d9dbe7e8563fae9ae1745c169b373e6b6ba3cd656c1e37e4cf56` |
| `docs/architecture/knowledge-sdk-alignment/contracts/package.json` | `dbf08a7c408387765d2f63b5708d7d105750542f676a548aaca978406a0e2c8e` |
| `docs/architecture/knowledge-sdk-alignment/contracts/uri-mapping.test.ts` | `0aa6832477a886f69a53d6452f546299e57a70580f9d038d960578dbae088a17` |
| `docs/architecture/knowledge-sdk-alignment/contracts/uri-mapping.ts` | `e90ebc7ceb5d28fac50edbdb1f4bd47f3ed47cca2ac5fc8588772269d10408c4` |
| `docs/architecture/knowledge-sdk-alignment/contracts/validate_assets.py` | `77995e2400f7e3a7cc41e462b033240edd3e5ad915131c0ef5480775c8b1e4a4` |
| `docs/architecture/knowledge-sdk-alignment/validate_m1_manifest.py` | `ca9c75ab38a44487e76991a54bec70effcd94289501f8a445741ed69b30903eb` |

### Original-source provenance

Owner ZIP: /workspace/align-wave1p5b-task-inputs/owner-t61-originals.zip,
SHA256d56268b4ebd533d23ee296544cd23bbe00ba1cec21e1bb54ea71572d3778e5e5.
Read06–10 completely and archived exact original bytes. All00–05 match the new
ZIP and were NOT overwritten. ZIP10 differs from the earlier standalone10;
both originals are retained, explicitly versioned below, never silently merged.
Source-provided role/signoff statements remain SOURCE/OWNER-PROVIDED, not this
executor's independent audit. Full archive inventory/byte counts/hashes and old
source-gap history:WAVE1P5B_SOURCE_PROVENANCE.json.

| File under docs/architecture/knowledge-sdk-alignment/ | Exact source SHA-256 |
|---|---|
| `06_WAVE1_ACCEPTANCE_AND_NEXT_DIRECTIVE.md` | `aa4adb3c73ef4488f24540f73f05f2f79567b635cea1ae39936709184c28d560` |
| `07_TEAM_A_TO_TEAM_B_CONSENSUS_RESPONSE.md` | `1cfe9b4b60522ed48871ce5272cfd2bfa8c35baaf7f6dc528de59731e696a70c` |
| `08_TEAM_A_DELTA_SIGNOFF_AND_MIN_SLICE.md` | `78efad1e4bc90c179edf46226475d4f3c1acfd4ba25b30390234c75cfb230096` |
| `09_WAVE1P5_CONSOLIDATED_EXECUTION_DIRECTIVE.md` | `0ed8076cf0fffda4dd794c9438cfd581e6a2c7c430a70fe4f03a3464cd4f3cac` |
| `10_WAVE1P5_ACCEPTANCE_AND_DELTA_DIRECTIVE.md` | `d7c3330c0c2c7ae9756fe23a2cab0de8b3c14bc192ea7eb2d4105d32e82a401d` |
| `SOURCE10_STANDALONE_T59_ORIGINAL.md` | `3c01cfb0e8fb43f675116ffb0963273a6edcc58596b01685172d854ccf0afc2c` |

Latest t61/ZIP10 corrects POST/v2/documents to POST/v2/assets (not an alias),
requires uncaptured v2 example flags, and confirms NFC. Original08's older
not-draft activation wording is superseded by09's strict published whitelist.
No runtime behavior or old governing-source byte was edited to conceal conflicts.

## 4. Five fixture families and evidence boundaries

All11 contract-fixture payloads have explicit uncaptured/draft provenance in
contracts/fixture-evidence-boundaries.json. New wrapper metadata also declares
runtime_captured:false. Examples cannot masquerade as v2 runtime capture.

| New fixture | Actual content / checks | Evidence boundary |
|---|---|---|
| identity-lifecycle-fixtures.json |7 proposed scenarios: composite tenant+issuer+raw_sub uniqueness; independent tenant identity; no cross-IdP email merge; explicit admin identity.rebound with generation increase; deactivation and stale-session/task rejection |contract_scenario_fixture; pure proposed reference model, NOT new runtime provisioning/auth proof |
| policy-generation-cases.json |12 exact requested boundaries:1,MAX_SAFE,stale,0,-1,missing,null,string1,abc,true,1.5,2^53; no bool/string/default coercion; missing remains distinct from null |contract_scenario_fixture, v2 drafting only; existing v1 generation0 handling unchanged |
| hash-vectors-utf8.json |All7 original08/09 inputs, normalized strings and BOTH literal SHA pairs; Python+Node actual SHA-256; source bytes pinned |offline_algorithm_vector_only; lowercase64, separate hash_algorithm:sha256 |
| signed-request-canonicalization.json |All4 literal HMACs;6/8-line switching, original%2F raw query, exact non-ASCII UTF8 body bytes, purpose-only empty agent line; Python matches actual SDK _message and Node crypto |offline_algorithm_vector_only; public TEST_ONLY_DO_NOT_USE_IN_PROD_* pseudo-key+historical timestamp, NEVER live authentication/replay proof |
| rollback-activation-cases.json |All8 source09 literal cases, all7states+pointer mismatch; exact formula created_version===current_version && state==='published' |contract_scenario_fixture; false for draft/in_review/approved/rejected/superseded/revoked or pointer mismatch |

The signed fixture's v2 examples200/403/409/422 each have runtime_captured:false
and reason:v2_runtime_prohibited_before_m1_freeze. They are draft examples, not wire.
ACTUAL signed SQLite loopback evidence is separate:v1-loopback-sanitized.json.
It records only implemented/v1 responses200/403/409/400, evidence_kind and
wire_protocol:v1_loopback_test_only, with actual request/response headers and
body, ephemeral signature redacted and random secret NEVER persisted. This is
sanitized structured application-layer capture, not a byte-for-byte packet trace.
409 is a real KB identity conflict, NOT future Idempotency-Key support;400 is the
actual TamperedExcerptError mapping, NOT fabricated/v2/422. Owned server/socket
and responses (HTTPError included) close in finally/with blocks. No v2 wire runs.

## 5. Draft contract consistency / ten minimum assertions

Only POST/v2/spaces and POST/v2/assets declare optional Idempotency-Key and
409IDEMPOTENCY_CONFLICT. There is NO/v2/documents path/alias. OpenAPI, TS endpoint
type, generator and machine checklist match. Standard JSON/v2 stays draft-only,
with x-contract-status:draft-pending-m1-freeze and false runtime metadata under
valid OpenAPI x-* extensions. No bare invalid OpenAPI root extension is used.

Write/rollback results ADD the five activation/scope fields while preserving all
prior DocumentVersion result fields through DocumentWriteResponse. No v1 return
fields change. Only published AND equal pointers activates; L2 drafts do not.
CURRENT security and business metadata stay authoritative; historical ACL/rights
are never restored. D1–D7 remain unsigned. Source08 §3's EXACT10minimum assertions
and both strengthening requirements are mirrored in minimum-slice-checklist.json
and M1_DECISION_PACKAGE.md; the validator checks text/source identity, not actual
future/v2 implementation. Six cross-team pending topics remain unresolved.

## 6. TypeScript29-codepoint/NFC/FEFF results and bare validators

Actual locked TypeScript5.9.3 strict --noEmit, compile and Node execution passed:
44 unchanged legacy URI assertions,142 independent strict-boundary assertions,
117 source-vector assertions =303total. Actual crypto:7hash+4HMAC+8rollback cases;
12policy cases. Source08/t61 confirms NFC followed by Python29-whitespace folding.
The previous source uncertainty is RESOLVED, not a runtime normalization change.

Exact whitespace set:U0009–000D,U001C–0020,U0085,U00A0,U1680,U2000–200A,
U2028–2029,U202F,U205F,U3000. Python exhaustive codepoint check confirms29.
FEFF is NOT whitespace and is preserved at edges/interior; decomposed Café is
NFC-composed for semantic hash only. No ECMAScript whitespace regex is used.
Final Node result:

```json
{"agreed_hash_vectors_executed": 7, "agreed_rollback_cases_executed": 8, "agreed_signed_vectors_executed": 4, "legacy_uri_assertions": 44, "normalization": "NFC_then_Python29_whitespace_FEFF_preserved", "policy_cases": 12, "runtime_v2_implemented": false, "status": "ALL_SOURCE_VECTORS_AND_BOUNDARIES_PASSED", "total_assertions": 303}
```

Bare commands work without PYTHONPATH, under-S and from foreign CWD using trusted
__file__-relative src bootstrap. Official OpenAPI3.1/JSON Schema actually ran;
stdlib-only mode honestly reports optional validator NOT_INSTALLED.

`env -u PYTHONPATH python3 -S .../contracts/validate_assets.py`:
```json
{"delta": {"agreed_hash_vectors_verified": 7, "agreed_rollback_cases_verified": 8, "agreed_signed_vectors_verified": 4, "complete": true, "missing_fixture_files": [], "missing_original_document_numbers": [], "status": "VERIFIED_DRAFT_CONTRACTS_PENDING_JOINT_SIGNOFF", "team_b_original_assertions_verified": 10}, "delta_fixtures": 5, "fixtures": 11, "legacy_fixtures": 6, "m1_joint_freeze": "PENDING", "negative_probes": 118, "official_optional_validator": "NOT_INSTALLED", "paths": 23, "runtime_v2_implemented": false, "schemas": 40, "status": "DRAFT_ASSET_SELFCHECK_PASSED", "verified_vectors": {"hash_vectors": 7, "hmac_vectors": 4, "identity_cases": 7, "minimum_slice_assertions": 10, "policy_cases": 12, "rollback_cases": 8, "runtime_v2_implemented": false}}
```
Existing optional dev environment, same bare assets script:
```json
{"delta": {"agreed_hash_vectors_verified": 7, "agreed_rollback_cases_verified": 8, "agreed_signed_vectors_verified": 4, "complete": true, "missing_fixture_files": [], "missing_original_document_numbers": [], "status": "VERIFIED_DRAFT_CONTRACTS_PENDING_JOINT_SIGNOFF", "team_b_original_assertions_verified": 10}, "delta_fixtures": 5, "fixtures": 11, "legacy_fixtures": 6, "m1_joint_freeze": "PENDING", "negative_probes": 118, "official_optional_validator": "PASSED", "paths": 23, "runtime_v2_implemented": false, "schemas": 40, "status": "DRAFT_ASSET_SELFCHECK_PASSED", "verified_vectors": {"hash_vectors": 7, "hmac_vectors": 4, "identity_cases": 7, "minimum_slice_assertions": 10, "policy_cases": 12, "rollback_cases": 8, "runtime_v2_implemented": false}}
```
`env -u PYTHONPATH python3 -S .../validate_m1_manifest.py`:
```json
{"contract_assets_verified": 28, "contract_delta_complete": true, "contract_delta_status": "VERIFIED_DRAFT_CONTRACTS_PENDING_JOINT_SIGNOFF", "decisions": 7, "freeze_authorized": false, "signoffs_verified": 0, "status": "WELL_FORMED_PENDING", "verified_vectors": {"hash_vectors": 7, "hmac_vectors": 4, "identity_cases": 7, "minimum_slice_assertions": 10, "policy_cases": 12, "rollback_cases": 8, "runtime_v2_implemented": false}}
```
Both exit0. WELL_FORMED_PENDING/contract_delta_complete mean valid DRAFT inputs,
NEVER approved/frozen. All partial/forged/frozen/signature states are rejected.

## 7. Actual local tests, exact-SHA CI receipt and remaining boundaries

21 NEW test methods. Full local strict stdlib:987collected,674passed313optional
skips,0failures/ResourceWarnings. Existing optional local environment WITHOUT a
PG fixture:987collected,778passed209skips;pytest778passed209skips337subtests,
1existing Starlette deprecation (not ResourceWarning),0failures/ResourceWarnings.
No new local PG cluster or Docker daemon was started for contract-only work.
PG-dependent coverage is NOT claimed from those local skips; final exact-SHA CI
provides actual disposable PG+pgvector/RLS and both Docker sandbox modes.

Final focused28tests passed after documentation/metadata/wire-header polish;
full-suite logs precede that final documentation-only polish. Final CI runs the
whole suite at the actual new commit. Python3.9 AST, build, wheelRECORD and
unpacked-S rollback/search smoke passed; no mandatory deps/version changes.
All12 tracked benchmark-source files, original115assertions and legacy75/100
sources are byte-identical to baseline (golden-source-integrity.json).
Old test-generated historical Q2 process log was copied outside then restored
ONLY to its original bytes; reports/ never touched. No performance reruns.

Actual logs/current local receipts:/workspace/align-wave1p5b-task-inputs/verification/.
Final rendered report+machine receipt resolve exact40SHA/diffstat/4jobCI after the
single normal push, without a second evidence commit or pushed amend. Local
only-source facts are not relabeled as final CI or independent review results.

Independent delta review/Team B candidate review and joint M1 signoff remain
PENDING. NoUIchanges/browser run. Enterprise/StratAI PAUSED. Zero src/engine/
runtime/Schema5DDL/physical tables or columns/golden/coredeps/workflow/deploy diffs.
Main/tag/Wave1/M1/M2 refs preserved. No/v2runtime/purge/Wave2/M3/PR/release/package
publication/production migration/integration/contact with teammates was started.
