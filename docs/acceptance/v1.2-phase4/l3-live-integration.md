# L3 — authoritative taskbook actual JSON-RPC HTTP + stdio

**SELF_TESTED PASS locally**, not independent acceptance or an official SDK claim.
Executed 2026-11-24 21:07 Asia/Shanghai; Python3.13.5; clean `.venv-phase4` has
FastAPI0.165.0 / uvicorn0.54.0 and **no external MCP SDK distribution**.
Tested implementation: `cf30cf2bd250e15c8e575fd65e3880207034b598`.

Raw log: [l3-local-http-stdio.log](l3-local-http-stdio.log).
Executable assertions: [live_mcp_probe.py](live_mcp_probe.py).
Command: `PYTHONPATH=src .venv-phase4/bin/python -W error::ResourceWarning docs/acceptance/v1.2-phase4/live_mcp_probe.py`.

| Real transport scenario | Observed result |
|---|---|
| `python -S -m knowledge_sdk.mcp` without identity | Nonzero, no anonymous/admin fallback |
| Actual newline-JSON stdio subprocess with fixed trusted Actor | initialize, initialized notification, ping, tools/list and all4 tools; only JSON stdout; genuine mcp_stdio receipts |
| Actual signed FastAPI POST /v1/mcp | initialize/list/search/verify/pack/report over loopback HTTP |
| Masked anchored search | Real reference/consume/attach receipt with trusted Agent ID, task stage, delivered hash |
| Citation hash | Correct hash valid; altered hash tampered |
| vector/hybrid unconfigured | Explicit JSON-RPC backend-not-configured error; no implicit adapter or rewrite |
| Pack | Authorized subset retained with collective redaction; denied/missing sources excluded_count=2, no excluded URI/title |
| Feedback | One stdio issue + one HTTP issue queued; exactly two typed queue rows |
| Formal data invariance | Entire documents/versions/chunks/ACLs/anchors table snapshots unchanged |
| Otherwise-valid identity injection | 36/36 runtime tools/call attempts blocked, not only schema checks |
| Unsigned / shared-worker nonce replay | 401; valid first use200; Cache-Control:no-store |
| Signed external purpose against default-prohibited rights | No authorized evidence; no model called |
| Concurrent tenant requests | Isolated Actor/Agent/doc results, no mutable session identity |
| Typed HTTP issue listing | POST /v1/issues/list current-authorized/redacted EvidenceIssue responses |

Two temporary HTTP workers used loopback ports49905/54369, a new temporary schema2
business DB and separate shared replay DB. They were SIGTERM'd and waited in finally;
raw logs show application shutdown complete for both. Returncodes -15 are expected
explicit cleanup, probe exit0. All temporary databases were removed. No ResourceWarning
or unraisable diagnostic. No existing service/port/Qdrant collection was touched.

## Not run / not implied

- Online Qdrant/embedding/real semantic tests: SKIPPED; isolated test environment
  deliberately does not enable live URL/model variables. No external model calls.
- Real reverse-proxy/root_path deployment and host login/cookie-CSRF/session mapping:
  NOT_RUN; operational contract documented, no production deployment.
- Real PDF/OCR extraction: NOT_RUN; inherited PDF geometry remains an offline host plugin fixture.
- Actual Claude Desktop/Cursor manual integration / external enterprise/design partner
  completing <=10min: NOT_RUN. The exact sandbox recipe/configuration is in
  [MCP integration](../../mcp-integration.md) (repository path `docs/mcp-integration.md`).
- Broad MCP conformance beyond the taskbook JSON-RPC methods, SSE/resumption/OAuth:
  not claimed. No official third-party MCP SDK is used by the current implementation.

The earlier official-SDK experiment belongs ONLY to `superseded-parent-brief/` and
must not be substituted for these authoritative transport results.
