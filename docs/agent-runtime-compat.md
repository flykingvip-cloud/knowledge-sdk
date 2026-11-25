# Align-Wave1 additive v1 compatibility

Schema remains 5; no table, column, DDL or migration changes. Core dependencies
remain empty and package version remains 1.2.0 (the v2.0.0 tag drift is historical,
not corrected without release instruction). Existing 62 operation formats remain;
eight additions bring OPERATIONS to 70. Local/Http share reflected signatures:
get_kb, update_kb, list_kb_members, revoke_kb_member, list_document_versions,
diff_document_versions, rollback_document, plan_sync. list_documents adds only
keyword-only archived_only=False. Existing list/default and version selectors
are unchanged. No runtime v2 endpoint exists.

All management/history methods hold client lock then the store's schema-v5
runtime transaction, recheck trusted current identity, and use DefaultPolicyEngine
including explicit Deny and User ∩ Agent. Unknown/foreign/unauthorized IDs have a
uniform `resource_unavailable` denial on new single-resource methods. New IDs and
version integers reject malformed values, including bools. DENY audits persist
for rejected protected operations. Successful mutations' audit/outbox share the
transaction; failure injection proves no partial membership removal.

Only name/visibility/governance_tier may be updated. Strict tier visibility
changes must preserve the actor's actual MANAGE_SPACE authority in the resulting
space; otherwise fail closed, never orphan management or transfer identity.
L2 spaces with retained documents cannot be downgraded to bypass publication.
Name-only changes do not revoke tasks; space-policy changes conservatively revoke
active organization tasks. Member removal keeps v5's intrinsic immutable Owner
(owner_id / owner_user_id, stored as an admin member); there is no owner-transfer
API, so removing that owner always conflicts even with other admins. Advisory
serialization enforces this across independent PG connections.

Revoking a membership removes that grant, atomically emits kb.member_revoked,
and conservatively revokes all active tasks owned by the removed user, including
empty-snapshot tasks. Revocations/ImpactAlerts link the originating event and do
not require dispatcher flushing. Independent legitimate enterprise/department
policy grants are not turned into a fabricated permanent explicit Deny.

Version lists return read-authorized publication-history metadata in ascending
order, no body/blob. Diff validates current and both historical version delivery
and redaction obligations before computing any lines/counts; failed hooks deny.
It fails closed above one million combined REDACTED characters or 10,000 lines.
Rollback validates READ and WRITE, copies target text and its available version
metadata (filename), appends current_version+1 even for identical text, retains
current ACL/rights/validity/document metadata, and does not revive archived,
revoked or historically revoked sources. L1 lifecycle is preserved; L2 produces
an unreadable draft behind the existing three-person workflow. Existing pending
versions cause Conflict rather than overwrite. Anchor drift/orphan events mirror
normal ingest. Old snapshots remain sealed; ordinary revisions produce SUPERSEDED.
The rollback audit explicitly records rollback_from_version=target_version,
previous_current_version and created_version as strict numeric fields.

IMPORTANT affected limitation: schema v5 never stored historical business-level
Document.metadata/title/ACL/rights/validity snapshots in DocumentVersion. Exact
restoration of past arbitrary document metadata cannot honestly be implemented
without inventing history or changing the forbidden schema/old serialized
contract. That affected subrequirement is NOT declared complete: retain current
security/document metadata and request owner/architect disposition at review.
No historical policy state is fabricated; historical publication plus current
policy are the existing authoritative gates.

Connector plans are pure preflight, never real run_once followed by rollback.
They share commit preflight decisions and validate source hashes/scope/content,
ACL updates and tombstones using request-local detached state. No business SQL
writes, audit writes, cursor advances, ack/consume/drain or source file writes,
even on rejection. Built-in controlled-filesystem scans/webhook verification are
explicit read-only implementations. Unknown custom connectors require a supplied
immutable batch through Runner.plan_sync; their sync_since is never called.
Nonstandard side-effectful policy engines are rejected for planning. Local/HTTP
plan_sync accepts only a server-configured connector_id registry, no code/URLs.
Agent/purpose narrowing applies. Authentication replay/failed-auth auditing is a
separate existing security boundary; HTTP authentication is not misrepresented
as a byte-for-byte read-only transport. Plan core itself writes nothing.

Performance uses request-local authoritative bulk metadata reads under the same
runtime transaction, plus per-request chunk/title-token reuse. No policy decision
or principal-generation checks are skipped; no cross-request/tenant/generation
rank cache exists. Pools/window=100/threshold=.6/weights and the 24-family fixture
are frozen and independently hashed, with pool-observer evidence. Public server
allowlists and enhanced score meanings remain Q3-M2 contracts.
