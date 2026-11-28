# SCHEMA_V7_SANDBOX_DESIGN_AND_ROLLBACK_SPEC

Status: **non-executable sandbox design and rollback prose only**. This file is not live migration code, is not a Schema v7 implementation, and is not an authorization to start Schema v7. `schema_v7_ddl_authorized` remains `false`. `schema_v8_v9_ddl_authorized` remains `false`. `formal_t01_t27` remains `NOT_RUN_NOT_ACCEPTED`. Space Gate 6 remains `NOT_MET`. This document contains zero DDL statements and does not change any file under `src/knowledge_sdk/storage/` or any Schema v6 migration artifact.

Order context: Owner order `t106u` (2026-11-28, Asia/Shanghai) unlocked `wave_v21_5_unlocked=true` and authorized Team A W5A-3 to write this isolated-branch design / rollback specification only. Production shadow migration, cutover, and any irreversible Schema v7 change remain unauthorized.

## 1. Purpose and hard limits

The purpose of this specification is to record, in prose, how a later authorized Schema v7 sandbox dry-run and a reversible rollback would have to behave if a subsequent official implementation authorization is issued. Nothing in this file may be executed as a migration. It does not mount `/v3/*` in production HTTP. `EXPERIMENTAL_V3_ENABLED` and `OPENBOT_KNOWLEDGE_SDK_V2_ENABLED` stay default false.

Hard limits that remain closed:

- Schema v6 remains the only authorized on-disk schema. The frozen baseline `9940818b962ccb186c0dfb0158de6bd9bd49057b` and the current `schema_version==6` lock are unchanged.
- Live migration modules, store implementations, and schema artifacts stay byte-identical to that baseline in this wave.
- Engineering has zero production-database contact. Real production export, if any, is lead / DBA only under Space Gate 4 = `MET_FOR_CONTRACT_AND_SANDBOX`.
- A sandbox dry-run may use only disposable, newly created owned resources (for example a new in-memory engine or a newly generated throwaway database that is not a production target and is not a v6-to-v7 upgrade of an existing store).
- Formal T-01–T-27 is not run and is not accepted by any result described here.

## 2. Design invariants now informed by the official SPACE-C01–C10 ruling

t106u formally adopts `空间-00F` and locks SPACE-C03 phase 1 as `1 organization_team = 1 Team Space`. A future authorized design must honor those in-effect clauses (see `FINAL_SPACE_AND_FAVORITES_ALIGNMENT.md`). In prose, the sandbox target invariants are:

- Flat three-layer placement: Tenant → Space → KnowledgeBase. Phase 1 does not introduce parent-space nesting, tree inheritance, or cross-space moves. Cross-tenant moves stay forbidden.
- Enterprise-employee personal spaces belong to the enterprise tenant and keep an unbypassable personal-private access invariant. Independent personal users belong to an independent personal tenant. Historical `tenantId=null` rows are never auto-migrated.
- Organization teams and collaboration groups stay distinct types. Department identifiers are not mapped as business teams. Phase 1 mapping cardinality is one organization team to one Team Space.
- One Space may hold many KnowledgeBases. Space and KnowledgeBase must share the same organization identifier. Detach removes a mount or reference only; it must not implicitly archive a shared asset.
- Eight independent permission actions, multi-layer intersection, explicit Deny first, transactional outbox, policy generation, and read-time authoritative verification. Revocation remains fail-closed.
- Favorites stay on a single write master (OpenBot) with at least `kb` and `asset` target types; the SDK hydrates batch real-time ACL. Dual-write is forbidden.
- Personal spaces default to private. Controlled read-only shares, if any, require real-time authorization. Leaver handling follows the official Gate 5 rules recorded below. Private body text is never auto-inherited.
- Agent consumption is bounded by Space ceiling, fine-grained resource scope, and the current user's real-time permission. Membership identity uses a stable user identifier, not an email as a permanent primary key.
- Existing `/v2/spaces` semantics at `knowledge-sdk@9940818b962ccb186c0dfb0158de6bd9bd49057b` stay unchanged. A new first-class Space surface, if later authorized, must use a distinct resource path or an explicit version negotiation. Silent semantic change of the old interface is forbidden.
- Knowledge supply remains typed: uploaded document, agent deliverable, enterprise materialized reference, and dynamic data capability, with independent lifecycle and permission semantics. Dynamic capabilities must not expose credentials or query powers that a ordinary document agent should not receive.

These invariants are design constraints for a future authorized sandbox. They are not a license to emit schema artifacts or to alter Schema v6.

## 3. Official Gate 4 / Gate 5 conditions that bound any later dry-run

Space Gate 4 is `MET_FOR_CONTRACT_AND_SANDBOX` only. The official contract v1.0 is `PRE03_ANONYMIZATION_SPEC_FOR_GATE4.md` with SHA-256 `66294adfb60d54d42c4307d5b19c8fda298828d7bd9b0f520c0a2958f1fb845e`. AUTH-V21-04 named custodian is Daniel \<daniel.hhd@gmail.com\>. A sandbox checker may validate only `SYNTHETIC_EXAMPLE` inputs that already obey the contract's twelve zero-PII rules. Product A remains aggregate-only. Product B remains the unsigned-until-separately-approved `candidate-pre03-v1` shape with `syn_` tokens, `sanitized=true`, and null proposed target identifiers until a later official allocation ruling is on file. Tokenization keys, salts, and mapping tables must not appear in any artifact.

Space Gate 5 is `MET` with the five Owner-stated PRE-04 / EXT-03 rules: resignation real-time freeze within 60 seconds; 90-day read-only isolation retention; work-product dual-approval handover; private body text must not auto-inherit; controlled shares are invalidated immediately. A future sandbox that models leaver or share paths must assert these rules. Security state is monotonic: historical access-control lists, user status, policy generations, revocations, source assertions, or private-content versions must never be restored in a way that re-grants access.

## 4. Proposed sandbox dry-run staging (not authorized to run as a v6-to-v7 upgrade)

The following is a future staging plan only. It is not authorized now.

1. Keep Schema v6 and `/v2/spaces` as the only live path. Do not rewrite history, drop old interfaces, or point a dry-run at a production store.
2. Accept only already-sanitized, file-like inputs that pass the official twelve-rule PRE-03 checker. Inputs are `syn_` tokens and aggregate counts. The checker does not discover credentials, does not read business bodies, and does not contact a database.
3. Report inventory and collision findings only: tenant counts, null-tenant residual counts, alias / name collisions, unclassifiable remainder, and mapping conflicts. A dry-run must not assign target Spaces or KnowledgeBases, must not invent counts, and must not auto-merge or auto-repair collisions.
4. Quarantine exceptions for human review: null-tenant rows, name or alias collisions, unknown team authority, orphan references, incomplete projections, generation mismatch, or failed checksums. No automatic null-to-enterprise assignment and no automatic owner inference.
5. Any later authorized additive expansion, if separately written, would have to be opt-in, journaled, idempotent, and reversible, while the original Schema v6 read path and every old interface remain in place. This paragraph is not that authorization.

A dry-run exit is a report, not a migration decision and not formal T-01–T-27 acceptance.

## 5. Rollback design (prose only)

- Current-wave rollback is limited to disabling or removing isolated-branch sandbox tooling and any disposable owned resources created for that tooling. The accepted Schema v6 runtime is unchanged, so there is no production data rollback in Wave-V21-5.
- A future authorized expansion, if one is ever issued, would have to retain original immutable data and the old read path, place rollback behind a separately controlled feature boundary, and reconcile additive objects without dropping originals. Reversibility would have to be proven with an approved backup / restore process and a per-tenant mapping journal. Success of this prose specification or of any later prototype does not prove that reversibility.
- Rollback must fail closed when it cannot preserve the current security state. It must not restore prior permissions, prior principal or profile generations, prior revocations, or private-content inheritance from historical versions.
- Lock timeout, concurrent revocation, outbox failure, or partial writer failure would require an atomic abort of the in-flight unit of work, with no stale-allow fallback. Owner loss or provider outage would require deny, evidence preservation, and escalation. Legal-hold or retention exceptions follow the official Gate 5 rules and are not invented here.
- Formal rollback review, production workload tests, HTTP / Python / MCP compatibility, and recovery drill remain unmet for Schema v7. Sandbox or prototype success does not sign those gates.

## 6. Residual locks

- Space Gate 6 is not MET. This specification is not Frozen alignment and is not a Gate 6 sign-off.
- `schema_v7_ddl_authorized=false`. No Schema v7 implementation work, including migration coding, is authorized by this file.
- Official VB-1 remains `111/13/0`. Formal T-01–T-27 remains `NOT_RUN_NOT_ACCEPTED`.
- This wave does not open a pull request and does not merge to `main`. Frozen tips `e97a8cca68df7b464ce1f017729022cba861c543`, `918293cada0610d6a6d7ef6b8e5f86990b411ce9`, and `main@b953c9922cc1096e0e88455dab6746c01a9d27f9` are not modified by the act of adding this document on a new isolated branch whose first parent is the Wave-V21-4 tip.
