# L3 — actual paired stores / signed HTTP / MCP / Runtime

Source/test SHA: `a57a4b9adda74f3ef6e102e7179b80dd56280021`.
Generated 2026-11-25, Asia/Shanghai. No browser or production endpoint used.

## Real stores and vectors

A newly created PostgreSQL 17 cluster, socket-only in this run's owned directory,
used a new database and NOSUPERUSER/NOBYPASSRLS/NOCREATEDB/NOCREATEROLE application
role. pgvector was provisioned by the owned test-cluster DBA. Per-test random
schemas were dropped afterwards. Existing clusters/services/data/containers were
not used. SQLite uses actual FTS5 and real in-memory cosine over explicit offline
HashEmbedder vectors; PostgreSQL uses actual tsvector and persisted pgvector rows.
There are no canned vector/rank callbacks in the positive measured evaluator.

`pairwise-eval-sqlite.json` and `pairwise-eval-postgres.json` preserve all 24
measured cases, 24 family breakdowns, actual returned IDs, counters, citations and
latencies. Same frozen corpus/query/config files are used by both stores; their
native baseline ordering differences remain observable. Actual vector/index
fingerprints are checked unchanged around both arms. Each evaluator runs the
same actor/purpose and corpus under the client lock/runtime transaction boundary.

The fixed files were committed/frozen before the first measured run. No measured
labels or document-family identity are inputs to scoring/calibration. Labels are
used afterwards for metrics only. All 32 families are disjoint across 4 train /
4 calibration / 24 evaluation families; raw file hashes are in dataset-freeze.json.

## Real signed transport — PASS

Each engine passed **80 assertion groups**, using a real Uvicorn loopback socket,
real signed HttpKnowledgeClient/urllib requests and real MCP JSON-RPC calls, not
only TestClient/ASGI stubs. Safe dynamic ports were chosen; reserved ports were
excluded. Each server thread/socket was joined/closed in finally blocks.

Tests demonstrate:

* Local/HTTP enhanced hybrid ordering and score parity; low-confidence refusal;
* raw secret body/title redaction before a server-registered observing ranker,
  with denied-body sentinel absent from every received candidate;
* unknown/malformed reranker and calibrator IDs, bool/NaN/Inf/out-of-range
  threshold, oversized window and injected URL/object parameters rejected with
  400 + Cache-Control:no-store even on none scope/empty hits;
* task-bound enhanced MCP and query snapshots use only the owner's task scope;
  explicit none scope remains empty, wrong-owner snapshot creation is denied;
* document revoke/archive/ACL, anchor drift/orphan, SCIM generation/deactivation,
  profile generation/disable: **nine variants / all six revoke families**;
* after each mutation, before dispatcher flush, snapshot reads and enhanced
  additions deny, task status is revoked, bound MCP refuses without text, and
  the observing ranker's measured call count is unchanged (guard before rank).

See http-sqlite.json and http-postgres.json for actual assertion/ranker counts.
M2 transport tests are HMAC-signed; earlier M1 OIDC evidence remains historical,
not relabelled as newly performed enterprise IdP integration.

## RLS and inherited protections — PASS

The real PG probe asserts current role is not a superuser. Each of agent_profiles,
task_contexts, context_snapshots and task_revocations still has ENABLE/FORCE RLS;
foreign tenant context returns exactly zero rows for all four. The app tenant
setting remains a trusted-host boundary, not a sandbox for arbitrary SQL.
All original runtime, generation, ACL and independent-connection race tests are
included in the full PG-enabled suite. Storage/schema/migration sources are
byte-identical to 69b6c98; M2 does not add a table or upgrade schema 5. Historical
M1 pg_dump/restore proof is preserved; no new production failover is claimed.

## Reproduce

From a checkout with optional HTTP/PG dependencies already installed:

```sh
PYTHONPATH=src:. python -W error::ResourceWarning \
  docs/acceptance/v2.1-q3-phase2/run_evidence.py \
  --engine sqlite --http --output /path/to/evidence
# Provision a NEW owned non-superuser pgvector fixture first; never point at a live DB.
KNOWLEDGE_SDK_TEST_PG_DSN='<owned disposable database>' PYTHONPATH=src:. \
  python -W error::ResourceWarning docs/acceptance/v2.1-q3-phase2/run_evidence.py \
  --engine postgres --http --output /path/to/evidence
```

The process-local offline evaluator instruments actual known provider/network
boundaries and has real attempted-call negative controls. It is not an arbitrary
code-execution security sandbox. No live Qdrant/model/embedding/paid service was
called. This run's owned PG cluster/data is stopped/removed after acceptance;
no credentials, tokens, HMAC secrets or password-bearing DSNs are archived.
