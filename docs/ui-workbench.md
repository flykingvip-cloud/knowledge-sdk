# Knowledge SDK Workbench

Optional, offline, framework-free UI for the SDK's `[http]` service. The core
package still has `dependencies = []`. No Flask, host-product imports, npm,
frontend compilation, external fonts, scripts, CDN, telemetry, or model startup.

## Start a disposable local demo

From a checkout (after installing the HTTP extra):

```sh
python -m pip install -e '.[http]'
python -m knowledge_sdk.server --host 127.0.0.1 --port 8090 --demo-seed
# Open http://127.0.0.1:8090/ui
```

In this box's prepared checkout, the single startup command is:

```sh
PYTHONPATH=src .venv-http/bin/python -m knowledge_sdk.server --host 127.0.0.1 --port 8090 --demo-seed
```

Stop with Ctrl-C. Demo data lives **only in memory**, and its random HMAC key
exists only in the server process. The CLI refuses a real database, non-loopback
binding, `--dev-insecure`, or `--no-ui` together with `--demo-seed`. It disables
proxy-header trust. It does not touch other services or reserve their ports.
Demo seed creates three explicit-tier spaces, six documents, four ACL policies,
and one consumer binding. It never calls an embedding or model service.

Try `handbook` (everyone), `aurora` (engineering incl. children), `budget`
(analyst + confidential), and `nebula` (author only). Compare admin, engineering
lead, engineering/platform employee, marketing employee, and visitor. A custom
actor supports raw organization roles, department / ancestor chains, clearance,
managed departments, space roles, and clearance tags. Only the demo treats
these UI fields as arbitrary test claims; they are not production identity.

## Four views and API map

The layout uses a dark workspace rail, an expandable global identity bar, and
responsive content cards. On narrow screens the rail becomes horizontal
navigation. All content uses text nodes, not interpolated HTML. The following
interface map is the reproducible UI reference; no browser screenshots are
claimed by this implementation's HTTP/static acceptance suite.

| View / interaction | SDK operation / route | What to check |
|---|---|---|
| Spaces: enterprise / department / personal cards, type filter, create | `list_kbs`, `create_kb`: `GET/POST /v1/kbs` | Explicit `space_type`, ownership; manage/upload badges from backend |
| Capability badges | `can_manage_kb`, `can_upload_to_kb`: `POST /v1/kbs/can-manage`, `/can-upload` | No inferred admin privilege in the UI |
| Documents: upload text / Markdown / file; same doc_id creates revision | `ingest`: `POST /v1/documents` | Optional tagged `DocumentACL` written **atomically** with document/version; 16 MiB UI limit |
| Current policy, selected version full text, all history metadata, chunks | `inspect_document`: `POST /v1/documents/inspect` | Fresh content authorization before any detail; no unauthorized metadata |
| Four-level policy editing | `set_document_acl`: `POST /v1/documents/acl` | `org_public`, `department` (+ children), `role_clearance`, `personal_only` |
| Archive (all versions) | `archive`: `POST /v1/documents/archive` | Disappears from listing/search/preview/reference; history retained |
| Scope + mode search | `search`: `POST /v1/search` | `KnowledgeScope`, scores, safe highlight spans, excerpt truncation + remaining chars |
| Explicit ask only | `ask`: `POST /v1/ask` | Answer, expandable versioned citations + hash, `model_called`; no evidence ⇒ refused / false |
| Search evidence → cite / attach | `create_ref`, `attach`: `POST /v1/references/create`, `/attach` | Optional selected consumer binding; versioned `KnowledgeRef` + `MaterialReceipt` |
| Bindings list / create | `list_consumer_bindings`, `bind_consumer`: `GET/POST /v1/bindings` | Organization + user isolation; revalidate scopes after permission changes |
| Receipt list / manual tamper check | `verify_ref`: `POST /v1/references/verify` | Valid receipt or explicit tamper error; editable JSON allows negative checks |

**Deliberate contract boundaries:**

- Archive is **document-wide**, including all historical versions. There is no
  independent historical-version archive or deletion API. The UI labels this
  explicitly; immutable versions are preserved for provenance.
- `KnowledgeRef.source_uri` follows the existing SDK contract, e.g.
  `kb://org/demo-org/doc/<id>@1#chunk=<id>` (`@1`, not a new `@v1` dialect).
- Bindings are persisted in SQLite by organization and user. References/receipts
  displayed by the UI are the **current identity's in-memory browser session**,
  not an invented durable audit ledger. Switching identity clears all results,
  document data, forms, selections, refs and receipts; late responses are ignored.
- A plain demo has keyword retrieval and the SDK's local extractive answer
  generator. Hybrid/vector controls are disabled unless an embedder + vector
  index are configured on the server client. No fake semantic backend is used.
- A configured `answer_generator` runs only on explicit ask and only after
  authorized evidence. The default extractive generator reports
  `model_called=false` even for answered questions. UI navigation never asks.
- PDF requires the optional `[parsers]` extra; unsupported files surface normal
  SDK errors. The UI does not parse PDF with browser libraries.

## Production authentication and mounting

```python
from knowledge_sdk.server.app import create_app

app = create_app(client, auth_secret=secret_from_host,
                 enable_ui=True, enable_demo_switcher=False)
# create_app(..., enable_ui=False) removes every /ui route and static asset.
```

Production startup, using your existing secure environment provisioning:

```sh
# KNOWLEDGE_AUTH_SECRET must already be set to a strong value of >=32 chars.
python -m knowledge_sdk.server --db knowledge.sqlite3 --host 127.0.0.1 --port 8090
# Add --no-ui to serve signed APIs only.
```

`/ui`, `/ui/`, `/ui/assets/*` and `/ui/config` are public, non-sensitive static
shell/capability routes. **Every `/v1` business API retains the existing HMAC
middleware**, timestamp/body/target binding and replay checking. Merely opening
the UI grants no access. Unsigned actor headers still return 401. Production
has no demo signer route (404); its identity controls are disabled.

A real host must authenticate the user via its own session/Directory, derive
Actor claims server-side, and proxy/sign same-origin API requests. A gateway
can inject HMAC headers before forwarding `/v1` calls. Alternatively, the host
can load a same-origin bootstrap script defining:

```javascript
window.knowledgeWorkbenchAuth = async ({method, target, body}) => {
  // Ask YOUR authenticated same-origin gateway for headers for this exact
  // request. The gateway derives Actor itself, never from Workbench fields.
  // Return {"X-KB-Actor": ..., "X-KB-Signature": ..., ...}.
};
```

Load that host script before the Workbench ES module (e.g. through the host's
HTML integration). No signing secret, token persistence, password form, or
browser-side HMAC signer is included. Without a configured gateway production
shell loading succeeds, but business calls correctly fail closed with 401.
CSRF/session protection of an embedding host gateway remains the host's job.

### Explicit local-only demo signer

`enable_demo_switcher=True` registers only `POST /ui/demo/sign`. It validates
an Actor and returns fresh HMAC headers for an allowlisted operation's exact
method/target/body. The UI then sends the normal signed `/v1` request; it does
not execute domain calls via an authentication bypass. The signer requires:

1. HMAC enabled with a valid secret; incompatible with `dev_insecure`.
2. A loopback TCP peer **and** loopback Host.
3. Exact same Origin as the request origin + `X-KB-Demo: 1`.
4. `Sec-Fetch-Site: same-origin`, when supplied, and an operation allowlist.

No CORS is enabled. Wrong origin, remote peer, rebinding Host and missing header
are rejected. Browser identity data cannot select a generator or override the
server Actor through business API parameters. Demo signatures remain subject
to the normal replay/tamper protection. Responses use no-store caching; static
routes add a strict self-only CSP, nosniff and no-referrer headers.

**Never enable the demo signer against real data, expose it through a reverse
proxy/tunnel, or use it as production login.** It deliberately simulates admin
identities for a single developer. The app factory cannot know your deployment
topology; use the constrained CLI for disposable demos.

## Architecture / packaging

```text
ui/static/{index.html,workbench.css,workbench.js}  ← wheel package-data
  │ same-origin HTTP, no build step / network imports
  ├── /ui/config: read-only capabilities + operation table
  ├── /ui/demo/sign: explicit loopback-only demo, absent by default
  └── /v1/* → existing HMAC middleware → LocalKnowledgeClient
                 → SQLite authority + optional retrieval/generator adapters
```

The small optional server module owns static routing and local demo signing;
core code imports no UI/FastAPI dependencies. Three backwards-compatible SDK
additions support complete UI contracts: atomic `ingest(..., acl=...)`,
permission-checked `inspect_document`, and scoped `search(..., scope=...)`;
`list_consumer_bindings` exposes already persisted actor-owned bindings with
fresh scope validation. The shared operation table keeps Python HTTP client,
server, and UI aligned. No database schema migration is needed.

## Verification

```sh
PYTHONPATH=src .venv-http/bin/python -m pytest -q
PYTHONPATH=src python3 -S -m unittest discover -s tests -t . -q
git diff --check
```

`tests/test_ui_workbench.py` checks offline assets, four-view controls, safe DOM
usage, no auto-ask, production fail-closed behavior, disabled UI, loopback /
Origin / Host signer guards, HMAC replay/tampering, all space/ACL types, identity
and organization isolation, versioned preview/chunks/archive, scoped search,
ask citations and zero-call refusal, bindings and ref tamper verification.
Optional HTTP tests skip cleanly when HTTP extras are absent. Acceptance does
not claim a rendered-browser screenshot or real user browser clicking run.

### Box acceptance result

Verified 2026-11-24 00:20 UTC+8, on local `main` based on `ebb9f4f`, without
commit/push or changes to any other checkout/machine:

- Full pytest: **203 passed** (original 174 + 29 new), 3 skipped; 35 existing
  subtests passed. One upstream Starlette/httpx deprecation warning remains.
- Standard-library-only `python3 -S`: 206 discovered, **154 passed**, 52 skipped
  (optional integrations, including 19 new HTTP tests).
- `git diff --check` and standalone JavaScript syntax validation passed.
- Wheel built successfully; all three static assets match source bytes, and its
  metadata has no unconditional runtime dependency.
- Temporary real server on `127.0.0.1:8095`: `/ui`, `/ui/`, config, CSS and JS all
  200; demo-signed business GET 200. Process terminated and port verified closed.

Raw logs and live HTTP evidence are in `docs/acceptance/ui-workbench/`; the
locally built wheel is in `reports/ui-workbench/wheels/`. These are local review
artifacts, not published releases. Rendered-browser click/screenshot acceptance
remains separate from this HTTP/static test run.
