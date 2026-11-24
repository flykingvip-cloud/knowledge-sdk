# L3 — actual official MCP client / Streamable HTTP and legacy HTTP

Status: **SELF_TESTED PASS for local wire only**. Independent acceptance is not implied.

- Executed 2026-11-24 20:47 Asia/Shanghai, Python3.13.5, official `mcp==1.30.0`.
- Exact tested tree: `24c4be242edf765020d295d413091ec12e6b0a52`.
- Raw output: [l3-local-mcp-wire.log](l3-local-mcp-wire.log); executable assertions: [live_mcp_probe.py](live_mcp_probe.py).
- Command: `PYTHONPATH=src .venv-mcp/bin/python -W error::ResourceWarning docs/acceptance/v1.2-phase4/live_mcp_probe.py`.
- Fresh temporary business schema2 DB and **separate** replay DB; no existing business DB was opened.
- Loopback temporary ports were 44007 (legacy HTTP), 54997 and 57447 (two actual MCP workers).

| Observed scenario | Actual result |
|---|---|
| Official `streamable_http_client` + `ClientSession.initialize/list_tools` | Successful real wire negotiation; exact four tools, strict schemas |
| search_evidence | Current external-authorized evidence; missing signed purpose defaults external; masked delivery and actual consumed receipt |
| Unconfigured explicit vector | Official tool error `vector_backend_not_configured`; no embedding/model fallback |
| verify_citation | Correct delivered hash valid; modified hash tampered/invalid |
| get_evidence_pack | Real receipts; any denied source denies whole collection, no partial raw content |
| report_evidence_issue | Queue row inserted with trusted Agent; inert hostile description; document-version JSON unchanged |
| Legacy HttpKnowledgeClient feedback | Existing signed HTTP contract works; body agent/purpose/policy_context each 400 |
| Injection with otherwise-valid required parameters | 36/36 actual tools/call identity-field attempts rejected, not merely JSON-schema claims |
| Concurrent official clients | Two tenants receive only their own doc/Actor/Agent context |
| Shared replay DB across two real MCP workers | Identical signed initialize accepted 200 on first worker, rejected 401 on second |
| Unsigned / signed read downgrade / removed signed purpose | All 401 |
| Hostile Origin | 403 |
| Database / cleanup | Schema remains2, exactly two queued fixture issues, graceful application shutdown, all three children waited; temporary DBs removed |

The child return codes `-15` are the probe's explicit SIGTERM cleanup after success;
raw logs show application shutdown complete for all children. Probe exit=0.
No ResourceWarning/unraisable diagnostics. No external model, embedding or Qdrant calls.

## Explicitly not inferred from the local result

| Boundary | Status / reason |
|---|---|
| Online Qdrant / real semantic embedding | SKIPPED — not configured; three existing live tests remain skipped |
| Real external Claude/Cursor/design-partner client setup <=10min | NOT_RUN — no external account/client exercised; the official SDK client is not a design partner |
| Production proxy/root_path deployment and same-origin host session/CSRF integration | NOT_RUN — runbook only; no production service touched |
| Multi-host replay storage | NOT_IMPLEMENTED — shared local SQLite worker model only |
| Real PDF/OCR coordinate extraction | NOT_RUN — inherited B02 sample remains a host-provided offline layout fixture |

See [QUICKSTART_AND_PRODUCTION.md](QUICKSTART_AND_PRODUCTION.md) and
[gateway_client_example.py](gateway_client_example.py) for a precise isolated sandbox
recipe, signing boundary, optional SDK/Python requirement and production checklist.
