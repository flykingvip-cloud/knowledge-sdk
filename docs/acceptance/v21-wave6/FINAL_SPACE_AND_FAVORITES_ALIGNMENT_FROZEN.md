Status: FROZEN_GATE6_MET

# FINAL_SPACE_AND_FAVORITES_ALIGNMENT_FROZEN

This file records official Owner order `t107u` (2026-11-28, Asia/Shanghai) for Space Gate 6. It is a new Wave-V21-6 document. It does **not** modify `docs/acceptance/v21-wave5/FINAL_SPACE_AND_FAVORITES_ALIGNMENT.md`, `docs/acceptance/v21-wave4/FINAL_SPACE_AND_FAVORITES_ALIGNMENT_DRAFT.md`, or any other prior alignment file.

The first line of this file is exactly `Status: FROZEN_GATE6_MET`. The rulings below are copied from t107u; this document does not itself issue those rulings. This file contains zero DDL SQL and does not authorize a production Schema v7 migration. Engineering has zero production-database contact.

## 1. Official rulings recorded from t107u (not self-issued)

t107u granted `TEAM_A_WAVE_V21_5_CLEAN_ACCEPT`, `TEAM_B_WAVE_V21_5_CLEAN_ACCEPT`, and `WAVE_V21_5_JOINT_CLEAN_ACCEPT`. It formally signed Space Gate 6 = `MET` with `final_alignment_frozen = true`, and issued `AUTH-V21-06-SANDBOX` with `wave_v21_6_unlocked = true` for an isolated-branch sandbox only.

Still false and unchanged for production and for the frozen v21-reuse-v1 contract pack:

- `schema_v7_prod_migration_authorized = false`
- `schema_v7_ddl_authorized = false` (production)
- `schema_v8_v9_ddl_authorized` remains false in `contracts/v21-reuse-v1/status.json`, which this wave does not edit
- `EXPERIMENTAL_V3_ENABLED` and `OPENBOT_KNOWLEDGE_SDK_V2_ENABLED` stay default false
- `formal_t01_t27` remains `NOT_RUN_NOT_ACCEPTED`
- Official VB-1 lock remains `111/13/0`
- The frozen contract file `contracts/v21-reuse-v1/status.json` is intentionally left byte-identical, including `final_alignment_frozen: false` as a pack lock. The Gate 6 alignment freeze recorded here is the t107u ruling; this wave does not rewrite the frozen pack flags.

Space Gate 4 remains `MET_FOR_CONTRACT_AND_SANDBOX` only. Real production export remains lead / DBA only. Pre-v7 seven gates are recorded as closed under that Gate 4 carrying condition.

Authorization reference: Owner order `t107u` (2026-11-28, Asia/Shanghai), issued under the written authorization of the project lead Daniel (daniel.hhd@gmail.com). That name is recorded as the official authorizer / custodian; this file is not a request to email anyone.

## 2. Gate 6 freeze anchors (independently re-hashed)

These SHA-256 values were reconfirmed from the source files immediately before this document was written. No digit is invented.

| Anchor | Full SHA-256 | Source |
| --- | --- | --- |
| Team A alignment | `46de73e86a1da7063658f041ece018780c4a22ce3d2bc5c6ae0bf8b9df5ca816` | SHA-256 of `docs/acceptance/v21-wave5/FINAL_SPACE_AND_FAVORITES_ALIGNMENT.md` at `feat/v21-wave5-gate6-freeze-and-dryrun@ce8297fba12849dd7725291d31a72de56279ce1d` (git blob `026cc29adb56281d7092d04533edb068e41a63f3`) |
| Team B countersign | `b803b9c34efd70e5666a3f3a0b5ea23dd8ae2ee3ce54ae1ca66a787c22d8bbf0` | SHA-256 of `docs/W5B3_GATE6_TEAM_B_COUNTERSIGN_MEMO.md` as independently hashed from the Team B handoff pack and as listed in that pack's `SHA256SUMS.txt` |

`final_alignment_frozen = true` is anchored to those two hashes, as stated in t107u.

## 3. Already-locked Wave-V21 tips that this freeze does not move

| Ref | Full SHA | Notes |
| --- | --- | --- |
| Wave-V21-5 Team A isolated tip `feat/v21-wave5-gate6-freeze-and-dryrun` | `ce8297fba12849dd7725291d31a72de56279ce1d` | Frozen parent of Wave-V21-6; not modified |
| Wave-V21-4 Team A isolated tip `feat/v21-wave4-pre-v7-prep` | `e97a8cca68df7b464ce1f017729022cba861c543` | Frozen; 0 PRs |
| Wave-V21-3 Team A isolated tip `feat/v21-wave3-interop-hardening` | `918293cada0610d6a6d7ef6b8e5f86990b411ce9` | Frozen; 0 PRs |
| knowledge-sdk `main` | `b953c9922cc1096e0e88455dab6746c01a9d27f9` | Must not be moved by this wave |

The historical Schema v6 baseline remains `9940818b962ccb186c0dfb0158de6bd9bd49057b`. Main-library `schema_version` remains `6`. The frozen v21-reuse-v1 manifest SHA-256 remains `212537fd41bd4cc4d9d7343cacafaea225ee98b6586df716bf036a397cb2a382`. The official Sync-W2-1 golden fixture remains 33863 bytes, SHA-256 `f8033a902af06b005fa591ab872a74f9569a3783fd3e7cef90c6dc94cf9d0fef`, git blob `5afaff1616ddd77dca604dc498fc691ae4a4f37b`.

## 4. What AUTH-V21-06-SANDBOX unlocks, and what it does not

`wave_v21_6_unlocked = true` authorizes isolated-branch sandbox work only, on a new branch whose first parent is exactly `ce8297fba12849dd7725291d31a72de56279ce1d`. That sandbox may implement a disposable Schema v7 SQLite migration and idempotent rollback, PostgreSQL DDL / FORCE RLS semantic validation without a live production or shared PostgreSQL, Tenant → Space → KnowledgeBase placement, the SPACE-C03 phase-1 lock `1 organization_team = 1 Team Space` with no department auto-mapping, the official five-layer Fail-Closed isolation chain, zero-copy Favorites pointers, the official PRE-04 five-rule leaver state machine, and a sandbox T-01–T-27 suite labeled `SANDBOX_DUAL_ENGINE_CANDIDATE`.

It does not authorize:

- any edit under `src/knowledge_sdk/storage/`
- any upgrade of an existing Schema v6 store
- `schema_v7_prod_migration_authorized`
- production or shared database contact
- opening a pull request or merging to `main`
- formal T-01–T-27 acceptance (`formal_t01_t27_accepted` must stay `false`)
- changing live `/v2/spaces` semantics or mounting production `/v3/*`

## 5. Official five PRE-04 / Gate 5 rules (unchanged; still in effect)

Recorded as already signed `MET` in t106u / t107u:

1. Resignation real-time freeze within 60 seconds
2. 90-day read-only isolation retention
3. Work-product dual-approval handover
4. Private body text must not auto-inherit
5. Controlled shares are invalidated immediately

Security state is monotonic.

## 6. What this frozen record does not claim

- Formal T-01–T-27 remains `NOT_RUN_NOT_ACCEPTED`. A later sandbox report on this branch is not formal acceptance.
- This file contains zero DDL SQL and is not a Schema v7 production migration.
- Official VB-1 stays `111/13/0`.
- Space Gate 4 stays `MET_FOR_CONTRACT_AND_SANDBOX` only.
- Production shadow migration / cutover remains unauthorized.
- `EXPERIMENTAL_V3_ENABLED` stays default false. `OPENBOT_KNOWLEDGE_SDK_V2_ENABLED` stays default false.
- This document is not a pull request and not a merge to `main`.
