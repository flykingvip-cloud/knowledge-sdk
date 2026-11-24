# Q1-M4 deterministic golden gate (exactly 60)

`golden.jsonl` is the frozen case index: `case_id`, `group`, distinct executable
`scenario`, shared fixture factory + explicit parameters, concrete `expected`.
The named functions in `run.py` construct and exercise the actual client,
engine, anchor/reanchor, gateway and MCP handlers; they do not compare two
static lists. Each scenario has a different safety/correctness condition, not
an ID-renamed duplicate. Expected values drive refusal/recall/state/selector
assertions; extra assertions protect policy and receipt invariants.

```sh
PYTHONPATH=src python3 -S -W error::ResourceWarning -m tests.benchmark.run \
  --json-output docs/acceptance/v1.2-phase4/benchmark-metrics.json \
  --report docs/acceptance/v1.2-phase4/benchmark-report.md
```

Exactly G1=20, G2=10, G3=10, G4=10, G5=10; no skips. Any failed scenario exits
nonzero. One unittest `GoldenGate` invokes this same suite; it is **not** 60
additional unittest methods. The existing GitHub CI core jobs run the CLI as
an explicit hard gate. No new CI provider or paid service was created.

- G1: tenant/department hierarchy/owner/admin/role denies, historical current
  revocation, agent scope/clearance/purpose, rights, missing redaction, forged
  vectors, uniform denial/no existence metadata.
- G2: 10 real no-evidence executions with generator invocation counters. The
  tenth also verifies a valid authorized positive answer using the existing
  local extractive generator, so universal refusal does not pass.
- G3: eight measurable Recall@5 fixtures; SQLite FTS and an explicit offline
  vector stub, no model rankings. Two additional deliberate exact500/>500
  cap negatives. Scope outside 600 candidates is SQL-filtered before budget.
- G4: host-provided **offline PDF layout fixture** (not PDF/OCR parsing), CSV
  scientific literals, stable unique IDs, ambiguity/structure drift, orphan,
  authorized confirmation, quote/hash tampering.
- G5: authenticated context/HMAC/replay, runtime identity and purpose injection,
  parallel isolation, genuine client receipts, collective pack obligations,
  inert review queue/no document mutations and cross-tenant conflict denial.

Metric denominators are limited to the described measured scenarios: ACL
0/20 G1 safety violations; refusal 10/10; anchor correctness 10/10; MCP
injection 36 identity-field calls across four tools plus four signed purpose
mismatches (40 total). Positive-control failures are separate from safety
failures. Any case failure still blocks the overall gate, including failures
outside these metric subsets. `model_call_count` measures the real explicit
spy-generator invocations in G2 (must be zero); no external adapter is used.

Domain fixtures/rankings/expected outcomes are fixed. Ephemeral signing keys,
nonces, temporary paths and generated storage IDs are randomized but never
printed and have no effect on asserted outcomes. No network is used by this
runner. Real official MCP client/wire validation is a separate optional test
and L3 probe, not a claim inferred from handler golden checks.
