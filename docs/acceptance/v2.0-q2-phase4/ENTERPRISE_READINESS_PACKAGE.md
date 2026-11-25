# Enterprise Security Readiness Package — Q2-M4

**Prepared for review, not enterprise approval.** Test keys only; no production
IdP or enterprise security team has approved this branch. Q2 exit remains OPEN.
L4 four hard requirements now PASS in an actual independent GitHub-hosted
headless run on both engines, source1186b06, run45526947873. See l4-browser.md
and l4-ci-run/ for runtime flags/context IDs/browser JSON and continuous logs.
This closes the previously unmeasured L4 assertions, not external Q2 gates. No merge/tag/release/deployment.

## Scope and provenance

Base: `adc3228602207771dc7041763f5832ffb862fa9b`. Owner taskbook is authoritative.
Its M3 architect conclusion (L1 523 pass/0 failure/0 ResourceWarning, full 721
pass, dual 75/75, 19 dual-engine M3 safety contracts, signed HTTP/red-team
acceptance and B05 closure) is **supplied**, not an independent architect audit
performed by this executor. Current M4 tests are implementation self-verification;
The parent now reports independent M4 core acceptance (supplied context, not
a review performed by this executor). Final integrated M4/L5 signoff and external
enterprise production-admission approval are still required. `knowledgeos-strategy-architecture-v0.2.md` remains missing
from the supplied staged inputs/repository; no claim to have read it. The full
M4 taskbook and Q2 core protocol v0.1 were read.

## STRIDE threat/control map

| Threat | Trust boundary and control | Evidence |
|---|---|---|
| Spoofing | JWT algorithm/key separation, signature, issuer/audience/time/identity claims; one-use jti; no header override; production rejects demo | OIDCSecurity, GatewayConfiguration; l3-enterprise-http.log |
| Tampering | Pack SQL/payload/digest parity; immutable contracts; source SHA; signed webhook timestamp/event/body; transactional audit chain | G7-15, connector unit contracts, l3 HTTP, legacy audit adversarial suite |
| Repudiation | Append-only tenant audit chain; successful SCIM mutation and authority/outbox same transaction; DENY audited | enterprise rollback/generation tests; legacy G6 tamper/gap cases |
| Information disclosure | Per-operation principal generation, policy/rights/redaction; tenant RLS; no-store; no draft/cross-tenant leakage | both golden engines; directory RLS tests; l3 HTTP; scoped L4 DOM evidence |
| Denial of service | JWT/JWKS/body bounds; TTL/cooldown; bounded dedupe stream; controlled file size; no implicit cloud/model calls | JWKS cooldown tests, bounded parser and capacity behavior; 100-case model spies |
| Elevation of privilege | Owner/admin do not bypass inactive/stale principal; SCIM/connector admin + tenant/KB checks; author/reviewer/publisher separation | G7/G8 and 46 focused tests; real high-privilege stale HMAC/JWT/cookie rejection |

## Ten security invariants and reproducible evidence

1. **Zero core dependencies / Python 3.9 syntax**: `dependencies=[]`, L1 `-S -W
   error::ResourceWarning`; 99 source/benchmark Python ASTs; wheel RECORD +
   extracted-wheel `-S` smoke. See l1/l2 logs and wheel-record.json.
2. **Unambiguous signed identity**: default RS256/ES256, explicit separate HS256
   keys, no none/confusion/untrusted key URLs. Actual RSA and ECDSA verified with
   optional cryptography; both-engine HTTP RSA and real HTTP JWKS fetch.
3. **Strict claims and replay**: iss/aud/exp/nbf/sub/org/roles/departments/
   clearance/generation; duplicate JSON/type/temporal attacks; atomic jti
   single winner (32 attempts), shared PG replay; l3 replay rejection.
4. **No JWKS SSRF/cache stampede**: validate all resolved IPs, pin connection,
   forbid metadata/private/non-TLS/redirects; kid rotation TTL/cooldown and
   failed-refresh cooldown tested. Loopback permitted only by explicit test flag.
5. **No production identity downgrade or header elevation**: startup rejects
   dev_insecure/demo in oidc/dual; no client org/generation/actor override. Every
   route and error no-store. Demo signing 404 via real nginx HTTP preflight;
   actual independent headless browser run measured zero console/page/request
   errors continuously before initial navigation through logout/context close;
   both signer paths404 and independent content JSON isolation passed.
6. **Authoritative immediate session revocation**: every actor-taking local
   operation, MCP entry, policy engine and HTTP reads current principal. Inactive
   or stale actor denied even with valid signed admin privileges. HMAC, JWT,
   session cookie and local/MCP adversarial tests; DENY audited.
7. **Atomic SCIM lifecycle**: principal/group/member + generation + AuditEvent +
   principal.policy_bumped Outbox commit together; rollback injection and group
   invalid member rollback; four independent PG connections yield 40 distinct
   generation increments with no lost update.
8. **Tenant-safe dual-engine schema v4**: v0/v1/v2/v3 SQLite migration/reopen and
   real PG v3 migration; new identity/group/cursor tables FORCE RLS; non-superuser
   without BYPASSRLS cannot read unscoped or foreign-tenant rows. SQL values bound.
9. **Atomic, immutable source synchronization**: exactly two reference adapters;
   directory-FD/O_NOFOLLOW traversal; no special files/symlinks/path escape;
   webhook signature/time/durable cursor replay controls; failed batch leaves
   all docs/events/cursor unchanged. Source/version/ACL idempotence tested.
10. **Revocation affects downstream evidence, never rewrites it**: tombstone
    emits one authoritative doc.revoked/doc.archived event, Outbox→ImpactRadar
    alerts→pack impacted. JSON/ZIP/read all recheck live rights. Ordered dissent
    dedupe, SQL/payload digest mismatch fail closed. Legacy 75 assertions/files
    preserved byte-for-byte; independent G7 15 + G8 10 reach total 100.

## Measured performance / concurrency, not an SLA

`performance.json` is the measured local result of `performance_probe.py`: 80
short documents, 40 authorized top-5 keyword queries per engine. Deterministic
local fixtures, no external model/embedding/network service. See exact p50/p95/
maximum and sample counts in that file. It also measures four independent
connections' 40 unique policy generations and four-worker 80-event Outbox drain
with **0 duplicate claims**, using SQLite BEGIN IMMEDIATE and PostgreSQL FOR
UPDATE SKIP LOCKED. These are small local microbenchmarks, not enterprise-scale
load, vector-recall claims, a p99/SLA, failover performance or healthy-delivery
exactly-once claims. Outbox has at-least-once retry semantics; consumers dedupe.

## Migration / backup / rollback

`dr-v4.json` records real PostgreSQL 17 pg_dump/pg_restore into a second empty
owned disposable sdk_dr_* database. All table row counts and SHA-256
fingerprints match, including identity_principals, scim_groups,
scim_group_members, connector_sync_state, audit, history, lineage, RLS and vector
data. Injected migration interruption rolls back DDL/version changes and repeated
apply is idempotent. Restored principal generation/active flag, group membership
and cursor are asserted. This is **non-destructive transaction rollback**, not a
promise that dropping schema-v4 authority tables to downgrade production is safe.
Table-owner backup temporarily relaxes FORCE inside owned test DBs, then restores
it; it is not the application RLS path or an arbitrary production backup service.

## Open limits and external gates

- L4 **PASS for four required isolated-fixture hard requirements**. GitHub-hosted
  Ubuntu24.04, Chromium141.0.7390.37 runtime --headless proof; independent fresh
  BrowserContexts; browser-owned GET/POST404 signer paths and eight independent
  content JSON bodies per engine; zero console/page/requestfailed from before
  initial navigation through logout/networkidle/context close. Run45526947873,
  tested source1186b06. Expected direct HTTP404/401 are separately recorded, not
  filtered page failures. Two failed prior CI harness runs are retained. This is
  not enterprise production topology or external review. See l4-browser.md.
- All owned box fixtures remain stopped. CI processes/connections/test schemas
  cleaned, service container/network removed; passing job metadata/logs and
  summary.json prove cleanup. No box browser was launched for this work.
- Generic tests.yml has a pre-existing Python3.9/ubuntu-latest26.04 setup failure;
  the independent L4 workflow uses ubuntu24.04/Python3.12 and passed46 enterprise
  regression tests. It does not turn the separate legacy workflow green.
- At least one real enterprise security/architecture team's production-admission
  review remains **PENDING_EXTERNAL**; this package is only an input to review.
- Real enterprise IdP registration, live JWKS rotation/availability/SSO operational
  integration and external SCIM interoperability are not certified. JWT gateway
  implemented; complete redirect authorization-code RP flow is not claimed.
- Opaque browser sessions are node-local; bearer replay can use shared PG. Use
  sticky routing/host gateway for multi-node UI sessions. Shared SQLite replay
  must be explicitly configured for local multiworker deployments.
- Managed principal invalidation is per operation/request, not Q3 mid-task push
  revocation. Unmanaged Q1 static actors remain compatible unless
  `require_principal=True`; deploy managed mode deliberately.
- RLS does not constrain malicious DB owners/superusers. Backup/failover topology,
  real enterprise load, TLS termination, CSP integration and host CSRF mapping
  need deployment-specific security assessment.
- Source connector cursor is a durable bounded dedupe stream, not a message bus;
  coordinate stream rollover before its fail-closed capacity. Exactly two
  references, no SaaS connector catalog or S3 SDK integration is claimed.
- Q1 online Qdrant + real embedding/semantic retrieval, actual host login/CSRF and
  production reverse-proxy/browser topology, real PDF/OCR, and external Claude
  Desktop/Cursor ten-minute onboarding remain unverified external boundaries.
- Core version metadata intentionally stays 1.2.0: no v2 tag/release was created.
  No Q3 Agent Profile/Task Context/mid-task runtime/vertical pack/reranker/graph.
