# v1.2 Phase 1: host gateway and operational contract

Scope: baseline/B08 only. No policy engine, schema v2, anchors, MCP, training,
model calls or production rollout is delivered here. Core remains stdlib-only.

## Authentication / worker deployment

`create_app(..., replay_store=None, fallback_secrets=(), ui_prefix='/ui')`
creates one bounded, locked InMemoryReplayStore **per app** by default. This is
only appropriate for one worker. Every worker/instance sharing a signing trust
boundary MUST share a `SQLiteReplayStore('/dedicated/local/auth-replay.sqlite3')`
on one local host, or an operator-supplied atomic ReplayStore for distributed
hosts. SQLite WAL is not a multi-host/network-filesystem solution. Capacity is
50,000 live nonces; replay/capacity/database failures deny authentication.
Use restrictive OS ownership/permissions for the replay database and directory;
never use the business database. Startup refuses existing unrelated tables.
Do not remove the replay database while any signed request could remain valid.
Nonce retention is 2*max_age+1 seconds from consumption (covers future stamps).
Nonce is global across signing keys/actors within this replay store. Invalid
signatures/claims do not consume a nonce. Legacy `seen` is preserved for old
callers; it is not thread/process safe. Explicit replay_store takes precedence.

CLI: `--replay-db /dedicated/path/replay.sqlite3 --ui-prefix /kb/ui`.
`KNOWLEDGE_AUTH_SECRET` is the current >=32-character secret;
`KNOWLEDGE_AUTH_FALLBACK_SECRETS` is a comma-separated list of old >=32-character
secrets. Empty CSV entries are ignored; short nonempty entries fail closed.
No .env loading, secret logging, or browser secret distribution is added.
Rotate: deploy new verification key plus old fallback on every worker, switch
host signer, wait for old maximum request window, then remove fallback. Keep
shared replay protection across rotations. No key or token is committed here.

Default Actor additions: `policy_generation='0', session_id=''` (strings only).
These default claims are omitted by signed_headers to preserve exact old wire
bytes; nondefault values are signed. JSON encode/decode retains both fields.
They reserve context only: no revocation/policy engine semantics are implied.

Legacy HMAC remains six newline-separated UTF-8 fields: uppercase method,
**exact raw upstream request target including query**, Actor Base64URL JSON,
integer timestamp, nonce, lowercase SHA256(body). No trailing newline.
If X-KB-Agent or X-KB-Purpose is present, append two lines: exact agent header
(or empty), exact purpose header (or empty). Missing both means no extra lines.
Removal/addition/change cannot downgrade a valid extended signature. Agent is
a <=8192-byte Base64URL JSON object with nonempty agent_id/org_id, matching the
Actor tenant. Purpose is read, ground_internal_llm, ground_external_llm, export,
or eval_and_train. These are signed context, NOT permissions or consent.
`request.state.agent` is a dict or None; purpose defaults to read. verify_headers
still returns Actor. dev_insecure remains explicitly unsafe loopback-only CLI
legacy mode; never use it in production.

## URL / proxy / CSP contract

UI prefix is independent of API routes: `/kb/ui` does NOT move `/v1` to `/kb/v1`.
Prefixes normalize one trailing slash and accept only slash-delimited ASCII
letters, digits, underscore and hyphen. Root, empty segments, dots, encoded
separators, whitespace, queries/fragments and `/v1` or descendants are rejected.
Use a distinct path not already owned by another host application. Forwarded
headers are NOT used to choose asset/API bases or enable development signing.
UI config and app OpenAPI versions come from knowledge_sdk.__version__.

Without ASGI root_path: `/kb/ui`, `/kb/ui/config`, `/kb/ui/assets/*`; API `/v1/*`.
With trusted ASGI root_path `/gateway`: browser UI `/gateway/kb/ui`, API
`/gateway/v1/*`. The proxy must set a consistent server-controlled root_path;
it may strip `/gateway` upstream, or preserve it if the ASGI router supports it.
`ui_base` and `api_base` in server config control browser URLs. `signature_base`
reflects the raw prefix actually observed by ASGI for the config request.
Gateway signers must sign the EXACT target received upstream after any proxy
rewrite, not a decoded/re-encoded URL. Proxy rewrites must be identical for UI
config, signer and business API. The optional browser auth callback receives
this upstream `target`; the browser fetch uses api_base separately. Never use
untrusted browser-provided target/Actor as an unrestricted signing oracle.

Static bootstrap remains external ES modules; module-relative config and i18n
resolve from the mounted assets. CSP is strict self-only (no inline scripts,
CDN, fonts or eval), with nosniff, no-referrer and no-store on UI responses.
Business responses are no-store. User documents, excerpts and metadata are
never translated by the UI. Default language and persisted switch are unchanged.

## Production integration checklist (host work, not implemented here)

- Default `enable_demo_switcher=False`. Signer routes return 404 regardless of
  headers. Identity simulation controls are disabled. Do not deploy --demo-seed.
- Authenticate same-origin host session on the gateway. Resolve Actor from
  trusted server directory/session each request; reject client identity headers.
- Bind org/session and current policy generation, enforce session expiry and
  revocation at gateway, strip client X-KB-* headers, generate fresh nonce/time
  and HMAC server-side. No signing keys or raw session material in UI config.
- Enforce CSRF tokens + Origin/Sec-Fetch checks for mutations, secure HttpOnly
  SameSite cookies, TLS, deny cross-origin credentials, log no authentication
  material. Disable public schema routes at gateway when needed.
- Configure shared replay across all workers, monitor capacity, protect replay
  files, exercise key rollover. Test percent-encoded paths and ordered queries.
- Gateway session/Actor hooks and directory invalidation are not SDK features
  in this phase. UI callback alone is not a host authentication implementation.

## Evidence boundaries

L1 stdlib and L2 dependency-enabled tests are separate runs; skips never count as
passes. L3 local real HTTP does not imply live Qdrant or real semantic retrieval.
L4 requires a real browser and is NOT_RUN without it. L5 is architect B08 review,
not self-approved. Phase 2 remains locked pending explicit acceptance.
