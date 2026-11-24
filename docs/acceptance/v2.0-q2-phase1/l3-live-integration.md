# L3 — partial event-foundation checkpoint

Actual isolated wire probe:

```
PYTHONPATH=src:. .venv-phase4/bin/python -W error::ResourceWarning \
  docs/acceptance/v2.0-q2-phase1/live_checkpoint_probe.py
```

Results: `l3-local-http-webhook.log`. A real Uvicorn listener on an OS-assigned
loopback port exercises signed `/v1/audit/query` and `/v1/audit/verify`, typed HTTP
client parity, unsigned 401, non-admin 403, and cross-tenant empty results. A
separate real `ThreadingHTTPServer` loopback receiver verifies all four Webhook
headers and HMAC-SHA256 over timestamp + delivery ID + event ID + exact bytes.
Both listener lifecycles and all connections are closed by the probe.

Webhook signature envelope:
`sha256=HMAC_SHA256(secret, timestamp + '.' + webhook_id + '.' + event_id + '.' + raw_body)`.
The verification helper defaults to a 300-second freshness tolerance. Receivers
must additionally deduplicate the stable Webhook ID for replay resistance.

`live_mcp_probe.py` is a copy of Q1's wire regression probe with its schema
expectation updated to v3. The historical Q1 script/logs were not modified.

NOT_IMPLEMENTED in this checkpoint: `/v1/impact/alerts`, `/v1/impact/ack`, actual
usage lineage and ImpactRadar. Consequently there is no claim of 100% impact
completeness, B04 closure, or end-to-end impact-Webhooks within one minute.
No live Qdrant, embedding, model, paid API, proxy, browser or PDF/OCR integration
was exercised.
