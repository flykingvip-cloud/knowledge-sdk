# L4 real reverse proxy + browser evidence — PENDING

The implementation executor has performed **HTTP preflight only**, not browser
interaction. No browser, Playwright, CDP or Puppeteer was driven from Shell.
No headless run, console-error count, page-error count or browser pass is claimed.
Parent must dispatch its sanctioned computerUse/browser agent and return evidence.

## Ready isolated fixtures (2026-11-25 Asia/Shanghai)

| Engine | Real nginx URL | One-use test bearer file (outside git) |
|---|---|---|
| SQLite v4 | http://127.0.0.1:18474/kb-prod/ui | `/workspace/knowledge-sdk-q2m4-artifacts/l4-sqlite.jwt` |
| PostgreSQL 17 + pgvector, non-superuser | http://127.0.0.1:18475/kb-prod/ui | `/workspace/knowledge-sdk-q2m4-artifacts/l4-postgres.jwt` |

Nginx **1.26.3**, stripped `/kb-prod/` upstream prefix, ASGI `root_path=/kb-prod`.
Both backends use `auth_mode=oidc`, RS256 test keys, directory enforcement,
`dev_insecure=False`, `enable_demo_switcher=False`. No real enterprise IdP is
claimed. Secure cookies are disabled **only for these loopback HTTP fixtures**;
production `create_app` defaults to Secure cookies. HTTP preflight confirms UI,
config, same-origin JS and health 200/no-store, disabled signer 404/no-store.

## Parent computerUse instructions

1. Start console/page-error capture **before navigation**, in separate fresh
   contexts for each engine if possible. Do not print bearer files, JWTs or
   cookies; do not put any token in URLs or screenshots.
2. Open the URL. Confirm no `#identity-form`, no `#preset`, no demo switcher.
3. Use **Or import a bearer token file** (`#token-file`) to upload the matching
   local file. This is the real app authentication boundary: file is read only in
   browser memory, verified via `POST /v1/auth/session`, exchanged for an opaque
   HttpOnly cookie; both token inputs are cleared. No demo signing/bypass exists.
4. Wait for `#status` to start `Authenticated.` and two authorized space names.
   Click **Load authorized documents** and **Search evidence** (query `alpha`).
   Expect `doc-published` / `APPROVED_PUBLIC_MARKER`. No `doc-draft`,
   `DRAFT_NEVER_LEAK_MARKER`, foreign space or `FOREIGN_NEVER_LEAK_MARKER` may
   appear in returned DOM/API content. Capture DOM text after inputs are empty.
5. Citation input: `kb://org/m4-browser/doc/doc-published@1`. Click **Verify
   citation** and assert a successful verified tool result: `result.structuredContent.valid === true`
   and `current_status === 'valid'` (not merely nonempty).
6. Pack ID: `browser-pack`; click **Read pack**, assert sealed pack and digest.
   Click **Load alerts**; expect `access_revoked`, `doc-impact` and an affected
   `impacted-pack` identifier. Alerts contain identifiers, never source text.
7. Using browser request API (not navigation that intentionally pollutes the
   page console), GET `/kb-prod/ui/demo/sign` and expect 404/403. Assert no-store
   responses and same-origin `/kb-prod/ui/assets/enterprise.js` loading.
8. Record **all** console errors, unhandled page errors and failed requests, with
   source. Zero cannot be asserted without actual listeners/measurement. Take
   sanitized screenshots/DOM evidence; redact credentials if any appear.
9. Return actual tool/script/modality, URLs, timestamps Asia/Shanghai, assertions,
   logs and artifact paths to the parent. Visible/manual computerUse is real
   browser evidence, but **not** proof of the requested *headless* modality.
   If headless execution is unsupported, keep that acceptance criterion OPEN.

`l4_playwright_recipe.py` is the reproducible script, **not executed by executor**.
If the sanctioned browser agent cannot execute scripts through its browser
surface, use its native actions and honestly state the modality. Do not execute
this script with Shell or bypass the browser-tool requirement.

## Lifecycle

See `browser-fixtures.json` for exact owned PIDs and stop commands. Keep only
these isolated fixtures and their PG cluster alive until parent browser testing
finishes. Stop HTTP fixtures gracefully before the cluster so PG schemas clean
up. Tokens expire six hours after fixture startup, are one-use, and must not be
reused after a successful login exchange; restart only owned fixture with a new
empty work directory if regeneration is needed.
