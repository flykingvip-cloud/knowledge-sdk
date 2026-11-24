# Q2-M1 handoff — engineering implemented; independent acceptance pending

Date: 2026-11-24, Asia/Shanghai (UTC+8).
Repository: `flykingvip-cloud/knowledge-sdk`.
Branch: `feat/q2-phase1-outbox-audit-impact`.
Branch URL: https://github.com/flykingvip-cloud/knowledge-sdk/tree/feat/q2-phase1-outbox-audit-impact
Exact starting baseline: `9c6a64b42893944a24e75ce4317e4dce8fee1751`.
Final tested runtime/test source: `60307212dc6fe23b6da8e9964add4a323542a30a`.
The following evidence/documentation commit changes no runtime or executable test
source; consult the branch tip/log for its final SHA and remote verification.

## 1. Scope and status

**Tasks0–5 of Q2-M1 are implemented and local acceptance was actually executed.**
This supersedes the deliberately incomplete `54dca43` checkpoint. The original
checkpoint report/probe remain under `superseded-checkpoint/` for provenance;
their NOT_IMPLEMENTED wording does not describe the current code.

Both complete owner-supplied specifications were read from the parent-provided
accessible `/workspace/q2-task-inputs/` exports. The sole execution scope is M1,
not all Q2. The separately referenced strategy-architecture-v0.2 file was not
found in this checkout; no claim of reading an absent document is made. The
supplied architect assessment is context, not an independent review of this code.

No PostgreSQL/pgvector adapter (M2), L2 workflow or EvidencePack creation/export
service (M3), OIDC/SCIM/Connector sync implementation (M4), or Q3 runtime was
added. Future schemas have reserved tables only, with defensive processing of
already-imported reserved pack rows as required by the impact specification.

**Independent L5/owner acceptance remains PENDING. M2 is not automatically
unlocked, and neither full Q2 nor enterprise production readiness is claimed.**

## 2. Implementation and commits

- `b3fbb7a` — lossless v0/v1/v2→v3 SQLite migration. All nine exact new tables
  and specified indexes; review_decisions, evidence_packs, connector_sync_state
  reserved without future services. Version>3 rejects. Real prior-layout
  fixtures check documents/versions/ACLs/anchors/issues byte-for-byte and force
  DDL failure to prove rollback of schema and user_version.
- `0e982c0` — frozen AuditEvent/AuditChainReport and tagged/public exports;
  tenant-local atomic seq_no, canonical JSON SHA256 chain and physical-column
  consistency verification. Full engine decisions and critical operations,
  including trusted denials, are audited without source text. Tenant/self-only
  ordinary audit queries; tenant-wide admin/manage_org/auditor; live source
  policy/redaction filtering. No public ledger update/delete API.
- `6a59b64` — atomic authoritative business write+Outbox, including revision,
  archive/restore, rights/revoke/ACL and confirmed/pending/orphan reanchor events.
  Atomic claims, expired leases, retry exponential backoff/default5, dead_letter,
  stable event/delivery IDs, per-subscription success dedup and failure isolation.
  DNS-pinned HMAC Webhooks with no proxies or redirects.
- `b3fcd9a` — signed tenant audit query/verify and HTTP-client parity.
- `54dca43` — historical partial checkpoint; no longer the current handoff.
- `407bf7e` — exact frozen UsageEvent/ImpactAlert/ImpactReason contracts and
  storage, real successful consume/attach/batch/final MCP delivery lineage,
  original actor/agent/purpose/task/receipt hashes, policy-rechecked ImpactRadar,
  preserved snapshots, signed impact list/ack/admin drain APIs+client parity.
- `49a7cab` — successful write audits share the authoritative transaction; denial
  audits survive rollback. Client→store lock order, stale worker fencing, old
  tagged binding compatibility/private trusted identity context, stronger IPv6
  translated/site-local SSRF defense.
- `06fa3c5` — new event APIs require signed identity even in dev mode and return
  no-store; tenant-wide operations reject mismatched/scoped/restricted agents;
  preserves legacy inferred operation purpose while auditing actual purpose.
- `6049de0` — fifteen distinct genuine G6 cases, measured audit/impact counters
  with failing negative controls, complete real impact HTTP/Webhook wire probe,
  isolated extracted-wheel verification and full regression assertions.
- `6030721` — reject invalid administrative purpose BEFORE drain side effects,
  retain actual policy_context generation/request/task in successful write audit,
  and preserve attributes of injected policy engines through the audit delegate.

## 3. Required impact and HTTP contracts

Usage rows come from actual consumed/partial MaterialReceipts, including final
MCP search_evidence/get_evidence_pack delivery, not preliminary verification.
UsageEvent and old receipts/versions/bindings have no replacement mutation API.
Existing tagged binding JSON is still readable; no implicit migration/rewrite of
old binding payloads occurs. New private storage records the trusted original
actor/agent for policy re-evaluation, without exposing claims in alerts.

ImpactRadar computes revision SUPERSEDED, archive RESOURCE_ARCHIVED,
rights/revocation/ACL ACCESS_REVOKED, and exact anchor-id DRIFTED/ORPHANED targets.
It reevaluates the original actor/agent/purpose, applies fail-closed redaction,
and is idempotent on source event+target. Both actual usage and binding targets
are represented. Scope-only pre-Q2 bindings are treated as subscriptions, not
invented receipts. Existing reserved pack payloads/hashes remain untouched;
only their separate status may become impacted. No pack service was created.

Signed endpoint/client parity:
- POST `/v1/audit/query`
- POST `/v1/audit/verify`
- POST `/v1/impact/alerts`
- POST `/v1/impact/ack`
- POST `/v1/events/drain` (alias `/v1/outbox/drain`)

Audit queries isolate actor.org_id; ordinary actors cannot request another
actor_id. Verify and drain require admin/manage_org; a tenant admin cannot claim
foreign events. Impact list/ack require recorded target ownership, space manager
or org-admin authority, current tenant/space checks and redaction. Revoked
consumers may read ONLY opaque identifiers of their OWN alerts: live source-read
DENY remains DENY, with no source/title/excerpt/receipt disclosure. Identical
consumer_id/task_id strings owned by another person do not grant access.
Unauthenticated forged claims are never accepted as a tenant audit identity.

## 4. Actual acceptance results

| Run | Actual result |
|---|---|
| Exact9c6a64b baseline stdlib | 446 run = **350 passed,96 skipped** |
| Exact9c6a64b baseline full deps | 446 run = **443 passed,3 skipped**; pytest443 passed,3 skipped,167 separate subtests |
| Exact baseline old golden | **60/60**, ACL0/20, implicit model calls0 |
| Final stdlib, python3 -S -W error::ResourceWarning | 502 run = **404 passed,98 skipped**, no failures/ResourceWarning |
| Final full-deps unittest, warning-strict | 502 run = **499 passed,3 skipped** |
| Final full-deps pytest | **499 passed,3 skipped,200 separate subtests**; one upstream Starlette/httpx deprecation warning, not ResourceWarning |
| Final benchmark75 | **75/75**, G6 **15/15**, no skips, ACL0/20, zero implicit model calls |
| Measured audit-chain detection | **19/19**, including physical fields/encoded corruption and interior sequence loss |
| Measured impact completeness | **45/45**, unexpected targets0 |
| Genuine loopback impact wire integration | **7 unique Webhook deliveries**, **14/14 expected alert IDs** in signed bodies, valid signature accepted/tamper rejected, under60s |
| AST3.9 | **67 src +5 benchmark files**, syntax parse passed |
| Build/extracted wheel | sdist+wheel passed; isolated python-S third-party blocker, four MCP tools, actual stdio entrypoint, schema3, audit/usage/revision-impact assertions passed |

The original golden v1 is byte-identical, and the first60 lines in v2 are
identical. All60 original G1–G5 scenario function bodies are AST-identical to
9c6a64b; runner changes add G6/metrics/default75 without weakening those bodies.
`original60-preservation.log` records actual assertions. Fixture SHA256:
`1b7c5ace8249495477457431e7b64f047868757ce28985ede56c483771b13fea`.
Metric-negative-control tests disable the radar or falsely report a tampered
chain valid and prove that completeness/detection and the overall gate fail.
Counters are observations, not constant percentages. No independent run is
implied by this executor's repeated local runs.

Wheel SHA256:
`752fd19e7d5416aee1f6051a52f00670f1ef6849b3763e9bda13275a1cfc6e03`.
Core dependencies remain `[]`. Wheel metadata remains1.2.0; no release/tag or
claim that all Q2 v2.0 is ready. AST3.9 is syntax evidence, NOT an actual Python3.9
runtime run; actual runtime was Python3.13. Full-dependency skips are the three
explicit opt-in live-Qdrant/real-embedding tests. Stdlib additionally skips
optional HTTP dependencies. See EVIDENCE_INDEX.md for commands and raw logs.

## 5. Security properties and honest limits

1. **Audit:** SDK append-only, tenant hash-chain tamper-evident, not absolute WORM.
   Changed fields/encoded data/interior seq gaps are detected. A privileged
   attacker can rewrite an entire unanchored chain or remove its unanchored tail;
   proving those cases requires a separately trusted external checkpoint/hash.
   Usage immutability is likewise an SDK contract, not physical DB write defense.
2. **Atomicity/idempotence:** successful authoritative write, audit and Outbox
   share one transaction; failure rolls them back. Trusted denial decisions are
   recorded after rollback. SQLite claims/fencing serialize workers and reject
   stale attempts. However external POST+local success marker cannot be one
   atomic transaction: delivery is **at-least-once across crashes**, never a claim
   of exactly-once. Receiver dedup of stable IDs is required after a crash between
   POST acceptance and local commit. Dead letters need host operational handling.
3. **SSRF/Webhooks:** default HTTPS only, all DNS answers validated at registration
   AND delivery; reject metadata/private/reserved/multicast/non-global/mixed DNS,
   IPv6 mapped/translated/site-local/NAT64/6to4/Teredo. Pin actual peer to a valid
   numeric IP while retaining original TLS hostname. No redirects or proxy env.
   Loopback requires BOTH explicit subscription and trusted client/dispatcher test
   flags. Registration is trusted local only; no remote secret or insecure-switch
   API. Secrets reside in access-controlled SQLite, never returned/logged; no
   encryption-at-rest or KMS claim. HMAC helper has300s freshness; stable-ID replay
   dedup remains the receiver's responsibility.
4. **Operations:** no automatic background worker is silently started. Hosts must
   explicitly configure OutboxDispatcher with ImpactRadar(client) and
   WebhookDispatcher(store), start/close it, or use signed tenant-admin drain.
   SQLite network dispatch holds a writer transaction/client lock and can block
   writers; this is not enterprise cluster throughput or an unconditional <60s
   production SLA. The actual local benchmark/wire fixtures meet the required
   <60s gate. M2 clustering/performance work remains out of scope.
5. **Identity refresh:** original trusted claims are persisted. Hosts should
   supply trusted identity_resolver(org_id,user_id,agent_id) for current role/
   identity changes. Legacy bindings without claims are evaluated conservatively
   unless a resolver supplies current trusted identity; no privileges are invented
   from strings. No M4 SSO/SCIM implementation is claimed.
6. **Acceptance boundary:** L4 remains NOT_RUN (no UI work). Independent L5 and
   the owner's specified independent container rerun remain pending. The separate
   architecture-v0.2 reference document was unavailable in this checkout.

## 6. Unchanged Q1 real-world gates

No v1.2.0 tag or Q1 real-world acceptance is assumed. Online Qdrant plus actual
Embedding/semantic chain remain SKIPPED; real proxy+host-session+CSRF+browser L4
NOT_RUN; PDF/OCR offline fixtures only; external Claude Desktop/Cursor partner
10-minute onboarding PENDING_EXTERNAL. The supplied architecture assessment is
not current independent L5 proof. No unsupported uplift or production claim.

## 7. Safety, provenance and next owner action

Only the existing LOCAL BOX checkout, disposable DBs and safe ephemeral loopback
listeners were used. No Mac, existing production service/database, Qdrant
collection, protected port, .env.production or StratAI script was touched. No
paid/model/embedding calls. reports/ remains untracked/uncommitted. No PR, merge
main, force push, global git config, tag, release or deployment.

Normal feature-branch push is owner-authorized. The final executor response
records the pushed tip SHA and equality with git ls-remote; pushing this branch
is not deployment or phase acceptance. Next owner step is independent review/
rerun and explicit acceptance, not more M1 coding or automatic M2 work. Retained
development failures and the superseded partial checkpoint are indexed honestly.
