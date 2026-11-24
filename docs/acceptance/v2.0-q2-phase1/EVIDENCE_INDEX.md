# Evidence index — INCOMPLETE Q2-M1 checkpoint

All evidence is from actual local box runs, 2026-11-24 Asia/Shanghai (UTC+8).
No synthetic pass counts. No independent review claimed.

| Evidence | Actual result |
|---|---|
| `baseline-stdlib-configured.log` | Baseline exact `9c6a64b`: 446 run = 350 passed + 96 skipped |
| `baseline-benchmark60.log` | Baseline 60/60, ACL 0/20, model calls 0 |
| `l1-stdlib-only.log` | Checkpoint: 469 run = **373 passed + 96 skipped**, zero failure/ResourceWarning |
| `l2-full-and-build.log` | Full deps unittest: 469 run = **466 passed + 3 skipped**; pytest **466 passed, 3 skipped**, **195 subtests** separately; 1 upstream Starlette/httpx deprecation warning (not ResourceWarning) |
| `l2-webhook-final-assertion.log` | Additional full-deps focused run: 13/13, strengthened non-starvation/replay assertion |
| `checkpoint-benchmark60.log` | 60/60 unchanged old cases; ACL violations 0/20, refusal 10/10, reanchor 10/10, MCP 10/10, injection 36/36 blocked, implicit model calls 0 |
| `build-wheel.log`, `wheel-module-verification.log` | Build sdist+wheel; AST Python3.9 syntax: 65 src + 4 benchmark files; extracted wheel `python -S` third-party import blocker + four MCP tools + console entrypoint + schema3 + audit-chain verification + real Outbox rows PASS |
| `l3-local-http-webhook.log` | Real ephemeral signed HTTP audit query/verify + real signed loopback Webhook PASS; **impact endpoints not implemented** |
| `l4-browser.md` | NOT_RUN |
| `l5-independent-review.md` | PENDING; no independent review |

Commands (repository root):

```
PYTHONPATH=src python3 -S -W error::ResourceWarning -m unittest discover -v
PYTHONPATH=src .venv-phase4/bin/python -W error::ResourceWarning -m unittest discover -v
PYTHONPATH=src .venv-phase4/bin/python -m pytest -q
PYTHONPATH=src python3 -S -W error::ResourceWarning -m tests.benchmark.runner --json
PYTHONPATH=src .venv-phase4/bin/python -m build
PYTHONPATH=src .venv-phase4/bin/python docs/acceptance/v2.0-q2-phase1/verify_wheel.py
PYTHONPATH=src:. .venv-phase4/bin/python -W error::ResourceWarning docs/acceptance/v2.0-q2-phase1/live_checkpoint_probe.py
```

The 23 new tests cover real v0/v1/v2 migration and v3 DDL rollback; immutable
contracts; every physical audit column corruption; encoded text corruption and
middle sequence deletion; two-connection audit sequencing and claim contention;
business+outbox rollback; exponential retries/deadletter and lease recovery;
real HMAC delivery and stable IDs; redirect non-following; per-subscription retry
isolation; metadata/private/IPv6/mixed-DNS/rebinding rejection; and explicit
loopback double opt-in.

Unchanged golden fixture SHA256:
`1b7c5ace8249495477457431e7b64f047868757ce28985ede56c483771b13fea`.
No changes anywhere in `tests/benchmark/`. **G6 and benchmark75 are NOT DONE.**
A current 60-case `gate_passed=true` is not the Q2-M1 75-case acceptance gate.

Retained unsuccessful development runs:
- `baseline-stdlib.log`: missing PYTHONPATH (environment invocation corrected).
- `checkpoint-audit-stdlib.log`: expected schema assertion/init-file issues,
  corrected in `checkpoint-audit-stdlib-fixed.log`.
- `l2-initial-schema-assertion-failure.log`: old optional wire probe expected
  schema2; Q1 archived evidence was preserved and a current-schema copy created.
- `l2-initial-probe-copy-failure.log`: overbroad copy replacement accidentally
  changed expected issue count 2 to 3; restored to 2 and full suites rerun green.

The wheel keeps package version 1.2.0 at this unfinished checkpoint; this is NOT
a v2.0 release. Wheel SHA256:
`f867f55eed0f675eccfe42e74394d435b3c612c5ac7ff90777238d0082cc1759`.
Syntax verification is AST3.9, not a claim of a real Python3.9 runtime run.
