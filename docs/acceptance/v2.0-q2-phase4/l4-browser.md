# L4 hard requirements — PASS (actual independent hosted headless CI)

Run: https://github.com/flykingvip-cloud/knowledge-sdk/actions/runs/45526947873
Job: https://github.com/flykingvip-cloud/knowledge-sdk/actions/runs/45526947873/job/138912543003
GitHub reports completed/success; job and every step, including service-container
teardown, succeeded. **Tested SOURCE SHA: `1186b066e984c29fa347bdd946fdc63ecb50e950`**. Final documentation-only
commit is separate; it was not the commit tested by this run. No runtime/core
metadata changed after the previously accepted implementation.

## Four hard requirements and actual proofs

| Requirement | Measured result | Evidence under l4-ci-run/ |
|---|---|---|
| Auditable HEADLESS runtime | Playwright1.56.0 launched Chromium141.0.7390.37 with headless=True; runtime Browser.getBrowserCommandLine returned --headless, headless_shell executable and --ozone-platform=headless; Browser.getVersion product/user-agent HeadlessChrome141.0.7390.37 | headless-runtime.json; workflow-jobs.json; job.log |
| Independent NEW contexts per engine | Two distinct CDP browserContextIds, distinct targetIds; both started with zero cookies and zero storage origins | independent-contexts.json |
| Browser negative requests and JSON isolation | Each context's real APIRequestContext GET and POST to BOTH /ui/demo/sign and /kb-prod/ui/demo/sign returned404/no-store; bodies recorded. Eight independent content API JSON bodies per engine inspected semantically and for forbidden fixture plaintext, plus rendered DOM | sqlite-browser-log.json, postgres-browser-log.json; *-dom.txt; *-browser.png |
| Continuous error capture | Listeners installed BEFORE first application goto and left attached through genuine UI logout, networkidle and context close. Both engines: console errors0, page errors0, requestfailed0; all console messages retained, no event exclusions | *-browser-log.json, summary.json, *-signed-out-dom.txt |

SQLite capture: 2026-11-25 **09:37:46.714–09:37:48.433 Asia/Shanghai**.
PG capture: **09:37:48.434–09:37:50.297 Asia/Shanghai**. Timestamped logs use UTC+8;
original GitHub job logs retain their original UTC timestamps as raw evidence.
The managed browser from the earlier partial run was NOT attached or reused.
No browser automation was executed on the box or a self-hosted user machine.

## Real application assertions on both engines

Twelve grouped assertions per engine, not twelve independent benchmark cases:
production UI without demo controls; legitimate RS256 bearer-file/session exchange
with inputs cleared; exactly authorized controlled/sources spaces; published
`doc-published`/APPROVED_PUBLIC_MARKER search; verified citation
`structuredContent.valid=true` and `current_status=valid`; sealed browser-pack and
64-hex digest; access_revoked/doc-impact/impacted-pack alerts; both signer paths
fail closed; independent JSON isolation; actual logout clears UI/cookie and
subsequent browser-context API access returns401; all required page responses200
and no-store. New contexts and runtime proof are additional assertions.

Independent browser API JSON inspection covers spaces, documents, published and
denied-marker searches, citation JSON-RPC, pack and alerts. Forbidden fixture
identifiers/markers and revoked source plaintext are absent from these bodies and
captured DOM. Semantic published-state/authorized-space checks accompany string
checks; this is measured fixture coverage, not universal proof about every input.
Content bodies come from genuine authenticated browser-context requests, not
mocked data or HTTP performed by the box. Auth/session/logout page response
headers/status and UI/cookie/authorization semantics were checked; no claim that
an unconsumed page logout Response.json body was successfully read is made.

### What zero errors means

All page console messages, pageerror events and requestfailed events are retained.
No real events were filtered to obtain green. Both page event arrays and all page
response statuses are checked. Expected direct APIRequestContext HTTP negatives
are separately logged: four404 signer responses and one401 post-logout response
per engine. HTTP404/401 responses are not transport failures or page navigations;
we do not call them successful HTTP responses or silently subtract page events.
Logout is followed by settled network and context close before final assertions;
the previous initial-navigation/signout capture gaps are closed in this run.

## Environment, reproducibility and privacy

Workflow .github/workflows/q2-m4-l4.yml: one standard GitHub-hosted ubuntu24.04 job,
15-minute job timeout, read-only contents permission, no new secrets/billing/access
changes, seven-day bounded artifact retention. Repository is public; no paid
runner/large runner/self-hosted compute was activated. PostgreSQL16 + pgvector
0.8.7 uses sdk_m4 with NOSUPERUSER/NOBYPASSRLS; real nginx strips /kb-prod to
production OIDC backends with demo/dev-insecure disabled. RS256 keys are synthetic
local test keys, NOT enterprise IdP acceptance. Playwright default runtime flags
(including its CI --no-sandbox) are retained verbatim for audit; no application CSP
or browser error policy was weakened. No model/embedding/Qdrant endpoint called.

Reproducer: push a change to the narrowly scoped workflow/runner on this feature
branch. New workflows cannot be workflow_dispatch'ed without default-branch
registration, so the authorized normal push trigger was used; main is untouched.
`l4_ci_runner.py` refuses execution unless GITHUB_ACTIONS=true and
RUNNER_ENVIRONMENT=github-hosted on Linux. This guard is not permission to spoof
those variables on the box. The old l4_playwright_recipe.py is historical,
nonexecuted and superseded by the actual executed CI runner.

No traces/HARs/auth headers/cookie values/private token files are uploaded. Tokens
were imported once through real auth, never put in URLs or logs/screenshots.
Screenshots were visually reviewed; token controls are empty and data synthetic.
GitHub original artifact14983845263 archive digest independently matched downloaded
bytes: `02ff6ab56ff999f1e0104fa0d1dd45f67e14adf84db70603b1426df3d0e51d32`.
Every extracted file matched the verified archive. Hashes: l4-ci-run/manifest.json.
Persistent archive/logs/downloads: /workspace/knowledge-sdk-q2m4-artifacts/ci-45526947873*.

## Transparent failures and regression boundaries

Two prior CI runs failed and are preserved in l4-ci-attempts/:
- 45525909492 / fc221ec: test harness string-eval wait violated unchanged CSP,
  producing one actual pageerror. Fixed using locator assertions, not CSP bypass.
- 45526254425 / e025ff5: bounded180s timeout reading unconsumed page logout
  Response.json. Content JSON checks now use independent browser-context requests;
  genuine UI/cookie/authorization logout and all event checks remain mandatory.

A transient GitHub500 push and watch TLS timeout were retried using the same
sanctioned operations; neither was represented as a test pass. Current run passed
46 enterprise regression tests with strict ResourceWarning handling. No product
source changes were needed. Existing generic tests.yml independently fails its
Python3.9 setup on ubuntu-latest26.04 (already failing at84f796c); it is not the L4
workflow and has not been silently relabelled green or modified outside scope.
Previously measured full770-method/dual100/legacy75 evidence remains applicable to
unchanged runtime, not newly claimed as rerun in this CI job.

## Cleanup and remaining Q2 gates

CI summary verifies owned backend/nginx processes stopped, zero other application
client connections and zero sdk_test_* schemas after cleanup. GitHub job log/API
confirm PostgreSQL service container and network removed. Earlier box fixtures
remain stopped (infrastructure-shutdown.json); no box browser/service was started
for this CI work. L4 four hard requirements are now satisfied for these isolated
fixtures. **Q2 exit remains HOLD** pending final independent M4/L5 review and
actual enterprise production-admission approval. Live enterprise IdP/SCIM,
Q1 Qdrant/models/PDF-OCR/external MCP boundaries remain OPEN. No tag/release/deploy.

Earlier sanctioned managed-browser observations are preserved in
l4-browser-partial-historical.md and their original observation/screenshot files;
their limitations were real and are not retroactively rewritten as headless.
