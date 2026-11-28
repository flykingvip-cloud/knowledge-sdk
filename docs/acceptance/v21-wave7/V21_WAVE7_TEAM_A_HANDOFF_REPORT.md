# V21_WAVE7_TEAM_A_HANDOFF_REPORT

Status: **Team A Wave-V21-7 implementation handoff (W7A-1, W7A-2, and W7A-3, plus this isolated-branch report after independently confirmed CI green on the implementation tip), not formal T-01–T-27 acceptance**. This report records official Owner order `t108u` rulings already issued; it does not self-issue formal T-01–T-27 acceptance, Gate 6, or a production Schema v7 authorization. `formal_t01_t27_accepted` is `false`. `formal_t01_t27` remains `NOT_RUN_NOT_ACCEPTED`. `schema_v7_prod_migration_authorized` remains `false`. `schema_v8_v9_ddl_authorized` remains `false`. Engineering has zero production-database contact.

Order: Owner order `t108u` (2026-11-28, Asia/Shanghai). Verdicts already recorded as stated: `TEAM_A_WAVE_V21_6_CLEAN_ACCEPT` and `WAVE_V21_6_JOINT_CLEAN_ACCEPT`; T-01–T-27 sandbox dual-stack is `SANDBOX_JOINT_VERIFIED`; `AUTH-V21-07-CORE-V7` issued; `wave_v21_7_unlocked = true`; `schema_v7_core_branch_ddl_authorized = true` only on this Wave-V21-7 isolated branch. `formal_t01_t27_accepted` remains `false` pending official Wave-V21-7 final acceptance. Still false and unchanged for production and for the frozen v21-reuse-v1 pack: `schema_v7_prod_migration_authorized`, `schema_v7_ddl_authorized`, `schema_v8_v9_ddl_authorized`, `prod_shadow_migration_cutover_authorized`. `EXPERIMENTAL_V3_ENABLED` and `OPENBOT_KNOWLEDGE_SDK_V2_ENABLED` stay default false. Official VB-1 lock remains `111/13/0`. The frozen contract file `contracts/v21-reuse-v1/status.json` was not edited (including `schema_v7_ddl_authorized: false` and `formal_t01_t27: NOT_RUN_NOT_ACCEPTED`). Isolated-branch Schema v7 authorization is registered in `scripts/verify_v21_boundaries.py` and `.github/workflows/tests.yml`, not by rewriting pack flags.

The local file `/workspace/kb-sdk-align/WAVE_V21_6_JOINT_CLEAN_ACCEPT_AND_WAVE_V21_7_AUTH_V21_07_CORE_V7_LAUNCH_ORDER_2026-11-28.md` is the Team B / joint counterpart of the same launch family (different W7B tasks). If that copy conflicts with t108u, t108u is controlling for Team A. Owner-stated Team B pin `7486bc4688778e7d815d80e0248821789fb739fe` is recorded only.

## 1. Branch and commits

- Repository: `knowledge-sdk` (`flykingvip-cloud/knowledge-sdk`)
- Isolated branch: `feat/v21-wave7-core-schema-v7-and-formal-t01-t27`
- Isolated worktree: `/workspace/knowledge-sdk-v21-wave7`
- Frozen Wave-V21-6 tip (unmodified parent of the first Wave-V21-7 commit): `91b8b6f350ff300925b3ad6fc1f9a4bec6e40104`
- Frozen Wave-V21-5 tip (unmodified): `ce8297fba12849dd7725291d31a72de56279ce1d`
- Frozen Wave-V21-4 tip (unmodified): `e97a8cca68df7b464ce1f017729022cba861c543`
- Frozen Wave-V21-3 tip (unmodified): `918293cada0610d6a6d7ef6b8e5f86990b411ce9`
- knowledge-sdk `main` (unmodified): `b953c9922cc1096e0e88455dab6746c01a9d27f9`
- W7A-1 / W7A-2 / W7A-3 implementation tip (CI-green, parent chain below): `a5fa513b9e25a3912ca5fa6884cff363c42a0ab3`
- First implementation commit: `2d4b4dba52dcd4124c897f7bcebd9b4f251efa18` (first parent is exactly `91b8b6f350ff300925b3ad6fc1f9a4bec6e40104`)
- Follow-up isolated-branch fixes on the same work (ordinary commits, no amend, no force-push):
  - `8c6c704bed32bfbd02c778f88073dd92862c5a97` — escape PostgreSQL `LIKE` percents in Schema v7 DDL; close failed disposable PG sandbox connections; register a bound-agent profile before live `/v2/spaces`
  - `cd97a414772dd97bf46a31bedb66874d9d71ea8a` — use `ON CONFLICT DO NOTHING` for key-only Schema v7 upserts
  - `a5fa513b9e25a3912ca5fa6884cff363c42a0ab3` — infer PostgreSQL FORCE RLS tenant scope from the `tenant_id` placeholder (not `args[0]`); rewrite `resign()` to the store transaction/tenant scope so PostgreSQL never sees SQLite `BEGIN IMMEDIATE`
- This report is a follow-on docs commit on the same isolated branch. Its parent is exactly `a5fa513b9e25a3912ca5fa6884cff363c42a0ab3`. The exact branch-tip SHA after this commit, and the remote SHA after the ordinary handoff push, belong in the external receipt `/workspace/v21-wave7-task-inputs/W7A_RECEIPT.md`.
- Existing worktrees were left untouched: `/workspace/knowledge-sdk-v21-wave6` at `91b8b6f350ff300925b3ad6fc1f9a4bec6e40104`, `/workspace/knowledge-sdk-v21-wave5` at `ce8297fba12849dd7725291d31a72de56279ce1d`, `/workspace/knowledge-sdk-v21-wave4` at `e97a8cca68df7b464ce1f017729022cba861c543`, `/workspace/knowledge-sdk-v21-wave3` at `918293cada0610d6a6d7ef6b8e5f86990b411ce9`, `/workspace/knowledge-sdk` at `feat/space-alignment-v1-design-proto@4bed2a1c86153035314815165f29d26a078fab50`.
- No PR, no merge to `main`, no force-push, no amend, no `--no-verify`, no tag, no release. After the ordinary pushes of the implementation commits, `gh pr list --repo flykingvip-cloud/knowledge-sdk --state all` was empty, and the frozen remote tips listed above were unchanged.

Ancestry of this isolated branch down through the frozen Wave-V21-6 tip:

```
a5fa513b9e25a3912ca5fa6884cff363c42a0ab3  (implementation tip; CI 37/37 on this SHA)
cd97a414772dd97bf46a31bedb66874d9d71ea8a
8c6c704bed32bfbd02c778f88073dd92862c5a97
2d4b4dba52dcd4124c897f7bcebd9b4f251efa18  (first Wave-V21-7 commit; parent is exactly 91b8b6f3)
91b8b6f350ff300925b3ad6fc1f9a4bec6e40104  (Wave-V21-6 Team A tip, unmodified)
```

`git diff --stat 91b8b6f350ff300925b3ad6fc1f9a4bec6e40104 a5fa513b9e25a3912ca5fa6884cff363c42a0ab3`:

```
 .github/workflows/tests.yml                        |    4 +-
 .../v21-wave7/W7A2_CORE_V7_T01_T27_REPORT.json     |  214 ++++
 scripts/verify_v21_boundaries.py                   |  102 +-
 src/knowledge_sdk/storage/migration_v6.py          |   11 +-
 src/knowledge_sdk/storage/migration_v7.py          |  670 +++++++++++
 src/knowledge_sdk/storage/migrations.py            |    7 +-
 src/knowledge_sdk/storage/postgres_store.py        |    2 +-
 src/knowledge_sdk/storage/schema_v7.py             | 1253 ++++++++++++++++++++
 src/knowledge_sdk/storage/sqlite_store.py          |   10 +-
 tests/wave7/__init__.py                            |    0
 tests/wave7/test_core_v7_t01_t27_cases.py          |  749 ++++++++++++
 tests/wave7/w7a2_report.py                         |   66 ++
 12 files changed, 3060 insertions(+), 28 deletions(-)
```

`git diff 91b8b6f3 -- contracts/v21-reuse-v1 pyproject.toml` is empty. `src/knowledge_sdk/storage/postgres_schema.sql` is byte-identical to baseline `9940818b962ccb186c0dfb0158de6bd9bd49057b`. `pyproject.toml` `dependencies` remains `[]`.

`.github/workflows/tests.yml` still starts with the frozen `9940818b` baseline bytes (append-only after the existing v21 job), so the 709-file / 0-drift gate continues to pass for unmodified baseline files. The `v21-wave0-boundaries` job title now names the Schema v7 isolated-branch gate, and the job runs `unittest` / `pytest` on `tests/wave7` under `-W error::ResourceWarning`. CI on the implementation tip therefore executed the new core v7 / T-01–T-27 suite. Live PostgreSQL paths run in `unit-suite` and `pytest-suite` (disposable non-superuser pgvector role via `KNOWLEDGE_SDK_TEST_PG_DSN`), not against any production DSN.

## 2. Frozen contract identity (unchanged in W7A-1 / W7A-2 / W7A-3)

- Pack status: `FROZEN_V21_REUSE_V1`
- Deterministic manifest SHA-256: `212537fd41bd4cc4d9d7343cacafaea225ee98b6586df716bf036a397cb2a382`
- File count: 18
- Five schema groups and 51 vectors remain byte-identical to `91b8b6f3` / `ce8297fb` / `e97a8cca` / `918293ca`. W7A-1 / W7A-2 / W7A-3 did not edit `contracts/v21-reuse-v1/`.
- Frozen pack flags left untouched, including `schema_v7_ddl_authorized: false` and `formal_t01_t27: NOT_RUN_NOT_ACCEPTED`.
- Golden fixture `sandbox/v21_reuse_v1/fixtures/w2_interop_golden.json` remains SHA-256 `f8033a902af06b005fa591ab872a74f9569a3783fd3e7cef90c6dc94cf9d0fef` (33863 bytes; worktree blob equals git blob `5afaff1616ddd77dca604dc498fc691ae4a4f37b`).
- `scripts/verify_v21_boundaries.py` still hard-locks the manifest SHA above, `dependencies == []`, M1 28 assets, the 709-file baseline inventory against `9940818b962ccb186c0dfb0158de6bd9bd49057b`, and the golden fixture hash above. On this isolated branch the Schema gate is `schema_version_gate()` (returns 7): `postgres_schema.sql` must stay byte-identical to the v6 baseline; new additive `migration_v7.py` must declare `SCHEMA_VERSION = 7`, keep `SCHEMA_V7_PROD_MIGRATION_AUTHORIZED = False`, and expose `upgrade_v7` / `rollback_v7` with the owned-nonproduction gate. Authorized baseline storage edits (`migration_v6.py`, `migrations.py`, `sqlite_store.py`, `postgres_store.py`) remain counted in the 709 inventory and are not treated as drift. New files `migration_v7.py` and `schema_v7.py` plus prefixes `docs/acceptance/v21-wave7/` and `tests/wave7/` are allowlisted. Unrelated frozen gates were not loosened. Verifier output records `schema_version=7`, `schema_v7_core_branch_ddl_authorized=true`, and `schema_v7_prod_migration_authorized=false`.

## 3. What Team A delivered

### W7A-1 — controlled core Schema v7 upgrade on the isolated branch

- Additive `src/knowledge_sdk/storage/migration_v7.py` on top of the existing v6 path (`migration_v6.py` history was not rewritten). Fresh stores still initialize at v5; `upgrade_v6` / `upgrade_v7` remain explicit. `owned_nonproduction=True` is required; `schema_v7_prod_migration_authorized` stays false, so a production or shared v6 store is not upgraded in place.
- SQLite idempotent v6→v7 migration and rollback replay guards (`PRAGMA user_version = 7`, `upgrade_v7` / `rollback_v7` / `validate_v7`).
- PostgreSQL Schema v7 DDL with `ENABLE` / `FORCE` RLS. RLS policies bind `tenant_id` to `current_setting('app.current_org_id')`. v7 tables are `ks_v7_*` beside the existing v6 schema. `postgres_schema.sql` is unchanged.
- Tenant → Space → KB (1 Space : N KB) on the real storage stack. SPACE-C03 phase 1 is locked as `1 organization_team = 1 Team Space`. Department auto-mapping and phase-1 `parent_space_id` nesting are refused.
- Five-layer Fail-Closed isolation is the official chain (Layers 0–4) from `docs/acceptance/v21-wave6/FINAL_SPACE_AND_FAVORITES_ALIGNMENT_FROZEN.md`, `sandbox/v21_schema_v7/`, and the reserved formal plan. No layers were invented.
- Favorites are zero-copy relationship pointers (`userId` + `assetId` / `user_id` + `target_type` + `target_id` style only). Body / Chunk / Embedding / Evidence are never stored on the pointer.
- Transactional revocation / Outbox consistency, and PRE-04 leaver five-rule hooks: resignation real-time freeze within 60 seconds (implemented as immediate freeze, elapsed 0s); 90-day read-only isolation retention; work-product dual-approval handover; private body text must not auto-inherit; controlled shares invalidated immediately. Security state is monotonic.
- Existing v6 callers remain backward compatible: `require_v6` / `upgrade_v6` / `put_version` accept schema versions 6 and 7; a v6 database can be opened and then migrated; old APIs still work. `EXPERIMENTAL_V3_ENABLED` stays default false. HTTP `/v2/spaces` stays frozen at baseline `9940818b`; the core v7 HTTP surface is the distinct `/v7-core/spaces` path. `/v3` is not mounted.
- Implementation lives in the real `src/knowledge_sdk/storage/` stack (`SchemaV7` in `schema_v7.py` plus store/migration wiring). Production modules were not swapped for the Wave-V21-6 sandbox package; that sandbox remains a design reference and continues to pass.

### W7A-2 — formal-path T-01–T-27 suite against real storage and /v2 + MCP surfaces

- `tests/wave7/test_core_v7_t01_t27_cases.py` is discovered by `unittest discover -p '*cases.py'` and by the `tests.yml` hook. SQLite cases always run. Live PostgreSQL cases run when `KNOWLEDGE_SDK_TEST_PG_DSN` is set (CI disposable fixture); otherwise they are skipped with an explicit reason, and SQLite plus PostgreSQL DDL / FORCE RLS semantic checks still run. Live in-process HTTP `/v2` + MCP cases run when FastAPI / uvicorn are present (CI `pytest-suite` / `unit-suite`); otherwise they are skipped with an explicit reason, and protocol / MCP policy validators still run.
- Official reserved titles follow `FORMAL_TEST_PLAN_NOT_RUN.md` (read-only `4bed2a1c` tree) together with the wave2 matrix and wave6 sandbox coverage. All 27 IDs T-01 through T-27 are covered on this branch, including T-11–T-17.
- Evidence report: `docs/acceptance/v21-wave7/W7A2_CORE_V7_T01_T27_REPORT.json`. It lists every T-01–T-27 case ID with a PASS summary, `scope: CORE_STORAGE_V7_ISOLATION_BRANCH`, and `formal_t01_t27_accepted: false`. `formal_t01_t27` remains `NOT_RUN_NOT_ACCEPTED`. This is not formal acceptance.
- Local Postgres was not available at report generation (`KNOWLEDGE_SDK_TEST_PG_DSN` unset; `127.0.0.1:5432` not accepting connections). No production DSN was used. CI `unit-suite` and `pytest-suite` on the implementation tip executed the live PostgreSQL path and succeeded.

### W7A-3 — isolated-branch Schema v7 registration, local 10/10, ordinary push, CI, this report

- `scripts/verify_v21_boundaries.py` and `.github/workflows/tests.yml` register the Wave-V21-7 isolated-branch authorized state (`schema_version==7`) as described in section 2. Historical M1 28 items and the frozen manifest / golden fixture have zero drift.
- A minimal `tests.yml` hook was added so CI runs the new core v7 / T-01–T-27 suite, without breaking the 709 zero-drift gate for unmodified baseline files.

## 4. Local verification (re-run on implementation tip `a5fa513` before this handoff commit)

Commands run in `/workspace/knowledge-sdk-v21-wave7`:

```
python3 contracts/v21-reuse-v1/validate.py
python3 scripts/verify_v21_boundaries.py
python3 docs/acceptance/v2.2-align-wave2/verify_frozen.py
PYTHONPATH=src:. python3 -W error::ResourceWarning -m unittest discover -s sandbox/v21_reuse_v1 -p '*cases.py'
PYTHONPATH=src:. python3 -W error::ResourceWarning -m unittest discover -s sandbox/v21_schema_v7 -p '*cases.py'
PYTHONPATH=src:. python3 -W error::ResourceWarning -m unittest discover -s tests/wave7 -p '*cases.py'
```

Results:

- `validate.py`: 51/51, `formal_acceptance=false`, manifest SHA-256 `212537fd41bd4cc4d9d7343cacafaea225ee98b6586df716bf036a397cb2a382`
- `verify_v21_boundaries.py`: `passed=true`, `schema_version=7`, `schema_v7_core_branch_ddl_authorized=true`, `schema_v7_prod_migration_authorized=false`, baseline 709 files / 0 drift, golden fixture SHA-256 `f8033a902af06b005fa591ab872a74f9569a3783fd3e7cef90c6dc94cf9d0fef` (33863 bytes, git blob `5afaff1616ddd77dca604dc498fc691ae4a4f37b`), `formal_acceptance=false`
- `verify_frozen.py`: M1 28 assets / 0 drift, `passed=true`
- `sandbox/v21_reuse_v1` `*cases.py`: 110/110, 10 consecutive all-green runs under `-W error::ResourceWarning` (zero ResourceWarning)
- `sandbox/v21_schema_v7` `*cases.py`: 38/38, 10 consecutive all-green runs under `-W error::ResourceWarning` (zero ResourceWarning)
- `tests/wave7` `*cases.py`: 62 tests, 10 consecutive all-green runs under `-W error::ResourceWarning` (zero ResourceWarning); 30 skipped locally (live PostgreSQL and live HTTP / FastAPI surfaces). SQLite T-01–T-27, DDL / FORCE RLS semantic checks, compatibility, frozen-flag, and MCP policy cases ran. Live PostgreSQL was not run locally; it is expected in CI and was confirmed green there on this tip.

## 5. Remote GitHub Actions (implementation tip)

Independently confirmed after the ordinary push of `a5fa513b9e25a3912ca5fa6884cff363c42a0ab3`:

- Workflow: `tests` (`.github/workflows/tests.yml`)
- Event: `push`
- Run ID: `46149920829`
- URL: https://github.com/flykingvip-cloud/knowledge-sdk/actions/runs/46149920829
- Head SHA: `a5fa513b9e25a3912ca5fa6884cff363c42a0ab3`
- Conclusion: `success`
- Jobs: 37/37 success (including `v21-wave0-boundaries`, `unit-suite` 3.9 and 3.12, and `pytest-suite` 3.9 and 3.12)
- Created: 2026-11-28 21:30:15 CST (Asia/Shanghai) (source `2026-11-28T13:30:15Z`)
- Completed / updated: 2026-11-28 21:44:05 CST (Asia/Shanghai) (source `2026-11-28T13:44:05Z`)

Earlier implementation commits on this isolated branch were not all-green and were superseded by ordinary follow-up commits on the same branch (no amend, no force-push): run `46147816526` (`2d4b4db`, PostgreSQL `LIKE` placeholder escaping), run `46148477126` (`8c6c704`, key-only `ON CONFLICT` upserts), and run `46149140464` (`cd97a41`, T-04 tenant-scope inference and T-27 `BEGIN IMMEDIATE`). Those failures are not claimed as acceptance evidence. This report is being committed only after the independently confirmed all-green result on `a5fa513`. The handoff-commit CI run is not part of this file's already-observed evidence; it will be recorded in the local receipt after it completes.

## 6. What this handoff does not claim

- Formal T-01–T-27 remains `NOT_RUN_NOT_ACCEPTED`. `formal_t01_t27_accepted` is `false`. Core-branch PASS rows are not formal acceptance and are not a production-migration authorization.
- `schema_v7_prod_migration_authorized` remains `false`. `schema_v8_v9_ddl_authorized` remains `false`. Schema v7 is authorized only on this isolated branch (`schema_v7_core_branch_ddl_authorized=true`). `main` remains `b953c992` / Schema v6 and was not modified.
- Official VB-1 stays `111/13/0`.
- Production shadow migration / cutover remains unauthorized. Engineering had zero production-database contact.
- `EXPERIMENTAL_V3_ENABLED` stays default false. `OPENBOT_KNOWLEDGE_SDK_V2_ENABLED` stays default false. `/v3/*` stays unmounted.
- This report is not a pull request and not a merge to `main`.
