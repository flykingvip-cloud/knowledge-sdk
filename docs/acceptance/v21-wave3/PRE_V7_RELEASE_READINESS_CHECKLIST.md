# PRE_V7_RELEASE_READINESS_CHECKLIST

Status: **read-only readiness checklist, not an approval and not a release gate**. Completing a row here does not authorize Schema v7 DDL, formal T-01–T-27, Space Gate 3/4, production cutover, or any change to the official VB-1 lock. `formal_t01_t27` remains `NOT_RUN_NOT_ACCEPTED`. This document contains zero DDL.

Order context: `WAVE_V21_2_JOINT_CLOSURE_AND_WAVE3_LAUNCH_ORDER` (2026-11-28, Asia/Shanghai) recorded `WAVE_V21_2_JOINT_CLEAN_ACCEPT` and `wave_v21_3_unlocked=true`. The unlocked work is isolated-branch Wave-V21-3 hardening only. Still false and unchanged: `schema_v7_ddl_authorized`, `schema_v8_v9_ddl_authorized`, `final_alignment_frozen`, `prod_shadow_migration_cutover_authorized`.

Exact command outputs and the isolated-branch tip SHA belong in `V21_WAVE3_TEAM_A_HANDOFF_REPORT.md`. If GitHub Actions is queued or in progress when that report is written, it must not be predeclared green.

## 1. Hard locks that remain closed

| Item | Required state | Ready for Schema v7 / formal acceptance? |
| --- | --- | --- |
| `schema_v7_ddl_authorized` | `false` (zero DDL in this wave) | No |
| `formal_t01_t27` | `NOT_RUN_NOT_ACCEPTED` | No |
| Space Gate 3 / Gate 4 | `NOT_MET` | No |
| Official VB-1 lock | `111/13/0` | No change, not closed as a v7 prerequisite |
| `EXPERIMENTAL_V3_ENABLED` | default `false`; `/v3/*` unmounted | No product v3 mount |
| `OPENBOT_KNOWLEDGE_SDK_V2_ENABLED` | default `false` | Not flipped here |
| Production shadow migration / cutover | unauthorized | No |
| Pull request or merge to `main` | forbidden in this wave | Not opened |

## 2. Already landed facts this checklist can cite (not new authorizations)

| Item | Recorded state |
| --- | --- |
| Pack status | `FROZEN_V21_REUSE_V1` |
| Frozen manifest SHA-256 | `212537fd41bd4cc4d9d7343cacafaea225ee98b6586df716bf036a397cb2a382` |
| Schema version in the boundary verifier | `6` |
| `pyproject.toml` `dependencies` | `[]` |
| M1 frozen verify | 28 assets / 0 drift |
| Boundary baseline | 709 files / 0 drift against `9940818b` |
| Official Sync-W2-1 | `CRYPTOGRAPHICALLY_ALIGNED_BYTE_EXACT` (see `W3_INTEROP_PARITY_RECORD.md`) |
| Golden fixture `w2_interop_golden.json` | 33863 bytes; SHA-256 `f8033a902af06b005fa591ab872a74f9569a3783fd3e7cef90c6dc94cf9d0fef` |
| Hard `receipt_hash` values | `G4-POS-FOUR-CHANNEL-SUCCESS` = `f4055894fdebb0fc55ae563aaed03ab6f4162b53c4eeab31ad479f6c6707b476`; `G4-POS-CHANNEL-TIMEOUT-NOT-PURGED` = `6e8c7f178ec452b590e0d0f06defa0a2c21c0fac5c6a672a356a02b31470f0d0` |
| Wave-V21-2 isolated tip (unmodified parent of this wave) | `4d546272cd51605edeed5b80b4e3adc278608e94` |
| T-01..T-27 sandbox matrix | still a tracking aid only; every formal row stays `NOT_RUN_NOT_ACCEPTED` |

## 3. Wave-V21-3 Team A checks (isolated branch only)

| Check | Intent | Result belongs in |
| --- | --- | --- |
| W3A-1 parity record | Register official three-party Sync-W2-1 values without inventing unpublished hash suffixes or official-order OpenBot SHAs | this tree: `W3_INTEROP_PARITY_RECORD.md` |
| W3A-1 boundary increment | Allow only `docs/acceptance/v21-wave3/`; hard-lock the golden fixture SHA-256; do not loosen frozen manifest, M1 28, 709, `dependencies==[]`, or `schema_version==6` | `scripts/verify_v21_boundaries.py` plus the handoff |
| W3A-2 HTTP loopback | Pure-stdlib `http_loopback_cases.py`: `127.0.0.1:0`, clean close, zero `ResourceWarning`, paths only under `/sandbox/v21/*`, no `/v3/*` mount, replay the five official golden groups over HTTP JSON and official `X-V21-*` headers | local unittest / CI discover `*cases.py` |
| Contract pack | `python3 contracts/v21-reuse-v1/validate.py` stays `formal_acceptance=false` and the frozen manifest SHA is unchanged; do not invent a `status.json` flip | handoff |
| Frozen M1 verifier | `python3 docs/acceptance/v2.2-align-wave2/verify_frozen.py` still 28 / 0 drift | handoff |
| Isolated GitHub Actions | Record the run id/url/status honestly after push. Queued or in-progress is not green. Zero PRs | handoff |

## 4. Commands that must be green locally before push

Run in the isolated Wave-V21-3 worktree:

```
python3 contracts/v21-reuse-v1/validate.py
python3 scripts/verify_v21_boundaries.py
python3 docs/acceptance/v2.2-align-wave2/verify_frozen.py
PYTHONPATH=src:. python3 -W error::ResourceWarning -m unittest discover -s sandbox/v21_reuse_v1 -p '*.py'
```

These local greens are sandbox and boundary evidence only. They are not formal T-01–T-27 acceptance.

## 5. Explicit residuals (remain open)

- Formal T-01–T-27 was not run and is not accepted.
- Space Gate 3/4 stay `NOT_MET`. Official VB-1 stays `111/13/0`.
- Schema v7 is not authorized and is not started. No migration, no DDL, no production cutover.
- `/v3/*` remains an unmounted draft. `EXPERIMENTAL_V3_ENABLED` remains default false.
- This checklist does not open a pull request and does not merge to `main`.
