# L4 browser observations — knowledge-sdk Q2-M4

Run date: 2026-11-25 (Asia/Shanghai, UTC+08:00). Browser validation began 08:54:37 and continued through the PostgreSQL evidence capture after 08:55:58.

## Modality / scope
- Interaction: sanctioned `browser_run_code` (browser-controlled Playwright script surface) for navigation, file-input upload, UI actions, DOM text assertions, and page event listeners; `browser_take_screenshot` for screenshots. No Shell/CDP/standalone Playwright browser driving was used.
- The tool exposes scripted browser actions and console/pageerror/requestfailed listeners, but does not expose a headless-mode flag or whether the managed browser runtime is headless. **Headless modality is unverified/open; no headless claim is made.**
- A fresh browser context per engine was not available through the sanctioned surface. SQLite was explicitly signed out (UI status observed as `Signed out`) before navigating to PostgreSQL, and the PG token was then uploaded once.
- Token contents were never read, emitted, or included in screenshots; no token was put in a URL. After each token-file upload, both the OIDC bearer textbox and `#token-file` value were observed empty before content evidence was captured.
- No fixture, code, or service was modified or stopped.

## SQLite — `http://127.0.0.1:18474/kb-prod/ui`
Observed times: UI navigation/reload 08:54:49.378; token upload/auth 08:54:56.957 (Asia/Shanghai).
- No `#identity-form`, no `#preset`, and no demo-switcher text in the loaded UI.
- Authenticated status: `Authenticated. Only authorized data is displayed.` Two authorized spaces: `Controlled enterprise evidence · controlled`; `Connector sources · sources`.
- Token inputs cleared: yes.
- Load authorized documents: `doc-published` present. DOM checks absent: `doc-draft`, `DRAFT_NEVER_LEAK_MARKER`, `foreign-space`, `FOREIGN_NEVER_LEAK_MARKER`.
- Search query was `alpha`; result contains `doc-published` and `APPROVED_PUBLIC_MARKER`. Same four forbidden-string checks absent from observed result DOM.
- Citation URI `kb://org/m4-browser/doc/doc-published@1`: visible tool-result JSON asserted `result.structuredContent.valid === true` and `current_status === "valid"`.
- `browser-pack`: visible pack status `sealed`; digest `0ec6f2bbeb6d0a6da8826b1bbffa12ff1d7ac629020c8b43dbf1b724566ce1c9`.
- Alerts: observed `access_revoked`, `doc-impact`, and `impacted-pack`. Alert summaries contained identifiers/impact metadata only; known source markers were absent.
- Captured same-origin responses: `/kb-prod/ui` 200 no-store; `/kb-prod/ui/assets/workbench.css` 200 no-store; `/kb-prod/ui/assets/enterprise.js` 200 no-store; `/kb-prod/ui/config` 200 no-store; `/kb-prod/v1/auth/session` 200 no-store; `/kb-prod/v1/kbs` 200 no-store; `/kb-prod/v1/documents` 200 no-store; `/kb-prod/v1/search` 200 no-store; `/kb-prod/v1/mcp` 200 no-store; `/kb-prod/v1/packs/get` 200 no-store; `/kb-prod/v1/impact/alerts` 200 no-store.
- For the captured navigation/auth/documents+search/citation+pack+alerts phases: console errors 0, unhandled page errors 0, failed requests 0. Event details were empty in those captured phases.

## PostgreSQL — `http://127.0.0.1:18475/kb-prod/ui`
Observed times: UI navigation 08:55:53.726; token upload/auth 08:55:58.592 (Asia/Shanghai).
- No `#identity-form`, no `#preset`, and no demo-switcher text in the loaded UI.
- Authenticated status: `Authenticated. Only authorized data is displayed.` Two authorized spaces: `Controlled enterprise evidence · controlled`; `Connector sources · sources`.
- Token inputs cleared: yes.
- Load authorized documents: `doc-published` present. DOM checks absent: `doc-draft`, `DRAFT_NEVER_LEAK_MARKER`, `foreign-space`, `FOREIGN_NEVER_LEAK_MARKER`.
- Search query was `alpha`; result contains `doc-published` and `APPROVED_PUBLIC_MARKER`. Same four forbidden-string checks absent from observed result DOM.
- Citation URI `kb://org/m4-browser/doc/doc-published@1`: visible tool-result JSON asserted `result.structuredContent.valid === true` and `current_status === "valid"`.
- `browser-pack`: visible pack status `sealed`; digest `ac0050c15bfcc54296080e69824b24ce2cdf39d6ee004257bd9bde8fd9ad76ac`.
- Alerts: observed `access_revoked`, `doc-impact`, and `impacted-pack`. Alert summaries contained identifiers/impact metadata only; known source markers were absent.
- Captured same-origin responses: `/kb-prod/ui` 200 no-store; `/kb-prod/ui/assets/workbench.css` 200 no-store; `/kb-prod/ui/assets/enterprise.js` 200 no-store; `/kb-prod/ui/config` 200 no-store; `/kb-prod/v1/auth/session` 200 no-store; `/kb-prod/v1/kbs` 200 no-store; `/kb-prod/v1/documents` 200 no-store; `/kb-prod/v1/search` 200 no-store; `/kb-prod/v1/mcp` 200 no-store; `/kb-prod/v1/packs/get` 200 no-store; `/kb-prod/v1/impact/alerts` 200 no-store.
- For the captured navigation/auth/documents+search/citation+pack+alerts phases: console errors 0, unhandled page errors 0, failed requests 0. Event details were empty in those captured phases.

## Unmeasured / caveats
- The browser tool does not permit direct HTTP requests through `page.request`/`context.request`, and the user prohibited navigating to `/kb-prod/ui/demo/sign`. Therefore `/kb-prod/ui/demo/sign` status 404/403 is **unmeasured** (not assumed).
- Browser response bodies are not exposed by this tool. Leakage checks above are on app-rendered DOM evidence; API response bodies were **not independently inspected**, so API-body leakage is unmeasured.
- One wrapper script clicked SQLite Sign out successfully, then timed out waiting for the wrong expected status text (`Sign in through the configured issuer`); the observed actual status in the timeout diagnostics was `Signed out`. The page was not retried for signout; a fresh captured PG navigation then proceeded. The local event arrays from that sign-out wrapper call were not returned, so that narrow step's event log is unmeasured. This was a wrapper wait mismatch, not a reported page error.
- The very first SQLite navigation's listener arrays were not returned; a second pre-auth SQLite navigation was captured with zero console/page/request failures and all loaded resources.

## Evidence files
- SQLite screenshot (captured after token inputs cleared): `/workspace/knowledge-sdk-q2m4-artifacts/l4-sqlite-browser.png`
- PostgreSQL screenshot (captured after token inputs cleared): `/workspace/knowledge-sdk-q2m4-artifacts/l4-postgres-browser.png`
- Sanitized DOM assertion summary and captured network/event log summary: `/workspace/knowledge-sdk-q2m4-artifacts/l4-browser-dom-log.md`. No bearer token or cookie values are included.
