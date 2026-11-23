# knowledge-sdk

**v1.0.0 · Python ≥3.9 · MIT · no mandatory third-party dependencies**

A framework-independent knowledge library with authoritative SQLite storage,
immutable document versions, explicit permission boundaries, multilingual FTS5,
pluggable vector retrieval, and verifiable references. Use it in-process or as an
optional signed HTTP sidecar. It does **not** contain account management, an LLM,
a paid embedding call, or application-specific business state.

## Install

```bash
python3 -m pip install .                    # core: stdlib + SQLite3
python3 -m pip install '.[http]'             # optional FastAPI + uvicorn
python3 -m pip install '.[parsers]'          # optional pypdf fallback
```

Core requires a Python build with SQLite **FTS5** enabled (ordinary CPython builds
usually include it). TXT, Markdown, HTML, CSV and text-only DOCX/PPTX/XLSX extraction
are built in. PDFs need `pdftotext` or optional `pypdf`; unreadable/scanned PDFs
raise `ValidationError` rather than indexing binary garbage. Register an OCR
parser explicitly. `[qdrant]` and `[ocr]` are dependency-free extension markers:
Qdrant REST uses `urllib`; OCR is a hook, not an included recognition engine.

## In-process quick start

```python
from knowledge_sdk import Actor, LocalKnowledgeClient, SQLiteStore

client = LocalKnowledgeClient(SQLiteStore("knowledge.db"))
actor = Actor(user_id="alice", org_id="acme")  # authenticated by the host
kb = client.create_kb(actor, "Research", visibility="team")
client.grant_kb_member(actor, kb.kb_id, "bob", "viewer")
version = client.ingest(actor, kb.kb_id, "# Notes\n知识库 supports evidence.",
                        filename="notes.md", metadata={"tags": ["research"]})
hit = client.search(actor, "知识库").hits[0]
ref = client.reference(actor, hit.doc_id, hit.version,
                       chunk_ids=[hit.chunk_id], excerpt=hit.excerpt)
receipt = client.consume(actor, ref)
assert receipt.status == "partial"  # selected excerpt, not a whole-document claim
page = client.retrieve(actor, version.doc_id, offset=0, limit=4096)
```

`ingest` returns `DocumentVersion`; its `doc_id` identifies the document. Pass that
ID to `ingest` for a semantic revision. Identical bytes or normalized text return
the previous version without modifying it. There is no implicit cross-document
or cross-tenant deduplication, which could disclose the existence of private data.

## Features

- Organization isolation; `private | team | enterprise` visibility; explicit KB
  `viewer | editor | admin` membership; document allow/deny users, roles, departments.
- Raw SHA-256 and normalized-text SHA-256; immutable history; archive/restore;
  optional organization/document-isolated original blobs.
- Hierarchical or fixed overlapping chunks, source offsets, stable hashes and
  added/unchanged/removed chunk delta.
- Actual SQLite FTS5 `MATCH` + `bm25`; safely quoted query tokens; CJK character/
  bigram indexing; keyword, vector and weighted rank-fused hybrid modes.
- Every vector hit revalidated against current authoritative tenant, KB/ACL,
  archive state, version and actual chunk. Vector payloads never authorize access.
- Budgeted, normalized previews (800 / enterprise 1600 Unicode code points),
  truncation/remaining counts, safe highlight offsets and explicit partial/masking
  notices. Full reads are separately paginated.
- Stable `kb://org/{org}/doc/{doc}@{version}[#chunk={id}]` references; SHA-256 and
  source-membership verification; `consumed | partial | unavailable | denied`
  receipts and bounded batch consumption.
- Optional Qdrant REST adapter; injected `Embedder`/`VectorIndex`/`Reranker`
  protocols. `HashEmbedder.non_semantic = True`: lexical test vectors, not AI.
- Same Python interface for `LocalKnowledgeClient` and `HttpKnowledgeClient`;
  optional FastAPI service, OpenAPI routes, HMAC-SHA256 Actor assertions.

## Optional HTTP service

Supply `KNOWLEDGE_AUTH_SECRET` securely through your deployment's environment
(minimum 32 characters; do not commit it). Then:

```bash
knowledge-sdk-server --db knowledge.db --host 127.0.0.1 --port 8088
```

```python
import os
from knowledge_sdk import HttpKnowledgeClient
remote = HttpKnowledgeClient("http://127.0.0.1:8088",
                              auth_secret=os.environ["KNOWLEDGE_AUTH_SECRET"])
# remote.create_kb / ingest / search / retrieve / reference / consume etc.
```

A trusted backend signs Actors **after authenticating users**. Never put the shared
secret in browsers or untrusted clients; a holder can impersonate any Actor.
Use TLS outside loopback. `--dev-insecure` must be explicitly selected and is
restricted to loopback by the CLI. Even in that mode an Actor header is required.
[Protocol and threat model](docs/api-contract.md).

## Test and build

```bash
PYTHONPATH=src python3 -S -m unittest discover -s tests -t . -v
# Core works with site-packages disabled; HTTP tests explicitly skip when absent.
python3 -m venv .venv
.venv/bin/pip install -e '.[http,dev]'
.venv/bin/python -m unittest discover -s tests -t . -v
.venv/bin/python -m build
```

HTTP tests start an ephemeral loopback port, never a fixed application port.
Isolation tests launch a fresh `python -S` process and exercise the complete core
flow without web frameworks, model SDKs or vector clients. Syntax tests additionally
parse every module against Python 3.9 grammar. CI runs real 3.9 and 3.12 runtimes.
Qdrant tests mock the REST contract; they do **not** claim a live Qdrant integration.

## Production boundaries

This release supplies library capabilities, not a complete hosted knowledge SaaS.
Actors, tenant member identity, rate limiting, TLS, secret rotation, backups,
encryption, malware scanning and resource isolation belong to deployment/host.
SQLite is intended for embedded/single-node use; load-test your actual workload.
OOXML extraction is text-only, not visual layout reconstruction. No OCR engine,
semantic embedding model, reranking implementation, connector crawler, queue,
field-redaction engine or administrative UI is bundled. Feed already-redacted
content before attaching masking notices; notices themselves do not redact data.

Vector index writes are synchronous, separate from SQLite commits. On remote
failure the operation raises after the authoritative change may have committed;
`health()` becomes degraded. Durable pending markers plus administrator `reindex`
repair that state. Archived/unauthorized content stays blocked even with stale
vector hits. Search examines a bounded candidate set, so very restrictive ACLs
can return fewer than `limit` results; it is not exhaustive relevance pagination.

See [architecture](docs/architecture.md), [API contract](docs/api-contract.md) and
[host integration preparation](docs/strat-ai-integration.md).
