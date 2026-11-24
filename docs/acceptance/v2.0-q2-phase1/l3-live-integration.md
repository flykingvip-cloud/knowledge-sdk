# L3 — actual local HTTP → usage → impact → signed Webhook

Executed 2026-11-24 23:23 Asia/Shanghai (UTC+8), tested source `60307212dc6fe23b6da8e9964add4a323542a30a`.

```sh
PYTHONPATH=src:. .venv-phase4/bin/python -W error::ResourceWarning \
  docs/acceptance/v2.0-q2-phase1/live_impact_probe.py
```

Actual output: `l3-local-http-webhook.log`. The probe creates a real Uvicorn
listener and a separate real ThreadingHTTPServer Webhook receiver, both using
OS-assigned loopback ports, temporary SQLite/replay DBs and disposable keys.
Connections, listeners, threads and temporary directories are closed in finally
blocks. No existing service or production DB is used.

## Verified on the wire

- Signed HttpKnowledgeClient consume/attach persist real immutable receipt lineage.
- Typed signed audit query/verify, impact list/ack and tenant-admin events/drain
  work over actual HTTP, not only an ASGI test client.
- Actual document revisions produce SUPERSEDED, DRIFT_PENDING and ORPHANED
  alerts; archive, revocation and ACL deny produce the exact expected owned usage
  and binding targets. Old v1 source rows, references, bindings and receipts stay
  unchanged; the probe does not silently reconstruct them at the current version.
- **7 unique signed real Webhook deliveries cover 14/14 expected alert IDs in
  under 60 seconds.** Valid HMAC passes; mutated raw bytes fail. Ordinary replay
  does not create duplicate logical deliveries.
- Unsigned requests401, replayed signatures401, unrelated users403, foreign tenant
  cannot read source-tenant alerts/audits. A foreign user may legitimately see
  their OWN tenant's new decision audits; this is not source-tenant leakage.
- A tenant-admin drain cannot claim another tenant's pending events.

Webhook envelope:
`sha256=HMAC_SHA256(secret, timestamp + '.' + delivery_id + '.' + event_id + '.' + raw_body)`.
Required headers are X-KB-Webhook-Id, X-KB-Event-Id,
X-KB-Webhook-Timestamp and X-KB-Webhook-Signature. Verification defaults to300s
freshness; receivers also need stable-ID deduplication across process crashes.

Related full-suite coverage exercises redirect non-following, mixed/private DNS,
DNS rebinding, validated numeric peer pinning, TLS hostname retention, IPv6
translation/site-local rejection, retry/dead-letter, contention and stale claims.
Only explicit double opt-in permits loopback for these disposable tests. No
external HTTPS endpoint was contacted and no production network perimeter was
certified.

`live_mcp_probe.py` preserves the Q1 wire regression with ONLY the current schema
expectation3; original archived Q1 evidence is untouched. The complete full-deps
suite executes the actual MCP HTTP/stdio tools as well. The old foundation-only
probe and report are under `superseded-checkpoint/`, not current acceptance.

No live Qdrant/Embedding/model/paid API, real PDF/OCR parser, proxy, host-session,
CSRF or browser path was exercised. L4 remains NOT_RUN; independent L5 PENDING.
The measured local fixture is not an unconditional one-minute production SLA.
