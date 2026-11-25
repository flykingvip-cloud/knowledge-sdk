# Q3-M1 Agent Knowledge Runtime (unreleased)

The detailed Q3-M1 taskbook is the implementation authority. The referenced
`knowledgeos-q3-core-protocol-spec-v0.1.md` and
`knowledgeos-strategy-architecture-v0.2.md` were absent from the checkout and
`/workspace/q2-task-inputs` / `/workspace/q3-task-inputs`. This is **not a claim
of conformance to an unseen supplemental specification**. Packaging metadata
remains 1.2.0; use the exact feature-branch SHA, not that version label, to identify
this unreleased engineering result. No package handoff or enterprise integration
has been resumed.

## Trusted local usage

```python
from knowledge_sdk import Actor, LocalKnowledgeClient, ContextBudget, Purpose

client = LocalKnowledgeClient()
admin = Actor('admin', 'example', org_roles=('admin',))
reader = Actor('reader', 'example')  # supplied by a trusted host, never user headers
try:
    client.register_agent_profile(admin, 'assistant',
        allowed_purposes=(Purpose.GROUND_INTERNAL_LLM,),
        allowed_kb_ids=('handbook',),
        default_budget=ContextBudget(3, 8, 1000, 4000, 300))
    # A trusted host creates/populates handbook using existing ingestion APIs.
    task = client.create_task_context(reader, 'assistant',
        purpose=Purpose.GROUND_INTERNAL_LLM, ttl_seconds=300)
    snapshot = client.create_context_snapshot(reader, task.task_id, 'leave policy')
    pinned = client.read_task_snapshot(reader, task.task_id, snapshot.snapshot_id)
    client.complete_task_context(reader, task.task_id)
finally:
    client.store.close()
```

All six contracts are frozen and serialize with `to_dict/from_dict` and the
existing `encode/decode`: ContextBudget, AgentProfile, TaskContext, SnapshotItem,
ContextSnapshot, MidTaskRevocation. No optional dependency is needed for the local
runtime. Core `dependencies=[]` is unchanged.

## Supplemental implementation choices (not quoted from the missing spec)

* Budget fields: `max_documents`, `max_items`, `max_chars_per_item`,
  `max_total_chars`, `max_ttl_seconds`; defaults 5/20/2000/8000/900. Integers are
  strict (booleans/floats/negative values rejected); zero is a real zero budget.
* Empty profile KB/space whitelists mean no additional restriction. Empty task
  scope `{}` means `all_authorized`, never bypassing actor policy. Explicit
  `KnowledgeScope('none')` is deny-all, not an empty selector fallback.
* Requested budget and TTL only narrow the profile's maxima. Supplied entry order
  is preserved and deterministically clipped; keyword queries use existing stable
  retrieval ordering. Entries are `{doc_id, version?, anchor_id?, chunk_ids?}`;
  caller text, hashes, ownership, identity generations and profile generations
  are never accepted. Ineligible entries are omitted; a valid empty snapshot is
  possible. Unanchored text uses the SDK's canonical whitespace-normalized
  delivered representation. Anchor text is the validated delivered quote.
* Snapshot content is immutable and SHA-256 sealed (excluding external lifecycle
  status). Redundant SQL fields, counts and JSON are crosschecked on every read.
  Only SQL revocation status can change; JSON remains its original valid payload.
  UsageEvent.task_id links the task, and consumer_type=`context_snapshot` plus
  consumer_id links the snapshot. Hashes detect accidental/partial storage
  corruption, not a fully privileged DBA recomputing every seal.
* New published revisions issue SUPERSEDED metadata without replacing valid old
  snapshot text. Unhealthy bound/latest anchors, revoked/archived resources,
  current policy/redaction failure, directory generation/deactivation and profile
  generation/disable all fail closed. For safety, any ACL/rights update affecting
  a bound task proactively invalidates it, even if that change might be a
  relaxation; a new task is required. No terminal task is silently revived.
* Every rejected runtime operation persists an audited DENY before raising.
  Runtime guards hold `client._lock -> store.runtime_transaction()` across
  validation and consumption; SQLite uses BEGIN IMMEDIATE. PG uses a conservative
  database-scoped advisory serialization boundary for runtime/policy writes,
  **not** outbox claims. Independent-connection race tests cover profile/SCIM
  writes during snapshot insertion. This is not a throughput benchmark.
* Proactive write hooks commit source mutation, event-linked task/snapshot
  revocation, task_revocations and redacted task_context ImpactAlert atomically.
  ImpactRadar processes events idempotently, ignores stale generation events,
  and does not revoke newly created contexts for older queued changes. No
  background daemon is started automatically. On-demand reads/MCP do not wait
  for an OutboxDispatcher flush.
* Bare task IDs are not legacy free-form lineage labels anymore: a supplied
  task_id must resolve to a real owned active context. Legacy benchmark fixtures
  now register real contexts before their **unchanged** assertions run. Absent
  task_id, the four MCP tools retain their previous behavior. snapshot_id without
  task_id is invalid. Bound calls enforce task purpose/agent/profile/scope and
  revalidate every sealed reference. Oversized MCP material is rejected rather
  than rewriting its signed receipts; snapshot construction is deterministically
  clipped.

## Transport

`HttpKnowledgeClient` mirrors all runtime operations. Routes use trusted
HMAC/OIDC Actor context and `Cache-Control: no-store` (including errors):

| Operation | POST route |
|---|---|
| register_agent_profile | /v1/runtime/profiles |
| update_agent_profile (active=False disables) | /v1/runtime/profiles/update |
| get_agent_profile / list_agent_profiles | /v1/runtime/profiles/get / profiles/list |
| create_task_context / complete_task_context | /v1/runtime/tasks / tasks/complete |
| create_context_snapshot / read_task_snapshot | /v1/runtime/snapshots / snapshots/read |
| list_task_revocations | /v1/runtime/revocations |

Runtime parameters use the existing `{ "params": {...} }` transport envelope.
Purpose is a signed transport claim, not an unsigned JSON/header override.
Client-supplied Actor, task owner, profile/policy generation, or unsupported
parameters are rejected. Unknown/foreign/other-owner task IDs yield the same
`runtime_resource_unavailable` result. MCP JSON-RPC errors contain no source text.

PG RLS protects all four v5 tables with ENABLE/FORCE RLS. As before,
`app.current_org_id` is a **trusted application boundary**, not protection against
arbitrary untrusted SQL able to set that configuration. Admin profile authority
never expands the requesting user's resource permissions.

## Evidence and boundaries

See `acceptance/v2.1-q3-phase1/Q3_PHASE1_HANDOFF_REPORT.md`. No UI changed:
L4=`NOT_RUN_NO_UI_CHANGES`; Q2's headless browser proof remains historical.
Real enterprise IdP/SCIM, Qdrant/model/embedding, PDF/OCR and external MCP clients
are not newly certified here. Enterprise/StratAI integration remains paused.
Q3-M2/M3/M4 and Q4 functionality is not included.
