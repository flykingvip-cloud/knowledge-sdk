# Q3-M2: opt-in controlled reranking and offline paired evaluation

Unreleased engineering on `feat/q3-phase2-rerank-eval`, based on Q3-M1
`69b6c986251161ca02b1e77b0806e2c8861a30b6`. Package metadata remains 1.2.0;
identify artifacts by exact source SHA. Enterprise/StratAI integration is paused.
No package publication, main/tag change or M3 implementation is implied.

The entire staged Q3-M2 taskbook is the executable authority. Neither
`knowledgeos-q3-core-protocol-spec-v0.1.md` nor
`knowledgeos-strategy-architecture-v0.2.md` is present in the checkout or shared
Q2/Q3 task-input directories. Owner t54u accepted M1's assumptions and reports
Workbench publication; those documents were not downloaded/independently read
here. The following M2 consistency choices are explicit, not quotations from an
unseen spec, and remain available for independent review.

## Search and score semantics

```python
hits = client.search(actor, 'orbital recovery', mode='hybrid', limit=5,
    rerank=True, calibrator_id='default-v1', min_calibrated_score=.60,
    rerank_top_k=40)
```

* Without enhancement, existing `SearchHit.score` remains the old RRF score and
  the accepted-limit batching/return ordering is unchanged. New metadata defaults
  to empty IDs / false / zero; optional per-hit score fields are None.
* `rerank=True` selects `lexical-v1`; a named `reranker_id` also explicitly opts
  in. With reranking, `raw_score` is the original RRF, `rerank_score == score` is
  the finite reranker output, and `calibrated_score`, if requested, is the
  independently mapped rerank-channel confidence. Calibration does not silently
  overwrite `score`.
* Calibration alone preserves `score`. Its `raw_score` is the calibration input:
  keyword/hybrid use the existing RRF representation; vector-only uses native
  cosine from the actual vector index. Default independent keyword/hybrid ranges
  are [0,1/61], vector is [-1,1], rerank is [0,1]. These are explicit presets,
  not a fitted production probability model. A threshold selects default-v1 if
  no calibrator is otherwise supplied. No shared raw threshold spans channels.
* All enhanced results use the deterministic key
  `(-score, doc_id, version, chunk_id)`; monotone calibration cannot invert it.
  `filtered_by_threshold_count` (alias `filtered_below_threshold`) counts only
  accepted, authorized, redacted entries in the controlled window before the
  final output limit, including entries that would otherwise be outside top K.
* Enhanced window defaults to max(40,4*limit), capped at 500; explicit
  `rerank_top_k` is 1..500 and cannot shrink below the requested output limit.
  Every entry entering it passes existing scope, current version, L2 published,
  8-step policy, RedactionRegistry and make_excerpt checks first. Scorers receive
  only nine frozen fields, bounded title<=2000 / excerpt<=32000 characters,
  accepted-only 1-based rank and the prior RRF. No body, ACL, denied-object count
  or cross-request/tenant/generation ranking cache is provided.
* Empty candidate sequences never invoke the reranker or calibrator. Existing
  explicitly configured vector-query embedding remains part of vector retrieval;
  all evidence here uses the explicit offline HashEmbedder, not an online model.

`DeterministicLexicalReranker` uses the shared bilingual tokenizer (English
normalization, CJK characters/bigrams), coverage .50, title coverage .18,
phrase/proximity .22, saturated length-normalized density .09, and small accepted
rank prior .01. Weights must be finite, nonnegative, sum to one and keep the prior
<=.05. Candidate IDs/families/relevance judgments are not relevance features;
IDs are used only for the mandated full-order tie-break.

`ScoreCalibrator`, `ScoreCalibrationConfig` and `CalibrationChannelConfig` are
frozen, deep-tuple configurations with strict to_dict/from_dict. All four channels
must occur exactly once. Minmax, stable sigmoid and monotone piecewise-quantile
anchors are supported, including extreme finite values. Bool aliases, malformed
anchors, nonfinite inputs, unknown methods/channels and invalid thresholds fail
closed. Reranker output must have exactly one *float* per candidate, finite and
not bool/int; errors do not expose scorer exception text.

## Trust and transport

LocalKnowledgeClient permits explicit `reranker` / `calibrator` instances or
constructor registries. Registries are copied into read-only mappings. The
optional CallableRerankerAdapter is **local-only**, does not import/load a model,
and has no URL, automatic network or remote transmission mechanism. An injected
host callable is trusted application code, not an untrusted-code sandbox.

HTTP `/v1/search` and `/v1/runtime/snapshots` accept only known server registry
names, never injected objects/registries/code/URLs. Both `rerank`, `reranker_id`,
`calibrator_id`, threshold and bounded window have Local/HTTP parity. Accepting
named `calibrator_id` resolves the taskbook's concise HTTP list omission in favor
of its explicit dual-client parity requirement; it does not expose configuration
mutation or callbacks. Malformed options are rejected even with no hits/none
scope. All responses and errors remain no-store.

MCP `search_evidence` supports the same named enhancement parameters. Task-bound
MCP and query snapshots validate owner, task scope, profile and six-family live
revocation **before scoring**, within the established runtime transaction/lock.
Runtime entry-list snapshots reject enhancement options rather than pretending to
rank an unordered explicit list. No terminal task is revived.

## Fixed-set paired evaluation

`PairwiseRetrievalEvaluator` executes real LocalKnowledgeClient searches against
one corpus/index/Actor/Purpose for both arms, holding the runtime boundary. The
fixture additionally hashes the actual offline vectors / persisted pgvector rows
before and after evaluation and checks equality. Report index_sha256 is that
trusted harness commitment, not an external index attestation. Corpus checks
exclude evaluator audit/usage side effects and include document/ACL/current
version/chunk data; documents cannot change during the measured pair.

The 32-family dataset/corpus/general config were committed and SHA-frozen in
`e21f41a` **before the first measured run**: 4 train, 4 calibration, 24 evaluation
families (18 positive, 6 refusal). Splits are disjoint by doc_family. No labels
were fitted into weights/calibration, no per-case thresholds or canned outputs
are used; the single .60 threshold and 100-entry window apply to every measured
case. Family identity/labels are consumed only after retrieval for metrics. Both
engines use the same frozen files; native lexical rank differences are retained,
not normalized away. No dataset/config change was made after measuring gains.

Metrics use actual rankings. Recall/NDCG/MRR average only positive labeled cases;
DCG uses graded relevance and unique document first occurrence. Citation precision
is relevant **valid authorized** citations / all returned hits: real reference
creation, consume receipt/hash and policy checks are performed for each hit.
Refusal accuracy uses all 24 cases; false refusal uses the 18 positives. Empty
metric denominators map to 0.0 and their case/hit counts remain explicit.
Latency is perf_counter search-only inclusive of authorization/ranking/calibration,
not citation-check overhead; interpolated P50/P95 are measured, not an SLA.

An explicit process-local OfflineBoundaryMonitor counts/blocks known SDK model
provider / urllib / socket.create_connection boundaries. Negative controls make
real blocked attempts and verify a nonzero count fails the evaluation gate.
This is instrumentation, not a general arbitrary-code/network security sandbox;
use it only in an isolated evaluation process. Local hash embeddings are explicit
non-semantic test work, not hidden provider calls. Real PG uses native psycopg
local connections. No online model, embedding service or Qdrant was called.

Reports are canonical-JSON frozen and validate finite metrics, integer counts,
denominators and the gate. `to_dict` returns a detached copy. Gains on this small
purpose-built fixed offline set are **not** production/generalization claims;
quality gains trade off with the larger controlled candidate window and its
measured extra latency. Independent M2 L5 review remains pending.
