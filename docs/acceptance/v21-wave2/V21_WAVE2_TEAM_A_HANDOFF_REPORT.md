# V21_WAVE2_TEAM_A_HANDOFF_REPORT

Status: **Team A Wave-V21-2 implementation handoff (W2A-1 through W2A-3 local suite), not formal T-01–T-27 acceptance**. This report does not claim Space Gate 3/4 MET, Schema v7 authorization, official VB-1 lock changes, W2-Gate-1/2/3/4 MET, or production cutover. `formal_acceptance` remains false. Everything under the T-01..T-27 matrix is labeled **`DRY_RUN_SANDBOX_NOT_FORMAL_ACCEPTANCE`**.

Order: `WAVE_V21_1_JOINT_CLOSURE_AND_WAVE2_LAUNCH_ORDER` (SHA-256 `41a07761d2eb95eae9f0be02ef6db22ca460664c629d19a0dff0f1d83f618b8f`). Verdict already recorded as `WAVE_V21_1_JOINT_CLEAN_ACCEPT` with `wave_v21_2_unlocked=true`. Still false and unchanged here: `schema_v7_ddl_authorized`, `schema_v8_v9_ddl_authorized`, `final_alignment_frozen`, `prod_shadow_migration_cutover_authorized`. Official VB-1 lock remains `111/13/0`. AUTH-V21-04 remains HOLD. `formal_t01_t27` remains `NOT_RUN_NOT_ACCEPTED`.

## 1. Branch and commits

- Repository: `knowledge-sdk`
- Isolated branch: `feat/v21-wave2-e2e-interop`
- Isolated worktree: `/workspace/knowledge-sdk-v21-wave2`
- Frozen Wave-V21-1 tip (unmodified ancestor): `207953963872a4a7e65731def077c469b685f4e2`
- W2A-1 commit (already pushed, frozen, not amended): `37c982546f49bb8312670ad01be995d91f345043`
- W2A-2 / W2A-3 implementation commit: `bfd6b669b0ef87f34b572cc2a10985023ac27bb4` (parent is exactly `37c98254…`)
- This report is a follow-on docs commit on the same isolated branch. The exact branch-tip SHA after that commit, and the remote SHA after `git push -u`, belong in the external receipt `/workspace/v21-wave2-task-inputs/W2A23_RECEIPT.md`.
- Existing worktrees were left untouched: `/workspace/knowledge-sdk-v21-wave1` at `20795396…`, `/workspace/knowledge-sdk-v21-wave0` at `9d25ea96…`, `/workspace/knowledge-sdk` at `4bed2a1c…`.
- No PR, no merge to `main`, no force-push, no amend, no tag, no release. Frozen refs `main@b953c992`, `9d25ea96`, `20795396`, and `37c98254` were not rewritten.

## 2. Frozen contract identity (unchanged in W2A-1..W2A-3)

- Pack status: `FROZEN_V21_REUSE_V1`
- Deterministic manifest SHA-256: `212537fd41bd4cc4d9d7343cacafaea225ee98b6586df716bf036a397cb2a382`
- File count: 18
- Five schema groups and 51 vectors remain byte-identical to `20795396` / `37c98254`. W2A-1, W2A-2, and W2A-3 did not edit `contracts/v21-reuse-v1/` (`git diff 20795396 -- contracts/v21-reuse-v1` is empty).
- `scripts/verify_v21_boundaries.py` still hard-locks the SHA above. The only verifier edit in this wave after W2A-1 is incrementally allowing the new prefix `docs/acceptance/v21-wave2/`. Schema v6, `dependencies == []`, M1 28 assets, and the 709-file baseline lock were not loosened.

W2A-1 Sync-W2-1 values (already published in `/workspace/v21-wave2-task-inputs/W2A1_GOLDEN_RECEIPT.md`; this handoff does not re-send them to Team B):

- Commit SHA: `37c982546f49bb8312670ad01be995d91f345043`
- `sandbox/v21_reuse_v1/fixtures/w2_interop_golden.json` raw-byte SHA-256: `f8033a902af06b005fa591ab872a74f9569a3783fd3e7cef90c6dc94cf9d0fef`

## 3. What Team A delivered

### W2A-1 (already landed at `37c98254`, frozen)

Stdlib `interop_harness.py`, frozen golden fixture `fixtures/w2_interop_golden.json` (5 official groups, 16 cases, 4 canonicalization probes), and `interop_cases.py`. `receipt_hash` reuses `revocation.canonical_json_bytes`. Receipt: `/workspace/v21-wave2-task-inputs/W2A1_GOLDEN_RECEIPT.md`.

### W2A-2 — T-01..T-27 sandbox dry-run matrix and negative chaos cases

- `docs/acceptance/v21-wave2/T01_T27_SANDBOX_DRY_RUN_MATRIX.md` maps all 27 reserved IDs. Every row stays `NOT_RUN_NOT_ACCEPTED`. 11 IDs have an honest in-process analogue (`IN_PROCESS_DRY_RUN_ONLY`); 16 are `TRACKED_NOT_EXERCISED_IN_THIS_SANDBOX` because they need Space / Favorites / `/v2` / PG `FORCE RLS` / MCP / a reviewed production migration drill.
- `sandbox/v21_reuse_v1/dry_run_cases.py` (explicitly labeled `DRY_RUN_SANDBOX_NOT_FORMAL_ACCEPTANCE`) plus IKC / loopback `rollback_blue_green` cover the required chaos paths:
  - high-risk IKC blue/green rollback (live pointer only; both jobs stay `published`; `partial_available` remains forbidden; unapproved or no-target rollback fails closed);
  - KSG-Lite Phase 0 unapproved publish intercept (`APPROVAL_REQUIRED`, job stays `awaiting_approval` / `hidden`);
  - four-channel partial revocation with `purged=false`;
  - `RetrievalPlan` dual-view redaction with `redacted_unauthorized_count` and zero leak of unauthorized identifiers;
  - `ControlledDataBridge` tombstone → `UNAUTHORIZED` and Text-to-SQL / free SQL → `TEXT_TO_SQL_FORBIDDEN`.
- `status.json` was not modified.

### W2A-3 — zero-drift gate, CI discover, and this handoff

- `scripts/verify_v21_boundaries.py` incrementally allows `docs/acceptance/v21-wave2/` only. Frozen manifest SHA, Schema v6, 709 baseline files, M1 28 assets, and empty `dependencies` stay locked.
- `.github/workflows/tests.yml` (appended `v21-wave0-boundaries` job only; the file still starts with the exact `9940818b` baseline bytes) now discovers `*cases.py` so dry-run and interop cases run in CI. No PR was opened.

## 4. Local verification (W2A-3)

Commands run in `/workspace/knowledge-sdk-v21-wave2` after the implementation commit `bfd6b669b0ef87f34b572cc2a10985023ac27bb4` (and re-run after this docs commit as needed):

```
python3 contracts/v21-reuse-v1/validate.py
python3 scripts/verify_v21_boundaries.py
python3 docs/acceptance/v2.2-align-wave2/verify_frozen.py
PYTHONPATH=src:. python3 -W error::ResourceWarning -m unittest discover -s sandbox/v21_reuse_v1 -p '*.py'
```

Results:

- `validate.py`: exit 0; 51/51 vectors (18 accept / 33 reject); `manifest_sha256=212537fd41bd4cc4d9d7343cacafaea225ee98b6586df716bf036a397cb2a382`; `formal_acceptance=false`.
- `verify_v21_boundaries.py`: `passed=true`; `v21_contract_status=FROZEN_V21_REUSE_V1`; same manifest SHA; `schema_version=6`; 709 baseline files, 0 drift; `formal_acceptance=false`.
- `verify_frozen.py`: `passed=true`; M1 `contract_asset_count=28`; architecture and `pyproject.toml` byte diffs 0.
- unittest `-p '*.py'`: 55/55 OK (existing 45 cases plus 10 new dry-run cases).

## 5. GitHub Actions

Push of `feat/v21-wave2-e2e-interop` (W2A-2 / W2A-3 commits) is performed only after this local suite is green. The GitHub Actions Run ID is **not available until that push starts a workflow**.

- Placeholder at report-authoring time: `GH_ACTIONS_RUN_ID=PENDING_AFTER_PUSH`
- After push, record the actual Run ID (if the workflow starts) in `/workspace/v21-wave2-task-inputs/W2A23_RECEIPT.md`. If the run is still queued, record the run URL and do not claim green. If remote CI is blocked, do not treat a missing Run ID as formal acceptance, and do not open a PR to work around it.

This report does not predeclare a pending CI run green.

## 6. Residual notes (not claimed as closed)

- Formal T-01–T-27 remains `NOT_RUN_NOT_ACCEPTED`. The dry-run matrix is a tracking aid only.
- Space Gate 3/4 remain `NOT_MET`. Official VB-1 lock stays `111/13/0`.
- W2-Gate-1 is not claimed: Team B has not yet byte-aligned TypeScript `receipt_hash` against the W2A-1 golden fixture in this Team A run.
- W2-Gate-2 is not self-signed: the matrix exists and local bounds hold, but formal T-01..T-27 was not run.
- Schema v7/v8/v9 DDL remains unauthorized. Production shadow migration / cutover remains unauthorized.
- `/v3/*` stays an unmounted draft; `EXPERIMENTAL_V3_ENABLED` stays default false.
- Team A did not contact Team B in this W2A-2 / W2A-3 run.
