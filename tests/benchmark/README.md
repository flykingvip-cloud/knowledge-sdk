# Exact60 taskbook golden cases

Authoritative index: `golden_cases_v1.jsonl`, each case has exactly
case_id/group/title/scenario/expected. Runner: `runner.py`; unittest gate:
`test_golden_benchmark.py`; existing CI core jobs run the same hard gate.

```sh
PYTHONPATH=src python3 -S -W error::ResourceWarning -m tests.benchmark.runner --json
```

G1=20 security scenarios; G2=10 distinct refusal paths with real generator-spy
calls (including pre-generation revocation and an authorized extractive positive
control); G3=10 bounded fetch/scope/RRF/redaction scenarios; G4=10 physical-anchor
fixtures/states/history/confirmation/redaction; G5=10 JSON-RPC/tool/queue/auth/stdio
scenarios. No network/model is used, no skips allowed, any failure nonzero.
Stdio case launches a real -S subprocess; the HTTP-auth case calls the SAME production
GatewayAuthenticator.authorize_http HMAC/replay adapter, not a stubbed401. Actual
optional FastAPI wire is separately tested at L3, not inferred from a handler call.

Metrics: acl_violation_rate counts failed G1 safety assertions /20 scenarios;
refusal_accuracy passes/10 G2; implicit_model_calls sums measured generator spies;
reanchor_accuracy passes/10 G4; mcp_pass_rate passes/10 G5. The36 attempted identity
injections (9 forbidden fields x4 otherwise-valid tools) have positive controls
and their own actual blocked count. Safety and positive-control failures are distinct.
All60 passing, zero safety/model failures and complete denominators are hard gates.
Seven applicable fixed SQLite FTS / offline hybrid-stub fixtures have actual Recall@k
(usually5; the550-noise fixture has3 targets); no real semantic rankings, baseline
uplift or online performance claim. Exact500 and >500 negatives are separate.

PDF bbox is an explicit offline host plugin, not a PDF/OCR parser. Domain content,
ranking and expectations are fixed; random ephemeral signing keys/nonces/temp paths
are never printed and do not affect asserted outcomes. Prior incompatible evidence
is retained only in the explicitly superseded historical directory.
