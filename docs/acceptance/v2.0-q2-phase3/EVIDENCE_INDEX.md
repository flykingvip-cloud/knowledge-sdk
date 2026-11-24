# Q2-M3 evidence index

| Artifact | Evidence |
|---|---|
| Q2_PHASE3_HANDOFF_REPORT.md | Scope, implementation, explicit limits and handoff |
| l1-stdlib-only.log | Final `python3 -S -W error::ResourceWarning -m unittest discover -v` |
| l1-m3-dual-contracts.log | 19 independent M3 scenarios on SQLite and real PostgreSQL (38 executions) |
| l2-full-and-build.log | Final full unittest/pytest plus AST3.9/build/wheel summary |
| l2-full-unittest.log / l2-full-pytest.log | Complete final raw runner output |
| build-wheel.log / verify_wheel.py | Build, wheel RECORD size/SHA256 integrity, extracted stdlib SQLite and actual PG M3 |
| benchmark-75.json | Both-engine aggregate plus immutable golden hashes |
| benchmark-75-sqlite.json / benchmark-75-postgres.json | Full per-case unchanged 75-case golden results |
| original75-preservation.json | v1/v2 JSONL and g6.py byte-identical baseline SHA256 proof |
| l3-governance-packs-http.md / l3-governance-packs-http.log | Real subprocess signed HTTP, three identities, both engines, revoke→403 + pack impact |
| live_governance_probe.py / l3-*-process.log | Reproducible HTTP probe and actual subprocess logs |
| l4-browser.md | NOT_RUN (no UI change) |
| l5-independent-review.md | PENDING; owner-supplied M2 acceptance distinguished |
| environment.log / cleanup.log | Disposable infrastructure and stopped-resource state |
| acceptance-summary.json / evidence-sha256.json | Machine-readable final totals / artifact digests |
| development/ | Honest failed/superseded development runs, not final acceptance |

Reproduce from repo root with `PYTHONPATH=src:.` and a dedicated disposable test
`KNOWLEDGE_SDK_TEST_PG_DSN` (never production). Core stdlib needs no DSN or optional
libraries. Full env adds optional HTTP/parser/postgres/dev extras and pytest. Commands
are included with their final run summaries. No credential values are archived.

For the core-only run, unset `KNOWLEDGE_SDK_TEST_PG_DSN` and `KNOWLEDGE_SDK_DSN`
first (`env -u ...`), since `-S` intentionally cannot load optional psycopg.
