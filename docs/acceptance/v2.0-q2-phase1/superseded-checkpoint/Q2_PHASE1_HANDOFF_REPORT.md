# SUPERSEDED — partial checkpoint 54dca43

Historical record only; current results are in the parent directory. Referenced raw logs describe their then-current versions at commit 54dca43.

# Q2-M1 handoff — INCOMPLETE checkpoint, not phase acceptance

Date: 2026-11-24, Asia/Shanghai (UTC+8).
Repository: `flykingvip-cloud/knowledge-sdk`.
Branch: `feat/q2-phase1-outbox-audit-impact`.
Exact starting SHA: `9c6a64b42893944a24e75ce4317e4dce8fee1751`.

## 1. Authority and scope

Both complete owner-supplied Q2 specifications were read through the parent-
provided accessible task-input files. The M1 execution brief determines this
run's scope; no M2 PostgreSQL/pgvector, M3 governance or EvidencePack service, M4
OIDC/SCIM/connectors, or Q3 code was added. The referenced strategy-architecture
v0.2 file was not found in this checkout; no claim of having reviewed an absent
file is made. This is a meaningful implementation checkpoint because the whole
M1 implementation exceeds this executor run. **Do not call this Q2-M1 done.**

## 2. Delivered modules

- `b3fbb7a`: SQLite v0/v1/v2 -> v3 migration. Exact nine new tables and indexes
  from the protocol, including three reserved empty future-module tables. Real
  prior-layout fixtures verify byte-for-byte existing documents/versions/ACLs/
  anchors/issues and rollback of all v3 DDL + user_version on failure. Future
  schema >3 is refused. Existing schema-version test assertions now expect 3;
  the old 60 golden cases are byte-for-byte unchanged.
- `0e982c0`: frozen typed AuditEvent/AuditChainReport, tenant-sequenced atomic
  append, canonical SHA256 chain, physical-column/encoded-record consistency
  verification, no audit update/delete public API. Automatic operation audit,
  all engine decisions (including retrieval's direct evaluations), denial audit,
  actor/agent/purpose/generation capture, hash/count-only details. Ordinary users
  query only themselves; administrators/auditors are tenant-bound; linked
  document results recheck live policy and redaction requirements.
- `6a59b64`: transactional write Outbox; ingest/revision/archive/restore/ACL/
  rights/revocation/reanchor/drift/orphan event insertion in the SAME business
  transaction. Retry/dead-letter worker, expired processing lease recovery,
  idempotent logical Webhook deliveries, stable delivery ID. Exponential retry
  defaults to 5 attempts. Webhook receiver failure cannot starve other subs.
- `b3fcd9a`: signed audit HTTP query/verify + generated HTTP-client parity.
  Additional evidence corrections and stronger assertions are in the final
  checkpoint commit; consult git log for its SHA.

## 3. Security boundaries and limitations

- Core runtime `dependencies=[]` unchanged. stdlib-only audit/events/webhook.
  HTTPS-only by default; metadata, non-global, private/reserved/multicast and
  loopback destinations are blocked. DNS checks examine ALL addresses, reject
  mixed private/public answers, and repeat at delivery. Actual connection is
  pinned to a validated numeric IP; TLS verifies the ORIGINAL hostname. No proxy
  environment use and NO redirect following. Explicit local test registration
  AND dispatcher flags are both required for loopback HTTP.
- Webhook secret is persisted in the trusted local SQLite subscription record,
  never returned by registration or logged. The file must be host-access-
  controlled. No KMS/encryption-at-rest claim. Registration is local/trusted
  only; no remote subscription API or remotely supplied loopback switch exists.
- Audit is append-only through SDK APIs and hash-chain tamper-evident, not an
  externally anchored WORM service. A privileged DB attacker who rewrites the
  whole chain, or removes only its unanchored tail, cannot intrinsically be
  detected without a separately trusted last hash/count. Middle gaps and changed
  stored fields are tested. Do not overstate cryptographic immutability.
- External POST + local delivered-marker cannot be one atomic transaction.
  Delivery is at-least-once across process crashes; stable IDs enable receiver
  idempotency. A crash after POST before marker can repeat the same logical
  delivery. Concurrent claims are serialized and processing has a 60s lease;
  long handler runs beyond that lease require operational lease renewal/fencing
  work before claiming strong concurrent/crash exactly-once semantics.
- Dispatcher is a reusable module, NOT yet integrated with ImpactRadar. No
  background worker is started automatically. Do not drain real events with
  missing impact handlers and mistake them for completed impact processing.

## 4. Exact remaining implementation (must complete before M1 acceptance)

1. `contracts/impact.py`: exact frozen UsageEvent, ImpactAlert, ImpactReason;
   register tagged models and public exports. Add immutable usage/impact store
   APIs to MetadataStore/SQLiteStore. Persist trusted historical actor/agent/
   purpose information needed to re-evaluate original consumers; do not invent
   privilege-bearing identities from untrusted strings.
2. Real successful consume/attach lineage, including actual MCP search/pack
   binding identity and task_id, real receipt hashes and anchors. Preserve all
   existing snapshots and receipts; do not emit successful usage on denial.
3. ImpactRadar: precise source/version/anchor matching; live PolicyEngine rights/
   ACL tightening checks for each original consumer, all affected UsageEvents
   and ConsumerBindings; identifier-only summaries; idempotence. Reserved
   EvidencePack tables stay service-free but handle existing rows defensively.
4. Tenant/owner/manager protected live-policy/redaction checked impact list/ack;
   admin/internal drain (ensure a tenant admin cannot accidentally drain other
   tenants' events). Install radar+Webhook handlers and deterministic convergence.
   Signed `/v1/impact/alerts`, `/v1/impact/ack`, and client/protocol parity.
5. G6-01..15 + runner metrics, preserving all original 60 cases unchanged;
   benchmark75 and true impact completeness, integrity and <60s gate tests.
6. Extend real loopback L3 probe with actual impact-alert endpoints and actual
   end-to-end usage -> revision/revocation -> impact -> signed Webhook path.
   Rerun ALL acceptance and build/wheel checks, update this report to actual
   final status, then seek independent L5. Do NOT mark M1 accepted yet.

## 5. Evidence and actual test results

Actual baseline: 350 passed / 96 skipped; old golden 60/60.
Actual checkpoint stdlib: 373 passed / 96 skipped (469 run).
Actual full-deps unittest: 466 passed / 3 skipped (469 run).
Actual pytest: 466 passed / 3 skipped + 195 separately counted subtests;
one upstream Starlette/httpx deprecation warning, no ResourceWarning.
Checkpoint old golden: 60/60, ACL 0/20, zero implicit model calls.
Build/AST3.9/extracted-wheel checks passed, as did actual signed audit HTTP and
signed loopback Webhook delivery. See EVIDENCE_INDEX.md for commands and results. All raw failures are retained:
initial command omitted PYTHONPATH; early migration expectations and copied
probe issue-count assertions were corrected rather than hidden. A separate
upstream Starlette/httpx deprecation warning is not a ResourceWarning.
75-case JSON/report is deliberately NOT supplied: G6 has not been implemented.
The current runner's `gate_passed=true` describes only its OLD 60-case gate,
not the new M1 acceptance gate.

## 6. Unchanged Q1 real-world gates

No `v1.2.0` tag or Q1 real-world acceptance is assumed. Live Qdrant + real
Embedding/semantic chain remain SKIPPED, actual reverse-proxy + host-session/
CSRF + browser L4 remains NOT_RUN, PDF/OCR remains offline fixtures, and external
Claude Desktop/Cursor design-partner ten-minute onboarding is PENDING_EXTERNAL.
Independent L5 is still pending. The supplied architecture assessment is not
this run's independent L5 evidence.

## 7. Operational safety and Git

Only the existing box checkout and disposable test DBs/ephemeral safe loopback
listeners were used. No Mac checkout or services, existing production DBs,
Qdrant collection, protected ports, .env.production, or StratAI scripts were
modified. No paid/model/embedding calls. `reports/` stays untracked/uncommitted.
No PR, main merge, force push, tag, release or deployment. The requested normal
feature-branch push is a checkpoint, not permission to deploy or merge.
