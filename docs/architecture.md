# Architecture · v1.0.0

## Dependency direction

`contracts / exceptions` ← `permissions / ingestion / storage / retrieval`
← `client.local` ← optional `server.app`.

`client.http_client` uses only stdlib transport + lightweight `server.auth`;
importing the public `knowledge_sdk` never imports FastAPI, Flask, Qdrant clients
or model providers. `server.app` / `server.cli` import the optional HTTP extra.
Office text parsers are stdlib ZIP/XML plugins and do not need Office libraries.

The stable public API is re-exported by `knowledge_sdk.__init__`; transport models
are dataclasses. `KnowledgeClient`, `MetadataStore`, `BlobStore`, `Parser`,
`Chunker`, `VectorIndex`, `Embedder`, `Reranker`, `OCRHook` are structural protocols.
A reranker is an extension contract only: v1 does not invoke one implicitly.

## Authority, scope and permission ordering

1. Actor organization must match KB and document organization.
2. Document explicit deny (user / claimed role / claimed department) wins even
   over ownership and KB administration for content reads.
3. KB membership / ownership or same-org enterprise visibility is required.
   A document grant cannot bypass its KB boundary.
4. Document owner / KB admin can read, unless denied. An explicit document allow
   list, when present, narrows everyone else's access. Without it, same-org
   enterprise documents or team members can read; private documents need a grant.
5. Viewer reads, editor ingests/archives/restores, admin manages membership/ACLs
   and reindexing. Host role strings do not confer KB administrative privileges.
6. Archived content is excluded from all ordinary reads/search. Authorized
   archive-aware listing, restore and receipt availability checks are explicit.

Host-supplied department and role claims must originate from an authenticated
identity system. SDK membership does not verify that a user ID exists in an
external identity provider; the same-org check still applies on every read.

## Persistence and transactions

SQLite tables: `knowledge_bases`, `kb_members`, `documents`, `document_versions`,
`document_acls`, `chunks`, virtual `chunks_fts`, `pending_indexes`. Schema version
is `PRAGMA user_version=1`; unknown versions are rejected. Parameterized SQL,
foreign keys, serialized write transactions and WAL are enabled. Client calls
serialize with an RLock; a unique `(doc_id, version)` and in-transaction optimistic
version check prevent lost history across clients. Back up using SQLite's backup
API, not a live database file alone (WAL may contain committed data).

Document ID and KB ID are global opaque identities; conflicts never transfer an
existing resource to another organization. Versions are immutable snapshots of
parsed text, hashes, timestamp, filename, and optional content-addressed blob key.
Current document ACL applies to **all historical versions**; old references never
freeze or bypass current access policy. A semantic duplicate returns the existing
version, including its original bytes/hash/metadata; no silent history mutation.

Original blobs are optional, written atomically under `org/doc/hash`. Components
are validated and resolved paths must stay within the configured root. A failed
DB transaction can leave an unreferenced content-addressed blob; deployments may
collect those only after reconciling authoritative version references. SQL and
filesystem changes are not a distributed transaction.

## Retrieval and indexes

SQLite FTS5 stores only the active document's latest version. It uses `unicode61`
over application-tokenized words and CJK characters/bigrams. User FTS syntax is
never executed. `bm25()` orders keyword candidates; vector candidates use provider
ranking. Hybrid mode uses weighted reciprocal-rank fusion (default 0.5 / 0.5,
denominator 60), not uncalibrated BM25/cosine addition. CJK segmentation is a
lightweight fallback, not a full linguistic analyzer.

Candidate identities are resolved to authoritative records and actual chunks.
Cross-org, missing, archived, stale-version, ACL-denied and fabricated-chunk hits
are discarded, regardless of vector payload claims. Snippets are made only from
those authoritative chunks. Provider payload text is never returned.

Ingest/archive/restore commit FTS changes with authoritative metadata. With a
vector adapter, the same transaction records a pending marker. The client deletes
old remote document points, optionally embeds/upserts latest active chunks, and
clears the marker only on success. Exceptions propagate; the marker survives
restart. `health()` reports only a count (no cross-tenant document identifiers).
Administrator `reindex(actor,kb_id)` rebuilds that KB, including deletion of
archived remote points. This is eventual secondary-index consistency, not an
exactly-once distributed guarantee. Stale ACL/state hits remain safe regardless.

## Excerpt and evidence contracts

`make_excerpt` normalizes whitespace/NFC, then budgets Unicode code points;
`remaining_chars` counts normalized source characters, not raw bytes/tokens.
Highlights are `[start,end)` offsets into plain text, never executable HTML.
It never splits UTF-8 bytes; grapheme-cluster preservation is not guaranteed.
Forbidden input returns an empty excerpt/hash with no highlights/count leakage.
Partial/masking notices are explicit upstream metadata, not a redaction engine.

`retrieve` pages original parsed text by Unicode code point, independent of search
preview limits. Chunk-selection pages concatenate chunks in source order with a
newline (overlap is retained). References bind org, document, immutable version,
optional chunks, source URI, exact normalized excerpt and SHA-256. Matching a
self-asserted hash is insufficient: excerpt membership in the actual authorized
source is checked too. A receipt verifies supplied material against authoritative
state; it cannot prove an LLM or person actually read or understood the material.

## Scope and operations

Core is synchronous; optional HTTP is a sidecar facade. No implicit filesystem
watching, background workers, account system, external crawling or model call.
HTTP replay memory is process-local: use one worker per signing endpoint, or a
shared replay-protection gateway for multi-worker deployments. Resource sizes,
ZIP expansion limits and request age checks reduce accidental abuse, but hostile
file parsing belongs in a sandbox with OS-enforced CPU/memory limits.

Use a deployment-managed Qdrant collection with compatible dimensions. Explicit
URL/collection are mandatory. The REST adapter does not auto-create collections,
provision credentials, issue cloud requests, or configure a local fixed port.
