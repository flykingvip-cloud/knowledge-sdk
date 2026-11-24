# Q2-M1 evidence index — final engineering implementation

Actual LOCAL BOX runs, 2026-11-24 Asia/Shanghai (UTC+8).
Final tested runtime/test source: `60307212dc6fe23b6da8e9964add4a323542a30a`.
No invented pass counts; independent L5 has NOT run.

| Evidence | Actual result |
|---|---|
| baseline-stdlib-configured.log | Exact9c6a64b:446 run=350 passed+96 skipped |
| baseline-full-deps.log | Exact9c6a64b from disposable git-archive snapshot:443 passed+3 skipped; pytest443 passed,3 skipped,167 separate subtests |
| baseline-benchmark60.log | Exact baseline60/60, ACL0/20, model calls0 |
| l1-stdlib-only.log | Final502 run=404 passed+98 skipped; zero failures/ResourceWarning |
| l2-full-and-build.log | Final unittest502 run=499 passed+3 skipped; pytest499 passed,3 skipped,200 separate subtests; one upstream Starlette/httpx deprecation warning; final build+wheel logs appended |
| benchmark-75-report.json / .md / benchmark-75-run.log | 75/75; G6 15/15; ACL0/20; audit detection19/19; impact completeness45/45; unexpected targets0; implicit model calls0 |
| original60-preservation.log | Original fixture bytes+v2 first60 identical, all60 original executable G1–G5 scenario bodies AST-identical |
| build-wheel.log / wheel-module-verification.log | sdist/wheel; AST3.9:67 src+5 benchmark files; extracted python-S third-party blocker, four MCP tools/actual console stdio, schema3, audit, usage+revision impact pass |
| l3-live-integration.md / l3-local-http-webhook.log / live_impact_probe.py | Actual signed HTTP full usage→impact→Webhook loop:7 unique deliveries,14/14 alert IDs,<60s; unsigned/replay401/unrelated403/tenant drain isolation; immutable snapshots |
| final-security-unit.log |48 focused audit/impact/outbox/Webhook tests passed on final source |
| l4-browser.md | NOT_RUN, unchanged Q1 proxy/browser/session/CSRF boundary |
| l5-independent-review.md | PENDING_INDEPENDENT_REVIEW; owner assessment is not current L5 |

## Reproduce (repository root)

All acceptance runs disable opt-in external live integrations; no live endpoints
are configured. Runtime was Python3.13. AST3.9 is syntax, not runtime validation.

```sh
PYTHONPATH=src KNOWLEDGE_SDK_LIVE_QDRANT_URL= KNOWLEDGE_SDK_LIVE_EMBEDDING_URL= \
  python3 -S -W error::ResourceWarning -m unittest discover -v
PYTHONPATH=src KNOWLEDGE_SDK_LIVE_QDRANT_URL= KNOWLEDGE_SDK_LIVE_EMBEDDING_URL= \
  .venv-phase4/bin/python -W error::ResourceWarning -m unittest discover -v
PYTHONPATH=src KNOWLEDGE_SDK_LIVE_QDRANT_URL= KNOWLEDGE_SDK_LIVE_EMBEDDING_URL= \
  .venv-phase4/bin/python -m pytest -q
PYTHONPATH=src python3 -S -W error::ResourceWarning -m tests.benchmark.runner --json \
  --json-output docs/acceptance/v2.0-q2-phase1/benchmark-75-report.json \
  --report docs/acceptance/v2.0-q2-phase1/benchmark-75-report.md
PYTHONPATH=src python3 -S -W error::ResourceWarning -m tests.benchmark.runner \
  --cases tests/benchmark/golden_cases_v1.jsonl --json
PYTHONPATH=src .venv-phase4/bin/python -m build
PYTHONPATH=src .venv-phase4/bin/python docs/acceptance/v2.0-q2-phase1/verify_wheel.py
PYTHONPATH=src:. .venv-phase4/bin/python -W error::ResourceWarning \
  docs/acceptance/v2.0-q2-phase1/live_impact_probe.py
```

The baseline was tested from the exact SHA; the later full-deps rerun used a
local disposable `git archive 9c6a64b` snapshot, not branch switching, cloning,
editing main or touching any existing runtime DB. Tests use fresh databases.
The golden fixture SHA256 is
`1b7c5ace8249495477457431e7b64f047868757ce28985ede56c483771b13fea`.
Final wheel SHA256 is
`752fd19e7d5416aee1f6051a52f00670f1ef6849b3763e9bda13275a1cfc6e03`.
Package version remains1.2.0, not a full Q2 release or tag.

## Coverage and retained history

56 added unittest methods relative to446 baseline, plus separately counted
subtests. Coverage includes real v0/v1/v2 migration and DDL rollback; frozen/tagged
contracts; every physical audit column corruption, encoded-field mutation and
interior sequence deletion; concurrent tenant sequences/claims, stale attempts;
business+audit+Outbox rollback; retry/dead_letter; real signature, redirects,
private/IPv6/mixed/rebound DNS; background lock ordering; actual MCP lineage;
all source impact reasons, precise anchor/version targets, old snapshots,
redaction/agent/tenant/owner isolation, reserved pack payload preservation,
signed/no-store API parity and meaningful benchmark metric negative controls.

Historical checkpoint logs are retained, not substituted for final logs:
checkpoint-benchmark60.log, checkpoint-audit-stdlib-fixed.log,
l2-webhook-final-assertion.log, benchmark-unittest.log, binding-compatibility.log.
Their lower test counts reflect earlier code and are NOT final acceptance.
The old checkpoint handoff/probe are in superseded-checkpoint/.

Retained unsuccessful development runs:
- baseline-stdlib.log: initial command lacked PYTHONPATH; corrected invocation.
- checkpoint-audit-stdlib.log: initial schema assertion/test-init issues corrected.
- l2-initial-schema-assertion-failure.log: old optional probe expected schema2;
  current-schema copy introduced without modifying archived Q1 evidence.
- l2-initial-probe-copy-failure.log: overbroad copy replacement changed expected
  issue count2→3; restored to2, full suites rerun green.
- development-benchmark74.log: G6 fixture was accidentally plain text instead of
  Markdown, so no heading anchor existed; fixed fixture type, not safety gates.
- development-http-self-audit-expectation.log: foreign actor legitimately creates
  its OWN tenant audit rows; assertion corrected to verify tenant/doc ownership,
  not require its entire audit query to remain empty after its own operations.

See handoff for at-least-once crash semantics, unanchored-chain limitations,
explicit dispatcher startup, SQLite serialization, identity refresh and all
unchanged Q1 external gates. Local evidence does not replace independent review.
