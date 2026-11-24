# L3 — real isolated PostgreSQL + pgvector

All PG evidence uses a newly initialized box-local cluster, not an existing
service/database. Runtime role `sdk_app` is NOSUPERUSER / NOBYPASSRLS. The cluster
is limited to 32 MB shared buffers / 24 connections on a newly allocated loopback
port. Test schemas are unique and removed by their own fixture; DR uses new
`sdk_dr_*` databases only. No production credentials or passwords are required.
Full versions are in `environment.log`.

- `l3-pg-specialized.log`: actual non-superuser raw SQL RLS rejection, all tenant
  tables FORCE RLS, context reset and nested savepoints; audit 4-connection race
  (160 worker commits, 4 rolled-back appends, no holes/forks); shared atomic nonce
  race (4 instances, one winner), TTL reuse and tenant namespace; live cosine
  candidates rejected after rights revocation, missing redactor fails closed;
  expired row lock skipped and stale attempt fenced.
- The same log runs 4 independent OutboxDispatcher instances through real HTTP
  loopback WebhookDispatcher deliveries. 96 events are dispatched; two revision
  subscriptions produce 64 correctly signed, unique POST delivery IDs; 32 exact
  usage impact alerts remain. Every worker processes events; no deadlock. This
  demonstrates no duplicates in that healthy run, **not** universal exactly-once.
  Crash after receiver acceptance/before sender commit still requires receiver
  idempotency by `X-KB-Webhook-Id`.
- `l3-cjk-shared.log`: one identical CJK-English + scope + authorized-fetch
  contract per engine, including empty foreign-tenant filtered queries.
- `l3-pg-http.log` and `l3-http-process-{0,1}.log`: two real
  `knowledge-sdk-server` CLI processes, one explicit `--dsn`, one environment
  DSN; signed metadata/search/anchor/receipt/usage/impact APIs, real pgvector with
  local HashEmbedder, live ACL rejection, cross-tenant isolation, shared nonce
  first request 200 / replay on second server 401, unsigned 401, clean shutdown.
- `l3-dr.log` / `dr-report.json`: actual pg_dump custom archive + pg_restore into
  another new database, all-table row-count/canonical SHA-256 equality, real DDL
  interruption rollback then idempotent v3 reapply, restored multi-tenant audit,
  version-1 pins/anchors/bindings/usage/alerts and current ACL preservation. The
  empty `public` schema shell is excluded from restore TOC because target already
  holds the DBA-provisioned vector extension; no data entries are excluded.
  This is a table-owner/operator drill on empty test DBs, not a production
  downgrade/PITR/failover claim.
- `migrate-cli.log`: installed entry point and `python -m` status/apply/check,
  repeated apply returns v3 with no missing tables.

The parameterized suite retains the original 75 scenario assertions and cases.
Test-only SQLite `?`/unscoped diagnostic probes are adapted for PG, and explicit
ledger corruption probes temporarily use owner-level RLS disablement. The real
RLS denial test does NOT use that adapter. Deterministic vector-stub adversarial
scenarios remain injected by design; actual PG cosine security is separately
exercised. PG fixtures build real pgvector rows. Offline PDF coordinates remain
fixtures, not PDF/OCR acceptance; no remote model/embedding/Qdrant call is made.

Historical `development-*` logs retain real implementation/test-fixture failures
and reruns. Only named final logs/reports constitute acceptance evidence. Earlier
pre-final full logs included an accidental duplicate unittest class alias; final
suite removes it. No skipped PG test is counted as a pass.
