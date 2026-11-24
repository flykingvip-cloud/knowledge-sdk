# L3 — live integration boundaries

- Local real loopback HTTP: PASS, raw transcript `l3-local-http.log`.
- Command: `PYTHONPATH=src .venv-http/bin/python docs/acceptance/v1.2/live_http_probe.py`.
- Actual temporary port: 60583; isolated CLI process stopped and temp replay DB
  removed. Business database was `:memory:`. No reserved/application ports used.
- Exercised actual HTTP: custom prefix index/config/CSS/JS/i18n 200 + security
  headers; old UI paths 404; both disabled signer paths 404 despite demo headers;
  business unsigned 401; signed primary/fallback 200; replay 401; invalid-signature
  nonce poisoning rejected; purpose tampering 401. No model/embedding configured.
- Real Qdrant / real embeddings / semantic synonym chain: **SKIPPED — not
  configured**. Three existing live integration tests skipped with explicit
  reasons in L1/L2. Neither Mac services nor existing collections were contacted.
- Real reverse proxy: NOT_RUN. Trusted ASGI root_path preserved/stripped routing,
  signer behavior and assets are covered by L2 TestClient tests, not claimed as
  deployment/proxy validation. See host contract for upstream raw-target signing.
- SQLite cross-process nonce race: executed in L1 and L2 deterministic tests
  using six spawned Python processes and one dedicated temp database; one winner.
  This is process-level storage evidence, not multiple production HTTP workers.

No withdrawn earlier counts or PDF/collection-cleanup claims are used here.
