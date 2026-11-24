# PostgreSQL + pgvector (optional, Q2-M2)

Core remains Python 3.9+ / `dependencies = []`. SQLite remains the default.
Install `pip install 'knowledge-sdk[postgres,http]'` (for development add `dev`,
`parsers` and `pytest`). Drivers are lazy: `python3 -S` needs no PostgreSQL library.

## Provisioning and migration

Use a dedicated database, a non-superuser role without BYPASSRLS, and provision
`CREATE EXTENSION vector` as a DBA before selecting pgvector. Do not use production
credentials in command lines or evidence. Pass `KNOWLEDGE_SDK_DSN` securely in the
process environment; driver exception details are suppressed, not interpolated.

```
knowledge-sdk-migrate --status
knowledge-sdk-migrate --apply
knowledge-sdk-migrate --check
knowledge-sdk-server --host 127.0.0.1 --port 18088 --pg-rls
# Add --pgvector-dims 256 for the explicit local, non-semantic HashEmbedder.
# Or construct PgVectorIndex + your explicitly supplied embedder in a host.
```

`--dsn` overrides environment DSN. `--no-pg-rls` only omits RLS provisioning; it
never silently disables policies already installed by another instance. RLS is
schema configuration, not a request toggle. `create_app(dsn=..., auth_secret=...,
pg_rls=True, pgvector_dims=256)` owns and closes its connections at lifespan exit.
An explicitly supplied client remains host-owned. SQLite options are unchanged;
PostgreSQL cannot use demo seed or a separate SQLite replay file.

`PostgresStore(dsn, enable_rls=True, org_id=None, migrate=True)` is a trusted
in-process MetadataStore. All tenant payload queries bind `org_id`; every tenant
business table has ENABLE + FORCE RLS. `tenant_scope(org_id)` sets transaction-local
`app.current_org_id`; optional constructor `org_id` pins an instance to one tenant.
The small global `resource_directory(kind,id,tenant)` is identity routing metadata
only, required by the legacy org-less globally unique ID API. It never grants
content permissions. Administrative pending/outbox scans enumerate this directory
then enter individual tenant transactions. Do not expose SQL access, the DSN, or
`set_config` to untrusted clients. Use separate migration/runtime roles and
`migrate=False` after owner-provisioned schema in hardened deployments; do not use
a superuser/BYPASSRLS runtime account. Caller-supplied Actor still requires host
authentication. The policy engine remains authoritative above storage.

Transactions serialize one connection per instance; independent instances/processes
have independent connections and real concurrent transactions. Nested transactions
use psycopg savepoints. Audit appends take a per-tenant transaction advisory lock
before allocating the next sequence (no sequence object or rollback gaps).
CJK single-character/bigram tokens match the embedded tokenizer; PostgreSQL uses
`tsvector` + GIN and OR lexemes with deterministic rank tie breaks. Existing bounded
500-candidate authorized-fetch and `candidate_budget_exhausted` semantics are reused.

`PgVectorIndex(store=store, dimensions=N)` implements `upsert`, `search`,
`delete_document` (`query`/`delete` aliases). Direct `search` needs `org_id=` or a
pinned store. Hybrid retrieval automatically uses tenant-aware `search_for_org`.
Vectors contain identifiers/coarse flags only, never content, title or clearance.
Exact `<=>` cosine is used (no ANN recall/performance claim). All results go back
to live metadata, all eight policy stages and fail-closed redaction. Embedding
providers are never auto-called: CLI's optional HashEmbedder is local lexical
hashing, not semantic embedding.

`PostgresReplayStore` implements legacy `(nonce, ttl_seconds, now=...)`, explicit
`(org_id, nonce, expires_at, now=...)`, and HTTP's verified-tenant hook. TTL deletion
is tenant-scoped (idle tenants clean on their next authenticated request), capacity
is tenant-bounded, insert uses `ON CONFLICT DO NOTHING RETURNING`, and failures
reject. Shared storage makes independent signed HTTP instances reject the same
nonce. It is not an OIDC implementation.

Outbox claims use `FOR UPDATE SKIP LOCKED` and a 60-second lease. Processing holds a
row lock through handler/status completion and checks the claimed attempt number
as a fencing token. Unique keys protect logical impact/delivery records. **Delivery
is at-least-once**, not universal exactly-once: a receiver can accept a POST before
its sender transaction crashes. Receivers must deduplicate `X-KB-Webhook-Id`.
A healthy-run four-worker loopback stress verifies no duplicates, not crash-safe
exactly-once. Slow handlers hold connections/row locks; tune batches/worker counts
and use production connection limits. No daemon is started implicitly.

## Reproducible acceptance and DR

`KNOWLEDGE_SDK_TEST_PG_DSN` must name a dedicated disposable test database with
vector provisioned and CREATE SCHEMA permission. The tests create/drop only unique
`sdk_test_*` schemas. Run `python -m unittest -v tests.test_dual_engine_parity
 tests.q2.test_postgres` (one line) and `python -m tests.benchmark.run --engine
postgres --json-output benchmark.json`. Both retain all original 75 specifications
and assertions. White-box SQLite probes have a test-only adapter; deliberate
ledger corruption temporarily disables its table-owner RLS only inside that test.
Live non-superuser RLS denial is separately tested without that adapter. Deterministic
ranking redteam scenarios retain their original injected vector stubs; PG fixtures
also build real pgvector indexes, and the specialized stale-vector test exercises
real cosine retrieval, rights and redaction. No semantic-quality claim follows.

`python -m knowledge_sdk.storage.dr_drill --confirm-disposable --json-output dr.json`
requires `KNOWLEDGE_SDK_DR_SOURCE_DSN` and `KNOWLEDGE_SDK_DR_RESTORE_DSN` for two
**empty, caller-created databases named `sdk_dr_*`**, both vector-enabled. It rejects
existing business tables. It seeds multi-tenant/multi-version data, pinned usage
and bindings, anchors, pending/dispatched outbox, audit and impact; compares all
row counts and canonical SHA-256 through `pg_dump`/`pg_restore`; simulates a rolled
back migration interruption; re-applies v3 twice; rechecks audit, pins, alerts and
ACL. Backup uses the disposable table-owner role to temporarily remove FORCE RLS,
then restores it in `finally`. Run only against test DBs with no writers. This is
not a production backup/failover automation or a destructive v3-to-v2 downgrade.
Production backups need a separately authorized backup role, encryption, retention,
PITR and deployment-specific restore practice, none claimed by this drill.

Evidence: [Q2-M2 handoff](acceptance/v2.0-q2-phase2/Q2_PHASE2_HANDOFF_REPORT.md).
M3 governance/EvidencePack and M4 enterprise identity/connectors remain unimplemented.
