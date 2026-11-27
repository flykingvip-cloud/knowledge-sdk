# W3_INTEROP_PARITY_RECORD

Status: **Team A Wave-V21-3 Sync-W2-1 parity record only**. This document registers the official three-party alignment already confirmed by the Wave-V21-2 joint closure order. It is not formal T-01–T-27 acceptance, does not authorize Schema v7 DDL, and does not change Space Gate 3/4 or the official VB-1 lock.

Order recorded here: `WAVE_V21_2_JOINT_CLOSURE_AND_WAVE3_LAUNCH_ORDER` dated 2026-11-28 (Asia/Shanghai). The order states `WAVE_V21_2_JOINT_CLEAN_ACCEPT`, `wave_v21_3_unlocked=true`, Team B `TEAM_B_WAVE_V21_2_CLEAN_ACCEPT`, and official confirmation that Sync-W2-1 is `CRYPTOGRAPHICALLY_ALIGNED_BYTE_EXACT`. Still false and unchanged: `schema_v7_ddl_authorized`, production cutover authorization. `formal_t01_t27` remains `NOT_RUN_NOT_ACCEPTED`. Official VB-1 lock remains `111/13/0`. Space Gate 3/4 remain `NOT_MET`.

## 1. Official three-party confirmation (as stated by the joint closure order)

The independent acceptance end reported that it completed a three-party byte-for-byte comparison and formally confirmed:

| Item | Official confirmed value |
| --- | --- |
| Alignment status | `CRYPTOGRAPHICALLY_ALIGNED_BYTE_EXACT` |
| `sandbox/v21_reuse_v1/fixtures/w2_interop_golden.json` | 33863 bytes; SHA-256 `f8033a902af06b005fa591ab872a74f9569a3783fd3e7cef90c6dc94cf9d0fef`; three parties byte-identical |
| Dual-stack `receipt_hash` for `G4-POS-FOUR-CHANNEL-SUCCESS` | `f4055894fdebb0fc55ae563aaed03ab6f4162b53c4eeab31ad479f6c6707b476` (byte-identical across stacks) |
| Dual-stack `receipt_hash` for `G4-POS-CHANNEL-TIMEOUT-NOT-PURGED` | `6e8c7f178ec452b590e0d0f06defa0a2c21c0fac5c6a672a356a02b31470f0d0` (byte-identical across stacks) |
| Frozen `v21-reuse-v1` manifest SHA-256 | `212537fd41bd4cc4d9d7343cacafaea225ee98b6586df716bf036a397cb2a382` (unchanged) |
| Team B core originals | 12/12 exact match against `SHA256SUMS.txt` prefix `1a0f258b...` (the official order published only this prefix; the remainder is not invented here) |

Canonicalization for `receipt_hash` remains the existing Python rule in `sandbox.v21_reuse_v1.revocation.canonical_json_bytes`. This record does not introduce a second hash scheme.

## 2. Team A source identity for the golden fixture

The official Wave-V21-3 launch order requires Team A work to start from the unmodified Wave-V21-2 tip and does not rewrite that history.

- Golden fixture landed at Team A commit `37c982546f49bb8312670ad01be995d91f345043`.
- The same file remains byte-identical at the Wave-V21-2 isolated-branch tip `4d546272cd51605edeed5b80b4e3adc278608e94`.
- `scripts/verify_v21_boundaries.py` is incrementally updated in Wave-V21-3 to hard-lock the SHA-256 above so any later byte change fails the boundary gate.

## 3. Previously reported Team B pin (not named by the official order)

Team B earlier self-reported, in a Sync-W2-1 notice, that it had pinned a byte-identical copy of the golden fixture on OpenBot branch `codex/openbot/v21-wave2-e2e-interop` at `ab6bd10b7768a1d026900242448fa31b10826078` (parent `9d43cc784c4ebaa1ff3347a3d8d69ac85b0d2a7b`).

That pin is recorded here only as a previously reported Team B statement. **The official joint closure order itself did not name that OpenBot commit.** This record does not treat the self-reported SHA as an independently re-verified OpenBot-side fact in this Team A Wave-V21-3 run.

## 4. What this record does not claim

- Formal T-01–T-27 remains `NOT_RUN_NOT_ACCEPTED`.
- Space Gate 3/4 remain `NOT_MET`. Official VB-1 lock stays `111/13/0`.
- Schema v7/v8/v9 DDL remains unauthorized. Production shadow migration / cutover remains unauthorized.
- `EXPERIMENTAL_V3_ENABLED` stays default false. `/v3/*` stays unmounted.
- This is an isolated-branch documentation record. It is not a pull request, not a merge to `main`, and not a production-release approval.
