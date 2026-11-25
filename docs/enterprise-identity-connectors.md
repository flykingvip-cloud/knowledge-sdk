# Enterprise identity and source synchronization (Q2-M4)

## Resource-server boundary

`create_app(..., auth_mode="hmac" | "oidc" | "dual",
oidc_authenticator=OIDCAuthenticator(...))` retains the HMAC default. OIDC/dual
reject `dev_insecure` or demo switching **at startup**. Every response, including
static/error/schema routes, is `Cache-Control: no-store`. No client identity,
tenant, generation, purpose or privilege header overrides signed OIDC claims.
Dual rejects ambiguous Bearer + HMAC requests; invalid OIDC never falls back.

Default algorithms: RS256/ES256 (lazy optional `knowledge-sdk[oidc]`). HS256
requires an explicit allowlist and a separate `hs256_keys={kid: bytes}` map;
JWKS public material is never an HMAC key. `none`, unknown algorithms, duplicate
JSON keys and token-directed jku/x5u/jwk locations are rejected. Required claims:
iss, aud, exp, nbf, nonempty sub/org_id, roles, department_ids, clearance_level,
policy_generation, and (by default) jti. Times are positive integers, not booleans.
Leeway is bounded 0–120 seconds. TLS JWKS URLs are operator configuration; all DNS
answers are validated, connection IP pinned, redirects/proxies/private/metadata
addresses rejected. Unknown kids trigger at most one refresh per cooldown. A
failed/expired refresh fails closed, never stale-key fail-open.

The CLI exposes `--auth-mode`, `--oidc-issuer`, `--oidc-audience`, `--jwks-uri` (or
`KNOWLEDGE_OIDC_ISSUER/AUDIENCE/JWKS_URI`). HMAC secrets remain environment/config
only. Never put credentials in CLI arguments or source control. PostgreSQL DSN
wiring uses the shared PostgreSQL replay store; local multiworker operators must
supply shared replay storage explicitly.

By default a JWT jti is **single-use** for bearer transport. Machine callers mint
a fresh jti per call, or exchange once through `POST /v1/auth/session`. The
read-only OIDC UI imports/pastes a token only in memory, clears the input, and
uses a random HttpOnly, SameSite=Strict opaque cookie until JWT expiry. Unsafe
cookie-authenticated requests require exact same-origin Origin. Production
cookies are Secure by default; `/v1/auth/logout` invalidates the server session.
This is a JWT resource server, not an implemented enterprise authorization-code
redirect IdP client. Enterprise issuer provisioning/acceptance remains external.
Sessions are node-local; sticky routing or a host session gateway is required for
multi-node browser sessions. Durable PostgreSQL bearer replay is shared.

## SCIM and authoritative revocation

Configured `scim_tokens={secret: tenant_bound_admin_actor}` or authenticated
admin/scim_admin actors administer only their signed tenant. Routes:

- Users: POST/GET `/scim/v2/Users`; GET/PATCH/PUT/DELETE `/scim/v2/Users/{id}`.
- Groups: POST/GET `/scim/v2/Groups`; PATCH `/scim/v2/Groups/{id}`.

Users PATCH supports add/replace/remove of identity/role/department/clearance
attributes. Group membership PATCH supports add/replace/remove and
`members[value eq "id"]` removal. List supports bounded startIndex/count and
simple equality filters. Unsupported filters/paths fail explicitly; this is the
required core, **not a claim of complete SCIM interoperability/certification**.
Delete deactivates, retaining audit history. Group kind department/role/org_role
maps membership to corresponding authority attributes.

Every effective security change increments persisted policy_generation, writes
an audit event and `principal.policy_bumped` Outbox in the **same transaction**.
Repeated identical updates do not bump again. Group batches roll back if any
member is invalid. Old generations or inactive principals are denied before all
local operations, MCP tools, HTTP requests and policy evaluation, regardless of
owner/admin grants. DENY is audited. `require_principal=True` denies unmanaged
users; otherwise pre-directory static actors remain compatible. Directory
attributes are authoritative storage; token claims are trusted only after issuer
signature verification. Request bodies cannot select their own generation.

## Exactly two reference connectors

`BaseConnector.sync_since(cursor, *, org_id, kb_id) -> ConnectorSyncBatch`;
`ConnectorSyncRunner.run_once(actor, connector, *, org_id, kb_id, webhook=None)`.
Use frozen contracts in `knowledge_sdk.contracts.connectors`; nested JSON is
frozen as well. Runner requires tenant and space/connector management authority.
Source identity is connector/external_id-bound; it cannot overwrite an unrelated
SDK document. Batch authority, audit, Outbox, dedupe and cursor commit together.
Failure leaves old cursor/versions intact. Unchanged source content and rights
never consumes a new version; ACL-only changes do not reingest content.

1. `ControlledFilesystemConnector(id, root, org_id=...)`: stable ordered snapshots,
   relative paths and optional `file.acl.json` sidecars (`acl`, `rights`,
   `governance_tier`, `deleted`, `revoked`). Directory-FD traversal and
   O_NOFOLLOW reject symlink/path escapes and special files. Missing sources
   produce configured revoke/archive tombstones. POSIX local directory is this
   reference's implemented mode; no S3 SDK or third SaaS connector is bundled.
2. `WebhookSyncConnector(id, secret, org_id=...)`: normalized signed Wiki/DMS
   pushes, no outbound SaaS client. Header `X-KB-Event-Id`,
   `X-KB-Webhook-Timestamp`, `X-KB-Webhook-Signature`; signature is
   `sha256=HMAC_SHA256(secret, timestamp + "." + event_id + "." + body_bytes)`.
   Fixed time window, constant-time verify, durable cursor event-ID/body digest
   dedupe; conflicting same-ID payloads fail. The 100,000-event stream limit
   fails closed rather than silently evicting dedupe keys. Coordinate a new
   connector stream before capacity; cursor storage is not a general event bus.

POST `/v1/connectors/{id}/sync` or `/webhook`; configuration maps connector IDs
to instances and KBs on the server, never caller-selected roots/KBs. Both routes
also require normal authenticated connector administration. Webhook transport
signatures use the existing X-KB-Webhook-* family so dual HMAC authentication
can be present without signature-header ambiguity. Tombstones call existing
archive/rights APIs once; those APIs already emit doc.archived/doc.revoked.
Drain Outbox to generate ImpactAlerts and mark affected packs impacted without
rewriting historical evidence.

## Operational boundary

Schema v4 adds principals and SCIM group/member directories; reuses the reserved
connector cursor table. PG methods are tenant-scoped and parameterized, new
tables FORCE RLS. RLS protects application access, not a malicious DB owner or
superuser. DR performs non-destructive transactional migration interruption,
pg_dump/pg_restore and all-table fingerprints, not destructive schema downgrade.
No real Qdrant, external embedding/model, OCR, production IdP, enterprise security
signoff, or Q3 task-runtime features are claimed by the isolated acceptance.
