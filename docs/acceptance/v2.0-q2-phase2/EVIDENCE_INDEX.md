# Q2-M2 evidence index

- [Handoff](Q2_PHASE2_HANDOFF_REPORT.md)
- L1: [strict stdlib](l1-stdlib-only.log), [PG assembly/lazy/redaction guards](l1-pg-whitebox.log)
- L2: [full unittest](l2-full-unittest.log), [full pytest](l2-full-pytest.log), [AST/build/extracted wheel](l2-build-wheel.log), [required combined log](l2-full-and-build.log)
- Golden: [SQLite 75](benchmark-75-sqlite.json), [PostgreSQL 75](benchmark-75-postgres.json), [original75 preservation](original75-preservation.log)
- L3: [integration narrative](l3-postgres-integration.md), [combined parity/concurrency/DR](l3-pg-parity-concurrency-dr.log), [specialized live tests](l3-pg-specialized.log), [shared CJK](l3-cjk-shared.log), [real two-process HTTP](l3-pg-http.log), [actual DR](l3-dr.log), [DR rowcount/SHA256](dr-report.json), [migrate CLI](migrate-cli.log)
- L4: [NOT_RUN](l4-browser.md). L5: [independent review pending](l5-independent-review.md)
- [Environment](environment.log), [security/scope](security-and-scope.log), [cleanup](cleanup.log)
- [Evidence SHA-256 manifest](evidence-sha256.json) hashes captured files, not a signature or independent attestation.

Reproduction scripts: `live_pg_http_probe.py`, `verify_wheel.py`, package module
`knowledge_sdk.storage.dr_drill`, shared tests `tests/test_dual_engine_parity.py`
and `tests/q2/test_postgres.py`. Use only disposable PG test databases.
Historical development-* captures are real early failed/checkpoint runs, not the
final acceptance basis; their failures are described in the handoff. No skipped
or duplicated test is counted as an independent pass.
