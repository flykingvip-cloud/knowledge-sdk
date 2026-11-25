# Isolated SDK25 design prototype, not SDK runtime

DRAFT_PENDING_OWNER_RULING. No schema version upgrade, src imports, endpoint, production data or OpenBot writes. P_SPACE/P_DRY test names are NOT formal T-01–T-27 results. All4authorizationflags remain false. All tables here are p_* throwaway models only.

Nonroot runner with PostgreSQL17 binaries and development psycopg + pytest installed:
`python -W error::ResourceWarning sandbox/space_alignment_v1/run_owned.py --output /tmp/NEW_UNIQUE_sdk25_evidence`.
This creates a new random owned local cluster/control DB, chooses an unused allowed loopback port, runs SQLite and generated PostgreSQL app DB tests, verifies no app DBs/roles remain, and stops/removes only its own cluster. There is no caller-supplied DSN for this path. Output must be a NEW directory. The root bootstrap role is used for provisioning/cleanup only; authorization tests use generated owner roles that are NOSUPERUSER/NOBYPASSRLS with FORCE RLS on all9tables.

CI uses its own new dedicated PostgreSQL17 service. `OwnedPostgres.create` refuses generic/remote/unmarked control DSNs and creates new random sdk25_proto_* DB + sdk25_role_* owner. It never installs tables into the control DB or accepts an arbitrary app DB DSN. Both-engine tests are mandatory when SDK25_REQUIRE_PG=1; missing PG cannot silently skip that CI gate.

File-only dry run:
`python sandbox/space_alignment_v1/dry_run.py sandbox/space_alignment_v1/synthetic-pre03.json --output /tmp/NEW_sdk25_dry_run.json`.
Expected exit2 means synthetic collision/manual-review findings, not script failure or migration approval. Exit0 clean,3 invalid/refused. See newroot pre03-candidate.schema.json; official PRE03 format/signoff is missing. No DB/network import or null tenant inference. Only explicitly named new output file or stdout is written. Pseudonym shape is not proof of anonymization; supplier must sanitize.

Fixture mutation helpers seed/revoke/detach/attach are synthetic control operations, not production authorization APIs. SQL direct mutations in tests are controlled fixture setup. Current authority read checks hold row-share locks until hydration completes; revoke fixture uses consistent lock order and an atomic generation/outbox transaction. No production distributed-SLA/throughput claim follows from passing these small tests.

Prototype cases intentionally use *_cases.py, outside accepted SDK default pytest discovery; the dedicated prototype job explicitly runs ALL45cases under BOTH unittest and pytest with mandatory real owned PG. No accepted SDK test is excluded. Imports support package and standalone execution.
