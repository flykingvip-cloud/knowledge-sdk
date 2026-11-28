# PRE_V7_RELEASE_READINESS_CHECKLIST_V2

Status: **read-only Wave-V21-4 readiness checklist, not an approval and not a release gate**. Completing a row here does not authorize Schema v7 DDL, formal T-01–T-27, Space Gate 4/5/6, production cutover, a Frozen final alignment, or any change to the official VB-1 lock. `formal_t01_t27` remains `NOT_RUN_NOT_ACCEPTED`. This document contains zero DDL SQL.

Order context: Owner order `t103u` / `WAVE_V21_3_JOINT_CLEAN_ACCEPT + Space Gate 3 MET + 启动 Wave-V21-4` (2026-11-28, Asia/Shanghai) recorded `WAVE_V21_3_JOINT_CLEAN_ACCEPT`, `wave_v21_4_unlocked=true`, and Space Gate 3 = `MET` at `openbot-vp` `main@8b83e4eba9b4eec5532046481ca98259c3bcf1d6`. The unlocked work is isolated-branch Wave-V21-4 pre-v7 preparation only, starting from the frozen Team A Wave-V21-3 tip. Still false and unchanged: `schema_v7_ddl_authorized`, `schema_v8_v9_ddl_authorized`, `final_alignment_frozen`, `prod_shadow_migration_cutover_authorized`. Space Gate 4 / Gate 5 / Gate 6 remain `NOT_MET`. Official VB-1 lock remains `111/13/0`. `AUTH-V21-04` remains `HELD_PENDING_NAMED_RECIPIENTS`.

This V2 checklist supersedes `docs/acceptance/v21-wave3/PRE_V7_RELEASE_READINESS_CHECKLIST.md` only as the Wave-V21-4 registration surface. It does not rewrite that V1 file, and it does not rewrite `feat/v21-wave3-interop-hardening@918293cada0610d6a6d7ef6b8e5f86990b411ce9`.

Exact command outputs and the isolated-branch tip SHA belong in `V21_WAVE4_TEAM_A_HANDOFF_REPORT.md`. If GitHub Actions is queued or in progress when that report is written, it must not be predeclared green.

## 1. Hard locks that remain closed

| Item | Required state | Ready for Schema v7 / formal acceptance? |
| --- | --- | --- |
| `schema_v7_ddl_authorized` | `false` (zero DDL in this wave) | No |
| `formal_t01_t27` | `NOT_RUN_NOT_ACCEPTED` | No |
| Space Gate 4 / Gate 5 / Gate 6 | `NOT_MET` (see section 3) | No |
| Official VB-1 lock | `111/13/0` (`111 code-verified / 13 partial / 0 cannot-verify`) | No change; t103u does not alter this lock |
| `AUTH-V21-04` | `HELD_PENDING_NAMED_RECIPIENTS` | No |
| `EXPERIMENTAL_V3_ENABLED` | default `false`; `/v3/*` unmounted | No product v3 mount |
| `OPENBOT_KNOWLEDGE_SDK_V2_ENABLED` | default `false` | Not flipped here |
| `final_alignment_frozen` | `false`; the Wave-V21-4 draft must not be labeled Frozen | No |
| Production shadow migration / cutover | unauthorized | No |
| Pull request or merge to `main` | forbidden in this wave | Not opened |

## 2. Already landed facts this checklist can cite (not new authorizations)

Owner-stated values from `t103u` are recorded as stated. The remainder of the AUTH-V21-09B receipt pack is not invented here. OpenBot was not independently re-verified in this Team A run.

| Item | Recorded state |
| --- | --- |
| Wave-V21-3 joint verdict | `WAVE_V21_3_JOINT_CLEAN_ACCEPT` |
| Team A Wave-V21-3 verdict | `TEAM_A_WAVE_V21_3_CLEAN_ACCEPT`; `DEFECT-W3A-01` = `CLOSED` |
| `wave_v21_4_unlocked` | `true` |
| Space Gate 3 | `MET` at `openbot-vp` `main@8b83e4eba9b4eec5532046481ca98259c3bcf1d6` |
| Owner-stated PR #365 merge | 2026-11-28 15:47:57 CST (Asia/Shanghai), ordinary `--merge` (no `--admin`), into that same `openbot-vp` tip |
| Owner-stated AUTH-V21-09B receipt pack | `SHA256SUMS.txt` prefix `c5c1539a...` (9/9 matched; remainder not published in t103u and not invented here) |
| Owner-stated post-merge OpenBot suite | trunk four core vitest groups 106/106 green (both flags unset) |
| Team A Wave-V21-3 isolated tip | `feat/v21-wave3-interop-hardening@918293cada0610d6a6d7ef6b8e5f86990b411ce9`, frozen and unmodified by Wave-V21-4; `gh pr list --head feat/v21-wave3-interop-hardening --state all` is empty (0 open / 0 closed / 0 merged PRs) |
| knowledge-sdk `main` (independently observed at Wave-V21-4 start; not moved by this wave) | `b953c9922cc1096e0e88455dab6746c01a9d27f9` |
| Pack status | `FROZEN_V21_REUSE_V1` |
| Frozen manifest SHA-256 | `212537fd41bd4cc4d9d7343cacafaea225ee98b6586df716bf036a397cb2a382` |
| Schema version in the boundary verifier | `6` |
| `pyproject.toml` `dependencies` | `[]` |
| M1 frozen verify | 28 assets / 0 drift |
| Boundary baseline | 709 files / 0 drift against `9940818b962ccb186c0dfb0158de6bd9bd49057b` |
| Official Sync-W2-1 | `CRYPTOGRAPHICALLY_ALIGNED_BYTE_EXACT` (see `docs/acceptance/v21-wave3/W3_INTEROP_PARITY_RECORD.md`) |
| Golden fixture `w2_interop_golden.json` | 33863 bytes; SHA-256 `f8033a902af06b005fa591ab872a74f9569a3783fd3e7cef90c6dc94cf9d0fef`; git blob `5afaff1616ddd77dca604dc498fc691ae4a4f37b` |
| Hard dual-stack `receipt_hash` values | `G4-POS-FOUR-CHANNEL-SUCCESS` = `f4055894fdebb0fc55ae563aaed03ab6f4162b53c4eeab31ad479f6c6707b476`; `G4-POS-CHANNEL-TIMEOUT-NOT-PURGED` = `6e8c7f178ec452b590e0d0f06defa0a2c21c0fac5c6a672a356a02b31470f0d0` |
| Wave-V21-0 isolated tip (unmodified) | `9d25ea96b75b5ab528a2d2670b5419d9a217e39e` |
| Wave-V21-1 isolated tip (unmodified) | `207953963872a4a7e65731def077c469b685f4e2` |
| Wave-V21-2 isolated tip (unmodified) | `4d546272cd51605edeed5b80b4e3adc278608e94` |
| Space Gate 7 (unchanged prior official lock language) | `MET (with conditions)` |
| T-01..T-27 sandbox matrix | still a tracking aid only; every formal row stays `NOT_RUN_NOT_ACCEPTED` |

## 3. Remaining Space Gate 4 / Gate 5 / Gate 6 blockers

Wording below is reused from the official Pre-v7 exit-gate table in `GATE7_OFFICIAL_MET_SIGNOFF_2026-11-26` and from the official Wave-V21-4 launch red line (`Space Gate 4/5/6` still `NOT_MET`; `AUTH-V21-04` still waiting for named recipients). This checklist does not invent new gate criteria and does not mark any of these gates `MET`.

| Gate | Official exit-threshold content (reused wording) | Official status | Official next-step language (reused, not claimed done here) |
| --- | --- | --- | --- |
| Space Gate 4 | PRE-03 历史数据脱敏清单与官方格式 | `NOT_MET` | 团队 B 执行 `B2-3` + DBA 执行 `EXT-02`; Wave-V21-4 also states Team B W4B-1 is to prepare a read-only Gate 4 呈批包, limited to specification and anonymized simulated samples, with zero real production data, and with blank AUTH-V21-04 named-recipient slots |
| Space Gate 5 | PRE-04 离职与个人空间规则签批 | `NOT_MET` | 产品/法务推进 `EXT-03` 书面签批 |
| Space Gate 6 | 双团队合编签认 `FINAL_SPACE_AND_FAVORITES_ALIGNMENT.md` | `NOT_MET` | Gate 1–5 齐备并同步原文/编号（F-01/F-02）后合编. The Team A file in this wave is only `FINAL_SPACE_AND_FAVORITES_ALIGNMENT_DRAFT.md`, marked `Status: DRAFT_UNFROZEN_PENDING_GATE4_GATE5`, and must not be labeled Frozen |

Companion Wave-V21-4 Team B work (W4B-1 / W4B-2 / W4B-3) is authorized on the OpenBot side by the same launch family. This Team A checklist does not claim that work is complete and does not independently re-verify OpenBot.

## 4. Wave-V21-4 Team A checks (isolated branch only)

| Check | Intent | Result belongs in |
| --- | --- | --- |
| W4A-1 checklist V2 | Register Space Gate 3 `MET` @ `8b83e4eba9b4eec5532046481ca98259c3bcf1d6` and the remaining Gate 4 / Gate 5 / Gate 6 blockers; record the frozen Wave-V21-3 tip and 0 PRs | this tree: `PRE_V7_RELEASE_READINESS_CHECKLIST_V2.md` |
| W4A-1 alignment draft | Summarize already-locked cryptographic anchors; leave Gate 4 and Gate 5 sign-off fields blank; mark exactly `Status: DRAFT_UNFROZEN_PENDING_GATE4_GATE5`; zero DDL SQL; do not label Frozen | this tree: `FINAL_SPACE_AND_FAVORITES_ALIGNMENT_DRAFT.md` |
| W4A-2 boundary increment | Allow only `docs/acceptance/v21-wave4/`; do not loosen frozen manifest, M1 28, 709, `dependencies==[]`, `schema_version==6`, or the golden fixture SHA-256 | `scripts/verify_v21_boundaries.py` plus the handoff |
| Contract pack | `python3 contracts/v21-reuse-v1/validate.py` stays `formal_acceptance=false` and the frozen manifest SHA is unchanged; do not invent a `status.json` flip | handoff |
| Frozen M1 verifier | `python3 docs/acceptance/v2.2-align-wave2/verify_frozen.py` still 28 / 0 drift | handoff |
| Sandbox / HTTP loopback | `PYTHONPATH=src:. python3 -W error::ResourceWarning -m unittest discover -s sandbox/v21_reuse_v1 -p '*cases.py'` stays 68 tests, including a 10/10 consecutive streak with zero `ConnectionResetError` and zero `ResourceWarning`; also run `-p '*.py'` once | handoff |
| Isolated GitHub Actions | Record the run id/url/status honestly after push. Queued or in-progress is not green. Zero PRs | handoff |

## 5. Commands that must be green locally before the first push

Run in the isolated Wave-V21-4 worktree:

```
python3 contracts/v21-reuse-v1/validate.py
python3 scripts/verify_v21_boundaries.py
python3 docs/acceptance/v2.2-align-wave2/verify_frozen.py
PYTHONPATH=src:. python3 -W error::ResourceWarning -m unittest discover -s sandbox/v21_reuse_v1 -p '*cases.py'
PYTHONPATH=src:. python3 -W error::ResourceWarning -m unittest discover -s sandbox/v21_reuse_v1 -p '*.py'
```

The `*cases.py` suite must also be repeated 10 times consecutively. These local greens are sandbox and boundary evidence only. They are not formal T-01–T-27 acceptance.

## 6. Explicit residuals (remain open)

- Formal T-01–T-27 was not run and is not accepted.
- Space Gate 4 / Gate 5 / Gate 6 stay `NOT_MET`. Official VB-1 stays `111/13/0`. `AUTH-V21-04` stays `HELD_PENDING_NAMED_RECIPIENTS`.
- Schema v7 is not authorized and is not started. No migration, no DDL, no production cutover.
- `/v3/*` remains an unmounted draft. `EXPERIMENTAL_V3_ENABLED` remains default false. `OPENBOT_KNOWLEDGE_SDK_V2_ENABLED` remains default false.
- `FINAL_SPACE_AND_FAVORITES_ALIGNMENT_DRAFT.md` is a draft pending Gate 4 and Gate 5. It is not Frozen and is not a Gate 6 sign-off.
- `feat/v21-wave3-interop-hardening@918293cada0610d6a6d7ef6b8e5f86990b411ce9` stays frozen. This wave does not open a pull request and does not merge to `main`.
