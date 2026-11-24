# v1.2 Q1-M2: policy / redaction integration contract

This phase implements B03 after the user-authorized Phase 1 engineering gate.
It does not close historical live semantic/proxy/browser gaps. Core remains pure
stdlib Python 3.9+ syntax, dependencies=[], business SQLite user_version=1.
All resource extensions are JSON fields; rules are constructor/instance injected,
not a new database schema, policy service, condition DSL or Workbench redesign.

## Public contracts and ordered decisions

Purpose, PolicyAction, DecisionEffect, GovernanceTier, AgentIdentity,
ResourceRights, PolicyRule, PolicyContext and PolicyDecision are public exports.
New policy models are frozen dataclasses, strictly validate field types, normalize
purpose/action tuples and provide strict from_dict / JSON roundtrips. Mutable
input dictionaries/lists are defensively copied/frozen. Unknown nonempty
condition_meta is rejected, not interpreted as a permissive future condition.
All configured timestamps must be ISO8601 with an explicit UTC offset or Z;
comparison is in UTC, validity endpoints are inclusive. No naive datetime mix.

DefaultPolicyEngine.evaluate has eight short-circuit gates:
1. Tenant / document-space identity.
2. Revocation, archive, controlled lifecycle and validity windows.
3. Explicit ACL deny and matching deny rules (even owners/admins).
4. Space read/upload/manage capability — rules never override this boundary.
5. Existing v1.0/v1.1 document ACLs or qualified in-space allow rules.
6. Agent allowed purpose, KB scope, and known clearance ceiling (intersection).
7. Resource retention and usage rights (intersection, not boolean override).
8. All applicable redaction obligations, deduplicated in deterministic order.

Rules sort by ascending priority, stable at ties. IDs are unique within tenant,
not globally. Every nonempty subject selector dimension must match. Rule department
selectors match direct departments only; fine DocumentACL subdepartment behavior
is unchanged. Required clearance gates allow grants with the four standard
levels; unknown levels do not grant. A DENY rule's required_clearance does not
create a lower-clearance exemption: matched deny selectors conservatively deny.
Personal-only ACLs cannot be opened by rules. A legacy private document otherwise
unreadable requires an explicitly scoped document+user rule, not a broad wildcard.
Existing can_read/can_manage/can_upload/scope_filter signatures remain legacy ACL
primitives; all SDK content delivery additionally goes through the policy engine.

Decision audit output contains no source titles/bodies. context.policy_generation,
when nonempty, overrides the Actor generation. Context is trusted in-process input;
HTTP callers cannot supply it. Derived decisions fail closed for empty/denied
sources. Mixed source generations are marked `mixed` with an explicit generation
list in audit_summary, never falsely reported as a single shared generation.

### Normative default-rights correction

The task book's earlier two-purpose default conflicts with its explicit Step 7
correction. This implementation follows the correction: ResourceRights defaults
to READ + GROUND_INTERNAL_LLM + EXPORT, with allow_export=True. External LLM and
training remain denied. Explicit allowed_purposes always intersects booleans:
allow_external_llm=True alone does not add that purpose. Purpose is a trusted
usage declaration, not regulatory approval, training consent, or proof of what a
caller later does with delivered data. No external model was invoked in testing.

## SDK enforcement and safe delivery

LocalKnowledgeClient accepts keyword-only policy_engine, policy_rules and
redaction_registry. Each client defaults to its own engine/empty registry.
New evaluate_policy and set_document_rights APIs are transported over HTTP too.
The latter requires actual space management authority, cannot change membership
or ACLs, and returns a Document with user-supplied title/metadata suppressed (the
management operation is not a personal-content read grant).

Agent/purpose/context propagate through search/retrieve/preview, document/version
inspection, scopes/bindings, references/consume/verification/attach and ask.
Search rechecks every keyword/vector/hybrid candidate against authoritative SQLite
under SEARCH_INDEX; deny, missing hooks or failed hooks remove the candidate.
The vector payload is never an authority. Explicit write rules also gate existing
version updates and newly created document identities before blob/DB persistence.

Resource rights and lifecycle/validity controls supplied at ingest require space
admin; ordinary uploaders cannot publish controlled knowledge. All new semantic
uploads to controlled KBs default to draft unless an admin explicitly chooses a
state, including updates to previously published documents. Same-content admin
control changes persist without inventing a content version. Unspecified controls
are preserved across updates; None means no update (no implicit validity reset).
This is not an approval/release workflow engine. Uploads can succeed while their
post-write read is denied (e.g. missing redactor/revoked rights); response is then
metadata-only DocumentVersion with text/hash/filename/blob fields suppressed.
Normal legacy uploads still return content as before.

Redaction applies before excerpt construction/pagination, and to detached version,
chunk, title, filename, heading/section and descriptive metadata delivery views.
Stored source text/blob is not rewritten. Returned delivery text fingerprints and
chunk offsets/hash describe the transformed representation; original blob paths
are suppressed. A transformed version raw_hash is a delivery digest, NOT the
original upload-byte digest. Original storage remains authoritative provenance.
No raw blob download API is added. Missing hooks block metadata inspections too.

RedactionRegistry is empty by default. Register reviewed hooks explicitly; comma
profiles execute in order, with no plaintext fallback on missing/exception/invalid
returns. Errors are generic and do not chain plaintext-bearing plugin exceptions.
RegexRedactionHook accepts only operator-supplied patterns/replacements; summaries
contain substitution counts, not matched sensitive values. Hook metadata is copied.
Hooks must be trusted, deterministic, side-effect-free and reviewed for regex
runtime cost and safe summaries. They are not an untrusted-code sandbox; hooks,
parsers, vector/embedding adapters and host infrastructure remain trusted plugins.
Existing configured embedding/index backends were not replaced or certified for
external-data governance here; this phase tests those paths only with offline
stubs and does not infer provider location or authorize a remote model.

References are validated against the **current delivered** source representation,
not a raw-source hash falsely equated to masked content. Already-masked excerpts
are not masked twice. Old plaintext excerpts and empty full-content refs cannot
bypass newly required redaction. Full redacted references carry the delivered
excerpt/hash, and receipts match that exact representation. Profile changes can
invalidate an old reference; the response denies instead of silently accepting it.
Normal tampered legacy references still raise existing TamperedExcerptError.
Archived receipt compatibility remains unavailable/archived unless an explicit
trusted include_archived context is provided; there is no hidden read bypass.

## Ask and HTTP trust boundary

ask purpose omitted: built-in extractive generation uses READ; an explicit custom
or server-configured generator uses GROUND_INTERNAL_LLM. Explicit READ differs
from omission. Explicit external purpose must independently pass both agent and
resource rights. Before any generator, every source is re-read, SEARCH and READ
decisions intersected, redaction reapplied to current source and references /
receipts validated; decisions are checked again after hooks immediately before
handoff. Deny/missing hooks/ref mismatches refuse with model_called=False. Plugin
re-entrant revocation is tested before generation; after-generation revocation
also suppresses the answer (already-reported model usage cannot be undone).
If SEARCH-only and READ-only profiles produce incompatible reference
representations, ask conservatively refuses instead of dropping an obligation.
This does not provide a distributed transaction across a remote generator and
concurrent out-of-process mutations; production must manage that consistency.

HTTP strictly preflights AgentIdentity.from_dict **before nonce consumption**,
then verifies HMAC, tenant and replay; request.state holds typed AgentIdentity /
Purpose. Unknown/type-invalid agent claims return 401. The low-level Phase 1
signing helpers still support forward-compatible JSON objects, but the Phase 2
HTTP execution boundary rejects unsupported identity fields. Bodies may not set
actor/self/agent/purpose/policy_context (400 Invalid parameters). Header context
is injected only into supporting methods. HttpKnowledgeClient puts explicit agent
and purpose in signed headers, never the body; omitted defaults retain old six-line
signatures. Non-None HTTP policy_context is rejected locally. A malformed typed
agent cannot poison a nonce before a later valid request.

The Phase 1 synthetic request.state probe's expected JSON was updated from a raw
minimal dict to typed AgentIdentity's explicit defaults, as required by Q1-M2.
All existing behavioral checks remain; no denial assertion or real integration
was removed to make tests pass. No new host-login hook, demo signer activation,
UI redesign, production reload or background service is part of this work.
