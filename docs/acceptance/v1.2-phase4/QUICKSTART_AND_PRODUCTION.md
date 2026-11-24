# Q1 optional MCP: gateway integration and operational boundaries

## Dependency / compatibility

Core remains Python >=3.9, version 1.2.0, `dependencies=[]`, schema2. Importing
`knowledge_sdk` or `knowledge_sdk.mcp` does not import the external `mcp` SDK.
Only explicit `create_app` / CLI startup imports the official transport.

`pip install 'knowledge-sdk[mcp]'` opts into the **official Python MCP SDK
maintenance v1 line**, `mcp>=1.30,<2`, conditional on Python >=3.10. The tested
SDK 1.30.0 declares `Requires-Python: >=3.10`. Python3.9 core installation is
not broken: the marker excludes the optional SDK; starting MCP explicitly
fails clearly before opening databases. Actual local runtime is Python3.13.5;
3.9 compatibility was syntax/marker checked, not locally runtime certified.
Official v1 remains supported; `<2` deliberately avoids the incompatible v2
API. References consulted this turn:
https://raw.githubusercontent.com/modelcontextprotocol/python-sdk/v1.x/README.md
https://py.sdk.modelcontextprotocol.io/get-started/installation/
The installed SDK metadata and actual wire tests, not search snippets, are the
source of truth for the pinned line's API / Python requirement.

## Ten-minute sandbox recipe (no external account or model)

This is a reproducible **trusted gateway + official SDK client** example,
not evidence that a design partner/Claude/Cursor customer completed onboarding
in ten minutes. That external-client/design-partner gate remains NOT_RUN.
Never point the sandbox command at an existing production database.

From the checkout with a Python >=3.10 interpreter, in one terminal:

```sh
python3 -m venv .venv-mcp-sandbox
.venv-mcp-sandbox/bin/pip install -e '.[mcp]'
export PYTHONPATH=src
export KNOWLEDGE_AUTH_SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
export SANDBOX_DIR="$(mktemp -d)"
export MCP_PORT="$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')"
umask 077
.venv-mcp-sandbox/bin/python - <<'PY'
import os
from knowledge_sdk import Actor,LocalKnowledgeClient,SQLiteStore,ResourceRights,Purpose
c=LocalKnowledgeClient(SQLiteStore(os.path.join(os.environ['SANDBOX_DIR'],'business.db')))
try:
    a=Actor('sandbox-user','sandbox')
    k=c.create_kb(a,'Sandbox',visibility='enterprise',kb_id='sandbox-kb')
    c.ingest(a,k.kb_id,'sandbox fixed evidence only',doc_id='sandbox-doc',
             rights=ResourceRights(allowed_purposes=(Purpose.READ,Purpose.GROUND_INTERNAL_LLM,Purpose.GROUND_EXTERNAL_LLM),allow_external_llm=True))
finally:c.store.close()
PY
# Both files below are new dedicated sandbox files. No dotenv file is read.
.venv-mcp-sandbox/bin/python -m knowledge_sdk.mcp \
  --db "$SANDBOX_DIR/business.db" --replay-db "$SANDBOX_DIR/replay.db" \
  --host 127.0.0.1 --port "$MCP_PORT" &
MCP_PID=$!
.venv-mcp-sandbox/bin/python - <<'PY'
import os,threading
from urllib.request import urlopen
from urllib.error import HTTPError
for _ in range(100):
    try:
        with urlopen('http://127.0.0.1:'+os.environ['MCP_PORT']+'/mcp',timeout=1):pass
    except HTTPError as error:
        code=error.code;error.close()
        if code==401:break
    except OSError:pass
    threading.Event().wait(.05)
else:raise SystemExit('MCP readiness timeout')
PY
.venv-mcp-sandbox/bin/python docs/acceptance/v1.2-phase4/gateway_client_example.py \
  "http://127.0.0.1:$MCP_PORT/mcp"
# Stop ONLY the process this recipe launched. Never use a global stop script.
kill "$MCP_PID"
wait "$MCP_PID" || true
```

Allow the server to reach readiness before the client; the complete automated
ready/wait/finally-cleanup recipe is `live_mcp_probe.py`. The short example is
not stdio, does not expose a demo signer, and does not put a secret in a tool
argument. Keep the generated secret in this one trusted terminal environment;
do not print it, paste it into a model prompt, put it in a URL/CLI flag or
commit it. Temporary sandbox files may be removed by their owner after review.
The sample itself was not presented as a real external customer's setup time.

## Trust model and purpose

- This is official **stateless Streamable HTTP + JSON responses** via SDK
  `Server` and `StreamableHTTPSessionManager`, not a handcrafted JSON-RPC proxy.
  No stdio or anonymous/admin fallback is offered.
- A trusted gateway authenticates the human/service session and derives Actor
  and AgentIdentity. It signs the exact outgoing method/ASGI target/body with
  fresh nonce/timestamp on every initialize/list/notification/tool call, GET
  and DELETE. The SDK example is the signing gateway, not the LLM itself.
- Actor, Agent, purpose and PolicyContext never come from tool arguments.
  All four schemas use `additionalProperties=false`; runtime also rejects every
  unknown field and wrong scalar/array/bool type. Description/task strings are
  inert data, not host instructions or replacement actor IDs.
- X-KB-Agent is required and strictly parsed (unknown fields/types rejected
  before nonce consumption). Consumer receipts use `mcp_agent` and the trusted
  `agent_id`, never `task_id`. An MCP session/initialization is not an auth token.
- Default binding is GROUND_EXTERNAL_LLM. An omitted purpose header **still
  applies external**, never old HTTP READ. If present, the signed purpose must
  exactly match the configured binding; read/export/train/internal cannot
  downgrade an external gateway. Only trusted server configuration
  `--bound-purpose ground_internal_llm` selects private internal use. Missing
  purpose then means internal, but mismatched signed purposes remain rejected.
- Agent.allowed_purposes and current document rights still intersect this
  binding. Default documents do not allow external grounding; an administrator
  must explicitly set both allowed_purposes and allow_external_llm. This does
  not authorize a model call: these tools never generate or rewrite queries.

## Four tools and deliberate Q1 limits

- search_evidence: 1..1000 query, keyword/vector/hybrid, 1..20 results. With no
  configured vector/embedder, hybrid explicitly falls back to keyword and
  returns `mode_applied=keyword`; explicit vector returns a safe
  `vector_backend_not_configured` wire error. No implicit paid adapter/query
  rewriting. kb_ids and doc_ids are mutually exclusive; explicit empty arrays
  are rejected, not interpreted as all. Existing KnowledgeScope modes only.
- Every returned hit is reread under READ+SEARCH intersection; existing
  reference/consume/attach creates a real MaterialReceipt. Titles/text honor
  all profiles. Canonical excerpts use the existing excerpt policy without a
  query-dependent window, so URI+hash alone can be reverified deterministically.
  masking_summary describes source delivery redaction, not a denied-source count.
- verify_citation: canonical source-unit hash is optional; when supplied it
  must match current delivered (possibly redacted) content. No hash means only
  current evidence availability/integrity, **not proof of user comprehension**.
  Superseded versions are invalid by default; check_latest_version=false permits
  a still-authorized historical version. Pending/orphan receipts retain actual
  core reasons. Non-anchor URIs have reanchor_status=null, not fictitious physical
  anchors. Unauthorized/revoked/missing objects all yield denied, no latest
  version/existence metadata. `revoked` is reserved, not an external oracle.
- get_evidence_pack: Q1 controlled collection read only. No pack store exists;
  any pack_id gives uniform unavailable and returns no items, even if URIs are
  also supplied. Use explicit source_uris. Any denied source rejects the entire
  pack with no excluded count. All allowed sources' decisions intersect; a
  short-lived read-only client view only ADDS union redaction obligations to
  the current authority, never mutates the shared engine or turns a deny into
  an allow. Existing client ref/consume generates receipts for those exact
  delivered views. Collective-context hashes need not equal a standalone
  citation's weaker canonical hash: differing obligations fail closed.
- Pack max_chars defaults4000, range1..20000, at most50 source URIs and an
  overall HTTP body limit64KiB. Budget omits whole canonical units and marks
  `budget_omitted`, never slices an anchor or claims a receipt for unseen text.
  All sources are authorized before returning any body. This is not immutable
  Q2 EvidencePack, approval snapshots, storage, export or commercial pack logic.
- report_evidence_issue: authorized REPORT_ISSUE plus READ/necessary redaction
  for source and conflicting URI, 1..4000 description, four enumerated types.
  Pending anchors may be reported via their authorized impact view without
  pretending they were consumable. It inserts only into existing evidence_issues:
  internal status=open; outward status=queued_for_review. No official document,
  version, ACL, rights, vector index or model is modified. Raw review text stays
  inert JSON/SQL parameters; no UI/rendering/execution/messages/training occurs.
  A future renderer must escape it. Transport retries with new nonces may queue
  duplicates after a lost response; Q1 does not claim exactly-once feedback.

## Same-origin / proxy / multi-worker runbook

Keep the MCP service behind a same-origin trusted server gateway, not browser
JavaScript holding HMAC keys. Default loopback Host allowlist and strict Origin
validation are enabled by the official SDK. Present Origin must additionally
match the exact trusted allowlist; absent Origin is permitted for server-to-server
clients. No wildcard CORS/browser direct-login scheme is enabled. An Origin
allowlist is not an OAuth/CORS implementation. SDK sessions do not bypass
per-request HMAC or per-tool current authority.

Configure public reverse-proxy Host/Origin via trusted `--allowed-host` and
`--allowed-origin`. Do not trust arbitrary X-Forwarded-Prefix/role headers.
`proxy_headers=False` is intentional. A proxy may strip an external prefix;
the signing gateway must sign the exact path received by this ASGI gateway
(`/mcp` by default, raw query included) after that trusted rewrite. Forward the
body bytes unchanged. HMAC signatures continue to bind method/path/actor,
timestamp/nonce/body and optional Agent/Purpose extensions byte-for-byte.

Each worker must use the SAME dedicated `--replay-db` and signing/rotation
configuration. Never use the business DB as replay DB. SQLiteReplayStore is
WAL/atomic cross-worker fail-closed storage; use a local filesystem supporting
SQLite locking, restrict permissions, monitor capacity/latency. It is not a
multi-host/NFS distributed replay design. Rotate with the primary environment
secret plus temporary comma-separated KNOWLEDGE_AUTH_FALLBACK_SECRETS; every
key >=32 characters. Remove old keys after the signature/replay window. Never
log secret values, headers, raw arguments or review descriptions. No `.env`
is loaded. Back up/plan production rollouts separately; **this task did not
open or migrate any real business database or deploy a production service**.

If the same-origin host gateway uses browser cookies, it must enforce its own
CSRF protection, HttpOnly/SameSite session handling, expiry/logout and revocation
before minting fresh signed claims. The SDK does not implement that host login
hook or treat opaque Actor.session_id as an SSO revocation database.

Current source/ACL/rights/agent/purpose is checked on each tool call and again
around receipt delivery. Use the same policy generation and trusted session
revocation mapping at the gateway; do not treat MCP initialization as a durable
permission grant. Q2 approval governance/Outbox/Postgres and unified source UI
remain out of scope.
