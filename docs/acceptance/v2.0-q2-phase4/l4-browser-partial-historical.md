# L4 — BROWSER INTERACTION VERIFIED; HEADLESS / UNMEASURED ASSERTIONS OPEN

## Actual evidence and attribution

Parent-dispatched sanctioned computerUse used `browser_run_code` and
`browser_take_screenshot` on 2026-11-25, beginning 08:54:37 with PG authentication 08:55:58
and subsequent captures, Asia/Shanghai (UTC+8). Browser-reported navigation/auth timestamps are recorded in the supplied
observation files; the PG capture followed 08:55:58. No browser was driven through
Shell/CDP/standalone Playwright by the implementation executor. The executor
reviewed the supplied observations and screenshots, not an independent rerun.

- SQLite: http://127.0.0.1:18474/kb-prod/ui
- PostgreSQL 17 + pgvector: http://127.0.0.1:18475/kb-prod/ui
- Real isolated nginx 1.26.3 stripped `/kb-prod/`; production OIDC mode, test RS256
  issuer keys, directory enforced, no demo/dev-insecure. This is not a production
  IdP or enterprise-admission certification.
- Legitimate file-import bearer→`/v1/auth/session` verification→opaque HttpOnly
  cookie boundary. Parent observed both token inputs cleared before captures.
  No JWT/cookie was put in a URL, log or screenshot.

## Measured browser results — BOTH engines

- Authenticated status and exactly two authorized spaces: Controlled enterprise
  evidence and Connector sources; no identity-form/preset/demo-switcher UI.
- Authorized documents/search `alpha` show `doc-published` and
  `APPROVED_PUBLIC_MARKER`. Specified draft/foreign identifiers and
  `DRAFT_NEVER_LEAK_MARKER` / `FOREIGN_NEVER_LEAK_MARKER` were absent from the
  observed document/search DOM. This is not an exhaustive API-body claim.
- Citation `kb://org/m4-browser/doc/doc-published@1` rendered verified tool JSON:
  `result.structuredContent.valid === true`, `current_status === "valid"`.
- `browser-pack` rendered sealed with a 64-character SHA-256 digest; alerts show
  `access_revoked`, `doc-impact`, `impacted-pack`, without known source markers.
- Captured same-origin UI/CSS/enterprise.js/config/session/kbs/documents/search/
  MCP/pack/alerts responses were 200 with Cache-Control: no-store.
- Captured navigation/auth/document-search/citation-pack-alert phases measured
  **0 console errors, 0 unhandled page errors, 0 failed requests**. This is scoped
  to captured phases, not a claim of zero errors over every interaction.

Screenshots: l4-sqlite-browser.png, l4-postgres-browser.png. Supplied observations:
l4-browser-observations.md and l4-browser-dom-log.md. These two supplied text files
are byte-identical narrative/event summaries, not independently captured full DOM
or raw network-body dumps. Their original contents are preserved. Hashes and
sizes: l4-evidence-manifest.json. The executor visually reviewed screenshots;
only synthetic evidence/identifiers are visible, no token/cookie/private key.

## Exact unmet requirements / limitations

1. **Headless modality UNVERIFIED.** The sanctioned browser surface did not expose
   a headless flag/runtime confirmation. Scripted managed browser interaction is
   real browser evidence, but must not be relabelled a confirmed headless run.
2. **Browser demo signer status UNMEASURED.** Direct page/context request APIs were
   unavailable and no browser navigation to the signer was performed. No browser
   404/403 assertion is claimed.
3. **Browser API JSON response-body leakage UNMEASURED.** Rendered DOM assertions
   passed; the browser surface could not independently expose response bodies.
4. Fresh contexts per engine were unavailable. SQLite UI showed `Signed out`
   before PG navigation/authentication in the same managed context. The signout
   wrapper timed out waiting for incorrect expected text; actual status was
   `Signed out`. Its event arrays were not returned. That step's errors are
   unmeasured, not zero. The first SQLite navigation also lacked returned event
   arrays; a second pre-auth navigation was measured successfully.
5. To close full L4: rerun through an approved browser surface with demonstrated
   headless runtime, fresh contexts, direct negative signer status and independent
   JSON-body inspection, and complete event capture including signout/initial
   navigation. Retain the measured successes above; do not substitute HTTP-only
   evidence for these browser-specific missing assertions.

`l4_playwright_recipe.py` remains a reproducible **NONEXECUTED** headless recipe;
only an approved browser agent may run it through a supported browser surface,
never Shell. It is not proof of execution. Extend capture as needed to cover all
missing requirements above, including full response-body and failed-request
checks. New isolated fixtures/tokens would be needed for another run.

## Separate L3 HTTP supplement — NOT browser evidence

After the browser run, normal urllib GET and POST requests through both owned
nginx prefixes returned 404/no-store for `/kb-prod/ui/demo/sign`:
l3-browser-boundary-supplement.json. Existing real dual-engine HTTP probes also
asserted foreign/draft marker absence in authenticated search JSON
(live_enterprise_probe.py lines63–64, l3-enterprise-http.log). These are distinct
L3 HTTP measurements, not browser request/body measurements and not a blanket
proof of every possible response body. No browser cookie/token was read/reused.

## Lifecycle and acceptance

All owned backend/nginx/PG services are STOPPED. The shutdown receipt records
zero other client connections, removal of three remaining owned disposable
sdk_test_* schemas, zero remaining test schemas, no listener on the five owned
ports, all five owned PIDs absent, and no postmaster.pid. See
infrastructure-shutdown.json and browser-fixtures.json (historical URLs only).

Overall L4 remains PARTIAL / OPEN, not all-green. Independent M4/L5 and external
enterprise security/architecture approval remain OPEN; Q2 exit is not approved.
