# M1 joint decision package — PENDING, not a freeze

Owner t58u authorizes SDK-22 engineering ONLY. No person/team is recorded as having signed. All seven decisions remain pending_joint_signoff; approvals, selected options and owner identities are empty. No Team B contact occurred. This is directly reviewable/signable preparation, not authorization for Wave2/schema6/v2 runtime/release.

| ID | Decision | Options/recommendation | Pros / cons | Risk / migration | Proposed accountable role (unassigned person) | Status / dissent / evidence |
|---|---|---|---|---|---|---|
| D1 | Abolish canReadViaRobotBinding authority shortcut | A (recommended): User ∩ Agent with explicit Deny, current generation/clearance/scope; B: Robot binding grants human access | No user privilege expansion; auditable common policy path / Requires adapter to preserve trusted human identity | Misbound human/agent identity must fail closed; Remove shortcut in future adapter only after joint review; SDK already intersects | joint_architecture_sdk_adapter_review; owner_identity=null | pending_joint_signoff; dissent=[] (not reviewed); compatibility doc + C01-C09 + Wave1 evidence |
| D2 | Stable user_id for membership and ACL | A (recommended): Canonical stable tenant+user_id; issuer/subject mapping upstream; B: Email/username as ACL identity | Renames cannot transfer access / Migration requires verified identity mapping | Email recycling/ambiguous mappings must never grant access; Future explicit mapping/backfill with orphan/duplicate checks; no current ACL migration | joint_architecture_sdk_adapter_review; owner_identity=null | pending_joint_signoff; dissent=[] (not reviewed); compatibility doc + C01-C09 + Wave1 evidence |
| D3 | Personal-space tenant ownership | A (recommended): Personal space stays inside explicit canonical tenant with owner_user_id; B: Implicit personal tenant inferred from user/email/OpenBot alias | Preserves tenant hard boundary and current v5 behavior / Cross-tenant personal portability requires separate future design | Never guess tenant from URI or robot binding; No current data moves; future explicit owner/tenant migration needs signed plan | joint_architecture_sdk_adapter_review; owner_identity=null | pending_joint_signoff; dissent=[] (not reviewed); compatibility doc + C01-C09 + Wave1 evidence |
| D4 | version + opaque version_id dual identity | A (recommended): Keep v1 integer version and authoritative bijective coordinate mapping; B: Replace integer version or derive opaque ID heuristically | Lossless compatibility and evidence identity / Requires trusted lookup and ambiguity rejection | Wrong mapping can cite another resource; mapping grants no authority; Future physical version_id only in approved reversible migration; current TS helper is reference mapping only | joint_architecture_sdk_adapter_review; owner_identity=null | pending_joint_signoff; dissent=[] (not reviewed); compatibility doc + C01-C09 + Wave1 evidence |
| D5 | Future standard JSON v2 route evolution | A (recommended): Parallel draft /v2 JSON and stable v1; unified error envelope; B: Rewrite/wrap existing v1 immediately | Backwards-compatible adapter preparation / Two contracts need explicit version governance | Draft fields are not frozen/implemented API promises; Only assets now; no runtime routes until signed M1/Wave2 taskbook | joint_architecture_sdk_adapter_review; owner_identity=null | pending_joint_signoff; dissent=[] (not reviewed); compatibility doc + C01-C09 + Wave1 evidence |
| D6 | Baseline convergence and 1.2.0/v2.0.0 metadata drift | A (recommended): Preserve exact refs; make future release/version decision explicitly; B: Move tag, merge Q3 into main, or silently relabel package now | No unapproved consequential Git/release operation / Known historical SemVer drift remains visible | v2.0.0 is historical Q2+CI marker, not package metadata2.0; No current main/tag/version mutation; future owner release approval must define version/breaking policy | joint_architecture_sdk_adapter_review; owner_identity=null | pending_joint_signoff; dissent=[] (not reviewed); compatibility doc + C01-C09 + Wave1 evidence |
| D7 | Future Schema6 NON-security metadata_snapshot | A (recommended): Consider allowlisted business metadata snapshot after joint schema review; B: No snapshots, or security/ACL historical snapshots | Could support real historical title/business metadata rollback / New model/migration/storage/privacy requirements; absent old history remains absent | Explicitly exclude ACL, rights, principals, generations, secrets, grants; current security always authoritative; Future approved Schema6 only; forward/backward restore/retention design required | joint_architecture_sdk_adapter_review; owner_identity=null | pending_joint_signoff; dissent=[] (not reviewed); compatibility doc + C01-C09 + Wave1 evidence |

## Signature protocol / non-authority

Required roles: owner, architecture, team_a, team_b. Record real owner-provided approvals with independently verified provenance only in a future authorized review operation. Engineering t58u is not any joint signoff. No guessed names, copied signatures, email ACLs, fabricated dissent or automatic approvals.

The current validator ONLY accepts a well-formed pending package, returning WELL_FORMED_PENDING with freeze_authorized=false. It deliberately rejects all partial, self-signed or frozen states; this tool cannot authenticate real future approvals and must never print FROZEN. A future signed workflow needs explicit owner-provided evidence and independent identity verification, not edited JSON booleans.

## D7 security exclusion

Any future metadata_snapshot is non-security business data only. Historical ACL/rights, memberships, generation, principal/profile state, credentials and grants MUST NOT be restored from snapshots. V5 rollback already restores only content+filename, preserves CURRENT metadata/security and creates L2 drafts. No absent historical metadata is invented.

## Evidence / boundary

m1-freeze-manifest.json pins exact protected refs and original archive hashes. validate_m1_manifest.py checks identities/fields/status/ref/source integrity; its success is not signing authority. Current code/DDL stays schema5; independent acceptance and all M1 joint decisions remain pending.

## Wave1.5b source-confirmed candidate slice (t61u) — pending joint signoff

Original06–10 are now archived byte-for-byte. Original00–05 remain untouched and
match the new ZIP. New ZIP10 supersedes the earlier standalone10 for this delivery;
SOURCE10_STANDALONE_T59_ORIGINAL.md preserves the earlier13414-byte original.
WAVE1P5B_SOURCE_PROVENANCE.json records both hashes and archive provenance.
Owner-provided06 reports Wave1 acceptance and rollback-scope disposition;
owner-provided10 reports original Wave1.5 acceptance with ordinary-RRF waiver.
These are SOURCE/OWNER-PROVIDED independent conclusions, not this author's audit.
No performance rerun. Original M1 decisions D1–D7 and signatures remain pending.

### Minimum integration slice — exact source08 §3 assertions, future draft ONLY

Scope: isolated non-production enterprise tenant with explicit human membership,
one authorized Agent, one primary space and a small document. No inferred personal
tenant, production shadow, dual-write or fallback to a weaker source. Exclude purge,
IngestionJob, cross-space refs, service principals and automatic historic migration.
Machine mirror: contracts/minimum-slice-checklist.json. No v2 runtime is implemented.

| ID | Exact source08 §3 assertion | Review state |
|---|---|---|
| A01 | 无权用户+绑定 Agent 拒绝 | pending_joint_signoff |
| A02 | 有权用户+未绑定 Agent 拒绝 | pending_joint_signoff |
| A03 | 缺失/歧义身份或租户拒绝 | pending_joint_signoff |
| A04 | 跨租户拒绝 | pending_joint_signoff |
| A05 | 成员/Profile/Principal 撤权拒绝 | pending_joint_signoff |
| A06 | SDK 不可用时绝不回退至更宽松数据源 | pending_joint_signoff |
| A07 | 证据哈希与版本保真 | pending_joint_signoff |
| A08 | 历史映射缺失显式失败 | pending_joint_signoff |
| A09 | 受控草稿不冒充当前发布版 | pending_joint_signoff |
| A10 | 写重试不重复生成版本 | pending_joint_signoff |

Two source08 strengthening requirements (still draft, not runtime promises):
1. POST /v2/spaces and POST /v2/assets ONLY: optional Idempotency-Key scoped by
   (tenant_id, endpoint, idempotency_key) and payload hash, current authority always
   checked. Same key+payload returns the first result, no duplicate space/version;
   changed payload returns409IDEMPOTENCY_CONFLICT. No unkeyed automatic write retry.
2. Evidence preserves version, bare excerpt hash and full authorized coordinates;
   tampering fails, missing historical mapping fails explicitly, never guesses.
   Five-field write/rollback result: created_version, current_version, seven-state
   lifecycle_state, activated, rollback_scope='content_and_filename_only'.
   activated iff pointers match AND state==='published'; L2 drafts/approved states
   are NOT active. Current ACL/rights/security metadata never resurrect.

Source09 supersedes08's older 'not draft' wording. Source10/t61 corrects the
standalone10 /v2/documents typo to existing /v2/assets, not an alias or new route.
NFC then exactly29 Python whitespace codepoints is confirmed by source08 and t61;
FEFF is preserved. Seven hash and four signed literals are source-pinned offline
algorithm vectors, not current authentication or v2 runtime evidence. Identity
scenarios are contract_scenario_fixture, not implementation/production proof.

Asset-integrity success means verified DRAFT inputs and WELL_FORMED_PENDING only:
freeze_authorized:false, no signatures, no Wave2/M3 authorization. Six pending
cross-team topics in source07/08 (personal tenancy, detach ownership, service
principal, API/minimum slice, production cutover, nonsecurity snapshots) remain
unresolved even where grouped differently by the seven-item engineering package.
