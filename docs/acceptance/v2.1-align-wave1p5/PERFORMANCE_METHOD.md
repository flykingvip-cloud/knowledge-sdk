# Same-physical-snapshot before/after, fixed offline evaluation only

Pristine Wave1 `60b6436ed9fccb4b49ae32e30f1664412e505888` measurements were saved
before any extension runtime edits. SQLite backup + exact vector entries and a
retained isolated PG/pgvector schema survive both arms/phases. The existing
Wave1 perf_snapshot harness uses the frozen M2 dataset/config: 24 evaluation
families, rerank window100, threshold0.6, same weights/candidate pool/policy/audit.
One warmup, five paired repeats (120 measured samples/arm), search-only real
perf_counter timings, all latencies/P50/P95/means retained. Identical outer test
transaction rolls audit/usage-only writes back in both phases; the product does
not skip audit. No labels enter ranking/calibration or threshold tailoring.

Wave1's +0.043ms SQLite/+0.478ms PG plain-RRF P50 differences were small enough
that noise must not be called a proven causal regression. New before profiles
identify repeated principal reads (`_AuditedEngine.evaluate`), alongside required
policy/audit/store work. The only optimization reuses a successfully validated
identity in one existing locked runtime transaction. It keys the full Actor,
Agent, purpose, policy context and required-principal mode and invalidates on
principal writes; no denial, policy/redaction/resource/profile/task decision or
rank result is cached. Every request still refreshes at entry and completion;
vector-query and external rerank/calibration boundaries refresh again. Reentrant mutations fail
closed; PG's existing runtime advisory transaction lock orders second-connection
mutations and the next request immediately sees revocation. Lifetime is cleared
on success, exceptions and nested request exit. All candidate policy audits
remain real. There is no cross-request/tenant/generation cache.

Physical catalog hashes prove no table/column/index/RLS change. The initial
catalog capture occurs before the optimization's measured after run (Task0's
prior audit-only JSON changes do not touch DDL). Full source schema definition
files are also compared against Wave1. Compare script asserts identical dataset,
corpus, vector index, configuration, protected candidate identities/order/text
hashes and every repeated quality aggregate before emitting deltas. Latency
changes, including any slower arm/P95, must be reported honestly. This is a fixed
offline fixture result on one physical machine, not a production performance SLA.
