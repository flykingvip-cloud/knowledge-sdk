# Host integration preparation (no existing host modified)

StratAI can become a consumer after the independent SDK is accepted. This release
does not modify its repository, launch scripts, runtime ports or configuration.
It also does not depend on any reference project's runtime or source code.

1. Install a reviewed wheel in the host's environment, or deploy the HTTP extra
   separately. Do not inject `sys.path` or import host modules into the SDK.
2. At the trusted boundary, map authenticated users to `Actor(user_id, org_id,
   roles, department_ids)`. Never use untrusted request claims directly.
3. Store the SDK DB/blobs in a dedicated configured directory; create KBs and
   explicit viewer/editor/admin memberships using approved migration tooling.
4. Map host-specific concepts into namespaced metadata rather than new core
   fields. Redact field-sensitive content before ingestion; notices alone are not
   redaction. Historical content is governed by the current document ACL.
5. Replace host search/retrieve/reference/consume calls with a thin adapter
   around `KnowledgeClient`. Keep application routes and business logic outside.
6. For remote HTTP, use backend-only HMAC assertions and TLS. Configure URLs,
   Qdrant collection and embeddings explicitly; no fixed local port is assumed.
7. Test tenant/ACL isolation, archive/restore, old references, budgets and paged
   reads in a staging environment; compare receipt contracts before switching.
8. Plan an explicit migration/rollback with backups. No automatic importing,
   copying, deleting or stopping the existing host's data/services is performed.

Future enhancements: semantic embedding plugins, asynchronous indexing worker,
shared replay protection, migration tooling, sandboxed OCR, language-aware
ranking, PostgreSQL storage and independent live Qdrant integration validation.
