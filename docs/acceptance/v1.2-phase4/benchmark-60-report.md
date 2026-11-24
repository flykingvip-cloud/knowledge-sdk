# Q1-M4 offline golden benchmark

2026-11-24T21:07:57.833662+08:00 Asia/Shanghai

Cases: 60/60 passed; 0 skipped; gate_passed=True

| Group | Passed / Total |
|---|---|
| G1 | 20 / 20 |
| G2 | 10 / 10 |
| G3 | 10 / 10 |
| G4 | 10 / 10 |
| G5 | 10 / 10 |

```json
{
  "gate_passed": true,
  "case_count": 60,
  "passed": 60,
  "failed": 0,
  "skipped": 0,
  "groups": {
    "G1": {
      "passed": 20,
      "total": 20
    },
    "G2": {
      "passed": 10,
      "total": 10
    },
    "G3": {
      "passed": 10,
      "total": 10
    },
    "G4": {
      "passed": 10,
      "total": 10
    },
    "G5": {
      "passed": 10,
      "total": 10
    }
  },
  "acl_violation_rate": {
    "numerator": 0,
    "denominator": 20,
    "rate": 0.0
  },
  "refusal_accuracy": {
    "numerator": 10,
    "denominator": 10,
    "rate": 1.0
  },
  "reanchor_accuracy": {
    "numerator": 10,
    "denominator": 10,
    "rate": 1.0
  },
  "mcp_injection_blocked": {
    "numerator": 36,
    "denominator": 36,
    "rate": 1.0
  },
  "implicit_model_calls": 0,
  "mcp_pass_rate": {
    "numerator": 10,
    "denominator": 10,
    "rate": 1.0
  },
  "positive_control_failures": 0,
  "security_assertion_failures": 0,
  "offline_recall_at_5": {
    "eligible_cases": 7,
    "mean": 1.0,
    "values": [
      1.0,
      1.0,
      1.0,
      1.0,
      1.0,
      1.0,
      1.0
    ]
  },
  "executed_at": "2026-11-24T21:07:57.833662+08:00",
  "timezone": "Asia/Shanghai"
}
```

These are 60 distinct executable offline scenarios, not 60 unittest methods or added subtests. No skips are allowed.
ACL denominator: 20 G1 security scenarios; refusal denominator: 10 G2 no-evidence scenarios with real generator spies; anchor denominator: 10 G4 fixture scenarios.
MCP injection denominator: actual runtime rejected argument/purpose attempts (not tool schema declarations). Positive controls and safety assertions are tracked separately.
implicit_model_calls is the measured explicit generator-spy invocation count in G2; no real model/network/vector service is configured. Positive answer control uses the local extractive generator.
Recall@k (k=3 for the three-target scope fixture, otherwise5) is measured only on the seven eligible fixed SQLite FTS / deterministic hybrid-stub fixtures. Two deliberate 500-cap negative fixtures are excluded. No online semantic improvement or historical baseline uplift is claimed.
PDF geometry is a host-injected offline layout fixture, not a PDF/OCR parser. Handler golden checks are not HTTP/stdio wire acceptance; actual transports are separately exercised at L3.
