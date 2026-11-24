# L3 — real signed HTTP governance and packs (PASS)

Tested implementation: `a9bdd9aa298aa520f25cbd2e063f56ef485aa006`. Actual `knowledge_sdk.server` subprocesses
bound only to new loopback ephemeral ports. SQLite uses a dedicated test business/
replay DB; PostgreSQL uses an isolated disposable schema, non-superuser FORCE RLS,
real pgvector + local HashEmbedder and PostgresReplayStore. No ASGI mock is claimed
as the wire evidence. HMAC keys/DSNs/headers/source bodies are not printed.

Author, reviewer and publisher are separate signed identities. Admin self-review
and reviewer-publication are rejected; real signed draft/release/issue/pack/ZIP
flows succeed. New unpublished drafts leave live v1 searchable; publication
switches it and marks the old pack impacted without changing its seal. After source
revocation, get/JSON/ZIP all return real 403 with no sealed plaintext; an
access_revoked evidence_pack alert is present. Unsigned/replayed requests are 401.
All four manual resolutions and audit-chain validity are checked. Server-side
output_path injection is rejected; HttpKnowledgeClient writes only caller-local
files after successful authorization. Child processes and schemas are cleaned.

Command (trusted test DSN only in environment):

```
PYTHONPATH=src:. python -W error::ResourceWarning docs/acceptance/v2.0-q2-phase3/live_governance_probe.py
```

Raw probe output:

```
2026-11-25T05:47:34.376006+08:00 Asia/Shanghai
PASS sqlite real signed HTTP: draft -> submit -> distinct reviewer -> distinct publisher; dissent and all 4 manual issue resolutions
PASS sqlite JSON/get/verify/list and deterministic RO-Crate1.2; draft/live isolation and publish -> SUPERSEDED pack alert with seal unchanged
PASS sqlite revoke -> get/json/zip 403 with no plaintext; ACCESS_REVOKED evidence_pack alert; unsigned/replayed 401; audit chain valid
PASS sqlite subprocess stopped, sandbox removed, logs contain no key/DSN/ResourceWarning
PASS postgres real signed HTTP: draft -> submit -> distinct reviewer -> distinct publisher; dissent and all 4 manual issue resolutions
PASS postgres JSON/get/verify/list and deterministic RO-Crate1.2; draft/live isolation and publish -> SUPERSEDED pack alert with seal unchanged
PASS postgres revoke -> get/json/zip 403 with no plaintext; ACCESS_REVOKED evidence_pack alert; unsigned/replayed 401; audit chain valid
PASS postgres subprocess stopped, sandbox removed, logs contain no key/DSN/ResourceWarning
```

Process logs: `l3-sqlite-process.log`, `l3-postgres-process.log`.
Reproduction source: `live_governance_probe.py`. This is not browser/proxy/login/
CSRF/OIDC or external design-partner acceptance. See L4/L5 and the handoff limits.
