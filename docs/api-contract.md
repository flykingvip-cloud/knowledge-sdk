# Python / HTTP contract · v1

## API shape

Every domain method takes a trusted `Actor` first; `health()` is the only exception.
`LocalKnowledgeClient` and `HttpKnowledgeClient` have identical public method
signatures. The remote client serializes typed dataclasses with `__type__` markers
and reconstructs them; use `contracts.models.encode/decode` for direct HTTP calls.
Mappings containing a `__type__` user key are escaped as `__mapping__` objects, so
custom metadata does not masquerade as a transport model. Never use pickle.

POST requests use `{"params": {...}}`; GET list methods use a JSON `params` query
parameter. Responses are encoded domain objects directly, not an extra `result`
envelope. Null means a successful command with no returned object. Binary ingest
uses `content_b64` (validated standard base64), while text uses `content`.

| Python method | HTTP | Parameters after Actor | Result |
|---|---|---|---|
| create_kb | POST /v1/kbs | name, visibility="private", kb_id=None | KnowledgeBase |
| list_kbs | GET /v1/kbs | — | list[KnowledgeBase] |
| grant_kb_member | POST /v1/kbs/members | kb_id, user_id, role | null |
| ingest | POST /v1/documents | kb_id, content, filename="document.txt", title=None, visibility=None, doc_id=None, metadata=None | DocumentVersion |
| list_documents | GET /v1/documents | kb_id=None, include_archived=False | list[Document] |
| get_document | POST /v1/documents/get | doc_id, version=None | Document or DocumentVersion |
| preview | POST /v1/documents/preview | doc_id, version=None, limit=800 | RetrieveResponse |
| archive | POST /v1/documents/archive | doc_id | null |
| restore | POST /v1/documents/restore | doc_id | null |
| set_document_acl | POST /v1/documents/acl | doc_id, acl:DocumentACL | null |
| search | POST /v1/search | query, mode="keyword", limit=20, filters=None | SearchResponse |
| retrieve | POST /v1/retrieve | doc_id, version=None, chunk_ids=None, offset=0, limit=8000 | RetrieveResponse |
| reference | POST /v1/references | doc_id, version=None, chunk_ids=None, excerpt="" | KnowledgeRef |
| consume | POST /v1/references/consume | ref:KnowledgeRef | MaterialReceipt |
| batch_consume | POST /v1/references/batch-consume | refs:list[KnowledgeRef] (max 100) | list[MaterialReceipt] |
| reindex | POST /v1/reindex | kb_id | null |
| health | GET /v1/health | no Actor | status, version, pending_index_count |

Resource aliases are also available: GET `/v1/documents/{doc_id}/versions/{version}`;
POST `/v1/documents/{doc_id}/archive`, `/restore` (empty body), and `/acl`
(`{"acl": <encoded DocumentACL>}` or a plain ACL object). Same authorization and
models, not independent logic. GET `/openapi.json` documents paths/auth and request
envelopes. This document defines the parameter/model contract beyond the generic
OpenAPI envelopes; v1 does not claim an auto-generated strongly typed web client.

Search filter keys: `kb_id`, `doc_id`, `tags` (all requested tags required).
Search mode: `keyword`, `vector`, `hybrid`. Vector modes require both injected
index and embedder. Limits: search 1..100 hits; query 1..10000 chars; retrieve
1..100000 code points; nonnegative offsets; ingest 32 MiB; HTTP body 48 MiB.
`next_offset=None` means end. Search preview hashes use normalized excerpts;
retrieve pages use original parsed text and have independent offsets.

## Response and receipt semantics

`SearchHit`: doc_id, version, chunk_id, title, score, excerpt, excerpt_hash,
source_uri, truncated, remaining_chars, partial_notice, masking_summary,
highlights. `SearchResponse`: hits, mode. No unauthorized hits are emitted.

`RetrieveResponse`: doc_id, version, text, offset, limit, total_chars, truncated,
next_offset, source_uri, chunk_ids.

`KnowledgeRef`: org_id, doc_id, version, source_uri, chunk_ids, excerpt,
excerpt_hash. URI identity must match the model; fragment chunk must be selected.
Use `reference()` to build one or map a search hit's authoritative identity.
`MaterialReceipt`: status, source_uri, evidence_kind, chunk_ids, reason_code,
excerpt_hash. A complete unselected document is `consumed`; selected chunks or a
proper excerpt are `partial`; an authorized archived/missing version is
`unavailable`; inaccessible/cross-org is `denied`. Denied receipts do not validate
or reveal source contents. Fabricated hash, URI, unknown chunk or excerpt raises
`TamperedExcerptError`, not a success-like receipt. A forged item aborts batch
validation (no side effects are performed). Receipts are not signed attestations
and are not an audit trail of actual cognition.

Errors: JSON `{"error": "ExceptionClass", "message": "..."}`. Missing, invalid,
stale or replayed authentication: 401. PermissionDeniedError: 403. NotFoundError:
404. ConflictError: 409. ValidationError/TamperedExcerptError: 400. Optional server
transport validation may additionally return 422. Core methods raise SDK
exceptions. A remote storage/adapter infrastructure failure may return 500;
health/reindex diagnoses pending index writes. There is no promise that a failed
remote vector sync rolled back its already committed SQLite mutation.

## Signed Actor gateway contract

A secret holder is a **trusted gateway**, not a normal end user. Actor includes
`user_id`, `org_id`, `roles`, `department_ids`; SDK does not authenticate those
claims itself in-process. In HTTP, HMAC verifies that a trusted gateway asserted
them. Never accept an unsigned Actor from a browser in production.

Headers: `X-KB-Actor` = URL-safe base64 of the JSON Actor, `X-KB-Timestamp` = epoch
seconds, `X-KB-Nonce` = fresh 16..128 character nonce, `X-KB-Signature` = hex HMAC.
The signed UTF-8 message is these six values joined with `\n` (no trailing newline):

1. uppercase HTTP method
2. exact request path plus query string, when present
3. exact encoded Actor header string
4. exact timestamp string
5. exact nonce
6. lowercase SHA-256 hex digest of the exact request body bytes (empty for GET)

HMAC-SHA256 uses the deployment-managed secret (at least 32 characters). Verify
with constant-time comparison; allow ±300s clock skew; reject reused nonces and
fail closed when the bounded replay cache fills. Cache lifetime covers both sides
of the timestamp window. Replay cache is in-memory/per-process; use a shared
gateway replay cache or one service worker, and account for restart replay risk.
TLS is required for confidentiality and to prevent signed requests being stolen.
HMAC is integrity/authentication, not encryption. No secrets are logged by SDK.

`server.auth.signed_headers` is the canonical helper. `dev_insecure=True` skips
signature verification but still requires a valid explicit Actor header. Never
expose that mode outside a private loopback development environment. Health and
OpenAPI/docs are public metadata surfaces; protect/disable docs at your gateway
if required. Body-size checking occurs after ASGI body buffering; enforce ingress
limits at the reverse proxy too.

## Compatibility

Versioned Python contracts are snake_case, HTTP routes are `/v1`; package version
is currently 1.2.0 (no Q2 release/tag). No application-specific fields enter the kernel. Use metadata for host
extensions. API-breaking changes require a new major version or `/v2` surface;
additive optional fields should have defaults. Unknown params are rejected rather
than silently ignored. Publish contract changes together with both client tests.

## Q2-M1 audit, lineage and impact APIs

All endpoints below use the existing signed Actor/Agent/Purpose HMAC envelope;
identity fields in `params` are rejected. These event endpoints reject
`dev_insecure` identities even when that legacy dev mode is enabled elsewhere.
Responses use `Cache-Control: no-store`. Core local equivalents have matching
`HttpKnowledgeClient` signatures and tagged typed results.

| Local / HTTP-client operation | Signed endpoint |
|---|---|
| `query_audit_events(actor, *, doc_id=None, actor_id=None, action=None, since=None, until=None, limit=100)` | POST `/v1/audit/query` |
| `verify_audit_chain(actor, *, from_seq=1, to_seq=None)` | POST `/v1/audit/verify` |
| `list_impact_alerts(actor, *, doc_id=None, status=None, target_id=None)` | POST `/v1/impact/alerts` |
| `acknowledge_impact_alert(actor, alert_id, *, status="acknowledged")` | POST `/v1/impact/ack` |
| `drain_outbox(actor, *, limit=50)` | POST `/v1/events/drain` (alias `/v1/outbox/drain`) |

These methods additionally accept the established trusted `agent`, `purpose`,
`policy_context` keywords; HTTP context remains server-controlled.

Audit queries are tenant-bound, ordinary users only their own actor_id, org
`admin`/`manage_org`/`auditor` may query tenant-wide. Limit is 1..1000; source-linked
results recheck current policy/redaction. Verification requires org admin or
manage_org and validates the prefix from genesis even for a requested subrange.
The report includes valid/checked/first_invalid_seq/reason_code/last_hash/org_id.
There is no audit update/delete API, no raw source text in audit details.

Impact visibility requires current tenant/space access plus recorded target-owner,
space-manager, or org-admin authority. A revoked source still permits its original
consumer to receive **identifier-only owned alert metadata**, not source/title/
excerpt/claims/receipt content; the live read DENY is recorded, never converted
into a source-read grant. Redaction profiles must remain available even for this
metadata path. Ack permits only acknowledged/resolved and repeats the same checks.
Same consumer_id/task_id text belonging to another user never grants access.

Drain requires org admin/manage_org, and claims only `actor.org_id`. Org-wide
verification/drain reject cross-tenant, purpose-restricted, or KB-scoped agent
contexts that cannot act tenant-wide. Successful writes, their Outbox records and
write audit entries share the authoritative transaction; denied trusted decisions
are recorded after rollback. Unauthenticated forged claims are never trusted as a
tenant identity for audit insertion.

`consume` / `attach` / batch and final MCP search/pack delivery persist immutable
UsageEvent rows with actual receipt SHA256, document/version/anchor, actor/agent,
purpose and task/binding identity. Old DocumentVersions, receipts and bindings are
never silently replaced. Existing tagged binding JSON remains readable; newly
saved bindings also retain private identity context for policy re-evaluation.

Webhook registration is trusted LOCAL administration only:
`register_webhook_subscription(actor, url, secret, event_types, *, allow_insecure_local=False)`.
Secrets (>=32 chars) are never returned; they reside in the access-controlled
SQLite subscription record. Normal URLs require HTTPS and public validated IPs;
DNS answers are all checked and the actual peer pinned, TLS verifies the original
host, proxies and redirects are not used. Translation/site-local IPv6, metadata,
private/reserved and mixed-DNS addresses are rejected. Loopback HTTP requires BOTH
explicit registration and `LocalKnowledgeClient(..., allow_insecure_local_webhook=True)`
(or the equivalent trusted dispatcher test flag); HTTP callers cannot enable it.

Webhook headers: X-KB-Webhook-Id, X-KB-Event-Id, X-KB-Webhook-Timestamp,
X-KB-Webhook-Signature. Signature input is `timestamp + '.' + delivery_id + '.' +
event_id + '.' + raw_body`, HMAC-SHA256, prefixed `sha256=`. Body carries event IDs,
identifier/version payload and identifier-only impact alerts. Verification helper
has a 300-second default freshness window; receivers must deduplicate stable IDs.
At-least-once crash delivery is not exactly-once delivery.

For a background embedded worker, explicitly construct OutboxDispatcher with
ImpactRadar(client) and WebhookDispatcher(store), then start/close it. Poll interval
is <=30 seconds, default 1; the tenant-admin drain provides deterministic tests.
No background thread is silently started by client construction. See the Q2-M1
handoff for SQLite serialization, identity refresh and unanchored-chain limits.
