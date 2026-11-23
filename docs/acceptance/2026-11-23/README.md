# Live vector acceptance — 2026-11-23 (Asia/Shanghai, UTC+8)

Accepted locally at approximately 22:25 Asia/Shanghai. Implementation commits:
`af9bb3d` (adapters/tests/docs) and `080dd35` (mock error resource cleanup).
This report and full logs are a documentation-only follow-up. Nothing was pushed
or posted to GitHub; approval is still required before public publication.

## Environment discovered without secrets

- Mac Qdrant: `http://127.0.0.1:6333`, **1.20.2**,
  commit `23065a0bf6857c3e5da45f6c8939cc746cc0580e`.
- Existing collections: `financial_reports` (**0 exact points**) and
  `stratai_grounded_v2` (**2 exact points**).
- Keyless Ollama: `http://127.0.0.1:11434`; existing embedding model
  **nomic-embed-text:latest**, actual returned dimension **768**.
- Mac Python **3.15.2**. No sentence-transformers/torch/transformers/ollama Python
  packages detected; no installation or model download needed.
- Box Python **3.13.5**, dependency-free core and existing HTTP-extra environment.

No `.env`/`.env.production`, credential/token, protected project source, startup
script or port 3000 was accessed. Only the independent SDK checkout was updated.

## Changes and compatibility findings

- Added stdlib `OpenAICompatibleEmbedder`, exported from public package and adapter
  namespace: explicit URL/model/optional key, configurable timeout/dimensions/
  gateway headers/batch size, indexed batch ordering, finite values and consistent
  dimensions, safe generic errors and denied redirects. `non_semantic=False`.
- Existing Qdrant point IDs were **already valid deterministic UUIDs**; regression
  tests now verify UUID validity/stability and version distinction. No arbitrary
  string-ID bug was present. Existing upsert and document filter-delete REST bodies
  were correct and verified against the real server.
- Previous adapter used only deprecated `/points/search`. It now prefers
  `/points/query` and decodes `result.points`; only 404/405 uses legacy search.
  Unit tests verify fallback and non-fallback errors. Real 1.20.2 exercises query.
- Unrelated/malformed vector payloads now skip safely instead of crashing a query.
  Tenant, domain, ACL, version and chunk checks remain SQLite-authoritative.
- Added opt-in live acceptance and integration guide; no implicit service startup,
  collection creation by the production adapter, or credential discovery.

## Results

| Environment | Discovered | Passed | Skipped | Failures |
| --- | ---: | ---: | ---: | ---: |
| Box full, HTTP extra present | 111 | **108** | 3 live opt-in | 0 |
| Box stdlib-only (`python -S`) | 111 | **88** | 20 HTTP + 3 live | 0 |
| Mac stdlib-only (`python -S`) | 111 | **88** | 20 HTTP + 3 live | 0 |
| Mac live Qdrant + Ollama, explicitly enabled | 3 | **3** | 0 | 0 |

The three zero-coupling isolation tests are included and pass in both core runs.
Full unabridged logs: [box full](box-full.log), [box core](box-core.log),
[Mac core](mac-core.log), [Mac live](mac-live.log).

Live tests passed twice during this run; committed logs retain the final run:

1. Full lifecycle with deterministic 256-dimension **non-semantic hash** vectors.
2. Same complete lifecycle with **real nomic semantic vectors (768 dimensions)**:
   - multi-tenant ingestion and private/team/enterprise visibility;
   - keyword, vector and hybrid retrieval;
   - direct REST injection of cross-tenant/private/explicitly-denied/stale/missing/
     fake-chunk/malformed points; forbidden candidates were absent from every
     checked SDK result despite being present in real Qdrant;
   - 80/120-character test-policy truncation, hashes, reference creation,
     partial/consumed/denied receipts, denied precision retrieval and empty
     restricted excerpt (default 800/1600 policies are also covered offline);
   - archive followed by exact remote `doc_id`-filtered point count **zero**;
     restore and explicit reindex made documents searchable again in all modes.
3. Real semantic recall: `automobile maintenance` found
   `Car servicing includes engine oil changes and tire inspection.` at **top 1**,
   while keyword search returned **zero** hits. No exact-word overlap.

## Cleanup and invariant checks

Each test generated its own `knowledge_sdk_e2e_<uuid>` name, confirmed it did not
exist, and confined all collection/point writes and deletion to that name.
`finally` deleted the generated collection and verified the collection set plus
all existing configs and exact point counts against a pre-test snapshot.

Final-run temporary names (all removed):
- `knowledge_sdk_e2e_6b5cdaed613b4e4fb138e89893a44f7c`
- `knowledge_sdk_e2e_f29eda7d0a4f49bf8df6e9ed056dcead`
- `knowledge_sdk_e2e_be7d44736c714d02a2c076f8e3e82c94`

Final independent read-only `/collections` query again returned exactly
`financial_reports` and `stratai_grounded_v2`; no temporary collections remained.
The SDK never mutated any existing collection. Config/count equality is an
explicit invariant check, not a byte-for-byte audit of preexisting point payloads.

## Scope and next steps

The semantic provider exercised was local Ollama, not OpenAI/vLLM/OneAPI; those
compatible providers have mocked protocol coverage but no paid-service claim.
No load/latency SLA, production migration, StratAI integration or public release
is implied. README and `docs/vector-integration.md` contain reproducible commands.
