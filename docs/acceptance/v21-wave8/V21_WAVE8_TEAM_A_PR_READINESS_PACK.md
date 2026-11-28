# V21_WAVE8_TEAM_A_PR_READINESS_PACK

Status: **Team A Wave-V21-8 PR-readiness pack (W8A-1)**. This document records official Owner order `t109u` / `AUTH-V21-08-PR-PREP` rulings already issued. It does not self-issue those rulings, does not authorize a merge to `main`, and does not authorize a production Schema v7 migration.

Order: Owner order `t109u` (2026-11-28, Asia/Shanghai), issued under the written authorization of the project lead Daniel (daniel.hhd@gmail.com). That name is recorded as the official authorizer / AUTH-V21-04 custodian only; this file is not a request to email anyone.

This pack is committed on isolated branch `feat/v21-wave8-pr-prep-main-readiness`, created from the frozen Wave-V21-7 tip `2b6944e559dd63b61640b64b104a86d8a502086f`. It does not modify frozen tips `2b6944e5`, `91b8b6f3`, `ce8297fb`, `e97a8cca`, `918293ca`, or `main@b953c992`. Frozen contract pack `contracts/v21-reuse-v1/` is not edited. Official post-Wave-V21-7 flags are recorded only in `docs/acceptance/v21-wave8/`.

## 1. Official Wave-V21-7 joint clean accept and formal T-01–T-27

The following flags were already issued by the Owner in `t109u`. They are recorded here; they are not self-issued by Team A.

| Flag | Official value | Notes |
| --- | --- | --- |
| `TEAM_A_WAVE_V21_7_CLEAN_ACCEPT` | true (Owner-issued) | Team A isolated-branch Wave-V21-7 clean accept |
| `TEAM_B_WAVE_V21_7_CLEAN_ACCEPT` | true (Owner-issued) | Recorded as Owner-stated; Team A did not independently re-verify OpenBot |
| `WAVE_V21_7_JOINT_CLEAN_ACCEPT` | true (Owner-issued) | Joint Wave-V21-7 clean accept |
| `formal_t01_t27_accepted` | **true** | Label: `FORMAL_CORE_V7_DUAL_STACK_ACCEPTED`. Meaning: certified dual-stack engineering and isolated-branch verification all passed. **Does not authorize production database migration.** |
| `wave_v21_8_unlocked` | true (Owner-issued) | Unlocks Wave-V21-8 work on this isolated branch |
| `draft_pr_open_authorized` | true (Owner-issued) | Allows creation of exactly one Draft PR for pre-merge review and CI only |

Frozen / runtime artifacts were **not** rewritten to flip historical flag values:

- `contracts/v21-reuse-v1/` remains byte-identical. Deterministic manifest SHA-256 is `212537fd41bd4cc4d9d7343cacafaea225ee98b6586df716bf036a397cb2a382`. The frozen pack `status.json` still carries historical values, including `formal_t01_t27: NOT_RUN_NOT_ACCEPTED` and `schema_v7_ddl_authorized: false`.
- `src/knowledge_sdk/storage/schema_v7.py` still has `FORMAL_T01_T27_ACCEPTED = False` and `SCHEMA_V7_PROD_MIGRATION_AUTHORIZED = False`. `scripts/verify_v21_boundaries.py` continues to require those runtime constants stay false. This is a production-adjacent engineering lock, not a contradiction of the Owner's process ruling, which lives in this wave8 document.
- `docs/acceptance/v21-wave7/W7A2_CORE_V7_T01_T27_REPORT.json` is a frozen Wave-V21-7 evidence artifact (SHA-256 `46f0f60b754973cc6a5ee91dc100a2e4e396ec4c2550adeb5a237b89c3edce8f`) and still records `formal_t01_t27_accepted: false` as written at Wave-V21-7 implementation time. It was not edited.

### 1.1 Frozen Team A Wave-V21-7 tip and CI (already independently accepted by Owner)

- Isolated branch: `feat/v21-wave7-core-schema-v7-and-formal-t01-t27`
- Frozen tip (unmodified parent of this Wave-V21-8 branch): `2b6944e559dd63b61640b64b104a86d8a502086f`
- Exact first-parent chain of that tip: `2b6944e5` → `a5fa513b` → `cd97a414` → `8c6c704b` → `2d4b4dba` → `91b8b6f3`
- Implementation tip of W7A-1 / W7A-2 / W7A-3: `a5fa513b9e25a3912ca5fa6884cff363c42a0ab3`
- GitHub Actions `tests.yml` run `46149920829` on `a5fa513b`: 37/37 success, completed 2026-11-28 21:44:05 CST (Asia/Shanghai) (source `2026-11-28T13:44:05Z`). URL: https://github.com/flykingvip-cloud/knowledge-sdk/actions/runs/46149920829
- GitHub Actions `tests.yml` run `46151386006` on `2b6944e5`: 37/37 success, completed 2026-11-28 21:59:38 CST (Asia/Shanghai) (source `2026-11-28T13:59:38Z`). URL: https://github.com/flykingvip-cloud/knowledge-sdk/actions/runs/46151386006
- Owner independently re-verified those runs, including live disposable PostgreSQL in CI. Relative to `91b8b6f3` the Wave-V21-7 tip was 13 files, +3202/−28.
- At the frozen Wave-V21-7 tip, `main..wave7` was exactly `ahead_by=73`, `behind_by=0`. This pack's own commit increases the ahead count; see section 2.

### 1.2 Production-migration caveat (unchanged)

`formal_t01_t27_accepted = true` / `FORMAL_CORE_V7_DUAL_STACK_ACCEPTED` certifies the engineering dual-stack and isolated-branch T-01–T-27 verification. It does **not** authorize a production database Schema v7 migration. `schema_v7_prod_migration_authorized` remains **false**. `schema_v8_v9_ddl_authorized` remains **false**. Engineering has zero production-database contact. See section 4.

### 1.3 Owner-stated Team B Wave-V21-7 pin (not independently re-verified here)

Recorded as Owner-stated only; this pack does not independently re-verify OpenBot:

- Team B Wave-V21-7 tip: `b29385f2`
- Inventory: `f1f5c58b...`
- 16/16, 222/222, 0 PR

## 2. Exact difference inventory

Inventories below are for **this readiness-pack / W8A-2 allowlist commit** on `feat/v21-wave8-pr-prep-main-readiness`. The parent of this commit is the frozen Wave-V21-7 tip `2b6944e559dd63b61640b64b104a86d8a502086f`. A later handoff-report commit (W8A-3) will increase `ahead_by` by one and is not included here.

`behind_by=0` is confirmed for both `main@b953c992` and baseline `9940818b`: both are ancestors of this branch, so this branch contains every commit on those refs.

Owner-stated Wave-V21-7 value was `main..wave7` `ahead_by=73`, `behind_by=0`. After this Wave-V21-8 commit the exact counts are greater than 73, as required.

### 2.1 `b953c992..HEAD` (knowledge-sdk `main`)

- `main` SHA: `b953c9922cc1096e0e88455dab6746c01a9d27f9`
- `ahead_by`: **74** (73 Wave-V21-7-and-prior commits already on the frozen tip, plus this Wave-V21-8 commit)
- `behind_by`: **0**
- `git diff --shortstat b953c992..HEAD`: 397 files changed, 115336 insertions(+), 137 deletions(-)
- Files changed: **397**

This commit versus `main` adds one new path (`docs/acceptance/v21-wave8/V21_WAVE8_TEAM_A_PR_READINESS_PACK.md`) on top of the 396-file Wave-V21-7 tip inventory, and modifies already-listed `scripts/verify_v21_boundaries.py`.

Name-status (A/M/D) of `b953c992..HEAD`:

```
A	.dockerignore
M	.github/workflows/tests.yml
A	Dockerfile
A	contracts/v21-reuse-v1/.gitignore
A	contracts/v21-reuse-v1/README.md
A	contracts/v21-reuse-v1/ai-execution-trace.schema.json
A	contracts/v21-reuse-v1/ai-execution-trace.vectors.json
A	contracts/v21-reuse-v1/check.ts
A	contracts/v21-reuse-v1/controlled-data-bridge.schema.json
A	contracts/v21-reuse-v1/controlled-data-bridge.vectors.json
A	contracts/v21-reuse-v1/dto.py
A	contracts/v21-reuse-v1/dto.ts
A	contracts/v21-reuse-v1/memory-resource-bridge.schema.json
A	contracts/v21-reuse-v1/memory-resource-bridge.vectors.json
A	contracts/v21-reuse-v1/model-adapter.schema.json
A	contracts/v21-reuse-v1/model-adapter.vectors.json
A	contracts/v21-reuse-v1/openapi-v3-draft.vectors.json
A	contracts/v21-reuse-v1/openapi-v3-draft.yaml
A	contracts/v21-reuse-v1/package-lock.json
A	contracts/v21-reuse-v1/package.json
A	contracts/v21-reuse-v1/status.json
A	contracts/v21-reuse-v1/tsconfig.json
A	contracts/v21-reuse-v1/v21-contract-manifest.json
A	contracts/v21-reuse-v1/validate.py
A	deploy/README.md
A	deploy/container-requirements.txt
A	deploy/openbot-sandbox/.gitignore
A	deploy/openbot-sandbox/README.md
A	deploy/openbot-sandbox/compose.postgres.yaml
A	deploy/openbot-sandbox/compose.sqlite.yaml
A	deploy/openbot-sandbox/compose.wave2.yaml
A	deploy/openbot-sandbox/init-fixture-postgres.sql
A	deploy/openbot-sandbox/prepare_sandbox.py
A	deploy/openbot-sandbox/probe_openbot_sandbox.py
A	deploy/openbot-sandbox/probe_wave2.py
A	deploy/openbot-sandbox/seed_openbot_sandbox.py
A	deploy/openbot-sandbox/serve_sandbox.py
A	deploy/openbot-sandbox/upgrade_wave2.py
M	docs/acceptance/v2.0-q2-phase1/live_mcp_probe.py
A	docs/acceptance/v2.1-align-wave1/ALIGN_WAVE1_HANDOFF_REPORT.md
A	docs/acceptance/v2.1-align-wave1/ci-container-startup-correction.json
A	docs/acceptance/v2.1-align-wave1/ci-source-verification.json
A	docs/acceptance/v2.1-align-wave1/docker-local-status.json
A	docs/acceptance/v2.1-align-wave1/docker-startup-readiness-regression.log
A	docs/acceptance/v2.1-align-wave1/docker_probe.py
A	docs/acceptance/v2.1-align-wave1/draft-official-validation.json
A	docs/acceptance/v2.1-align-wave1/full-unit-source77493a4.log
A	docs/acceptance/v2.1-align-wave1/golden-before.json
A	docs/acceptance/v2.1-align-wave1/golden-postgres-default.json
A	docs/acceptance/v2.1-align-wave1/golden-postgres-legacy100.json
A	docs/acceptance/v2.1-align-wave1/golden-postgres-legacy75.json
A	docs/acceptance/v2.1-align-wave1/golden-sqlite-default.json
A	docs/acceptance/v2.1-align-wave1/golden-sqlite-legacy100.json
A	docs/acceptance/v2.1-align-wave1/golden-sqlite-legacy75.json
A	docs/acceptance/v2.1-align-wave1/owned-fixture-cleanup.json
A	docs/acceptance/v2.1-align-wave1/package-build.log
A	docs/acceptance/v2.1-align-wave1/paired-performance-comparison.json
A	docs/acceptance/v2.1-align-wave1/perf-after-final-postgres.json
A	docs/acceptance/v2.1-align-wave1/perf-after-final-sqlite.json
A	docs/acceptance/v2.1-align-wave1/perf-baseline-recheck-postgres.json
A	docs/acceptance/v2.1-align-wave1/perf-baseline-recheck-sqlite.json
A	docs/acceptance/v2.1-align-wave1/perf-before-postgres.json
A	docs/acceptance/v2.1-align-wave1/perf-before-sqlite.json
A	docs/acceptance/v2.1-align-wave1/perf_snapshot.py
A	docs/acceptance/v2.1-align-wave1/profile-after-final-postgres.txt
A	docs/acceptance/v2.1-align-wave1/profile-after-final-sqlite.txt
A	docs/acceptance/v2.1-align-wave1/profile-baseline-recheck-postgres.txt
A	docs/acceptance/v2.1-align-wave1/profile-baseline-recheck-sqlite.txt
A	docs/acceptance/v2.1-align-wave1/profile-before-postgres.txt
A	docs/acceptance/v2.1-align-wave1/profile-before-sqlite.txt
A	docs/acceptance/v2.1-align-wave1/pytest-source77493a4.log
A	docs/acceptance/v2.1-align-wave1/readonly-physical-proof.log
A	docs/acceptance/v2.1-align-wave1/run_evidence.py
A	docs/acceptance/v2.1-align-wave1/stdlib-golden115.log
A	docs/acceptance/v2.1-align-wave1/stdlib-sourcec1f2a17.log
A	docs/acceptance/v2.1-align-wave1/typescript-final.log
A	docs/acceptance/v2.1-align-wave1/verification-summary.json
A	docs/acceptance/v2.1-align-wave1/verify_package.py
A	docs/acceptance/v2.1-align-wave1/wave1-package-integrity.log
A	docs/acceptance/v2.1-align-wave1/wire-postgres.json
A	docs/acceptance/v2.1-align-wave1/wire-sqlite.json
A	docs/acceptance/v2.1-align-wave1p5/ALIGN_WAVE1P5B_DELTA_HANDOFF.md
A	docs/acceptance/v2.1-align-wave1p5/ALIGN_WAVE1P5_HANDOFF_REPORT.md
A	docs/acceptance/v2.1-align-wave1p5/CI_PROVENANCE.json
A	docs/acceptance/v2.1-align-wave1p5/PERFORMANCE_METHOD.md
A	docs/acceptance/v2.1-align-wave1p5/TASK0_ROLLBACK_AUDIT_PROVENANCE.json
A	docs/acceptance/v2.1-align-wave1p5/VALIDATION_SUMMARY.json
A	docs/acceptance/v2.1-align-wave1p5/ci-initial-sandbox-sqlite-runtime.log
A	docs/acceptance/v2.1-align-wave1p5/collect_evidence.py
A	docs/acceptance/v2.1-align-wave1p5/compose-network-final.log
A	docs/acceptance/v2.1-align-wave1p5/docker-local-status.json
A	docs/acceptance/v2.1-align-wave1p5/docker_sandbox_probe.py
A	docs/acceptance/v2.1-align-wave1p5/final-compose-validation.log
A	docs/acceptance/v2.1-align-wave1p5/final-full-pytest.log
A	docs/acceptance/v2.1-align-wave1p5/final-full-unittest.log
A	docs/acceptance/v2.1-align-wave1p5/final-l1-stdlib.log
A	docs/acceptance/v2.1-align-wave1p5/final-package-verification.log
A	docs/acceptance/v2.1-align-wave1p5/golden-postgres-default.json
A	docs/acceptance/v2.1-align-wave1p5/golden-postgres-legacy100.json
A	docs/acceptance/v2.1-align-wave1p5/golden-postgres-legacy75.json
A	docs/acceptance/v2.1-align-wave1p5/golden-sqlite-default.json
A	docs/acceptance/v2.1-align-wave1p5/golden-sqlite-legacy100.json
A	docs/acceptance/v2.1-align-wave1p5/golden-sqlite-legacy75.json
A	docs/acceptance/v2.1-align-wave1p5/l3-inherited-postgres-process.log
A	docs/acceptance/v2.1-align-wave1p5/l3-inherited-sqlite-process.log
A	docs/acceptance/v2.1-align-wave1p5/openapi-structural.json
A	docs/acceptance/v2.1-align-wave1p5/p5-focused-all.log
A	docs/acceptance/v2.1-align-wave1p5/pending-manifest.json
A	docs/acceptance/v2.1-align-wave1p5/perf-after-final-postgres.json
A	docs/acceptance/v2.1-align-wave1p5/perf-after-final-sqlite.json
A	docs/acceptance/v2.1-align-wave1p5/perf-before-postgres.json
A	docs/acceptance/v2.1-align-wave1p5/perf-before-sqlite.json
A	docs/acceptance/v2.1-align-wave1p5/perf-paired-comparison.json
A	docs/acceptance/v2.1-align-wave1p5/performance-timestamp-provenance.json
A	docs/acceptance/v2.1-align-wave1p5/principal-final-reentrant-task.log
A	docs/acceptance/v2.1-align-wave1p5/profile-after-final-postgres.txt
A	docs/acceptance/v2.1-align-wave1p5/profile-after-final-sqlite.txt
A	docs/acceptance/v2.1-align-wave1p5/profile-before-postgres.txt
A	docs/acceptance/v2.1-align-wave1p5/profile-before-sqlite.txt
A	docs/acceptance/v2.1-align-wave1p5/protected-sources.json
A	docs/acceptance/v2.1-align-wave1p5/sandbox-replay-init-failure.log
A	docs/acceptance/v2.1-align-wave1p5/sandbox-shutdown-final.log
A	docs/acceptance/v2.1-align-wave1p5/schema-after-postgres.json
A	docs/acceptance/v2.1-align-wave1p5/schema-after-sqlite.json
A	docs/acceptance/v2.1-align-wave1p5/schema-before-postgres.json
A	docs/acceptance/v2.1-align-wave1p5/schema-before-sqlite.json
A	docs/acceptance/v2.1-align-wave1p5/schema_and_perf.py
A	docs/acceptance/v2.1-align-wave1p5/ts-final-tests.json
A	docs/acceptance/v2.1-align-wave1p5/v1-loopback-sanitized.json
A	docs/acceptance/v2.1-align-wave1p5/verify_package.py
A	docs/acceptance/v2.1-align-wave1p5/wire-postgres.json
A	docs/acceptance/v2.1-align-wave1p5/wire-sqlite.json
A	docs/acceptance/v2.1-align-wave1p8/ALIGN_WAVE1P8_HANDOFF_REPORT.md
A	docs/acceptance/v2.1-align-wave1p8/CI_STEP_MAPPING.json
A	docs/acceptance/v2.1-q3-phase1/Q3_PHASE1_HANDOFF_REPORT.md
A	docs/acceptance/v2.1-q3-phase1/benchmark-115-postgres.json
A	docs/acceptance/v2.1-q3-phase1/benchmark-115-sqlite.json
A	docs/acceptance/v2.1-q3-phase1/ci-four-job-matrix.json
A	docs/acceptance/v2.1-q3-phase1/ci-q2-convergence-candidate.json
A	docs/acceptance/v2.1-q3-phase1/cleanup.json
A	docs/acceptance/v2.1-q3-phase1/dr-v5-fingerprints.json
A	docs/acceptance/v2.1-q3-phase1/evidence-manifest.json
A	docs/acceptance/v2.1-q3-phase1/l1-stdlib-only.log
A	docs/acceptance/v2.1-q3-phase1/l2-full-and-build.log
A	docs/acceptance/v2.1-q3-phase1/l3-runtime-http-results.json
A	docs/acceptance/v2.1-q3-phase1/l3-runtime-postgres-http.md
A	docs/acceptance/v2.1-q3-phase1/l4-browser.md
A	docs/acceptance/v2.1-q3-phase1/legacy100-postgres.json
A	docs/acceptance/v2.1-q3-phase1/legacy100-sqlite.json
A	docs/acceptance/v2.1-q3-phase1/legacy75-postgres.json
A	docs/acceptance/v2.1-q3-phase1/legacy75-sqlite.json
A	docs/acceptance/v2.1-q3-phase1/live_runtime_probe.py
A	docs/acceptance/v2.1-q3-phase1/main-policy-observation.json
A	docs/acceptance/v2.1-q3-phase1/package-sha256.json
A	docs/acceptance/v2.1-q3-phase1/postgres-v0-v4-migration.json
A	docs/acceptance/v2.1-q3-phase1/task0-convergence.md
A	docs/acceptance/v2.1-q3-phase1/verify_package.py
A	docs/acceptance/v2.1-q3-phase2/Q3_PHASE2_HANDOFF_REPORT.md
A	docs/acceptance/v2.1-q3-phase2/benchmark-115-postgres.json
A	docs/acceptance/v2.1-q3-phase2/benchmark-115-sqlite.json
A	docs/acceptance/v2.1-q3-phase2/ci-four-job-matrix.json
A	docs/acceptance/v2.1-q3-phase2/cleanup.json
A	docs/acceptance/v2.1-q3-phase2/dataset-freeze.json
A	docs/acceptance/v2.1-q3-phase2/evidence-manifest.json
A	docs/acceptance/v2.1-q3-phase2/http-postgres.json
A	docs/acceptance/v2.1-q3-phase2/http-sqlite.json
A	docs/acceptance/v2.1-q3-phase2/l1-stdlib-only.log
A	docs/acceptance/v2.1-q3-phase2/l2-full-and-build.log
A	docs/acceptance/v2.1-q3-phase2/l3-rerank-postgres-http.md
A	docs/acceptance/v2.1-q3-phase2/l4-browser.md
A	docs/acceptance/v2.1-q3-phase2/legacy100-postgres.json
A	docs/acceptance/v2.1-q3-phase2/legacy100-sqlite.json
A	docs/acceptance/v2.1-q3-phase2/legacy75-postgres.json
A	docs/acceptance/v2.1-q3-phase2/legacy75-sqlite.json
A	docs/acceptance/v2.1-q3-phase2/package-sha256.json
A	docs/acceptance/v2.1-q3-phase2/pairwise-eval-postgres.json
A	docs/acceptance/v2.1-q3-phase2/pairwise-eval-sqlite.json
A	docs/acceptance/v2.1-q3-phase2/run_evidence.py
A	docs/acceptance/v2.1-q3-phase2/unchanged-goldens-schema-dependencies.json
A	docs/acceptance/v2.1-q3-phase2/verify_package.py
A	docs/acceptance/v2.2-align-wave2/ALIGN_WAVE2_HANDOFF_REPORT.md
A	docs/acceptance/v2.2-align-wave2/OWNER_PROCLAMATION.md
A	docs/acceptance/v2.2-align-wave2/ci-command-preservation-map.json
A	docs/acceptance/v2.2-align-wave2/docker_wave2_probe.py
A	docs/acceptance/v2.2-align-wave2/dr-v6.json
A	docs/acceptance/v2.2-align-wave2/frozen-verification.json
A	docs/acceptance/v2.2-align-wave2/golden-v6-postgres115.json
A	docs/acceptance/v2.2-align-wave2/golden-v6-sqlite115.json
A	docs/acceptance/v2.2-align-wave2/resolve_receipt.py
A	docs/acceptance/v2.2-align-wave2/verify_frozen.py
A	docs/acceptance/v2.2-align-wave2/wire-v2-captured.json
A	docs/acceptance/v21-wave0/OWNER_WAVE_V21_0_DIRECTIVE.md
A	docs/acceptance/v21-wave0/SOURCE_GAPS.md
A	docs/acceptance/v21-wave0/V21_WAVE0_TEAM_A_HANDOFF_REPORT.md
A	docs/acceptance/v21-wave0/resolve_receipt.py
A	docs/acceptance/v21-wave0/verify_frozen.output.json
A	docs/acceptance/v21-wave0/verify_v21_boundaries.output.json
A	docs/acceptance/v21-wave1/V21_WAVE1_TEAM_A_HANDOFF_REPORT.md
A	docs/acceptance/v21-wave2/T01_T27_SANDBOX_DRY_RUN_MATRIX.md
A	docs/acceptance/v21-wave2/V21_WAVE2_TEAM_A_HANDOFF_REPORT.md
A	docs/acceptance/v21-wave3/PRE_V7_RELEASE_READINESS_CHECKLIST.md
A	docs/acceptance/v21-wave3/V21_WAVE3_TEAM_A_HANDOFF_REPORT.md
A	docs/acceptance/v21-wave3/W3_INTEROP_PARITY_RECORD.md
A	docs/acceptance/v21-wave4/FINAL_SPACE_AND_FAVORITES_ALIGNMENT_DRAFT.md
A	docs/acceptance/v21-wave4/PRE_V7_RELEASE_READINESS_CHECKLIST_V2.md
A	docs/acceptance/v21-wave4/V21_WAVE4_TEAM_A_HANDOFF_REPORT.md
A	docs/acceptance/v21-wave5/FINAL_SPACE_AND_FAVORITES_ALIGNMENT.md
A	docs/acceptance/v21-wave5/SCHEMA_V7_SANDBOX_DESIGN_AND_ROLLBACK_SPEC.md
A	docs/acceptance/v21-wave5/V21_WAVE5_TEAM_A_HANDOFF_REPORT.md
A	docs/acceptance/v21-wave6/FINAL_SPACE_AND_FAVORITES_ALIGNMENT_FROZEN.md
A	docs/acceptance/v21-wave6/V21_WAVE6_TEAM_A_HANDOFF_REPORT.md
A	docs/acceptance/v21-wave6/W6A2_SANDBOX_T01_T27_REPORT.json
A	docs/acceptance/v21-wave7/V21_WAVE7_TEAM_A_HANDOFF_REPORT.md
A	docs/acceptance/v21-wave7/W7A2_CORE_V7_T01_T27_REPORT.json
A	docs/acceptance/v21-wave8/V21_WAVE8_TEAM_A_PR_READINESS_PACK.md
A	docs/agent-runtime-compat.md
A	docs/agent-runtime.md
A	docs/architecture/knowledge-sdk-alignment/00_CURRENT_STATE_AUDIT.md
A	docs/architecture/knowledge-sdk-alignment/01_OPENBOT_REQUIREMENTS_MAPPING.md
A	docs/architecture/knowledge-sdk-alignment/02_DOMAIN_MODEL_ALIGNMENT.md
A	docs/architecture/knowledge-sdk-alignment/03_DOMAIN_CONTRACTS.md
A	docs/architecture/knowledge-sdk-alignment/04_TEAM_A_NEXT_STAGE_EXECUTION_PLAN.md
A	docs/architecture/knowledge-sdk-alignment/05_TEAM_A_EXECUTION_DIRECTIVE_WAVE1.md
A	docs/architecture/knowledge-sdk-alignment/06_WAVE1_ACCEPTANCE_AND_NEXT_DIRECTIVE.md
A	docs/architecture/knowledge-sdk-alignment/07_TEAM_A_TO_TEAM_B_CONSENSUS_RESPONSE.md
A	docs/architecture/knowledge-sdk-alignment/08_TEAM_A_DELTA_SIGNOFF_AND_MIN_SLICE.md
A	docs/architecture/knowledge-sdk-alignment/09_WAVE1P5_CONSOLIDATED_EXECUTION_DIRECTIVE.md
A	docs/architecture/knowledge-sdk-alignment/10_WAVE1P5_ACCEPTANCE_AND_DELTA_DIRECTIVE.md
A	docs/architecture/knowledge-sdk-alignment/12_WAVE1P8_PRE_M2_FOUNDATION_DIRECTIVE.md
A	docs/architecture/knowledge-sdk-alignment/ARCHIVE_KB_BOUNDARY.md
A	docs/architecture/knowledge-sdk-alignment/M1_DECISION_PACKAGE.md
A	docs/architecture/knowledge-sdk-alignment/OWNER_SUPPLEMENT_WAVE1_T56U_ORIGINAL.md
A	docs/architecture/knowledge-sdk-alignment/PROVENANCE.json
A	docs/architecture/knowledge-sdk-alignment/PROVENANCE.md
A	docs/architecture/knowledge-sdk-alignment/SOURCE10_STANDALONE_T59_ORIGINAL.md
A	docs/architecture/knowledge-sdk-alignment/WAVE1P5B_SOURCE_PROVENANCE.json
A	docs/architecture/knowledge-sdk-alignment/contracts/.gitignore
A	docs/architecture/knowledge-sdk-alignment/contracts/README.md
A	docs/architecture/knowledge-sdk-alignment/contracts/contract-fixtures/agent-intersection-deny.json
A	docs/architecture/knowledge-sdk-alignment/contracts/contract-fixtures/calibrated-search-response.json
A	docs/architecture/knowledge-sdk-alignment/contracts/contract-fixtures/dual-uri-evidence.json
A	docs/architecture/knowledge-sdk-alignment/contracts/contract-fixtures/error-envelope.json
A	docs/architecture/knowledge-sdk-alignment/contracts/contract-fixtures/hash-vectors-utf8.json
A	docs/architecture/knowledge-sdk-alignment/contracts/contract-fixtures/identity-context.json
A	docs/architecture/knowledge-sdk-alignment/contracts/contract-fixtures/identity-lifecycle-fixtures.json
A	docs/architecture/knowledge-sdk-alignment/contracts/contract-fixtures/kb-lifecycle.json
A	docs/architecture/knowledge-sdk-alignment/contracts/contract-fixtures/policy-generation-cases.json
A	docs/architecture/knowledge-sdk-alignment/contracts/contract-fixtures/rollback-activation-cases.json
A	docs/architecture/knowledge-sdk-alignment/contracts/contract-fixtures/signed-request-canonicalization.json
A	docs/architecture/knowledge-sdk-alignment/contracts/delta_contracts.py
A	docs/architecture/knowledge-sdk-alignment/contracts/fixture-evidence-boundaries.json
A	docs/architecture/knowledge-sdk-alignment/contracts/fixture-schemas.json
A	docs/architecture/knowledge-sdk-alignment/contracts/generate_assets.py
A	docs/architecture/knowledge-sdk-alignment/contracts/minimum-slice-checklist.json
A	docs/architecture/knowledge-sdk-alignment/contracts/openapi-v2-draft.yaml
A	docs/architecture/knowledge-sdk-alignment/contracts/openbot-adapter-dto.d.ts
A	docs/architecture/knowledge-sdk-alignment/contracts/package-lock.json
A	docs/architecture/knowledge-sdk-alignment/contracts/package.json
A	docs/architecture/knowledge-sdk-alignment/contracts/uri-mapping.test.ts
A	docs/architecture/knowledge-sdk-alignment/contracts/uri-mapping.ts
A	docs/architecture/knowledge-sdk-alignment/contracts/validate_assets.py
A	docs/architecture/knowledge-sdk-alignment/m1-freeze-manifest.json
A	docs/architecture/knowledge-sdk-alignment/validate_m1_manifest.py
A	docs/rerank-evaluation.md
M	pyproject.toml
A	sandbox/v21_reuse_v1/README.md
A	sandbox/v21_reuse_v1/__init__.py
A	sandbox/v21_reuse_v1/adapters.py
A	sandbox/v21_reuse_v1/dry_run_cases.py
A	sandbox/v21_reuse_v1/fixtures/w2_interop_golden.json
A	sandbox/v21_reuse_v1/http_loopback_cases.py
A	sandbox/v21_reuse_v1/ikc.py
A	sandbox/v21_reuse_v1/interop_cases.py
A	sandbox/v21_reuse_v1/interop_harness.py
A	sandbox/v21_reuse_v1/ksg_lite.py
A	sandbox/v21_reuse_v1/loopback_service.py
A	sandbox/v21_reuse_v1/pre03_validator.py
A	sandbox/v21_reuse_v1/resources.py
A	sandbox/v21_reuse_v1/retrieval_plan.py
A	sandbox/v21_reuse_v1/revocation.py
A	sandbox/v21_reuse_v1/sandbox_cases.py
A	sandbox/v21_reuse_v1/semantic_reference.py
A	sandbox/v21_reuse_v1/test_pre03_validator_cases.py
A	sandbox/v21_schema_v7/README.md
A	sandbox/v21_schema_v7/__init__.py
A	sandbox/v21_schema_v7/constants.py
A	sandbox/v21_schema_v7/engine.py
A	sandbox/v21_schema_v7/pg_ddl_semantics.py
A	sandbox/v21_schema_v7/protocol.py
A	sandbox/v21_schema_v7/report.py
A	sandbox/v21_schema_v7/schema_v7_sandbox_cases.py
A	sandbox/v21_schema_v7/sqlite_sandbox.py
A	sandbox/v21_schema_v7/t01_t27_cases.py
A	scripts/verify_v21_boundaries.py
A	scripts/wave1p8/verify_scope.py
M	src/knowledge_sdk/__init__.py
A	src/knowledge_sdk/audit/telemetry.py
M	src/knowledge_sdk/client/base.py
A	src/knowledge_sdk/client/compat.py
M	src/knowledge_sdk/client/http_client.py
M	src/knowledge_sdk/client/local.py
M	src/knowledge_sdk/connectors/base.py
M	src/knowledge_sdk/connectors/http.py
A	src/knowledge_sdk/connectors/planning.py
M	src/knowledge_sdk/contracts/__init__.py
M	src/knowledge_sdk/contracts/audit.py
M	src/knowledge_sdk/contracts/events.py
A	src/knowledge_sdk/contracts/idempotency.py
M	src/knowledge_sdk/contracts/impact.py
A	src/knowledge_sdk/contracts/ingestion_jobs.py
M	src/knowledge_sdk/contracts/models.py
A	src/knowledge_sdk/contracts/runtime.py
A	src/knowledge_sdk/contracts/v2_json.py
A	src/knowledge_sdk/contracts/v2_schemas.py
M	src/knowledge_sdk/impact/radar.py
M	src/knowledge_sdk/ingestion/chunkers/fixed.py
M	src/knowledge_sdk/ingestion/parsers/__init__.py
M	src/knowledge_sdk/ingestion/parsers/builtin.py
M	src/knowledge_sdk/mcp/tools.py
A	src/knowledge_sdk/retrieval/adapters/reranker.py
A	src/knowledge_sdk/retrieval/calibration.py
A	src/knowledge_sdk/retrieval/eval.py
M	src/knowledge_sdk/retrieval/hybrid.py
A	src/knowledge_sdk/retrieval/rerank.py
A	src/knowledge_sdk/retrieval/strategies.py
A	src/knowledge_sdk/runtime/__init__.py
A	src/knowledge_sdk/runtime/service.py
M	src/knowledge_sdk/server/app.py
A	src/knowledge_sdk/server/container.py
A	src/knowledge_sdk/server/operations.py
M	src/knowledge_sdk/server/scim.py
A	src/knowledge_sdk/server/v2.py
A	src/knowledge_sdk/server/v2_auth.py
M	src/knowledge_sdk/storage/base.py
M	src/knowledge_sdk/storage/dr_drill.py
A	src/knowledge_sdk/storage/migration_v6.py
A	src/knowledge_sdk/storage/migration_v7.py
M	src/knowledge_sdk/storage/migrations.py
A	src/knowledge_sdk/storage/persistent_contracts.py
M	src/knowledge_sdk/storage/postgres_schema.sql
M	src/knowledge_sdk/storage/postgres_store.py
A	src/knowledge_sdk/storage/runtime.py
A	src/knowledge_sdk/storage/schema_v7.py
M	src/knowledge_sdk/storage/sqlite_store.py
A	src/knowledge_sdk/storage/v2_metadata.py
A	tests/alignment/__init__.py
A	tests/alignment/test_wave1_assets.py
A	tests/alignment/test_wave1_compat.py
A	tests/alignment/test_wave1_wire.py
A	tests/alignment_p5/__init__.py
A	tests/alignment_p5/test_manifest.py
A	tests/alignment_p5/test_principal_snapshot.py
A	tests/alignment_p5/test_rollback.py
A	tests/alignment_p5/test_sandbox.py
A	tests/alignment_p5b/__init__.py
A	tests/alignment_p5b/test_contract_delta.py
A	tests/alignment_p5b/test_wire_evidence.py
A	tests/benchmark/g9.py
A	tests/benchmark/golden_cases_v4_runtime.jsonl
M	tests/benchmark/runner.py
A	tests/foundation/__init__.py
A	tests/foundation/helpers.py
A	tests/foundation/test_cross_protocol_parity.py
A	tests/foundation/test_dual_engine.py
A	tests/foundation/test_ingestion.py
A	tests/foundation/test_operations.py
A	tests/foundation/test_primitives.py
M	tests/mcp/test_phase4_issues.py
M	tests/mcp/test_phase4_tools.py
M	tests/permissions/test_phase2_policy_engine.py
M	tests/q2/test_impact.py
M	tests/q2/test_postgres.py
M	tests/q2/test_q2_m4_enterprise.py
M	tests/q2/test_schema_v3.py
A	tests/q3/__init__.py
A	tests/q3/test_runtime.py
A	tests/retrieval/eval_config_q3_m2.json
A	tests/retrieval/eval_corpus_q3_m2.jsonl
A	tests/retrieval/eval_dataset_q3_m2.jsonl
A	tests/retrieval/eval_freeze_q3_m2.json
A	tests/retrieval/q3_m2_fixture.py
A	tests/retrieval/test_pairwise_evaluator.py
A	tests/retrieval/test_rerank_and_calibration.py
A	tests/runtime_helpers.py
M	tests/server/test_phase1_auth.py
A	tests/server/test_q3_m2_http.py
A	tests/server/test_q3_runtime_http.py
M	tests/storage/test_phase3_sqlite_v2_and_fetch.py
A	tests/wave2/__init__.py
A	tests/wave2/run_golden_v6.py
A	tests/wave2/test_persistence.py
A	tests/wave2/test_runtime.py
A	tests/wave2/test_sandbox.py
A	tests/wave2/test_schema_source.py
A	tests/wave7/__init__.py
A	tests/wave7/test_core_v7_t01_t27_cases.py
A	tests/wave7/w7a2_report.py
```

Commits already contained in the frozen parent `2b6944e5` (`b953c992..2b6944e5`, 73):

```
2b6944e docs(v21): add Wave-V21-7 Team A handoff report
a5fa513 fix(v21): scope Postgres writes by tenant_id and drop BEGIN IMMEDIATE
cd97a41 fix(v21): use ON CONFLICT DO NOTHING for key-only Schema v7 upserts
8c6c704 fix(v21): escape PostgreSQL LIKE percents in Schema v7 DDL
2d4b4db feat(v21): add Wave-V21-7 core Schema v7 and T-01-T-27 formal-path suite
91b8b6f docs(v21): add Wave-V21-6 Team A handoff report
410f4bf feat(v21): add Wave-V21-6 Schema v7 sandbox and T-01-T-27 suite
ce8297f docs(v21): add Wave-V21-5 Team A handoff report
6c59ad9 feat(v21): add Wave-V21-5 Gate 6 prep and PRE-03 sandbox validator
e97a8cc docs(v21): add Wave-V21-4 Team A handoff report
fe912a8 docs(v21): add Wave-V21-4 pre-v7 checklist and alignment draft
918293c fix(v21): drain POST bodies before early 403/404 loopback replies
72c227e docs(v21): add Wave-V21-3 Team A handoff report
bfaa55c feat(v21): add stdlib HTTP loopback replay and pre-v7 checklist
b1b3241 docs(v21): record Sync-W2-1 parity and hard-lock golden SHA
4d54627 docs(v21): add Wave-V21-2 Team A handoff report
bfd6b66 feat(v21): add T-01..T-27 sandbox dry-run matrix and loopback cases
37c9825 feat(v21): add Wave-V21-2 interop harness and golden fixture
2079539 docs(v21): add Wave-V21-1 Team A handoff report
39052a9 feat(v21): add stdlib adapter clients and loopback service
116877f feat(v21): promote v21-reuse-v1 to FROZEN_V21_REUSE_V1
9d25ea9 docs(v21): remap Wave-V21-0 handoff to official section-7 audit fields
02bf587 fix(v21): ignore ephemeral CI evidence paths in the boundary scanner
0046254 docs(v21): add Team A handoff report, source gap, and receipt resolver
171dfc2 feat(v21): add Wave-V21-0 boundary verifier and independent CI job
32e71e8 feat(v21): add zero-DDL sandbox prototypes and closed-loop tests
cb8571f feat(v21): add isolated Wave-V21-0 reuse contracts and draft DTOs
9940818 fix(v2): enforce current task scope on new assets and exact replay
c6bd038 test(wave2): add dual-engine sandbox evidence and preserved parallel CI
3f91384 feat(api): mount isolated strict signed JSON v2 minimum runtime
5299076 feat(storage): add owned v6 migration and durable contract stores
5a139e5 fix: satisfy unchanged source gate and extend L2 tool parity
496ea98 docs: record Wave1.8 acceptance boundaries and reproducible evidence
10d584f feat: harden v1 telemetry and prove three-protocol revocation parity
fd0524f fix: fail closed on malformed ingestion and prove dual-engine isolation
f296e8c feat: add memory-only idempotency and ingestion job foundations
b9e9631 ci: decompose preserved validation gates into bounded parallel jobs
07f5d39 docs(contracts): close Wave1.5b source-verified pending M1 draft assets
5775d42 docs(readiness): archive actual dual-engine gates mixed latency and five-part pending-signoff handoff
7b2594c fix(readiness): give loopback-published adapter a return route while keeping fixture PG network private
9dd323c fix(readiness): close real fixture connections even when replay initialization refuses startup
4b59d48 test(readiness): prove reentrant same-user task purpose and tenant gates remain uncached
ae73063 test(readiness): retain all inherited package checks and add readiness AST and extracted-wheel audit smoke
9242393 test(readiness): wait for actual PG TCP initialization and handle successful one-shot seeds portably
6638b26 fix(readiness): close sandbox store cleanly without inventing a replay-store close API
8d530a3 test(readiness): keep image UID assertions while tightening inherited CI fixture keys to 0600
e0ce6d0 fix(readiness): reject ambiguous URI reverse maps and isolate default sandbox project names
841f67e fix(readiness): explicitly retain SQLite compose asset despite database filename ignore
fb0c9f4 perf(readiness): bound successful principal reuse to one locked request with fresh revocation gates
cefd046 feat(readiness): add signed dual-engine sandbox assets and executable locked TypeScript draft mapping
c9be087 docs(readiness): add seven pending M1 decisions and non-authorizing manifest verifier
d8a6176 feat(readiness): make v5 content-only rollback audit scope explicit without new response fields
60b6436 test(alignment): retry transient container startup resets while retaining real readiness and full matrix gates
a1c3789 docs(alignment): archive real dual-engine gates, protected-pool latency comparison and honest review limitations
c1f2a17 test(alignment): prove previews physically read-only and exercise extracted v1 wheel
97ea9c8 ci(alignment): resolve dynamic test service port in a supported step context
77493a4 test(alignment): record the frozen base_score field in protected-pool evidence
a8497cd feat(alignment): add v5 compatible management, safe previews, request-local ranking optimization and draft adapter assets
bc0a515 docs(alignment): preserve six supplied governance originals and independent owner directive provenance
d153295 docs(q3): archive measured rerank gains, unchanged115 regressions and real dual-engine acceptance
a57a4b9 fix(retrieval): enforce bounded scoring sequences and threshold validation at the internal search boundary
711701b test(retrieval): enforce adversarial scoring, dual-engine paired quality and real signed runtime revocation probes
e21f41a feat(eval): freeze disjoint multilingual corpus and implement instrumented paired real retrieval metrics
1042e7c feat(search): rank only accepted redacted summaries across local HTTP MCP and task runtime
923186d feat(retrieval): add independent monotone calibration channels and strict named strategy selection
36d7892 feat(retrieval): add frozen controlled reranker protocol and deterministic bilingual lexical scoring
69b6c98 docs(q3): archive verified dual-engine runtime evidence and explicit remaining gates
8acce64 fix(contracts): reject boolean timestamp and digest aliases in frozen runtime models
07a2ddc fix(runtime): reject future directory generation claims before creating tasks or mutating profiles
9c5e1e4 test(runtime): migrate historical MCP wire fixture setup without weakening assertions
82eb9fb test(runtime): add G9 goldens, adversarial dual-engine races and real signed HTTP probes
ac9be74 feat(runtime): add policy-bound immutable task snapshots and atomic mid-task revocation
8f09e5e feat(storage): add frozen runtime contracts and lossless tenant-scoped schema v5
```

This commit (74th ahead of `main`) is the ordinary Wave-V21-8 readiness / allowlist commit that introduces this pack and registers `docs/acceptance/v21-wave8/` in `scripts/verify_v21_boundaries.py`.

### 2.2 `9940818b..HEAD` (Wave2 / Schema v6 baseline)

- Baseline SHA: `9940818b962ccb186c0dfb0158de6bd9bd49057b`
- `ahead_by`: **28** (27 commits already on the frozen Wave-V21-7 tip, plus this Wave-V21-8 commit)
- `behind_by`: **0**
- `git diff --shortstat 9940818b..HEAD`: 84 files changed, 17288 insertions(+), 7 deletions(-)
- Files changed: **84**

This commit versus `9940818b` adds one new path (`docs/acceptance/v21-wave8/V21_WAVE8_TEAM_A_PR_READINESS_PACK.md`) on top of the 83-file Wave-V21-7 tip inventory, and modifies already-listed `scripts/verify_v21_boundaries.py`. `src/knowledge_sdk/storage/postgres_schema.sql` remains byte-identical to `9940818b` (SHA-256 `30a218734fe49bc4b7625b215603f8d85a63da4742bdddfecfe0fa869d338a6e`). `.github/workflows/tests.yml` is not modified in this wave and still starts with the `9940818b` baseline bytes. `pyproject.toml` `dependencies` remains `[]`.

Name-status (A/M/D) of `9940818b..HEAD`:

```
M	.github/workflows/tests.yml
A	contracts/v21-reuse-v1/.gitignore
A	contracts/v21-reuse-v1/README.md
A	contracts/v21-reuse-v1/ai-execution-trace.schema.json
A	contracts/v21-reuse-v1/ai-execution-trace.vectors.json
A	contracts/v21-reuse-v1/check.ts
A	contracts/v21-reuse-v1/controlled-data-bridge.schema.json
A	contracts/v21-reuse-v1/controlled-data-bridge.vectors.json
A	contracts/v21-reuse-v1/dto.py
A	contracts/v21-reuse-v1/dto.ts
A	contracts/v21-reuse-v1/memory-resource-bridge.schema.json
A	contracts/v21-reuse-v1/memory-resource-bridge.vectors.json
A	contracts/v21-reuse-v1/model-adapter.schema.json
A	contracts/v21-reuse-v1/model-adapter.vectors.json
A	contracts/v21-reuse-v1/openapi-v3-draft.vectors.json
A	contracts/v21-reuse-v1/openapi-v3-draft.yaml
A	contracts/v21-reuse-v1/package-lock.json
A	contracts/v21-reuse-v1/package.json
A	contracts/v21-reuse-v1/status.json
A	contracts/v21-reuse-v1/tsconfig.json
A	contracts/v21-reuse-v1/v21-contract-manifest.json
A	contracts/v21-reuse-v1/validate.py
A	docs/acceptance/v21-wave0/OWNER_WAVE_V21_0_DIRECTIVE.md
A	docs/acceptance/v21-wave0/SOURCE_GAPS.md
A	docs/acceptance/v21-wave0/V21_WAVE0_TEAM_A_HANDOFF_REPORT.md
A	docs/acceptance/v21-wave0/resolve_receipt.py
A	docs/acceptance/v21-wave0/verify_frozen.output.json
A	docs/acceptance/v21-wave0/verify_v21_boundaries.output.json
A	docs/acceptance/v21-wave1/V21_WAVE1_TEAM_A_HANDOFF_REPORT.md
A	docs/acceptance/v21-wave2/T01_T27_SANDBOX_DRY_RUN_MATRIX.md
A	docs/acceptance/v21-wave2/V21_WAVE2_TEAM_A_HANDOFF_REPORT.md
A	docs/acceptance/v21-wave3/PRE_V7_RELEASE_READINESS_CHECKLIST.md
A	docs/acceptance/v21-wave3/V21_WAVE3_TEAM_A_HANDOFF_REPORT.md
A	docs/acceptance/v21-wave3/W3_INTEROP_PARITY_RECORD.md
A	docs/acceptance/v21-wave4/FINAL_SPACE_AND_FAVORITES_ALIGNMENT_DRAFT.md
A	docs/acceptance/v21-wave4/PRE_V7_RELEASE_READINESS_CHECKLIST_V2.md
A	docs/acceptance/v21-wave4/V21_WAVE4_TEAM_A_HANDOFF_REPORT.md
A	docs/acceptance/v21-wave5/FINAL_SPACE_AND_FAVORITES_ALIGNMENT.md
A	docs/acceptance/v21-wave5/SCHEMA_V7_SANDBOX_DESIGN_AND_ROLLBACK_SPEC.md
A	docs/acceptance/v21-wave5/V21_WAVE5_TEAM_A_HANDOFF_REPORT.md
A	docs/acceptance/v21-wave6/FINAL_SPACE_AND_FAVORITES_ALIGNMENT_FROZEN.md
A	docs/acceptance/v21-wave6/V21_WAVE6_TEAM_A_HANDOFF_REPORT.md
A	docs/acceptance/v21-wave6/W6A2_SANDBOX_T01_T27_REPORT.json
A	docs/acceptance/v21-wave7/V21_WAVE7_TEAM_A_HANDOFF_REPORT.md
A	docs/acceptance/v21-wave7/W7A2_CORE_V7_T01_T27_REPORT.json
A	docs/acceptance/v21-wave8/V21_WAVE8_TEAM_A_PR_READINESS_PACK.md
A	sandbox/v21_reuse_v1/README.md
A	sandbox/v21_reuse_v1/__init__.py
A	sandbox/v21_reuse_v1/adapters.py
A	sandbox/v21_reuse_v1/dry_run_cases.py
A	sandbox/v21_reuse_v1/fixtures/w2_interop_golden.json
A	sandbox/v21_reuse_v1/http_loopback_cases.py
A	sandbox/v21_reuse_v1/ikc.py
A	sandbox/v21_reuse_v1/interop_cases.py
A	sandbox/v21_reuse_v1/interop_harness.py
A	sandbox/v21_reuse_v1/ksg_lite.py
A	sandbox/v21_reuse_v1/loopback_service.py
A	sandbox/v21_reuse_v1/pre03_validator.py
A	sandbox/v21_reuse_v1/resources.py
A	sandbox/v21_reuse_v1/retrieval_plan.py
A	sandbox/v21_reuse_v1/revocation.py
A	sandbox/v21_reuse_v1/sandbox_cases.py
A	sandbox/v21_reuse_v1/semantic_reference.py
A	sandbox/v21_reuse_v1/test_pre03_validator_cases.py
A	sandbox/v21_schema_v7/README.md
A	sandbox/v21_schema_v7/__init__.py
A	sandbox/v21_schema_v7/constants.py
A	sandbox/v21_schema_v7/engine.py
A	sandbox/v21_schema_v7/pg_ddl_semantics.py
A	sandbox/v21_schema_v7/protocol.py
A	sandbox/v21_schema_v7/report.py
A	sandbox/v21_schema_v7/schema_v7_sandbox_cases.py
A	sandbox/v21_schema_v7/sqlite_sandbox.py
A	sandbox/v21_schema_v7/t01_t27_cases.py
A	scripts/verify_v21_boundaries.py
M	src/knowledge_sdk/storage/migration_v6.py
A	src/knowledge_sdk/storage/migration_v7.py
M	src/knowledge_sdk/storage/migrations.py
M	src/knowledge_sdk/storage/postgres_store.py
A	src/knowledge_sdk/storage/schema_v7.py
M	src/knowledge_sdk/storage/sqlite_store.py
A	tests/wave7/__init__.py
A	tests/wave7/test_core_v7_t01_t27_cases.py
A	tests/wave7/w7a2_report.py
```

Commits already contained in the frozen parent `2b6944e5` (`9940818b..2b6944e5`, 27):

```
2b6944e docs(v21): add Wave-V21-7 Team A handoff report
a5fa513 fix(v21): scope Postgres writes by tenant_id and drop BEGIN IMMEDIATE
cd97a41 fix(v21): use ON CONFLICT DO NOTHING for key-only Schema v7 upserts
8c6c704 fix(v21): escape PostgreSQL LIKE percents in Schema v7 DDL
2d4b4db feat(v21): add Wave-V21-7 core Schema v7 and T-01-T-27 formal-path suite
91b8b6f docs(v21): add Wave-V21-6 Team A handoff report
410f4bf feat(v21): add Wave-V21-6 Schema v7 sandbox and T-01-T-27 suite
ce8297f docs(v21): add Wave-V21-5 Team A handoff report
6c59ad9 feat(v21): add Wave-V21-5 Gate 6 prep and PRE-03 sandbox validator
e97a8cc docs(v21): add Wave-V21-4 Team A handoff report
fe912a8 docs(v21): add Wave-V21-4 pre-v7 checklist and alignment draft
918293c fix(v21): drain POST bodies before early 403/404 loopback replies
72c227e docs(v21): add Wave-V21-3 Team A handoff report
bfaa55c feat(v21): add stdlib HTTP loopback replay and pre-v7 checklist
b1b3241 docs(v21): record Sync-W2-1 parity and hard-lock golden SHA
4d54627 docs(v21): add Wave-V21-2 Team A handoff report
bfd6b66 feat(v21): add T-01..T-27 sandbox dry-run matrix and loopback cases
37c9825 feat(v21): add Wave-V21-2 interop harness and golden fixture
2079539 docs(v21): add Wave-V21-1 Team A handoff report
39052a9 feat(v21): add stdlib adapter clients and loopback service
116877f feat(v21): promote v21-reuse-v1 to FROZEN_V21_REUSE_V1
9d25ea9 docs(v21): remap Wave-V21-0 handoff to official section-7 audit fields
02bf587 fix(v21): ignore ephemeral CI evidence paths in the boundary scanner
0046254 docs(v21): add Team A handoff report, source gap, and receipt resolver
171dfc2 feat(v21): add Wave-V21-0 boundary verifier and independent CI job
32e71e8 feat(v21): add zero-DDL sandbox prototypes and closed-loop tests
cb8571f feat(v21): add isolated Wave-V21-0 reuse contracts and draft DTOs
```

### 2.3 `2b6944e5..HEAD` (this Wave-V21-8 increment only)

- Frozen Wave-V21-7 tip: `2b6944e559dd63b61640b64b104a86d8a502086f` (unmodified)
- `ahead_by`: **1** at this pack commit
- `behind_by`: **0**
- `git diff --shortstat 2b6944e5..HEAD`: 2 files changed, 747 insertions(+)
- Files changed: **2**

```
A	docs/acceptance/v21-wave8/V21_WAVE8_TEAM_A_PR_READINESS_PACK.md
M	scripts/verify_v21_boundaries.py
```

Why:

- `docs/acceptance/v21-wave8/V21_WAVE8_TEAM_A_PR_READINESS_PACK.md` — W8A-1 readiness pack (this file).
- `scripts/verify_v21_boundaries.py` — W8A-2 allowlist of prefix `docs/acceptance/v21-wave8/`. No other gates were loosened. `schema_version` remains 7 on this branch.

## 3. `schema_version==7` backward-compatibility and idempotent-rollback checklist

This checklist describes the isolated-branch core Schema v7 already accepted at `2b6944e5`. Wave-V21-8 does not change storage DDL, migration code, or tests. It is a PR-readiness and documentation increment only.

1. **v6 callers remain backward compatible.** `require_v6` / `upgrade_v6` accept schema versions 6 and 7. A v6 database can be opened and then explicitly upgraded. Existing v6 tables, JSON, ACLs, reviews, audit, and search rows are not rewritten by v7. Fresh stores still initialize at v5; `upgrade_v6` / `upgrade_v7` remain explicit. HTTP `/v2/spaces` stays frozen at baseline `9940818b`; the core v7 HTTP surface is the distinct `/v7-core/spaces` path. `/v3` is not mounted.
2. **`upgrade_v7` replay guard.** `upgrade_v7(store, owned_nonproduction=True)` requires an owned non-production database. If `schema_version` is already 7, the function validates v7 and v6 and returns (idempotent replay). If the version is not 6 or 7, it fails closed with `SCHEMA_V6_REQUIRED`. Production or shared stores are not upgraded in place; `schema_v7_prod_migration_authorized` stays false.
3. **`rollback_v7` replay guard.** `rollback_v7(store, owned_nonproduction=True)` is an idempotent structural rollback to Schema v6. It drops `ks_v7_*` objects, restores `PRAGMA user_version=6` on SQLite when coming from 7, and is a no-op on replay. It does **not** restore historical ACLs or grants. A second rollback must not re-apply grants.
4. **No department auto-mapping.** SPACE-C03 phase 1 remains `1 organization_team = 1 Team Space`. Department auto-mapping is refused.
5. **No phase-1 `parent_space_id` nesting.** Tenant → Space → KB is flat (1 Space : N KB). `parent_space_id` is forbidden in phase-1 DDL and validators (`PARENT_SPACE_FORBIDDEN`).
6. **Five-layer Fail-Closed isolation** is the official chain and is not overridable: Layer 0 tenant hard isolation (Tenant + PG FORCE RLS); Layer 1 Identity & Revocation; Layer 2 Space Gate; Layer 3 KB & Document Gate; Layer 4 User ∩ Agent & Redaction.
7. **Zero-copy Favorites.** Favorites are relationship pointers only (`user_id` + `target_type` + `target_id` / `userId` + `assetId` style). Body / Chunk / Embedding / Evidence are never stored on the pointer (`FAVORITE_BODY_FORBIDDEN`).
8. **`EXPERIMENTAL_V3_ENABLED` default false.** `EXPERIMENTAL_V3_ENABLED_DEFAULT = False`. `OPENBOT_KNOWLEDGE_SDK_V2_ENABLED` stays default false. Production HTTP must not mount `/v3`.
9. **PostgreSQL v7 is additive.** v7 tables are `ks_v7_*` beside the existing v6 schema, with `ENABLE` / `FORCE` RLS bound to `current_setting('app.current_org_id')`. `postgres_schema.sql` stays byte-identical to `9940818b`. v7 DDL lives in `migration_v7.py`.
10. **SQLite version fence.** Successful upgrade sets `PRAGMA user_version = 7`. Rollback sets it back to 6. `validate_v7` checks required tables/columns, forbids `parent_space_id`, and forbids favorite body columns.

## 4. DBA production-migration handoff red lines

This section is a red-line handoff, not an authorization to migrate any production database. **Do not treat any text in this pack as authorized production DDL cutover SQL.** No production cutover SQL is provided or authorized here.

| Red line | Required value | Binding statement |
| --- | --- | --- |
| `schema_v7_prod_migration_authorized` | **false** | Isolated-branch Schema v7 and formal T-01–T-27 engineering acceptance do not authorize production migration. |
| `schema_v8_v9_ddl_authorized` | **false** | Schema v8 / v9 DDL remains unauthorized. |
| `pr_merge_authorized` | **false** | Wave-V21-8 may open exactly one Draft PR for review and CI. `gh pr merge`, `gh pr ready`, and `--admin` are forbidden. Auto-merge must stay off. |
| `EXPERIMENTAL_V3_ENABLED` | default **false** | Do not mount `/v3` in production HTTP. |
| Production-database contact | **zero** | Engineering has zero production-database contact. No production DSN may be used, stored, or probed by this branch or by CI. |
| Real production export / migration | lead / DBA only | Any future real production export or Schema v7 migration remains lead/DBA work, and only after a later explicit Owner authorization that is not this order. |
| AUTH-V21-04 custodian | Daniel (daniel.hhd@gmail.com) | Named custodian remains Daniel. This record is not a request to email the custodian. |

CI live PostgreSQL, when used, is a disposable non-superuser pgvector role via `KNOWLEDGE_SDK_TEST_PG_DSN` in GitHub Actions. It is not a production DSN.

## 5. Frozen identity this pack must not drift

- `pyproject.toml` `dependencies == []`
- `contracts/v21-reuse-v1/` manifest SHA-256 `212537fd41bd4cc4d9d7343cacafaea225ee98b6586df716bf036a397cb2a382`
- Golden fixture `sandbox/v21_reuse_v1/fixtures/w2_interop_golden.json` SHA-256 `f8033a902af06b005fa591ab872a74f9569a3783fd3e7cef90c6dc94cf9d0fef` (33863 bytes)
- `src/knowledge_sdk/storage/postgres_schema.sql` byte-identical to `9940818b962ccb186c0dfb0158de6bd9bd49057b`
- Core `tests/benchmark` golden sources unchanged
- Frozen docs under `docs/acceptance/v21-wave5/`, `docs/acceptance/v21-wave6/`, and `docs/acceptance/v21-wave7/` are not edited

## 6. What this pack does not claim

- This is not authorization to merge the Draft PR to `main`.
- This is not authorization of a production Schema v7 migration.
- This is not a ready/non-draft PR and not an auto-merge enablement.
- This pack does not rewrite frozen contract flags or runtime `FORMAL_T01_T27_ACCEPTED`.
- Team A does not claim formal Owner acceptance of Wave-V21-8 in this file; Wave-V21-8 is in progress (W8A-1 of W8A-1 / W8A-2 / W8A-3).
