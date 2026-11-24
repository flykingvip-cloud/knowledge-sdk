# Exact75 Q2-M1 taskbook golden cases

Default index: `golden_cases_v2.jsonl` = the original 60 unchanged v1 lines plus
`G6-01..G6-15`. Runner: `runner.py`; extra scenarios: `g6.py`; unittest hard gate:
`test_golden_benchmark.py`. Existing core CI runs this same default 75-case gate.

```sh
PYTHONPATH=src python3 -S -W error::ResourceWarning -m tests.benchmark.runner --json
```

G1=20 ACL/security, G2=10 refusal/generator-spy, G3=10 authorized bounded fetch,
G4=10 physical-anchor/offline layout, G5=10 MCP/tool/auth, G6=15 real SQLite audit,
usage/impact, transactional outbox and signed-Webhooks scenarios. No skips,
external service, paid/model/embedding calls. Webhook transport in G6 is explicitly
in-memory to a validated numeric public address: no HTTP request or external DNS
query. Real loopback network acceptance is separately tested at L3 and by
`tests.server.test_q2_impact_http` when HTTP extras are installed.

Metrics preserve the old G1..G5 definitions: ACL failed G1 safety assertions /20;
refusal passes/10; measured generator-spy invocation count; reanchor passes/10;
MCP passes/10; 36/36 actual forbidden-identity injections rejected. Safety and
positive-control failures are distinct and ALL groups must pass. Seven eligible
fixed SQLite/offline hybrid fixtures retain actual Recall@k; no online semantic
or baseline uplift claim. PDF geometry remains an injected offline fixture.

New metrics are observed, not constants:
- `audit_chain_detection`: detected first-invalid-sequence checks / attempted
  corruptions (all 17 stored columns + 2 middle-gap/prefix checks = 19).
- `impact_completeness`: observed intersection / independently expected target
  IDs across G6 fixtures (45/45), with **zero unexpected targets** separately
  hard-gated. Includes usage, consumer-binding, revision, drift, orphan, archive,
  revoke/ACL and 30-consumer convergence cases.
- Unit negative controls disable the radar or force a falsely-valid chain report;
  the relevant benchmark assertion then FAILS and measured metrics fall to zero.

The default hard gate requires 75/75, G6=15/15, both new metrics 100%, zero
unexpected/safety/model failures and all prior denominator/recall controls.
`--cases tests/benchmark/golden_cases_v1.jsonl` can explicitly reproduce the old
60-case gate, but that is NOT Q2-M1 acceptance. Signing keys/nonces/temp paths are
randomized locally, never printed, and do not influence the expected outcomes.
