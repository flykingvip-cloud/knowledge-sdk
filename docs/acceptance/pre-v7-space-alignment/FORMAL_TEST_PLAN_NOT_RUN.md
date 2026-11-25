# Candidate formal test plan — NOT RUN / NOT ACCEPTED

Candidate scenario allocation to reserved T-01–T-27 IDs ONLY: authoritative full test definitions are not supplied; numbering must be reconciled during review. These are future SQLite/PostgreSQL FORCE-RLS/HTTP/Python/MCP plan items, not claimed executable formal tests. Prototype P_SPACE/P_DRY/P_CONTRACT identifiers are separate and do not pass any T gate. Specifically T-18–T-27 have NOT passed. Review itself is NOT complete.

| Reserved ID | Proposed scenario | Required surfaces | Status |
|---|---|---|---|
| T-01 | Explicit enterprise tenant and tenant boundary | SQLite + non-superuser FORCE-RLS PostgreSQL; HTTP/Python/MCP where applicable | NOT_RUN_NOT_ACCEPTED |
| T-02 | Flat Tenant-Space-KB, no parent | SQLite + non-superuser FORCE-RLS PostgreSQL; HTTP/Python/MCP where applicable | NOT_RUN_NOT_ACCEPTED |
| T-03 | Same-org composite KB binding | SQLite + non-superuser FORCE-RLS PostgreSQL; HTTP/Python/MCP where applicable | NOT_RUN_NOT_ACCEPTED |
| T-04 | Detach not archive and same-home reattach | SQLite + non-superuser FORCE-RLS PostgreSQL; HTTP/Python/MCP where applicable | NOT_RUN_NOT_ACCEPTED |
| T-05 | Employee personal owner boundary | SQLite + non-superuser FORCE-RLS PostgreSQL; HTTP/Python/MCP where applicable | NOT_RUN_NOT_ACCEPTED |
| T-06 | Enterprise admin no private-content shortcut | SQLite + non-superuser FORCE-RLS PostgreSQL; HTTP/Python/MCP where applicable | NOT_RUN_NOT_ACCEPTED |
| T-07 | Two same-tenant collaboration groups isolation | SQLite + non-superuser FORCE-RLS PostgreSQL; HTTP/Python/MCP where applicable | NOT_RUN_NOT_ACCEPTED |
| T-08 | Eight independent action grants | SQLite + non-superuser FORCE-RLS PostgreSQL; HTTP/Python/MCP where applicable | NOT_RUN_NOT_ACCEPTED |
| T-09 | Explicit Deny precedence | SQLite + non-superuser FORCE-RLS PostgreSQL; HTTP/Python/MCP where applicable | NOT_RUN_NOT_ACCEPTED |
| T-10 | Agent Space ceiling | SQLite + non-superuser FORCE-RLS PostgreSQL; HTTP/Python/MCP where applicable | NOT_RUN_NOT_ACCEPTED |
| T-11 | KB fine-grained consumption scope | SQLite + non-superuser FORCE-RLS PostgreSQL; HTTP/Python/MCP where applicable | NOT_RUN_NOT_ACCEPTED |
| T-12 | Knowledge-file scope | SQLite + non-superuser FORCE-RLS PostgreSQL; HTTP/Python/MCP where applicable | NOT_RUN_NOT_ACCEPTED |
| T-13 | Deliverable scope | SQLite + non-superuser FORCE-RLS PostgreSQL; HTTP/Python/MCP where applicable | NOT_RUN_NOT_ACCEPTED |
| T-14 | Folder scope | SQLite + non-superuser FORCE-RLS PostgreSQL; HTTP/Python/MCP where applicable | NOT_RUN_NOT_ACCEPTED |
| T-15 | Current User intersection and current profile | SQLite + non-superuser FORCE-RLS PostgreSQL; HTTP/Python/MCP where applicable | NOT_RUN_NOT_ACCEPTED |
| T-16 | Transactional revocation/outbox rollback | SQLite + non-superuser FORCE-RLS PostgreSQL; HTTP/Python/MCP where applicable | NOT_RUN_NOT_ACCEPTED |
| T-17 | Current policy generation strictness/staleness | SQLite + non-superuser FORCE-RLS PostgreSQL; HTTP/Python/MCP where applicable | NOT_RUN_NOT_ACCEPTED |
| T-18 | Future HTTP independent-version compatibility | SQLite + non-superuser FORCE-RLS PostgreSQL; HTTP/Python/MCP where applicable | NOT_RUN_NOT_ACCEPTED |
| T-19 | Future Python candidate protocol compatibility | SQLite + non-superuser FORCE-RLS PostgreSQL; HTTP/Python/MCP where applicable | NOT_RUN_NOT_ACCEPTED |
| T-20 | Future MCP candidate policy compatibility | SQLite + non-superuser FORCE-RLS PostgreSQL; HTTP/Python/MCP where applicable | NOT_RUN_NOT_ACCEPTED |
| T-21 | External source missing assertion | SQLite + non-superuser FORCE-RLS PostgreSQL; HTTP/Python/MCP where applicable | NOT_RUN_NOT_ACCEPTED |
| T-22 | External expired assertion | SQLite + non-superuser FORCE-RLS PostgreSQL; HTTP/Python/MCP where applicable | NOT_RUN_NOT_ACCEPTED |
| T-23 | External provider outage | SQLite + non-superuser FORCE-RLS PostgreSQL; HTTP/Python/MCP where applicable | NOT_RUN_NOT_ACCEPTED |
| T-24 | External revocation/tombstone/cursor | SQLite + non-superuser FORCE-RLS PostgreSQL; HTTP/Python/MCP where applicable | NOT_RUN_NOT_ACCEPTED |
| T-25 | Polymorphic favorite current-ACL hydration | SQLite + non-superuser FORCE-RLS PostgreSQL; HTTP/Python/MCP where applicable | NOT_RUN_NOT_ACCEPTED |
| T-26 | Future reviewed migration/rollback drill and security monotonicity | SQLite + non-superuser FORCE-RLS PostgreSQL; HTTP/Python/MCP where applicable | NOT_RUN_NOT_ACCEPTED |
| T-27 | Personal-sharing/offboarding approval gating and full reviewed acceptance | SQLite + non-superuser FORCE-RLS PostgreSQL; HTTP/Python/MCP where applicable | NOT_RUN_NOT_ACCEPTED |

## Eight exit gates

1. NOT_MET — C01–C10 written owner decisions absent; C02/C07 originals missing.
2. NOT_MET — PRE01–04 signed evidence absent.
3. NOT_MET — Authoritative dual-engine target design/official PRE03 dry run absent; candidate synthetic prototype only.
4. NOT_MET — Collision handling proposal exists but not formally decided/reviewed.
5. NOT_MET — Formal27-test cross-surface plan not reviewed, HTTP/MCP future tests not run.
6. NOT_MET — Candidate core prototypes pass only their listed P invariants; full authoritative scope/review absent.
7. NOT_MET — Rollback proposal not reviewed/approved.
8. NOT_MET — Separate Schema7/production/legal/security implementation authorization absent; allfourflagsfalse.

Do NOT generate FINAL_SPACE_AND_FAVORITES_ALIGNMENT.md or infer an implementation/cutover authorization.
