# Q1 MCP integration — authoritative t37u taskbook

This document supersedes the earlier parent-brief preference for an official
third-party MCP SDK. The kernel is **Python3.9+ and 100% stdlib self-implemented
JSON-RPC2**, with newline stdio and an optional signed HTTP `POST /v1/mcp` adapter.
Version1.2.0 / business schema2 / core `dependencies=[]` remain unchanged.
The exact extra is `fastapi>=0.100,<1`, `uvicorn>=0.23,<1`; no third-party MCP SDK
is imported or installed by it. Entry point: `knowledge-sdk-mcp = knowledge_sdk.mcp.server:main`.

## <=10-minute isolated stdio recipe (external desktop execution NOT_RUN)

Use a new sandbox DB only; do not point these commands at an existing running
business database. No API keys, model, embedding or external account is needed.

```sh
python3 -m venv .venv-mcp-sandbox
.venv-mcp-sandbox/bin/pip install -e .
export PYTHONPATH="$PWD/src"
export KNOWLEDGE_MCP_ACTOR_JSON='{"user_id":"sandbox-reader","org_id":"sandbox"}'
# Optional fixed Agent; never take these claims from LLM tool JSON:
export KNOWLEDGE_MCP_AGENT_JSON='{"agent_id":"sandbox-agent","org_id":"sandbox"}'
export KNOWLEDGE_MCP_PURPOSE=ground_internal_llm
# Choose a fresh private directory; this is not a production migration command.
export MCP_SANDBOX="$(mktemp -d)"
.venv-mcp-sandbox/bin/python - <<'PYTHON'
import os
from knowledge_sdk import Actor,LocalKnowledgeClient,SQLiteStore
c=LocalKnowledgeClient(SQLiteStore(os.path.join(os.environ['MCP_SANDBOX'],'business.db')))
try:
 a=Actor('sandbox-reader','sandbox');k=c.create_kb(a,'Sandbox',kb_id='sandbox-kb')
 c.ingest(a,k.kb_id,'sandbox fixed evidence','sandbox.md',doc_id='sandbox-doc')
finally:c.store.close()
PYTHON
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25"}}' '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' | .venv-mcp-sandbox/bin/python -S -m knowledge_sdk.mcp --db "$MCP_SANDBOX/business.db"
```

Stdio requires valid `KNOWLEDGE_MCP_ACTOR_JSON`; missing/invalid identity exits
nonzero **before opening a database**, with no anonymous/admin default. Optional
Agent must match the Actor tenant. Purpose defaults internal. Stdio stdout is
newline JSON-RPC only; operational errors go to stderr. No dotenv file is read.
A trusted host owns this fixed single-user sandbox configuration; it is not SSO.

For Claude Desktop's MCP configuration or Cursor's `mcpServers` configuration,
replace the absolute paths below with that isolated checkout/interpreter/DB:

```json
{"mcpServers":{"knowledge-sandbox":{"command":"/ABS/REPO/.venv-mcp-sandbox/bin/python","args":["-m","knowledge_sdk.mcp","--db","/ABS/NEW-SANDBOX/business.db"],"env":{"PYTHONPATH":"/ABS/REPO/src","KNOWLEDGE_MCP_ACTOR_JSON":"{\"user_id\":\"sandbox-reader\",\"org_id\":\"sandbox\"}","KNOWLEDGE_MCP_AGENT_JSON":"{\"agent_id\":\"sandbox-agent\",\"org_id\":\"sandbox\"}","KNOWLEDGE_MCP_PURPOSE":"ground_internal_llm"}}}}
```

These are explicit sandbox identities, not real credentials or an admin fallback.
Desktop UI/config-file paths differ by product/version: paste into the client's
MCP server configuration UI/file, then check server connection and `tools/list`.
Actual external Claude/Cursor operation and a customer completing <=10 minutes
remain **NOT_RUN**; the local subprocess probe is not evidence of that gate.

## Optional HTTP / trusted gateway

```sh
.venv-mcp-sandbox/bin/pip install -e '.[mcp]'
# Supply a random local test key in this trusted shell, never in a model prompt.
export KNOWLEDGE_AUTH_SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
.venv-mcp-sandbox/bin/python -m knowledge_sdk.mcp --transport http \
 --db "$MCP_SANDBOX/business.db" --replay-db "$MCP_SANDBOX/separate-replay.db" \
 --host 127.0.0.1 --port 18766
```

HTTP must be opted into on the host factory:
`create_app(client, secret, enable_mcp=True, default_mcp_purpose=Purpose.GROUND_INTERNAL_LLM)`.
Without `enable_mcp`, `/v1/mcp` is404. It is **never** an authentication whitelist.
Unsigned, invalid, replayed or illegal-Agent requests return401 + `Cache-Control:no-store`.
No demo signer or role simulator is enabled by default; dev_insecure + MCP is rejected.

Sign every method/target/body with the existing HMAC helper `signed_headers`;
Actor/Agent/Purpose are trusted headers only. Missing Purpose applies the server's
configured default **internal**, not legacy HTTP READ. A legitimate signed Purpose
header takes precedence. Cloud gateways MUST configure
`--default-mcp-purpose ground_external_llm` (or the factory equivalent) and must
never let a model choose the header. Current Agent/document purpose rights still
intersect every tool call. Default document rights prohibit external LLM/training.
No model invocation is performed by MCP tools.

Each worker must share the same dedicated `SQLiteReplayStore(path)` plus primary
key/fallback rotation configuration. Replay DB and business DB must be separate.
Use a local filesystem with SQLite locking; this is not multi-host/NFS replay.
Keys must each be>=32 characters. Optional comma-separated
`KNOWLEDGE_AUTH_FALLBACK_SECRETS` is loaded explicitly; never log values or headers.

Keep keys in a same-origin **server** gateway, not browser JavaScript. Host login,
Actor/Agent mapping, session expiry/logout/revocation and cookie-CSRF protection
are the integrating host's responsibilities, not newly implemented login hooks.
Present Origin must match the HTTP service origin; no wildcard CORS is enabled.
A reverse proxy must preserve body bytes and the gateway must sign the exact
ASGI raw target after its trusted prefix rewrite, including the query string.
No arbitrary client-supplied prefix/identity forwarding is trusted. Real proxy
and production same-origin deployment were NOT_RUN. Use existing bounded request
and replay capacity controls and coordinate production rollout separately.

## Protocol/tools and bounded Q1 semantics

- JSON-RPC2 methods: initialize, notifications/initialized, ping, tools/list,
  tools/call; standard parse/request/method/params errors; <=64KiB messages and
  <=20 batch requests. Stdio newline framing and stateless HTTP JSON responses
  share the exact dispatcher. SSE/resumption/OAuth and broad conformance beyond
  this taskbook subset are not claimed; no third-party MCP SDK certification.
- All four schemas have `additionalProperties:false`; runtime independently
  rejects unknown fields and identity/purpose/policy_context/self injections.
- search_evidence defaults **keyword**. Explicit vector/hybrid without a configured
  backend is an error, never an implicit paid call or silent keyword fallback.
  kb_ids/doc_ids are mutually exclusive nonempty selectors; existing scope modes
  only. Current READ+SEARCH, all redaction obligations and authoritative SQLite
  are rechecked. Returned evidence has real reference/consume/attach receipts,
  trusted mcp_agent consumer, Agent ID or mcp_stdio, and task_id as used_by_stage.
  Anchored matches are preferred when the delivered quote fits; otherwise chunk URI.
- verify_citation checks current access, pinned version/anchor and delivered hash.
  Missing hash means availability/integrity, not proof a user understood content.
  Revoked/absent/unauthorized all return denied, latest_version=null and no title.
- get_evidence_pack accepts ONLY required source_uris (1..20) and optional max_chars
  (1..32000, default4000). No pack_id store/product exists. Denied, missing-hook,
  cross-tenant, absent, pending and orphan entries are removed uniformly and only
  aggregate excluded_count is returned; no excluded URI/title/reason is disclosed.
  This aggregate is intentionally permitted by the authoritative taskbook, unlike
  the superseded earlier whole-pack-denial suggestion. Included sources intersect
  decisions and union redaction profiles before delivery. Budget truncates ordinary
  excerpts with new genuine receipts; an anchor too large is omitted whole rather
  than falsely claiming consumption of an incomplete quote. truncated signals budget
  loss; budget omission is not a permission-exclusion count. Zero returned items
  yields no_authorized_evidence. This is not an immutable Q2 EvidencePack product.
- report_evidence_issue only queues a typed EvidenceIssue, status=open internally;
  outward queued_for_review and a note that formal knowledge is unchanged.
  Source/conflicting citations are currently authorized; description is inert data.
  No documents/versions/chunks/ACLs/anchors mutate, no execution/training/messages/UI.
- Local/Http interfaces: report_evidence_issue -> EvidenceIssue, `POST /v1/issues`;
  list_evidence_issues -> current-authorized/redacted issues, `POST /v1/issues/list`.
  Current source/conflict revocation or missing redaction hooks filters list entries.
  DB statuses open/triaged/resolved/dismissed are a queue contract, not new workflow UI.
  Retries may create duplicates; exactly-once feedback is not promised.

## Evidence / exit boundaries

See `docs/acceptance/v1.2-phase4/PHASE4_HANDOFF_REPORT.md` for exact commits,
raw L1/L2 results, separate60 goldens, actual loopback HTTP and actual `python -S`
stdio subprocess evidence. Historical incompatible parent-brief logs are explicitly
archived under `superseded-parent-brief/`, never substituted for current acceptance.
L4 NOT_RUN; L5 independent architect review pending. External partner/enterprise
integration, real online semantic/model services, real PDF/OCR and production
rollout remain unproven. No main merge/tag/release/deployment or Q2 feature is done.

## Q2-M3 persisted EvidencePack extension

`get_evidence_pack` still supports the Q1 `source_uris` transient tool contract.
It additionally accepts `query` for transient search assembly, or `pack_id` for a
persisted immutable snapshot; choose exactly one selector. Persisted IDs undergo
whole-pack live EXPORT + gateway-purpose policy, redaction and digest checks before
any content is returned. Missing/denied/tampered packs return no items. Other tool
names, default internal purpose and stdio/signed-HTTP identity rules are unchanged.
No extra runtime dependency, model call, identity input or output-path input exists.
See [M3 protocol and boundaries](governance-packs.md).
