# SDK-22: document archive is not knowledge-base archive

Status: analysis only; M1 joint signoff pending. No new API, column, table,
secret JSON state, all-children archival workaround or Schema6 migration here.

Current `KnowledgeBase` has identity/name/visibility/space ownership and
governance fields, **no archival/status field**. V5 stores its serialized data
in `knowledge_bases.data` alongside physical `kb_id` and `org_id`. Therefore an
additional physical column is **not mathematically unavoidable**: a future
versioned public model could put an explicit field in that existing JSON.
That is not implemented or implicitly authorized, and cannot be achieved by a
hidden JSON marker: current decoders/contracts/authorization/listing/readiness
and compatibility semantics have no knowledge-base archival contract.

`Document.archived`, `archive`/`restore` and `archived_only` listing already
operate on individual documents. They do not archive a space, and archiving all
children would mishandle later ingestion, membership, history, restoration,
policy and concurrent writes. Do not claim they implement archive_kb.

A real future archive_kb/restore_kb design needs explicit jointly reviewed
lifecycle/read/write/search/member/task/revocation semantics, migration and
index/rollback behavior. If that design requires an indexed physical archival
column, **that is Wave2 / Schema6 and forbidden before separate authorization**.
Even a public JSON-model alternative is future scope, not a loophole to ship it
now. D7's proposed *non-security* historical metadata snapshot is a separate
future decision and must never preserve/restore historical ACL/rights/grants.

Evidence: `contracts/models.py:KnowledgeBase`, `storage/sqlite_store.py`
knowledge_bases DDL, `storage/postgres_schema.sql`, `client/compat.py` document
listing, `client/local.py:archive/restore`. Schema5 structural digests are
recorded alongside the retained same-physical-snapshot performance evidence.
