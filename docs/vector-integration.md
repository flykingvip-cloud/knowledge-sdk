# Real Qdrant and semantic embedding integration

## Explicit, independent adapters

`OpenAICompatibleEmbedder(base_url, model, api_key=None, timeout=30,
dimensions=None, extra_headers=None, batch_size=64)` uses only Python stdlib.
Use a base URL ending in `/v1`, or an explicit `/embeddings` endpoint. It works
with any provider implementing OpenAI's `input` list and indexed float-vector
`data` response. Model-specific input prefixes, context limits and language
support remain deployment responsibilities; compatibility is not a promise that
every model or gateway behaves identically. Remote providers may bill requests.
No model is downloaded, key discovered, environment file read, or service started.

- `api_key` sets Bearer authorization, omitted for keyless local services.
- `extra_headers` supports gateway headers (reserved auth/content/host headers
  cannot be overridden). Never put keys in the URL; query strings, userinfo and
  fragments are rejected. Use TLS whenever credentials or content leave loopback.
- Texts are batched, returned indices reordered, count and unique indices checked.
  Vectors must be finite, numeric, nonempty and dimensionally consistent across
  batches and calls. `dimensions` is sent only when explicitly requested; not all
  providers support it. Empty input makes no request. `non_semantic=False` marks
  intended semantic use, not a quality certification of the chosen model.
- `EmbeddingError` wraps transport/JSON/schema failures without exposing provider
  bodies, document text, URL, custom headers or keys in its message or chained
  traceback. Redirects are refused to prevent credential/content forwarding.
  No automatic retries or partial batch results. Inject retry/rate-limit policy
  externally; embedder instances do not promise concurrent mutable-state safety.

The Qdrant REST adapter requires a separately provisioned, unnamed dense-vector
collection. Obtain dimensions from an explicit embedding probe before provisioning:

```python
from knowledge_sdk import OpenAICompatibleEmbedder
from knowledge_sdk.retrieval.adapters.qdrant import QdrantIndex

embedder = OpenAICompatibleEmbedder("http://127.0.0.1:11434/v1",
                                   "nomic-embed-text:latest", timeout=120)
size = len(embedder.embed(["dimension probe"])[0])
# Deployment: PUT /collections/<new_name>
# {"vectors": {"size": size, "distance": "Cosine"}}
index = QdrantIndex("http://127.0.0.1:6333", "deployment_owned_collection")
```

Never reuse a collection from a different application/model. The SDK's document
IDs are globally generated and point IDs deterministic UUIDs derived from
`doc_id/version/chunk_id`. Upserts and filter deletes use `wait=true`. Archive
removes every point with matching `doc_id`; restore/reindex recreates current
chunks. `query` is preferred (Qdrant >=1.10); only HTTP 404/405 falls back to
legacy `search`, not authentication/validation/server errors. Malformed secondary
points are ignored. All candidate tenant/ACL/archive/version/chunk checks still
happen in authoritative SQLite; vector payloads never authorize access.

## Safe live acceptance

Offline tests do not connect to services. To explicitly opt in:

```bash
PYTHONPATH=src \
KNOWLEDGE_SDK_LIVE_QDRANT_URL=http://127.0.0.1:6333 \
python3 -S -m unittest tests.integration.test_qdrant_live -v
```

For a preinstalled, keyless local embedding model, add these public config values:

```bash
PYTHONPATH=src \
KNOWLEDGE_SDK_LIVE_QDRANT_URL=http://127.0.0.1:6333 \
KNOWLEDGE_SDK_LIVE_EMBEDDING_URL=http://127.0.0.1:11434/v1 \
KNOWLEDGE_SDK_LIVE_EMBEDDING_MODEL=nomic-embed-text:latest \
python3 -S -m unittest tests.integration.test_qdrant_live -v
```

The three tests cover lexical-hash full lifecycle, real-embedding full lifecycle,
and synonym top-1 retrieval with zero keyword hits. Each independently creates a
random `knowledge_sdk_e2e_<uuid>` collection after verifying name nonexistence.
Only that generated collection is mutated. Cleanup runs in `finally`, even when
assertions/requests fail. Existing collection names, configs and exact point
counts must match after cleanup. This verifies those invariants, not a bytewise
proof of all preexisting payloads. Run while other collection writers are quiet
(or unrelated concurrent writes can correctly make this assertion fail).

Coverage includes three visibility domains, cross-tenant and document ACL denies,
actual injected dirty/stale/missing vector points, authoritative rereads, excerpt
truncation/fail-closed access, reference/receipt integrity, archive point count zero,
restore/reindex and semantic synonym recall. No keys are read by these tests.
A configured but unavailable service FAILS the opted-in test, never silently skips.
The cleanup cannot protect against SIGKILL/power loss; printed generated names
allow an operator to inspect leftovers after such an interruption. It never scans
for and deletes other runs' collections.
