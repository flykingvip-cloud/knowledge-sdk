# Task 0 — CI repaired; consequential convergence still pending confirmation

## Read-only repository observations (2026-11-25, Asia/Shanghai)

* main: `0ed15b93e2a6eed893369ca81524909c328c8b5c`.
* GitHub branch summary: `protected=false`, protection enabled=false, required
  check enforcement off/contexts empty. Repository rulesets API returned `[]`.
  This is **not** a branch-protection blocker and no access policy was changed.
* `git ls-remote origin refs/heads/main 'refs/tags/*'` returned that main ref and
  **no tag refs**. In particular `v2.0.0` (and `v1.2.0`) is not observed remotely;
  the taskbook's historical v1.2.0 wording is not treated as a live tag claim.
* main is an ancestor of `a5d1432b525dbb35cbd6e5018214886243ccc333`.
* Separate Q3 work branch starts exactly at that verified Q2 commit.

## CI-only Q2 convergence candidate

`b953c9922cc1096e0e88455dab6746c01a9d27f9` contains Q2 plus only three CI/compatibility
fixes, before any Q3 runtime/schema implementation:

1. `f447fa4`: FIRST atomic commit, pin 3.9 to ubuntu-22.04 and 3.12 to ubuntu-24.04.
2. `48fa4e0`: inherited `PYTHONPATH=src` for -S subprocess tests and safe close of
   body-less fallback HTTPError on 3.9.
3. `b953c99`: supply closeable BytesIO bodies in HTTPError test fixtures; all
   existing assertions preserved, no test skip/filter/removal introduced.

Actual full four-job CI success:
https://github.com/flykingvip-cloud/knowledge-sdk/actions/runs/45531017247

Earlier actual failures are retained (not silently represented as passes):
https://github.com/flykingvip-cloud/knowledge-sdk/actions/runs/45529955819
https://github.com/flykingvip-cloud/knowledge-sdk/actions/runs/45530700743

The first runtime CI also caught an old free-form task label in the historical
MCP wire fixture; setup was migrated to register a real context and its schema
expectation advanced to v5, with behavior assertions unchanged. Failed run:
https://github.com/flykingvip-cloud/knowledge-sdk/actions/runs/45532084157
Fixed fixture full-matrix pass:
https://github.com/flykingvip-cloud/knowledge-sdk/actions/runs/45532562617

## Exact remaining convergence plan — NOT executed

The parent reserved main/tag writes for separate explicit confirmation despite
conditional permission in the detailed taskbook. Enterprise/StratAI integration
remains paused. We neither assert a technical permission denial nor call the
Q2 Git baseline fully converged.

After the owner confirms the exact target:

1. Re-read main, tag refs, protections/rulesets and candidate CI checks. Verify
   main is still 0ed15b9 (or review intervening work) and candidate is still the
   intended Q2-only `b953c9922cc1096e0e88455dab6746c01a9d27f9`.
2. If main is unchanged and policy permits, fast-forward main **only** to that
   verified Q2+CI candidate, not to the Q3 feature head. If protections changed,
   use their required review path after separate authorization; do not bypass.
3. Verify remote main and, only on explicit tag approval, create the previously
   absent annotated `v2.0.0` tag on the confirmed Q2 candidate. Never move an
   existing tag, force-push, release or deploy.
4. Reverify refs and archive the actual convergence SHA. Q3 remains a separate
   feature branch for independent review; no Q3 merge is implied.

Status: **CI gate PASS; main/tag convergence PENDING_EXPLICIT_CONFIRMATION**.
No PR, merge, tag, release, deployment or access-policy change occurred here.
