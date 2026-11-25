# SDK Schema v7 migration proposal — DESIGN ONLY

DRAFT_PENDING_OWNER_RULING / PROPOSED_PENDING_OWNER_RULING. NEW proposed document, not one of the missing six originals. This file contains no executable SDK migration. schema_v7_ddl_authorized=false; migration_authorized=false; prod_shadow_or_cutover_authorized=false; final_alignment_frozen=false.

## Conceptual target (not implemented Schema7)

| Logical entity | Candidate coordinates/constraints | SQLite design | PostgreSQL design |
|---|---|---|---|
| Tenant | explicit non-null stable org_id, no null personal-tenant assignment | NOT NULL + explicit equality on every query/transaction | same plus FORCE RLS |
| Space | (org_id,space_id), E/T/P, stable owner, lifecycle, policy_generation | composite unique, checked kind/state/generation, no parent column | composite unique/checks, org-bound ENABLE/FORCE RLS even owner |
| KB binding | (org_id,kb_id), immutable proposed home_space_id, nullable active space_id | composite same-org FKs; active null or equals home; immutable-home trigger proposal | same constraints/immutable trigger proposal; owner cannot bypass FORCE RLS |
| Membership/action decision | (org,space,subject,independent_action), explicit Deny | no admin-read shortcut, eight actions independently evaluated | same + tenant policy, non-superuser/NOBYPASSRLS app role |
| AgentProfile consumption | current version + Space ceiling + fine scopes | join current User and source policy on every read | same; no role with BYPASSRLS in auth tests |
| External projection assertion | tenant/subject/resource/generation/expiry; no secrets/body inheritance | no assertion/cache fallback on provider failure | same; source revocation immediately affects later authoritative reads |
| Transactional outbox | permission event+new policy_generation in same commit | atomic transaction, idempotent event coordinate | atomic transaction and consistent lock order; delivery not authority |

Names/columns are candidates only. Production Schema6 tables/migrations/indexes/RPCs remain untouched. The separate sandbox uses p_* throwaway tables in a newly generated owned database or new in-memory SQLite, not production targets or a v6->v7 migration. No metadata_snapshot/security rollback, no history rewrite, physical purge or source credentials.

## Preconditions and future staged plan (NOT authorized now)

1. Obtain all actual prior six documents, suggested-ruling source and PRE-01–04 signed records. Resolve Team mapping1:1 vs1:N, collaboration_group authority, personal sharing/offboarding, placeholder UX, state/action names and SLA.
2. Review target invariants, exact per-engine locks/online-DDL/backup/restore/old-binary compatibility strategy and all27 formal test plans. Inventory aliases and null tenants without reading business bodies.
3. Only after separate written implementation authorization: design opt-in additive expansion, immutable mapping journal and reviewed alias resolution; retain v6 read path and every old table/index/RPC. No implicit rename or tenant assignment. This document is not permission to run that step.
4. Future backfill would require approved deterministic mapping and idempotent batches, per-tenant transaction fences, checksums/counts and explicit quarantines. Current dry run only reports supplied mappings; it performs NO backfill.
5. Production shadow/cutover require separate approvals, not implied by design acceptance, prototype results or any later Schema7 DDL authorization.

## Candidate PRE-03 read-only analyzer

Actual Team B PRE-03 schema/data is NOT supplied. `sandbox/space_alignment_v1/dry_run.py` implements candidate-pre03-v1, described by `pre03-candidate.schema.json`; an explicit reviewed adapter must translate a future official format. Do not label the candidate as Team B signed.

File-only stdlib analysis; no database imports/connections, business body, secret discovery or SQL. Inputs contain only pseudonymized syn_* IDs/name/alias tokens and explicit nullable tenant/mapping coordinates, sanitized:true and declared provenance. Unknown properties, PII/body/credential fields and non-pseudonym tokens reject with a fixed non-echoing error. Pseudonym shape alone is not proof of anonymization: supplier remains responsible for sanitization. Examples are SYNTHETIC_EXAMPLE only.

Counts: explicit tenant count, null-tenant row count, supplied oldKB->Space+KB mappings, null aliases, duplicate legacy keys, same-tenant target collisions, casefolded/NFKC alias/name collisions. No cross-tenant alias merging; null tenant never inferred or emitted as an assigned mapping. Deterministic canonical input/order and sorted alerts; input SHA256 before/after must match. Exit0 clean,2 findings/manual review,3 invalid/refused. Only stdout or a NEW explicit output file may be written; input-as-output and existing output are refused. This is not a migration decision, an approved collision resolution, or real inventory evidence.

## Proposed reversible rollback and exceptions

- Current wave rollback = disable/remove only isolated prototype tooling/owned disposable resources; accepted v6 runtime is unchanged, so there is no production data rollback.
- Future authorized expansion rollback must retain original immutable data and old read path, route rollback behind a separately controlled feature boundary, and reconcile additive objects without dropping originals. Reversibility must be proven using approved backup/restore and per-tenant mapping journal, not asserted from this prototype.
- Security state is monotonic: never restore old ACLs, User status, principal/profile generations, revocations, source assertions or personal-content inheritance from historical content versions. Stop reads/fail closed if a rollback cannot preserve current security state.
- Null tenant, name/alias collision, unknown Team authority, orphan FK, incomplete projection, stale cursor/assertion, replay/generation mismatch or failed checksum => quarantine/report and owner review. No auto-merge, auto-owner or automatic null-to-enterprise assignment.
- Lock timeout, concurrent revocation, outbox failure or partial writer failure => atomic rollback; no stale-allow fallback. Owner loss/provider outage => deny, preserve evidence, escalate under PROPOSED SLA only. Legal hold/retention exceptions require PRE-04 decisions; no invented legal period.
- Formal rollback review, production workload tests, HTTP/Python/MCP compatibility and recovery drill remain NOT MET for future Schema7. Prototype success does not sign any of those gates.
