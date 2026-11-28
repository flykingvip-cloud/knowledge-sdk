Status: READY_FOR_TEAM_B_COUNTERSIGN_GATE6

# FINAL_SPACE_AND_FAVORITES_ALIGNMENT

This file is a Wave-V21-5 Team A compilation prepared for Team B countersignature toward Space Gate 6. It is **not** Frozen, and it does **not** claim Space Gate 6 MET. The status line at the top of this file is exactly `Status: READY_FOR_TEAM_B_COUNTERSIGN_GATE6`. The Team B countersign area and the final-acceptance freeze signature slots below are intentionally blank. This document contains zero DDL SQL and does not authorize Schema v7, formal T-01–T-27, production cutover, or any change to the official VB-1 lock.

Order context: Owner order `t106u` (2026-11-28, Asia/Shanghai) recorded that Wave-V21-4 is jointly closed, adopted `空间-00F` as the formal SPACE-C01–C10 ruling, locked SPACE-C03 phase 1 as `1 organization_team = 1 Team Space`, set Space Gate 5 (PRE-04 / EXT-03) = `MET`, set Space Gate 4 (PRE-03 / EXT-02 / AUTH-V21-04) = `MET_FOR_CONTRACT_AND_SANDBOX`, and set `wave_v21_5_unlocked=true`. Still false and unchanged: `schema_v7_ddl_authorized`, `schema_v8_v9_ddl_authorized`, `final_alignment_frozen`, `prod_shadow_migration_cutover_authorized`. `formal_t01_t27` remains `NOT_RUN_NOT_ACCEPTED`. Space Gate 6 remains `NOT_MET`. Official VB-1 lock remains `111/13/0`. `EXPERIMENTAL_V3_ENABLED` and `OPENBOT_KNOWLEDGE_SDK_V2_ENABLED` stay default false. `/v3/*` stays unmounted in production HTTP.

Hashes below are copied in full from already-locked in-repo Wave-V21 documents, from independently observed `git ls-remote` tips, or from Owner-stated values in t103u / t105u / t106u. Truncated official prefixes are left truncated. No suffix is invented. The Wave-V21-4 draft `FINAL_SPACE_AND_FAVORITES_ALIGNMENT_DRAFT.md` is not edited and is not relabeled Frozen.

The local file `/workspace/kb-sdk-align/WAVE_V21_5_LAUNCH_ORDER_2026-11-28.md` is the Team B counterpart of the same launch family (W5B tasks). If that copy conflicts with t106u, t106u is controlling. Older Team B notes that still say AUTH-V21-04 is unissued or that Gate 4 / Gate 5 are `NOT_MET` are superseded by t106u.

## 1. Owner-stated Wave-V21-4 closure and Wave-V21-5 unlock (OpenBot not independently re-verified here)

Recorded as stated in t105u and t106u. This Team A compilation does not independently re-verify or modify OpenBot.

| Item | Recorded value |
| --- | --- |
| Wave-V21-4 Team A verdict | `TEAM_A_WAVE_V21_4_CLEAN_ACCEPT` at `feat/v21-wave4-pre-v7-prep@e97a8cca68df7b464ce1f017729022cba861c543` |
| Wave-V21-4 joint verdict | `WAVE_V21_4_JOINT_CLEAN_ACCEPT` (Owner-stated; Team B `TEAM_B_WAVE_V21_4_CLEAN_ACCEPT` is recorded as stated and is not independently re-verified here) |
| `wave_v21_5_unlocked` | `true` |
| SPACE-C01–C10 | Formally in effect; `空间-00F` adopted; SPACE-C03 phase 1 locked as `1 organization_team = 1 Team Space` |
| Space Gate 4 | `MET_FOR_CONTRACT_AND_SANDBOX` (not unrestricted production `MET`) |
| Space Gate 5 | `MET` |
| Space Gate 6 | `NOT_MET` (this file is the Team A compilation; it is not a joint freeze) |
| Prior Wave-V21-3 / Gate 3 (unchanged) | `WAVE_V21_3_JOINT_CLEAN_ACCEPT`; Space Gate 3 = `MET` at `openbot-vp` `main@8b83e4eba9b4eec5532046481ca98259c3bcf1d6` (Owner-stated in t103u) |

## 2. Already-locked cryptographic anchors

Copied in full from `docs/acceptance/v21-wave4/FINAL_SPACE_AND_FAVORITES_ALIGNMENT_DRAFT.md` and from independently observed tips at the start of Wave-V21-5. No hash is truncated or invented.

### 2.1 Frozen v21-reuse-v1 pack

| Anchor | Full locked value |
| --- | --- |
| Pack status | `FROZEN_V21_REUSE_V1` |
| Deterministic manifest SHA-256 | `212537fd41bd4cc4d9d7343cacafaea225ee98b6586df716bf036a397cb2a382` |
| Schema version locked by `scripts/verify_v21_boundaries.py` | `6` |
| `pyproject.toml` `dependencies` | `[]` |
| `formal_acceptance` | `false` |
| Contract file count (as recorded in Wave-V21-3 handoff) | 18 |
| Historical frozen baseline SHA | `9940818b962ccb186c0dfb0158de6bd9bd49057b` |
| Boundary baseline | 709 files / 0 drift against that baseline |
| M1 frozen verify | 28 assets / 0 drift |

### 2.2 Official Sync-W2-1 golden fixture and dual-stack receipt hashes

Source: `docs/acceptance/v21-wave3/W3_INTEROP_PARITY_RECORD.md`, also registered in the Wave-V21-4 draft. Canonicalization for `receipt_hash` remains `sandbox.v21_reuse_v1.revocation.canonical_json_bytes`. This compilation does not introduce a second hash scheme.

| Anchor | Full locked value |
| --- | --- |
| Official Sync-W2-1 status | `CRYPTOGRAPHICALLY_ALIGNED_BYTE_EXACT` |
| Golden fixture path | `sandbox/v21_reuse_v1/fixtures/w2_interop_golden.json` |
| Golden fixture size | 33863 bytes |
| Golden fixture SHA-256 | `f8033a902af06b005fa591ab872a74f9569a3783fd3e7cef90c6dc94cf9d0fef` |
| Golden fixture git blob | `5afaff1616ddd77dca604dc498fc691ae4a4f37b` |
| Golden fixture landing commit (still byte-identical) | `37c982546f49bb8312670ad01be995d91f345043` |
| Dual-stack `receipt_hash` for `G4-POS-FOUR-CHANNEL-SUCCESS` | `f4055894fdebb0fc55ae563aaed03ab6f4162b53c4eeab31ad479f6c6707b476` |
| Dual-stack `receipt_hash` for `G4-POS-CHANNEL-TIMEOUT-NOT-PURGED` | `6e8c7f178ec452b590e0d0f06defa0a2c21c0fac5c6a672a356a02b31470f0d0` |
| Team B core originals from the Wave-V21-2 joint closure order | 12/12 exact match against `SHA256SUMS.txt` prefix `1a0f258b...` (the official order published only this prefix; the remainder is not invented here) |

### 2.3 Frozen and observed git tips

| Ref | Full SHA | Notes |
| --- | --- | --- |
| Wave-V21-0 isolated tip `feat/v21-wave0-contracts-and-adapters` | `9d25ea96b75b5ab528a2d2670b5419d9a217e39e` | unmodified by later waves |
| Wave-V21-1 isolated tip `feat/v21-wave1-runtime-adapters` | `207953963872a4a7e65731def077c469b685f4e2` | unmodified by later waves |
| Wave-V21-2 isolated tip `feat/v21-wave2-e2e-interop` | `4d546272cd51605edeed5b80b4e3adc278608e94` | unmodified parent of Wave-V21-3 |
| Wave-V21-3 Team A isolated tip `feat/v21-wave3-interop-hardening` | `918293cada0610d6a6d7ef6b8e5f86990b411ce9` | frozen; 0 PRs; not modified by Wave-V21-4 or Wave-V21-5 |
| Wave-V21-4 Team A isolated tip `feat/v21-wave4-pre-v7-prep` | `e97a8cca68df7b464ce1f017729022cba861c543` | frozen; 0 PRs; Wave-V21-5 starts from this exact parent and does not change this tip |
| knowledge-sdk `main` (independently observed at Wave-V21-5 start) | `b953c9922cc1096e0e88455dab6746c01a9d27f9` | must not be moved by this wave |
| `openbot-vp` `main` (Owner-stated Space Gate 3 MET tip) | `8b83e4eba9b4eec5532046481ca98259c3bcf1d6` | recorded as stated in t103u; not independently re-verified here |

### 2.4 Additional already-locked document hashes cited in prior Team A Wave-V21 docs

These are copied in full from documents already landed on the frozen Wave-V21-3 tip. They are citations, not new sign-offs.

| Document / object | Full SHA-256 or git SHA |
| --- | --- |
| Owner-provided Master Architecture v2.1 source document, as cited in `docs/acceptance/v21-wave0/SOURCE_GAPS.md` | SHA-256 `c5196ff1d050ac6477cc064390a708a4d10121cf7fe300bb24764a87a2a5b1c2` |
| `WAVE_V21_0_JOINT_CLOSURE_AND_WAVE1_LAUNCH_ORDER`, as cited in `docs/acceptance/v21-wave1/V21_WAVE1_TEAM_A_HANDOFF_REPORT.md` | SHA-256 `450108ec3b9e8ca5d04bbfe0718d2ce4712acd485a8c4eafb1a6286ce7b943da` |

## 3. SPACE-C01–C10 formally in effect (adopt 空间-00F; SPACE-C03 phase-1 lock)

t106u formally adopts `空间-00F`（《项目负责人建议裁决意见》, 2026-11-25) as the in-effect ruling for SPACE-C01–C10, and additionally locks SPACE-C03 phase 1 as `1 organization_team = 1 Team Space`. Clause wording below is copied from that official recommended ruling. The earlier “映射基数暂缓冻结 / 1 Team = 1 Space 或 1:N，等待 PRE-01 和产品负责人书面确认” reservation in `空间-00F` for SPACE-C03 is superseded by the t106u phase-1 lock. This section does not add invented clause text.

| Clause | Official in-effect wording (from 空间-00F, plus the t106u SPACE-C03 lock) |
| --- | --- |
| SPACE-C01 一期空间结构 | 采纳 Option A。一期采用 Tenant → Space → KnowledgeBase 扁平结构。一期关闭 parent_space_id 嵌套空间能力。保留未来扩展能力，但不提前引入树形继承和跨空间移动。 |
| SPACE-C02 个人空间 Tenant 归属 | 原则采纳 Option A，附带条件。企业员工个人 Space 归属企业 Tenant，但必须具有不可绕过的个人私有访问不变量。独立个人用户归属独立个人 Tenant。历史 tenantId=null 数据不得自动迁移。最终离职及个人数据处置规则已由 t106u Gate 5 / PRE-04 正式落地（见第 5 节）；本条的 Tenant 归属与禁止自动迁移口径不变。 |
| SPACE-C03 Team 映射 | 空间-00F 原文：采纳双类型标识方向；明确区分 organization_team 与 collaboration_group；不得继续将 department 直接映射为业务 Team。t106u 正式锁定一期：`1 organization_team = 1 Team Space`。该锁定取代 空间-00F 中“映射基数暂缓冻结”及“1 Team = 1 Space 或 1:N，等待 PRE-01 和产品负责人书面确认”的待决表述。 |
| SPACE-C04 Space 与 KnowledgeBase 关系 | 采纳 Option A。支持一个 Space 下多个 KnowledgeBase。强制 Space.org_id == KnowledgeBase.org_id。禁止跨 Tenant 移动。跨空间引用必须保留唯一主资产归属、实时权限验证和明确 detach 语义。detach 不得隐式归档共享资产。 |
| SPACE-C05 权限模型 | 采纳 Option A。支持八种独立权限动作。采用 Tenant、Space、KB、Asset、User、Agent 多层权限约束。显式 Deny 优先。采用事务 Outbox、policy_generation 和读时权威验证。撤权延迟目标及异常处理 SLA 必须形成正式安全验收标准。The eight independent actions named in the joint decision package Option A adopted by 空间-00F are: `read` / `upload` / `update` / `delete` / `manage_members` / `manage_permissions` / `archive` / `transfer_ownership`. |
| SPACE-C06 Favorites | 采纳 Option A。OpenBot 作为收藏关系唯一写主。至少支持 kb 和 asset 两种 target_type。SDK 提供批量实时 ACL 水合。禁止双写。旧 localStorage 数据迁移必须按 tenant_id 和稳定 user_id 严格隔离。不可访问和已删除目标采用脱敏占位，并保留取消收藏入口；具体 UX 由产品负责人确认。 |
| SPACE-C07 个人分享及离职处置 | 原则采纳 Option A，附带条件。个人空间默认私有。如保留分享能力，只允许受控只读引用和实时权限检查。离职时立即冻结相关访问。工作成果交接采用双人审批。不得自动继承个人正文。t106u Gate 5 now supplies the official PRE-04 / EXT-03 operational rules listed in section 5; those rules do not reopen this clause. |
| SPACE-C08 Agent 知识权限 | 采纳 Option A。保留 Space 上限及 KB、knowledge-file、deliverable、folder 等细粒度消费范围。有效权限必须同时满足 Agent Scope 和当前 User 实时权限。成员身份只认稳定 userId，不以邮箱作为永久授权主键。公域机器人必须绑定真实企业公开资源，不得保留旧权限绕过路径。B3 补丁在完成回归和代码审查前，不视为已合入生产。 |
| SPACE-C09 API 兼容与迁移 | 采纳 Option A。锁定 knowledge-sdk@9940818b 的 `/v2/spaces` 现有语义。新一级 Space 使用独立资源路径或明确版本协商，不得静默改变旧接口含义。Schema v6 → v7+ 必须先完成只读 Dry-Run、存量统计、碰撞报告和回滚设计。This compilation does not authorize Schema v7 DDL. |
| SPACE-C10 知识供给模型 | 采纳 Option A 的分型方向。至少区分：uploaded_document、agent_deliverable、enterprise_materialized_ref、data_capability。明确 Asset Envelope、Tombstone、freshness、masked_fields 和 publication_state。动态 data_capability 必须维持 Tool 执行能力边界，不得暴露普通文档 Agent 不应获得的凭据或查询权限。三类静态或物化资产与动态 Tool 能力必须具有独立生命周期和权限语义。 |

R-01 through R-06 in the joint decision package remain the previously aligned direction statements; they are not re-litigated here. Naming stays in the `SPACE-C01`–`SPACE-C10` namespace and does not overwrite frozen M1 `C-01`–`C-09`.

## 4. Space Gate status registered in this compilation

| Gate | Official status registered here | Notes |
| --- | --- | --- |
| Space Gate 3 | `MET` at `openbot-vp` `main@8b83e4eba9b4eec5532046481ca98259c3bcf1d6` (Owner-stated in t103u; unchanged) | This compilation does not reopen or re-litigate the grant |
| Space Gate 4 | `MET_FOR_CONTRACT_AND_SANDBOX` (t106u). This is **not** unrestricted production `MET`. | Official contract v1.0, AUTH-V21-04 named custodian, and the lead/DBA-only production-export condition are recorded in section 5.1 |
| Space Gate 5 | `MET` (t106u, PRE-04 / EXT-03) | The five Owner-stated rules are recorded in section 5.2 |
| Space Gate 6 | `NOT_MET` | 双团队合编签认 `FINAL_SPACE_AND_FAVORITES_ALIGNMENT.md`. This Team A file is ready for Team B countersignature and is not a joint freeze. Official next-step language remains: Gate 1–5 齐备并同步原文/编号（F-01/F-02）后合编, plus Team B countersign and a later official freeze. |
| Space Gate 7 | `MET (with conditions)` | Unchanged prior official Wave-V21 lock language |

## 5. Official Gate 4 and Gate 5 rulings recorded from t106u

### 5.1 Space Gate 4 — `MET_FOR_CONTRACT_AND_SANDBOX` (not unrestricted production MET)

- Official status: `MET_FOR_CONTRACT_AND_SANDBOX`
- Official contract v1.0 filename: `PRE03_ANONYMIZATION_SPEC_FOR_GATE4.md`
- Official contract v1.0 SHA-256 (full; independently re-hashed from the local official copy before use): `66294adfb60d54d42c4307d5b19c8fda298828d7bd9b0f520c0a2958f1fb845e`
- AUTH-V21-04 named custodian: Daniel \<daniel.hhd@gmail.com\>
- Carrying condition (t106u): real production export may be performed only by the lead / DBA; engineering has zero production-database contact
- Authorization reference: Owner order `t106u` (2026-11-28, Asia/Shanghai)
- This status does not authorize engineering to query, dump, or export production databases, Qdrant, or live tenant data. The sandbox PRE-03 checker in this wave accepts only `SYNTHETIC_EXAMPLE` mocks (official contract rule 12).

### 5.2 Space Gate 5 — `MET` (PRE-04 / EXT-03)

Official status: `MET`. The five Owner-stated rules in t106u are:

1. 离职 ≤60s 实时冻结
2. 90 天只读隔离保留
3. 工作产物双人审批交接
4. 私有正文严禁自动继承
5. 受控分享即时失效

Authorization reference: Owner order `t106u` (2026-11-28, Asia/Shanghai). These rules do not authorize Schema v7 DDL, formal T-01–T-27, or a Gate 6 freeze.

## 6. Team B countersign area (blank; not signed)

This section is the explicit Team B countersignature block required by W5A-1. It is left blank. Filling any of these fields, or changing Space Gate 6 to `MET`, or labeling this file Frozen, requires a later official authorization and Team B's own countersignature. This Team A compilation does not sign Gate 6 and does not countersign on behalf of Team B.

- Team B countersign status: ____________________
- Team B signatory: ____________________
- Date (Asia/Shanghai): ____________________
- Authorization / evidence reference: ____________________
- Notes / residual items from Team B: ____________________

## 7. Final-acceptance freeze signature slots (blank; not Frozen)

This section is the explicit final-acceptance freeze block required by W5A-1. It is left blank. This file must not be treated as Frozen until these slots are officially filled after Team B countersignature and a later official Gate 6 freeze instruction.

- Freeze status: ____________________
- Official freeze designation (must not be self-declared): ____________________
- Team A freeze signatory: ____________________
- Team B freeze signatory: ____________________
- Owner / authorizing official: ____________________
- Date (Asia/Shanghai): ____________________
- Authorization reference: ____________________
- Evidence / receipt pack reference: ____________________

## 8. What this compilation does not claim

- This file is not Frozen and does not claim Space Gate 6 MET.
- Formal T-01–T-27 remains `NOT_RUN_NOT_ACCEPTED`.
- `schema_v7_ddl_authorized` remains `false`. This file contains zero DDL SQL, and Schema v7/v8/v9 migrations are not started. The companion `SCHEMA_V7_SANDBOX_DESIGN_AND_ROLLBACK_SPEC.md` is non-executable design / rollback prose only.
- Official VB-1 lock stays `111/13/0`. t106u does not change that lock.
- Space Gate 4 is `MET_FOR_CONTRACT_AND_SANDBOX` only. It is not unrestricted production MET. Real production export remains lead / DBA only.
- Production shadow migration / cutover remains unauthorized.
- `EXPERIMENTAL_V3_ENABLED` stays default false. `OPENBOT_KNOWLEDGE_SDK_V2_ENABLED` stays default false. `/v3/*` stays unmounted.
- `feat/v21-wave4-pre-v7-prep@e97a8cca68df7b464ce1f017729022cba861c543`, `feat/v21-wave3-interop-hardening@918293cada0610d6a6d7ef6b8e5f86990b411ce9`, and knowledge-sdk `main@b953c9922cc1096e0e88455dab6746c01a9d27f9` stay frozen. This compilation is not a pull request and not a merge to `main`.
