# Q2-M3 handoff — L2 governance, issue closure and immutable EvidencePack

2026-11-25 · Asia/Shanghai (UTC+8)

## 1. Baseline, authority and delivery

- Exact start: `04b8c934f68b1cbb504385d9500d8c61d458e5d3`.
- Feature branch: `feat/q2-phase3-l2-governance-packs`.
- Final tested implementation source: `a9bdd9aa298aa520f25cbd2e063f56ef485aa006` (this evidence-only handoff is
  committed after it). Final delivery HEAD/normal-push remote equality is reported
  separately after the evidence commit, not invented as a self-referential SHA.
- Authority: staged full Q2-M3 taskbook plus Q2 core protocol v0.1. Local BOX work
  follows the established explicit owner override; no CloudAgent/PR was used.
- The taskbook states an architect independently accepted M2. That is a **supplied
  result**, not this executor's independent review. The current runs include M2
  regression assertions, but remain executor-generated evidence.
- `knowledgeos-strategy-architecture-v0.2.md` was still absent from the staged
  inputs and repository docs. It is not claimed read; the detailed M3 taskbook and
  supplied core protocol supplied the implementable requirements.

## 2. Task 0 — contracts and shared storage

Frozen `ReviewDecision`, `ReleaseManifest`, `IssueResolution`, `PackItem`,
`EvidencePack`, `PackVerificationReport`, `ExportResult`; strict stance/status and
source identities; recursively frozen decision JSON; transport round trips.
The existing reserved review/issue/pack tables are reused in Schema v3. Version
state/author/reviewer/publisher/source-issue metadata are additive version JSON,
not duplicate tables or a parallel schema. Pre-M3 L2 payloads infer state from
their current document. Unknown historical authors are **not** guessed from document
ownership: those candidates fail closed on approval/publication until a fresh
attributable ingestion (including identical content) creates a new draft. Publication
also requires an actual append-only approval record, not just an approved state flag. Both engines implement the expanded MetadataStore protocol.

PG methods use tenant decorators/scopes, bound `%s` SQL, existing ENABLE/FORCE RLS
and `('pack',pack_id,org_id)` resource-directory registration; pack reads explicitly
require org_id. SQLite serializes writes; PG locks the document row before state
changes. Independent-connection races and raw NOSUPERUSER/NOBYPASSRLS cross-tenant
reads are tested. Review UPDATE/DELETE is physically rejected by engine triggers.

## 3. Task 1 — L2 dual track and dissent

L1 publication behavior is unchanged. L2 ingestion cannot set published even as
admin. Draft/in_review/approved/rejected candidate state is separate from an old
live published pointer and its FTS/pgvector rows. Ordinary get/retrieve/reference/
anchor/search/MCP/pack surfaces never deliver draft text, even for admins. New
uploads return body-free draft receipts; no draft content UI/API was introduced.

Submission records the submitter; approval/rejection prohibit both author and
submitter, including admin. Publication requires an approved latest candidate and
a third distinct actor. Expected-version/state locks reject stale/racing actions.
First-publication document lifecycle mirrors candidate state; once a live release
exists, candidate transitions never change the live document state. A publication
racing ingestion cannot restore a stale live pointer. Publication, FTS/native PG
index refresh, append-only decision/audit and `doc.published` outbox are atomic.
Dissent is append-only, survives rejection/resubmission and enters manifests/packs.

Two older **non-golden** assertions were updated because M3 intentionally replaces
them: admin direct-ingest publication is now rejected in favor of the three-actor
workflow; MCP persisted pack_id is now supported and missing IDs return no items.
No golden cases/assertions/scenarios were rewritten.

## 4. Task 2 — manual EvidenceIssue resolution

All four actions are implemented: linked L2 revision draft (or existing-draft link),
metadata-only L1 revision followup, retrieval_tuning followup, permanent keep_dissent,
and dismissed false-positive closure. Other actions resolve the issue. Immutable
resolution metadata stays inside the existing issue record. Review authority,
source-version conflicts and terminal re-entry are enforced. State, draft/dissent,
audit and `issue.resolved` outbox commit or roll back together. No model is called,
no automatic tuning/weights change occurs, and no revision bypasses L2 review.

## 5. Task 3 — sealed snapshots, impact and fail-closed delivery

All published sources undergo current eight-gate policy, source EXPORT rights plus
the requested Actor/Agent purpose, redaction and anchor health checks. Supporting/refuting/negative/
conflict/contextual positions, conditions and all dissent remain parallel. Canonical
SHA256 covers exactly org_id/title/topic/items/dissent_notes/effective_decision;
status is an external mutable flag. Usage receipts retain per-item lineage.

Every typed get/list/verify/export rechecks the whole pack. Missing hooks, current
ACL/rights denial, revoked/archive state, changed redaction or bad digest cannot
release a partial snapshot. Policies are compared again after all hooks, including
a reentrant hook revoking an earlier item. Export performs another whole-pack
check immediately before output; denied JSON/ZIP writes create no file. Metadata
hash tampering yields digest_valid=False on verify and rejects get/export.

Real ImpactRadar consumes doc.published/revised/revoked/archived, ACL/rights and
anchor drift/orphan events, creates evidence_pack alerts and changes only status
into impacted. Items/excerpts/hash remain sealed. ACL/rights changes conservatively
request re-review (access_revoked marker); it is not itself an authorization verdict.
No worker/daemon is started implicitly; the probes explicitly drain the outbox.

Stdlib deterministic RO-Crate1.2 ZIP has metadata descriptor/conformsTo/about, root
Dataset name/description/license/datePublished/hasPart, source-linked evidence
entities, full machine-readable pack and stance-separated REVIEW_SUMMARY.md. The
license notice grants no additional rights. Tests check the normative graph fields;
no external validator certification or publisher digital signature is claimed.

## 6. Task 4 — adapters and reproducible evidence

Local and HttpKnowledgeClient plus KnowledgeClient protocol signatures match. Signed
POST routes cover submit/approve/reject/publish/dissent/manifest, issue resolution
and pack create/get/list/verify/export. New APIs disallow dev-insecure authentication
and use existing HMAC/ReplayStore. Pack endpoints default EXPORT. HTTP output_path
is caller-local only; server file writes from request parameters are rejected.

Trusted local CLI `knowledge-sdk-governance` exposes the same operations on SQLite
or PG with environment-bound Actor. MCP remains four tools: persisted pack_id is
mutually exclusive with transient source_uris/query, and has fail-closed policy/
redaction/seal checks. Actual Q1 compatibility was source_uris (the taskbook also
mentioned query); both transient selectors are now available and G5 stays 10/10.

Final frozen-source runs:

| Layer | Observed result |
|---|---|
| L1 stdlib `-S -W error::ResourceWarning` | 523 passed, 201 optional/live skips; zero failures/warnings |
| L2 full unittest + real PG | 721 passed, 3 integration skips |
| L2 pytest + real PG | 721 passed, 3 skipped, 201 additional subtests; one optional Starlette/httpx deprecation warning, no ResourceWarning |
| Dedicated M3 contracts | 19 SQLite + 19 actual PG; shared SQLite parity adds 19 executions |
| Immutable old golden75 | SQLite 75/75; actual PG+pgvector 75/75; v1/v2/g6 bytes unchanged |
| AST3.9 / build / wheel RECORD / extracted wheel | PASS (SQLite stdlib and actual PG M3 flows); runtime3.9 NOT_RUN |
| L3 actual signed HTTP | Both engines PASS, three identities, four issue actions, RO-Crate and revoke→403 + pack alerts |
| L4 / L5 | NOT_RUN / PENDING |

Final run totals and artifact hashes are in `acceptance-summary.json` and
`evidence-sha256.json`; required raw logs and benchmark results are linked in
`EVIDENCE_INDEX.md`. The implementation is not represented as independently accepted.

## 7. Safety, limitations and remaining gates

- Core `dependencies=[]` remains empty. Pack JSON/ZIP/hash use only stdlib. Python
  3.9 **syntax** is checked for all source/benchmark modules; no Python3.9 runtime
  is installed/run (test interpreter is Python3.13.5).
- Real signed loopback HTTP uses author/reviewer/publisher as three different
  trusted identities on SQLite and real PG+pgvector: draft → submit → approve →
  publish → four issue actions → pack/RO-Crate → newer publish/impact → revoke →
  JSON/get/ZIP **403** and evidence_pack access-revoked alert. It does not constitute
  production SSO/browser proof. OIDC/SCIM remain M4.
- Native PG vector operations share the store transaction. External remote indexes
  cannot join that database transaction; existing dirty-marker/reindex recovery is
  still required. No real embedding/model API or Qdrant was used; vector assertions
  use explicit local deterministic HashEmbedder, not semantic-quality validation.
- No UI change: L4 **NOT_RUN**. Independent M3 L5 **PENDING**. This executor does not
  claim M4 unlocked. No M4 identity/connectors/G7–G8 or Q3 features were implemented.
- Q1 gates remain open: live Qdrant+real embeddings/semantic chain; real reverse
  proxy/root_path plus host session/CSRF/browser; real user PDF/OCR validation;
  external design partner Claude/Cursor ten-minute integration. Offline fixtures
  and local HTTP do not close those gates.
- No Mac/other checkout, existing service/database, prohibited port, StratAI script,
  .env.production or Qdrant was touched. A fresh BOX-only test cluster was used;
  final stopped-resource state is in `cleanup.log`. The old M2 cluster was not
  restarted. Offline test directories remain for reproduction, not running services.
- No main merge, PR, tag, release, deploy, force push or global git config. Normal
  push is limited to the exact feature branch authorized in the owner taskbook.
  Existing `reports/` remains untracked/uncommitted.

Development failures are explicitly retained under `development/`: initial missing
new event enums / schema-fixture trigger compatibility / future-import guard;
superseded pre-M3 admin-bypass expectation; SQL_ASCII test-environment mismatch
(replaced with separate UTF8 initdb); and a missed PG legacy-getter adaptation
(corrected and then rerun). Final hardening also denies unattributable historical
authors rather than guessing identity and keeps default internal MCP agents bound
to their actual gateway purpose while enforcing EXPORT_PACK source rights. None is presented as a passing final run.

One stdlib invocation inherited the optional live-PG DSN from a prior shell run;
`-S` correctly cannot load psycopg, so that configuration produced PG setup errors.
It is retained in `development/stdlib-with-inherited-pg-dsn.log`. The final core
run explicitly unsets both PG DSN variables before the same strict `python3 -S`
command; real PG is tested separately in the full environment.
