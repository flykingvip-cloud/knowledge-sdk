# SDK-22 OpenBot adapter sandbox — fixture assets, NOT integration/deployment

Target: a prepared Docker host can get signed fixture API/MCP checks in about
five minutes after the image/dependencies are cached. Network pull/build times
are environment-dependent; measured CI setup times, not a guaranteed SLA, are
recorded in acceptance. Local box lacks Docker: do not claim a local image run.
No UI is required; no OpenBot repository/account/Enterprise/StratAI is touched.

## New isolated project only (nonroot application, read-only root)

1. Build from repository root: `docker build -t knowledge-sdk:align-wave1p5 .`.
   Pin PYTHON_IMAGE to a verified digest for reproducibility, as the CI probe does.
2. Use a NEW unused path/port (examples use8878, not the reserved application ports):
   `python deploy/openbot-sandbox/prepare_sandbox.py /tmp/sdk22-my-new-fixture --port 8878`.
   It refuses existing directories and occupied/unsafe ports, creates0700 dirs,
   a random ephemeral HMAC file0600, and0600 public-only sandbox.env. Never cat,
   commit, print, screenshot or reuse the key as a real credential. No baked key.
3. Choose exactly one config, SQLite or PostgreSQL:
   `docker compose --env-file /tmp/sdk22-my-new-fixture/sandbox.env -p sdk22-my-new-fixture -f deploy/openbot-sandbox/compose.sqlite.yaml up -d`.
   For PG use `compose.postgres.yaml` with the SAME flags but a fresh state/project.
   Choose a unique project name you own; never reuse another running project.
   JSON syntax of these files is valid YAML1.2. The application uses your nonzero
   host UID/GID to read0600 bind-mounted keys, overriding image's nonroot65532
   with another nonroot identity. Root is refused; no chmod-world-readable key.
   Data and secret are separate mounts; secret bind mount is read-only.
4. Real signed probe (inside your sandbox container, no host SDK install required):
   `docker compose --env-file /tmp/sdk22-my-new-fixture/sandbox.env -p sdk22-my-new-fixture -f deploy/openbot-sandbox/compose.sqlite.yaml exec -T sandbox python /opt/sandbox/probe_openbot_sandbox.py --url http://127.0.0.1:8088`.
   `/v1/health` and `/v1/ready` are minimal public GETs; business/MCP/metrics use
   real HMAC headers and canonical current fixture Directory identities. There
   is no dev_insecure/demo signer/bypassed auth. A stale/inactive/unknown subject,
   explicit Deny, foreign tenant or profile-only private-KB binding is denied.
5. Cleanup ONLY your explicitly new project:
   `docker compose --env-file /tmp/sdk22-my-new-fixture/sandbox.env -p sdk22-my-new-fixture -f deploy/openbot-sandbox/compose.sqlite.yaml down --volumes`.
   Remove ONLY your own fixture directory/key after container cleanup. Do not
   use prune, drop-all, existing project/container/network or production URLs.

## Fixture corpus and fail-closed seed

Two fixed fake tenants, six spaces (enterprise/department/personal per tenant),
10 documents: each space has a two-version document, each tenant also explicit
Deny and archived documents. Private-KB profile allowlist is not a human grant.
Stable fake IDs, no email ACLs or unnecessary PII. Determinism is business IDs,
text, versions, ACL/rights and identity generations. Fresh audit UUIDs/times are
intentionally real and not byte-identical database images. Initial seed uses one
transaction; receipt is written only afterward. A crash before receipt causes
safe refusal, never destructive repair.

Seed checks a prepared fixture marker and whitelisted LOCAL fixture host,
`openbot_fixture` database, `fixture_runtime` role and owned fixture_sdk schema.
An initdb-only database comment identifies the disposable fixture database.
Before SDK initialization, any nonempty/unrecognized SQLite file or PostgreSQL
schema without its seed receipt is refused. Re-run verifies the receipt and the
seed-owned business fingerprint and returns IDEMPOTENT_NO_WRITES. It never
updates/repairs/reseeds a diverged corpus. Receipt shape and physical schema
hash are validated before construction; existing PG fixtures use migrate=False. Idempotence only reads seed-owned
fixture tenants; it never overwrites unrelated tenants/data. Production URLs,
password-bearing DSNs and unrecognized targets are rejected without printing.

## PG identities, ownership and RLS (honest current-v5 limitation)

Only NEW PostgreSQL initdb uses the bootstrap superuser to install vector and
create fixture_migrator(NOLOGIN schema owner) + fixture_runtime(LOGIN,
NOSUPERUSER/NOBYPASSRLS/NOCREATEDB/NOCREATEROLE). Runtime inherits fixture schema
ownership privileges because the current v5 store bootstrap performs idempotent
owner-level setup. This is NOT a DML-only runtime-role claim. No production role
is widened. All business tables have ENABLE/FORCE RLS, so even ownership does
not bypass tenant filtering. Tests use the non-superuser runtime, never DBA.
Private internal Docker network only, PG publishes NO host port, auth trust is
restricted to this disposable fixture network. It is NOT a production template.
Explicit migration/runtime separation beyond this bootstrap limitation requires
future design, not an insecure pretend least-privilege claim.
