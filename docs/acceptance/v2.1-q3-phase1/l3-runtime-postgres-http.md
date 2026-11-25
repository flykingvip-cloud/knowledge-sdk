# L3 — real runtime / PostgreSQL / signed HTTP and MCP

Source implementation: `8acce646760da46f7c1797b83ea3b4fbd56a0d6e`.
Evidence generated 2026-11-25 (Asia/Shanghai); raw contract timestamps are UTC by
contract and are not relabelled as local time.

## Runtime transport — PASS

`live_runtime_probe.py` uses a real loopback Uvicorn server and real urllib / SDK
HTTP clients, not an ASGI transport stub. SQLite and PostgreSQL each passed
**109 assertion groups**. Each engine has independent disposable state. HMAC and
offline issuer-verified OIDC requests both read real sealed snapshots; no actual
enterprise IdP was contacted. All responses checked `Cache-Control: no-store`.

Nine variants cover all six revoke families:

* document revoked; archive; ACL deny;
* anchor DRIFT_PENDING and ORPHANED (actual revision/ingestion path);
* profile generation/purpose narrowing and disable;
* SCIM principal generation/department change and deactivate (actual PATCH).

For every variant, before dispatcher flush: task and snapshots were already
revoked, event-linked task_revocations existed, read/create returned no content,
and all three task-bound MCP search/verify/getpack paths refused. Auth-stale
principal MCP requests are rejected by middleware (401), while other revoked
contexts produce controlled JSON-RPC errors; neither contains source text.
Completed tasks cannot accept additions. Unknown task ownership and unsupported
profile-generation/body fields fail closed; unsigned budget/task/generation
headers do not change trusted server state. Current-principal generation must
match exactly, not merely be at least the directory generation.

Raw machine-readable results: `l3-runtime-http-results.json`.
Reproduce from the checkout using optional HTTP/PG dependencies:

```sh
PYTHONPATH=src:. KNOWLEDGE_SDK_TEST_PG_DSN='<owned disposable database>'   python -W error::ResourceWarning docs/acceptance/v2.1-q3-phase1/live_runtime_probe.py
```

## PostgreSQL + pgvector, RLS and races — PASS

A newly initialized box-only PostgreSQL 17 cluster listened only on its owned
Unix socket; no existing cluster, container, database or application service was
used. Every database/schema was new. pgvector was DBA-provisioned in those new
databases, and test/application role `sdk_q3` was NOSUPERUSER/NOCREATEROLE.
Golden tests used real pgvector with local deterministic HashEmbedder, never an
online embedding/model service.

All four v5 tables have ENABLE/FORCE RLS. Actual non-superuser SQL with foreign
org context returned **0 rows** for agent_profiles, task_contexts,
context_snapshots, task_revocations. The fixture also asserted `rolsuper=false`.
RLS remains a trusted application tenant-context boundary, not a grant to allow
arbitrary untrusted SQL/set_config.

Independent connection tests pause snapshot construction while another client
tries profile disable or SCIM deactivate. The mutation cannot interleave with
validation/insertion; once it commits, the produced snapshot is revoked and
subsequent consumption denies. Four independent profile writers produced all
16 unique generations without lost increments. The preserved SKIP LOCKED /
expired-claim fencing test passes: runtime serialization does not lock out claim
concurrency. An initial overly broad lock was caught by that existing test and
narrowed before this final evidence; diagnostic artifacts remain on the box.

## Lossless migration / DR v5 — PASS

SQLite automated tests cover v0..v4 reopen and v4 interrupted DDL rollback.
Real PostgreSQL v0..v4 migration-marker fixtures retained document JSON bytes
and upgraded to v5; see `postgres-v0-v4-migration.json`.

Actual `pg_dump`/`pg_restore` between two separately provisioned empty sdk_dr_*
databases returned identical **all-table row-count/SHA-256 fingerprints**.
Seeds include both tenants and all four v5 tables, with profiles/tasks/snapshots
and event-linked revocations. Restored tasks and snapshots remain revoked;
restored audit chains and ACL denials pass. The interruption probe reconstructs
v4->v5 DDL inside a transaction, injects a failing SQL statement, and verifies the
outer rollback restores every prior business fingerprint; idempotent migration
reapply also matches. See `dr-v5-fingerprints.json`.

This operator-only disposable drill transiently changes FORCE RLS to produce a
complete table-owner backup and restores it in finally blocks. It is **not** a
production failover, managed-service backup, or live topology certification.

No production credential, private key, HMAC secret, token or password-bearing
DSN is included in these evidence files. Test infrastructure is stopped and its
owned disposable database data removed after all acceptance runs.
