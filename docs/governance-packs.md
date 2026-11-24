# Q2-M3: controlled releases, manual correction and evidence snapshots

No new core dependency. SQLite and PostgreSQL use the same contracts/services;
existing schema-v3 reserved tables are reused, not duplicated. Existing L1
`ingest` remains immediately published. No OIDC/SCIM, external connectors or models.

## L2: three distinct actors, two version tracks

Create a KB with `governance_tier="l2_controlled"`. Ingestion always makes a draft;
`ingest(lifecycle_state="published")` is forbidden even for admins. A draft upload
receipt contains identifiers/state but **no draft body**. Normal content APIs
(including explicit version reads, references, anchors, MCP and all search modes)
never deliver drafts. Trusted local authors/editors may work with their source
input; this change does not introduce a draft editing UI/content-read API.

```python
# Actor claims must come from a trusted host, never an end-user JSON body.
c.submit_for_review(author, doc_id, version=2, expected_version=2, note="ready")
c.approve_release(reviewer, doc_id, version=2, expected_version=2,
                  comment="checked", conditions="valid in stated conditions")
c.publish_release(publisher, doc_id, version=2, expected_version=2)
```

All three IDs must differ. Admin is not an exemption. Approval/publish require
`APPROVE_RELEASE` / `PUBLISH_RELEASE` policy decisions; default policy requires
KB management. Legacy KBs still require explicitly granted membership/ownership,
not merely an org-role claim. Submission requires write permission. Explicit
stale candidates and wrong expected versions conflict. Submission's optional
`expected_version=None` follows the taskbook's compatibility signature; supply
it for optimistic concurrency. Latest version numbering is independent of the
online `documents.current_version` pointer. Versions/decisions remain per-version;
old approved/publication snapshots are never overwritten by a new draft.

An approved candidate is still unsearchable. Publication transaction advances the
live pointer, refreshes FTS, appends review+audit and `doc.published` outbox. Native
PG vector operations share the store transaction; external indexes still need the
existing durable dirty-marker/reindex recovery and cannot form a distributed
transaction. No external index was used for these tests. Do not infer a general
external-index atomicity guarantee from native PG results.

`reject_release(..., version, expected_version, reason)` returns `in_review` to
`rejected`, which can be resubmitted. `record_dissent(..., version, note,
stance="dissent", target_anchor_id="")` is append-only in review/approved/published
states. SQLite triggers and a PG trigger reject UPDATE/DELETE of review records.
`get_release_manifest(..., version=None)` returns immutable per-version metadata,
all dissent notes and resolved issue IDs; it is a management read, not a new grant
to draft content. Dissent survives re-review and appears in later sealed packs.
No method deletes or overwrites decisions. Trusted SQL owners can of course drop
triggers; this is not protection from a hostile database administrator.

Drafts preserve the old live document metadata and indexes. Ingesting an identical
controlled draft is a no-op, never a way to reset the online lifecycle. For changes
to **document-level** rights/ACL use `set_document_rights` / `set_document_acl`;
rights are not separately versioned. New draft metadata does not silently change
live metadata. Authors should use those explicit controls when restrictions need
to apply immediately, rather than expecting draft ingestion to change live rights.

## Four manual issue actions

`resolve_evidence_issue(actor, issue_id, resolution_action, note,
expected_version=None)` requires document review authority. Actions:

* `create_revision_draft`: L2 copies published context to a linked new draft, or
  links an existing draft via the immutable resolution. L1 records pending manual
  revision without changing content/version. Both retain source issue lineage.
* `retrieval_tuning`: records a manual optimization followup; no weights/models
  change. Offline evaluation and an explicit later implementation are still needed.
* `keep_dissent`: appends a permanent version/anchor-associated dissent record.
* `dismissed`: manually closes a false positive as dismissed.

Other actions resolve the issue. The immutable `IssueResolution` is persisted
inside the existing `EvidenceIssue`. Terminal issues cannot re-enter; the bound
source version is the optimistic token. State, audit, dissent/draft and
`OutboxEvent(aggregate_type="issue", event_type="issue.resolved")` commit or roll
back together. Outbox carries identifiers only, never notes or source plaintext.

## Sealed packs and fail-closed output

`create_evidence_pack(actor, title, entries, *, topic="", effective_decision=None,
dissent_notes=(), seal=True, purpose=Purpose.EXPORT, pack_id=None)` takes entries
with `doc_id`, explicit published `version`, optional `anchor_id`, `stance`,
`condition_note`. Stances are supporting/refuting/negative/conflict/contextual.
No caller-provided source excerpt or hash is accepted. The service selects actual
version/anchor content, applies live policy + redaction and stores usage lineage.
Unhealthy anchors, missing hooks, drafts, archived/revoked sources fail closed.

Digest = SHA256 of canonical JSON (`sort_keys=True,separators=(",",":")`, default
ASCII escaping) of org_id/title/topic/items/dissent_notes/effective_decision.
IDs, creation time, status are not part of that specified immutable snapshot.
`effective_decision` is recursively frozen. Imported records must use the strict
EvidencePack shape for typed get/export; legacy reserved-record impact scans remain
compatible. There is no mutation/reseal endpoint or partial-output mode.

`get_evidence_pack`, `list_evidence_packs`, `verify_evidence_pack`,
`export_evidence_pack` always recheck every source. Export rights are required even
when the requested purpose is read/internal, preventing a Purpose-header bypass.
New redaction that would change a sealed excerpt or review metadata rejects the
whole pack: it does not rewrite the historical snapshot. All hook calls precede
an additional full policy comparison; a hook cannot revoke an earlier item and
then make a partial plaintext pack escape. Every JSON/ZIP/file output follows
another complete check. Verify returns `digest_valid=False` for a metadata digest
mismatch; get/export reject tampering. Denied reads do not expose pack contents.

`export_evidence_pack(..., format="json"|"ro_crate", output_path=None)` returns
`ExportResult`: content UTF-8 JSON or base64 ZIP, encoding, media_type, SHA256 and
optional caller-local path. Local paths are written only after authorization and
seal checks; a denied export creates no output. `HttpKnowledgeClient` writes its
**caller's** path after a successful response; the server rejects any remote
`output_path`. File writes are not part of the database transaction.

RO-Crate is stdlib-only, deterministic stored ZIP: `evidence-pack.json`,
`ro-crate-metadata.json`, `REVIEW_SUMMARY.md`. Metadata includes descriptor
CreativeWork/conformsTo/about, root Dataset name/description/license/datePublished/
hasPart and typed evidence entities with stance/conditionNote/sourceUri/sha256/
dissentNotes. The license notice grants no additional rights. Root requirements
were checked against the [RO-Crate1.2 specification](https://www.researchobject.org/ro-crate/specification/1.2/root-data-entity.html).
No external validator/certification is claimed; tests assert the required graph.

Drain the existing outbox with an admin/worker. Real doc publication/revision,
revocation/archive, rights/ACL changes and anchor drift/orphan events flag matching
packs `impacted` and produce `ImpactAlert(target_type="evidence_pack")`. Rights/ACL
changes conservatively use access_revoked as a re-review marker, even if the pack
creator still has access; current access is always decided anew on read/export.
Only the status column changes, not the sealed items/excerpts/hash. No background
daemon is started automatically and no automatic replacement snapshot is made.

## Adapters

All methods exist on Local/HTTP clients and `KnowledgeClient` protocol; signed
HTTP operation table and argument shapes are in [api-contract.md](api-contract.md).
New governance/pack/issue-resolution APIs reject dev-insecure mode and reuse HMAC
+ ReplayStore. Pack endpoints default to EXPORT purpose, unlike legacy READ APIs.

CLI: `knowledge-sdk-governance <method> --db <isolated.db> --params '<JSON>'`;
for PG, supply `KNOWLEDGE_SDK_DSN` to a trusted process. Supply untagged
`KNOWLEDGE_SDK_ACTOR_JSON` as trusted host configuration. CLI params cannot override
actor/agent/context. It accepts all methods described above. No default identity.

MCP retains exactly four tools. `get_evidence_pack(pack_id=...)` reads a stored
snapshot under current gateway Actor/Agent/Purpose. It is mutually exclusive with
legacy `source_uris=[...]` and new `query="..."` transient modes. The real Q1
baseline used `source_uris`, not `query`; both transient modes are supported without
changing the 75 golden inputs. Denied/missing/tampered persisted IDs produce no
items; no model chooses identities, purposes or local output paths.

Legacy pre-M3 L2 version payloads lacking author identity cannot be approved or
published by guessing the document owner. Reingest the candidate (even identical
content) to create a new attributable draft, then use the normal three-actor flow.
Publication also checks an actual immutable approval record, not a state flag alone.
