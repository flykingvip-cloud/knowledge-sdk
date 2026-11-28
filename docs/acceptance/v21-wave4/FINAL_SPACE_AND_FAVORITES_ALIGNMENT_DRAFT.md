Status: DRAFT_UNFROZEN_PENDING_GATE4_GATE5

# FINAL_SPACE_AND_FAVORITES_ALIGNMENT_DRAFT

This file is a Wave-V21-4 Team A draft only. It is **not** Frozen, is **not** `FINAL_SPACE_AND_FAVORITES_ALIGNMENT.md`, and is **not** a Space Gate 6 sign-off. The status line at the top of this file is exactly `Status: DRAFT_UNFROZEN_PENDING_GATE4_GATE5`. Gate 4 and Gate 5 sign-off fields below are intentionally blank. This document contains zero DDL SQL and does not authorize Schema v7, formal T-01–T-27, production cutover, or any change to the official VB-1 lock.

Order context: Owner order `t103u` (2026-11-28, Asia/Shanghai) recorded `WAVE_V21_3_JOINT_CLEAN_ACCEPT`, Space Gate 3 = `MET` at `openbot-vp` `main@8b83e4eba9b4eec5532046481ca98259c3bcf1d6`, and `wave_v21_4_unlocked=true`. Still false and unchanged: `schema_v7_ddl_authorized`, `schema_v8_v9_ddl_authorized`, `final_alignment_frozen`, `prod_shadow_migration_cutover_authorized`. `formal_t01_t27` remains `NOT_RUN_NOT_ACCEPTED`. Space Gate 4 / Gate 5 / Gate 6 remain `NOT_MET`. Official VB-1 lock remains `111/13/0`. `AUTH-V21-04` remains `HELD_PENDING_NAMED_RECIPIENTS`. `EXPERIMENTAL_V3_ENABLED` and `OPENBOT_KNOWLEDGE_SDK_V2_ENABLED` stay default false. `/v3/*` stays unmounted in production HTTP.

Hashes below are copied in full from already-locked in-repo Wave-V21 documents, from independently observed `git ls-remote` tips, or from Owner-stated values in t103u. Truncated official prefixes are left truncated. No suffix is invented.

## 1. Owner-stated Wave-V21-3 closure facts (not independently re-verified OpenBot)

Recorded as stated in t103u. The remainder of the AUTH-V21-09B receipt pack is not invented here. This Team A draft does not independently re-verify or modify OpenBot.

| Item | Recorded value |
| --- | --- |
| Joint verdict | `WAVE_V21_3_JOINT_CLEAN_ACCEPT` |
| Space Gate 3 | `MET` at `openbot-vp` `main@8b83e4eba9b4eec5532046481ca98259c3bcf1d6` |
| `wave_v21_4_unlocked` | `true` |
| PR #365 merge (Owner-stated) | 2026-11-28 15:47:57 CST (Asia/Shanghai), ordinary `--merge` (no `--admin`) |
| AUTH-V21-09B receipt pack (Owner-stated) | `SHA256SUMS.txt` prefix `c5c1539a...` (9/9 matched) |
| Post-merge OpenBot suite (Owner-stated) | trunk four core vitest groups 106/106 green (both flags unset) |

## 2. Already-locked cryptographic anchors

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

Source: `docs/acceptance/v21-wave3/W3_INTEROP_PARITY_RECORD.md`, which registers the official Wave-V21-2 joint closure confirmation. Canonicalization for `receipt_hash` remains `sandbox.v21_reuse_v1.revocation.canonical_json_bytes`. This draft does not introduce a second hash scheme.

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
| Wave-V21-3 Team A isolated tip `feat/v21-wave3-interop-hardening` | `918293cada0610d6a6d7ef6b8e5f86990b411ce9` | frozen; 0 PRs; Wave-V21-4 starts from this exact parent and does not change this tip |
| knowledge-sdk `main` (independently observed at Wave-V21-4 start) | `b953c9922cc1096e0e88455dab6746c01a9d27f9` | must not be moved by this wave |
| `openbot-vp` `main` (Owner-stated Space Gate 3 MET tip) | `8b83e4eba9b4eec5532046481ca98259c3bcf1d6` | recorded as stated in t103u; not independently re-verified here |

### 2.4 Additional already-locked document hashes cited in prior Team A Wave-V21 docs

These are copied in full from documents already landed on the frozen Wave-V21-3 tip. They are citations, not new sign-offs.

| Document / object | Full SHA-256 or git SHA |
| --- | --- |
| Owner-provided Master Architecture v2.1 source document, as cited in `docs/acceptance/v21-wave0/SOURCE_GAPS.md` | SHA-256 `c5196ff1d050ac6477cc064390a708a4d10121cf7fe300bb24764a87a2a5b1c2` |
| `WAVE_V21_0_JOINT_CLOSURE_AND_WAVE1_LAUNCH_ORDER`, as cited in `docs/acceptance/v21-wave1/V21_WAVE1_TEAM_A_HANDOFF_REPORT.md` | SHA-256 `450108ec3b9e8ca5d04bbfe0718d2ce4712acd485a8c4eafb1a6286ce7b943da` |

## 3. Space Gate status registered in this draft

| Gate | Official status registered here | Official exit-threshold content (reused, not invented) |
| --- | --- | --- |
| Space Gate 3 | `MET` at `openbot-vp` `main@8b83e4eba9b4eec5532046481ca98259c3bcf1d6` (Owner-stated in t103u) | Recorded as stated; this draft does not reopen or re-litigate the grant |
| Space Gate 4 | `NOT_MET` | PRE-03 历史数据脱敏清单与官方格式. Official next-step language: 团队 B 执行 `B2-3` + DBA 执行 `EXT-02`. `AUTH-V21-04` remains `HELD_PENDING_NAMED_RECIPIENTS`. |
| Space Gate 5 | `NOT_MET` | PRE-04 离职与个人空间规则签批. Official next-step language: 产品/法务推进 `EXT-03` 书面签批. |
| Space Gate 6 | `NOT_MET` | 双团队合编签认 `FINAL_SPACE_AND_FAVORITES_ALIGNMENT.md`. Official next-step language: Gate 1–5 齐备并同步原文/编号（F-01/F-02）后合编. This draft is not that signed file. |
| Space Gate 7 | `MET (with conditions)` | Unchanged prior official Wave-V21 lock language |

## 4. Gate 4 sign-off (blank; not signed)

This section is the explicit Gate 4 sign-off block required by W4A-1. It is left blank. Filling any of these fields, or changing Space Gate 4 to `MET`, requires a later official authorization. This Team A draft does not sign Gate 4.

- Status: `NOT_MET`
- Signatory: ____________________
- Date (Asia/Shanghai): ____________________
- Authorization reference: ____________________
- Evidence / receipt pack reference: ____________________

## 5. Gate 5 sign-off (blank; not signed)

This section is the explicit Gate 5 sign-off block required by W4A-1. It is left blank. Filling any of these fields, or changing Space Gate 5 to `MET`, requires a later official authorization. This Team A draft does not sign Gate 5.

- Status: `NOT_MET`
- Signatory: ____________________
- Date (Asia/Shanghai): ____________________
- Authorization reference: ____________________
- Evidence / receipt pack reference: ____________________

## 6. What this draft does not claim

- This draft is not Frozen and must not be renamed or treated as `FINAL_SPACE_AND_FAVORITES_ALIGNMENT.md` until a later official Gate 6 joint compilation and sign-off exists.
- Formal T-01–T-27 remains `NOT_RUN_NOT_ACCEPTED`.
- `schema_v7_ddl_authorized` remains `false`. This file contains zero DDL SQL, and Schema v7/v8/v9 migrations are not started.
- Official VB-1 lock stays `111/13/0`. `AUTH-V21-04` stays `HELD_PENDING_NAMED_RECIPIENTS`.
- Production shadow migration / cutover remains unauthorized.
- `EXPERIMENTAL_V3_ENABLED` stays default false. `OPENBOT_KNOWLEDGE_SDK_V2_ENABLED` stays default false. `/v3/*` stays unmounted.
- `feat/v21-wave3-interop-hardening@918293cada0610d6a6d7ef6b8e5f86990b411ce9` stays frozen. knowledge-sdk `main` is not moved. This draft is not a pull request and not a merge to `main`.
