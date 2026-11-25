# SDK Space Lifecycle — PROPOSED_PENDING_OWNER_RULING

Status: DRAFT_PENDING_OWNER_RULING. SDK-25, design review preparation only.
Source: byte-original 81-line Pre-v7 directive, Team A §II; actual prior six Space documents, prior draft, and project-lead suggested-ruling original were not supplied. This is a NEW proposed document, not a recovered original or fully calibrated final design. No existing SDK model, endpoint or Schema6 behavior changes.

All four authorization flags remain false: schema_v7_ddl_authorized, migration_authorized, prod_shadow_or_cutover_authorized, final_alignment_frozen. PRE-01–04 are unsigned/not supplied. Personal sharing/offboarding: GATED_BY_PRE02_PRE04. There is no assumed legal retention period, personal-content inheritance, automatic offboarding transfer or approved Team mapping.

## Flat ownership and identity (SPACE-C01/C04)

Tenant -> Space -> KB, exactly three layers; no parent_space_id, nested Space or phase-one cross-Space move. A Space has one explicit org_id and one-or-more KBs after provisioning; an empty initializing Space may exist only if separately approved. Each attached KB has exactly one Space, equal org_id, and no implicit tenant inference. Composite (org_id,space_id)/(org_id,kb_id) references are mandatory. Names, aliases, email addresses, admin badges and robot bindings are not identity or permission authority.

PROPOSED immutable home_space_id preserves the original binding even when detached; active space_id may be null while quarantined. Reattach must equal the recorded home, so detach+reattach cannot become a hidden cross-Space move. Detach NEVER archives a KB, deletes it, changes its tenant, changes content rights, or rewrites a citation. The detached KB is not made globally readable. This home-coordinate name is an experimental mechanism, not an approved target column.

## Proposed state machines and owner transfer

All state/action names below are PROPOSED_PENDING_OWNER_RULING, not approved product labels.

| Kind | Initialization/active | Freeze | Archive | Owner transfer |
|---|---|---|---|---|
| Enterprise | explicit enterprise tenant + approved management authority; current content ACL still separate | active->frozen by distinct freeze_archive capability; non-allowlisted operations fail closed | frozen->archived; metadata/archive only, no purge | explicit current authority + target active stable principal in same org; dual-control review proposed; ownership does not confer private-content access |
| Team | explicit stable collaboration group supplied by PRE-01; 1:1 vs1:N UNDECIDED | active->frozen; membership or source-authority uncertainty denies | frozen->archived after reviewed group event; detach is not archive | same-org active successor, verified authoritative group event, distinct transfer_owner permission; no email fallback |
| Personal | created for a stable same-tenant employee identity; owner-only prototype default | active->frozen on reviewed identity freeze process ONLY after PRE-04; no automated operational rule enabled here | retention and disposition UNDECIDED; no timer/purge implementation | GATED_BY_PRE02_PRE04; no approved transfer/inheritance rule and no non-owner content read via enterprise admin |

Proposed reopen: archived->frozen->active only after current authorization and owner/member/source revalidation; never restore historical ACL/security metadata. Frozen/archived content access defaults deny in prototype, not a final retention/legal policy. Owner deletion, inactive successor, unknown Team dissolution or source outage => remain frozen/quarantined and queue human review, not infer an owner. Content/filename rollback must never roll back security attributes, principal generation, memberships or external assertions. Personal space sharing, cross-tenant sharing and employee offboarding stay disabled pending BOTH PRE-02 and PRE-04 signatures.

## SPACE-C05 independent actions and upper bounds

The directive specifies eight independent actions but does not supply canonical names. Candidate names below MUST NOT be described as approved mappings of current OpenBot RPCs.

| Proposed action | Separate capability | No implied extra grant |
|---|---|---|
| read_metadata | current metadata visibility | not read_content |
| read_content | current readable KB/asset | not private bypass, source authorization still required |
| create_kb | create under authorized Space | not manage_members |
| attach_kb | same-org, original home binding | not move/archive |
| detach_kb | remove active binding | not archive/read-anywhere |
| manage_members | explicit membership operation | not read employee personal content |
| transfer_owner | reviewed same-org transfer | not content inheritance |
| freeze_archive | reviewed lifecycle mutation | not purge, offboarding, legal disposition |

Effective access = explicit tenant equality ∩ authoritative active User ∩ action capability ∩ current Space/KB/asset restrictions ∩ AgentProfile Space ceiling ∩ fine-grained KB/knowledge-file/deliverable/folder consumption scope ∩ purpose/lifecycle/source assertion. Explicit Deny wins at every layer; lack of a grant, unknown state, stale generation, missing source assertion or failed authority lookup denies. Admin/owner labels, robot bindings and favorites are never independent read grants. Legacy read/write/admin RPC-to-action mapping is Team B's separate draft; not implemented or signed here.

Within one transaction: update the permission, advance policy_generation, append idempotent outbox event. Consumers may accelerate invalidation, but event delivery/cache invalidation is NOT read authority. Each consumption/batch hydration must perform an authoritative current-generation check. Prototype row-share/update locking linearizes hydration versus revocation and tests rollback/outbox atomicity; it is not a production scheduler, distributed SLO measurement or external callback integration.

### Proposed revocation targets and exception SLA acceptance

Every numeric value in this section is PROPOSED_PENDING_OWNER_RULING, not approved or measured production SLA:
- Security invariant: no later authoritative read linearized after committed revoke may allow the revoked permission. Event delivery delay never creates an allow grace window.
- Proposed notification targets: p95<=1s, p99<=5s after commit; reconciliation sweep<=60s. These are planning budgets only; no production measurement is claimed.
- Proposed authority-call deadline<=500ms; deadline, provider outage, missing/expired assertion or generation mismatch => deny/unavailable immediately, no stale-allow fallback. Proposed incident acknowledgment<=5min and triage<=30min; those exception targets do NOT extend access validity.
- Acceptance plan: independently timestamp commit/read linearization and outbox propagation; block/drop/duplicate/reorder events; expire source assertion; simulate provider timeout and partition; confirm all denied without title/excerpt/source/credentials leak. Count no stale allow as the hard security outcome; report actual observed latency separately from proposed thresholds. Signoff and load/clock/region assumptions remain missing.

## SPACE-C06 favorites (OpenBot single writer)

OpenBot alone owns favorites writes keyed by tenant_id+stable user_id. SDK candidate hydration is read-only for target_type kb|asset. A requested inaccessible/nonexistent/cross-tenant target produces only requested target_type,target_id,state=unavailable; it must not disclose title, owner, excerpt, source URI, credentials, counts or internal policy reasons. Available DTOs are built only after current authority checks. Generic unavailable UX is a proposed DTO behavior, NOT approved placeholder UX. No OpenBot backend/localStorage migration is implemented.

## SPACE-C08/C10 supply and consumption

AgentProfile Space ceiling is retained, never substituted for fine scope or current User rights. Empty prototype ceiling/scope denies; that is an explicit candidate choice, not an alteration of current SDK v2 allowlist semantics. Each consumption rechecks current profile generation and User policy. Folder/KB grants cannot bypass asset Deny, tenant equality or source constraints.

Unified AssetEnvelope discriminates uploaded_document, agent_deliverable and enterprise_materialized_ref. Five agent-deliverable labels draft/generating/ready/published/withdrawn are PROPOSED_PENDING_OWNER_RULING (the directive gives five states but no names). Materialized refs require projection_id, scope_applied, masked_fields, trace_refs, freshness, publication_state complete|partial, cursor and tombstone. Missing/expired/failed source authority denies; tombstone invalidates cursor and contains no materialized body/credentials. Proposed provider assertion binds tenant+subject+asset+generation+expiry; trust/signature/key distribution remains a review gap, not a live external integration. data_capability is a separate mediated Tool boundary, never a document payload or route to database credentials.

## SPACE-C09 compatibility

Candidate independent /v3/spaces and /v3/favorites:hydrate appear only as draft OpenAPI; /v2/knowledge-spaces is still an undecided alternative. No routes are mounted, no SDK src files modified, and accepted9940818b /v2/spaces/Schema6 semantics remain byte-original.
