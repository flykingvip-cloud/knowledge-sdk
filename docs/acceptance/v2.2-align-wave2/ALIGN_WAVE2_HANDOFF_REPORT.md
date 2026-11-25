# Align-Wave2 / SDK-24 handoff

## 1. Authority, exact source and reproducible final identity

- Only branch: `feat/align-wave2-m2-min-slice`; exact source/predecessor: `5a139e574ef68bcc045b70af32aee67f92c172b3` (accepted Wave1.8, run45602610491,22/22).
- Historical semantic contract baseline: `07f5d39f05ef4c7952be48b83025b9c86ea2458e`. Owner pt65u authorizes this **new, nonproduction** runtime; see `OWNER_PROCLAMATION.md`. Team B authoritative records were not locally supplied; no substitute signatures or records were created. Historical Pending manifest remains archival truth, not changed to Frozen.
- Protected remote refs read-verified before feature push: Wave1.8 `5a139e574ef68bcc045b70af32aee67f92c172b3`; Wave1.5 **actual** `0d2f172c2ca1c79483257953b5388098b7cdacaf`; Wave1 `60b6436ed9fccb4b49ae32e30f1664412e505888`; main `b953c9922cc1096e0e88455dab6746c01a9d27f9`; v2.0.0 object `4afc1d71f9f5583d93c28f3f4380544a4e5fcc46`, peeled main. No protected ref writes.
- Final self-SHA cannot be embedded in its own commit. Run `python docs/acceptance/v2.2-align-wave2/resolve_receipt.py --run-id RUN_ID --output /workspace/align-wave2-task-inputs/FINAL_RESOLVED_RECEIPT.json` after exact-HEAD CI. It requires matching full40SHA, all36success, each<1080seconds, and records literal finalSHA, CI URL, job statuses/durations and protected remote refs. That external receipt is authoritative; this committed text does **not** predeclare pending CI green. `git rev-parse HEAD` and `git diff --stat 5a139e574ef68bcc045b70af32aee67f92c172b3..HEAD` resolve final identity/difference without a self-reference commit loop.

## 2. CI: preserved22 →36 concurrent jobs

`ci-command-preservation-map.json` contains every old job's exact steps, commands, arguments, environment, services, matrix and destination. All original jobs remain, not replacements: core, optional unittest, pytest, package, contracts/TS/Node/Docker, six original golden jobs, each Python3.9/3.12 matrix. Old ResourceWarning flags, bare validate_assets, manifest validator, wheel verify_package, TS303 strict + Node, SQLite/PostgreSQL Docker security probes and all six golden modes remain. Standard runners only; timeout30min is a ceiling, **actual each job must be <18min**.

Added six equivalent v6-golden jobs × two versions and one real dual-engine migration/runtime job × two versions: 14new jobs, total36. The v6 wrapper upgrades owned fixture stores only; benchmark source bytes/assertions/arguments unchanged. Every PostgreSQL mode still provisions actual pgvector/NOSUPERUSER/NOBYPASSRLS PostgreSQL; no SQLite substitution. The existing contracts/Docker job additionally requires actual Wave2 Docker dual-mode evidence. All prior steps retained in sequence.

Exact final job timings/statuses, run URL and artifacts are in external `FINAL_RESOLVED_RECEIPT.json`; use matching sourceSHA, not another run. No paid/custom runners, workflow bypass, weakened warning/security checks, force push or PR.

## 3. A1–A5 implementation and zero disturbance

| Task | Main files | Implemented boundary |
|---|---|---|
| A1 | `storage/migration_v6.py`, `sqlite_store.py`, `postgres_store.py`, `migrations.py` | Explicit owned-test v5→6 transactional migration, serialized advisory/SQLite write lock, PG lock_timeout5s, rollback/retry, opaque immutable tenant-unique version_id backfill; new claim/job tables and PG ENABLE/FORCE RLS. Old v5 DDL retained; ordinary DB creation remains5. No startup auto-upgrade. |
| A2 | `storage/persistent_contracts.py` | Both engines, existing store transactions/tenant binding; durable business-key claim/fingerprint/fence/TTL and original JSON response snapshots. `execute` encloses current-authority recheck, claim, mutation and response in one transaction. Independent-process death/restart/concurrency tests. Durable seven-state jobs, CAS/retry/cancel races/idempotent submission; no worker. |
| A3 | `server/v2.py`, `server/v2_auth.py`, `contracts/v2_json.py`, `contracts/v2_schemas.py`, `storage/v2_metadata.py`; narrow app/operations/models/hybrid hooks | Exactly eight opt-in JSON routes, strict schema/identity validation, unchanged v1 actor/HMAC/wire/70operations, current User∩Agent/Deny, tenant+dualversion binding, content/filename-only rollback, SHA256 DTOs. Metadata-only own-submission controlled-draft receipts require current WRITE and no redaction; they do not grant draft-content GET. |
| A4 | `deploy/openbot-sandbox/{upgrade_wave2.py,compose.wave2.yaml,probe_wave2.py,serve_sandbox.py}`, `tests/wave2/`, `docker_wave2_probe.py` | Recognized owned-test v5 seed only, separate v6 receipt, original seed receipt unchanged, opt-in overlay; nonroot/read-only/cap-drop/loopback baseline retained; actual signed HTTP captures and dual-engine tests. |
| A5 | `.github/workflows/tests.yml`, CI map, resolver/guards and this evidence directory | Preserved22 baseline jobs plus14; strict final exact-source gate and per-job timing receipt. |

`verify_frozen.py` / `frozen-verification.json` verify all28 SHA256 historical assets, **entire tracked architecture tree** (including original00–10, Pending manifest and M1 decision package), contracts tree and benchmark tree against07: byte-diff0. `pyproject.toml` byte-identical predecessor, dependencies[]. Runtime schema subset provenance test compares exact transitive frozen DTO schema subset. All new acceptance evidence is under `docs/acceptance/v2.2-align-wave2/`. Preexisting untracked `reports/` untouched; only this execution's two generated old process logs restored from exact saved copies. No old task closure updates.

## 4. Actual evidence, compatibility and sandbox commands

Local strict evidence (Asia/Shanghai,2026-11-25; logs outside repository at `/workspace/align-wave2-task-inputs/`):
- Latest Wave2: **48tests,48pass,0skip**,13.033s, zero ResourceWarning; includes both real engines, byte-original predecessor subprocess v5 fixtures, lossless in-place upgrade, failure rollback/retry, concurrent migration, immutable coordinates, non-superuser FORCE RLS, six-way exactly-once writes, TTL/fencing, independent process death/reopen/exact replay, all49job transition pairs, retry/cancel races.
- Full optional unittest:1063tests,4genuine optional skips,221.110s (before two additional byte-original predecessor fixture tests; those pass in current48suite). Full pytest: **1061passed,4skipped,714subtests**,197.56s; one external Starlette/httpx deprecation warning, **zero ResourceWarning**. Stdlib `-S`:1065tests,355expected unavailable-optional-feature skips,30.540s, PASS. Exact final CI logs supersede these intermediate local counts when code versions differ.
- Upgraded full115-case goldens: **SQLite115/115 and real PostgreSQL+pgvector115/115**, zero skips/security failures/implicit model calls; `golden-v6-*.json`. CI retains all original six modes and adds all six upgraded modes.
- Actual PGv6 pg_dump/restore DR: **33table fingerprints equal**, audit/access/search contracts and new claims/jobs/version IDs retained, `dr-v6.json`. Backup is owner/test scope, not production failover/topology evidence.
- Wheel build/verify passed: extracted-wheel stdlib isolation, RECORD, zero dependencies, Python3.9 AST, unchanged benchmark sources. Final package/Docker/TS303+Node exact-source proof is required CI artifact evidence. Local Docker is unavailable; no local container claim is made.
- `wire-v2-captured.json`: **runtime_captured:true**, actual signed loopback parsed HTTP responses, synthetic identities/content and conspicuous TEST-ONLY pseudosecret,10frozen assertions each engine (A01–A10). Assertion labels refer to source10 minimum slice; they are not invented fixture-only wire events. Additional real requests check all12frozen generation cases plusfloat1.0; null/empty/missing/cross-tenant, service rejection, owner/private-robot explicit Deny, current actor/profile, idempotent restart/conflict, URI/dual IDs, actual delivered citation chunk/anchor locator/title tamper, rollback security metadata unchanged, full captured logs with PII/content/secret sentinels absent, real missing-table readiness503 and protected metrics auth.
- v1 compatibility: all baseline70Local/HTTP operations (including8compat methods), existing MCP4tools, old actor string-generation vectors and old golden/security suites retained unchanged. No v2 endpoint aliases or additional operations added.

### Explicit contract mappings (not frozen-asset edits)

Latest owner directive requires `/v2/assets/{doc_id}:rollback`, `/v2/retrieval:search`, `/v2/citations:verify`; older OpenAPI spells those `/v2/assets/{doc_id}/rollback`, `/v2/search`, `/v2/evidence/verify`. Runtime mounts only the owner's eight exact routes; DTO meanings come unchanged from the frozen schemas. HMAC full IdentityContext uses source08§2.2's allowed v2HMAC path, pinned trusted issuer, existing canonical six-line signature/replay machinery; no unsigned/bearer bypass. Historical v1 authentication is unchanged. Date-time format remains OpenAPI3.1 annotation-only, consistent frozen validator; unknown legacy published_at remains empty rather than a fabricated timestamp. Retrieval exposes actual keyword/vector ranks; unsupported rerank/calibration numeric scores are0 with calibration_applied:false (not claimed model scores). No paid model calls.

### Disposable sandbox only (not executed against existing services)

Use unique directories/project names, an allowed unused loopback port, owned images and the baseline preparation guard. Example SQLite; substitute `compose.postgres.yaml` for PostgreSQL with its disposable pgvector service:

```sh
python deploy/openbot-sandbox/prepare_sandbox.py --help
# Prepare a NEW state directory and free allowed loopback port using that CLI.
# Build a uniquely tagged local SDK image, then set SANDBOX_IMAGE to that tag.
docker compose --env-file "$NEW_STATE/sandbox.env" -p "$UNIQUE_PROJECT"   -f deploy/openbot-sandbox/compose.sqlite.yaml   -f deploy/openbot-sandbox/compose.wave2.yaml up -d
docker compose --env-file "$NEW_STATE/sandbox.env" -p "$UNIQUE_PROJECT"   -f deploy/openbot-sandbox/compose.sqlite.yaml   -f deploy/openbot-sandbox/compose.wave2.yaml exec -T sandbox   python /opt/sandbox/probe_wave2.py --url http://127.0.0.1:8088
# After evidence, down --volumes ONLY the exact owned UNIQUE_PROJECT/files.
```

Reproducible bounded actual dual-mode CI probe (requires Docker and nonroot runner):
`PYTHONPATH=src:. python -W error::ResourceWarning docs/acceptance/v2.2-align-wave2/docker_wave2_probe.py --require --output /tmp/unique-sdk24-evidence`.

## 5. Boundaries, risks and acceptance handoff

No production database/service/container/Qdrant access; no reserved ports3000/3001/8000/8002/8090/8091, Mac/openbot-vp writes, `.env.production`, start/stop scripts, external enterprise/StratAI integration, Team B contact or nomination. No service principals, physical purge, null-personal-tenant auto-migration, production shadow/history migration/cutover, P3/EvidenceGraph/vertical packs, scheduler/worker or security-metadata rollback. **No metadata_snapshot column/table introduced.** Default v1/default schema5 behavior retained; v2 explicit opt-in requires already-upgraded owned database and pinned issuer, not production auto-DDL.

Transactional DDL can briefly block; bounded PG lock acquisition is not a lock-free zero-downtime production guarantee. Updated v1 adapter supports5/6; no claim an old positional-INSERT binary can write v6. Business idempotency is restart-durable; nonce replay restart-durability depends on configured ReplayStore (sandbox uses durableSQLiteReplayStore), not a false claim about default in-memory nonce persistence. Schema6/job persistence is the explicit SDK24 authorization, not a retrospective edit of historical no-v2 evidence. Governance proclamation is supplied owner authority, not independently inspected Team B signatures.

Handoff is for **control-plane independent acceptance only**. Do not nominate a SHA to Team B until separately instructed after acceptance. Final green CI, artifact receipts, exact SHA, cleanup and unchanged protected refs must be recorded externally before declaring handoff ready; on any hard gate failure report the real blocker, never partial green.
