# L3 actual enterprise HTTP / RLS / concurrent Outbox — PASS

Reproduction: optional HTTP/PostgreSQL/cryptography environment, explicit new
owned disposable PostgreSQL test DSN, then:

```text
PYTHONPATH=src:. python -W error::ResourceWarning docs/acceptance/v2.0-q2-phase4/live_enterprise_probe.py
PYTHONPATH=src:. python docs/acceptance/v2.0-q2-phase4/performance_probe.py
PYTHONPATH=src python -m unittest tests.q2.test_q2_m4_enterprise tests.server.test_q2_m4_http -v
```

No browser API/TestClient substitutes were used for HTTP: actual uvicorn TCP
listeners, urllib requests, cryptographic signatures and a real loopback JWKS
HTTP server. SQLite v4 and PostgreSQL 17 + pgvector were exercised. Configured
keys/secrets are generated test-only values, never printed or committed. Raw
endpoint/status evidence: `l3-enterprise-http.log`.

- sqlite: 52 real endpoint/status assertions passed.
- postgres: 52 real endpoint/status assertions passed.

Coverage: dual HMAC/OIDC positive requests; RSA signed bearer and live JWKS fetch;
expired/malformed/issuer/audience/tenant/replay denial; OIDC→HttpOnly session;
cookie Origin/CSRF check; draft/cross-tenant content absence; no unsigned actor,
tenant or generation header override; full Users and Groups route surface,
malformed body 400, list equality filter, member selector PATCH; SCIM tenant/admin
checks; generation-only role change while active rejects an old signed token
(and accepts a freshly signed current generation); deactivation immediately blocks preissued signed high-privilege JWT,
HMAC, MCP, pack/alert API and existing cookie session; DENY audited. JSON and
ZIP export revocation is additionally covered by dual-engine G7 and M3 contracts.

Both configured reference connector HTTP routes passed. Signed Wiki upsert then
tombstone, Outbox drain and impacted pack were asserted, not inferred from
hand-built alert rows. Current runner emits the authoritative revocation event
exactly once via existing set_document_rights, with durable cursor/idempotence.

All new directory/group/member/cursor tables enforce ENABLE and FORCE RLS.
Unscoped and foreign-tenant reads by the non-superuser/non-BYPASSRLS application
role return no rows. Four independent PG connections produce 40 unique policy
generations; four concurrent Outbox workers claim/drain 80 events, 0 duplicate
claims, no deadlock (performance.json). PG uses native FOR UPDATE SKIP LOCKED;
this is healthy-run claim evidence, not an exactly-once failure/retry guarantee.
Real pg_dump/pg_restore and v4 migration interruption/reapply fingerprints match
(dr-v4.json), including restored identity/generation/group/cursor contracts.

**Boundary:** these are local test keys and databases. No real enterprise IdP,
production proxy/login mapping, external SCIM certification or enterprise
admission approval is implied. Nginx prefix HTTP preflight is separately recorded
in proxy-http-preflight.json; actual independent hosted headless L4 now passes all four hard requirements
(run45526947873, l4-browser.md). The original HTTP assertions remain L3, not
retroactively browser-measured. HTTP-only signer GET/POST
through both nginx prefixes was additionally 404/no-store after the browser run
(l3-browser-boundary-supplement.json).
