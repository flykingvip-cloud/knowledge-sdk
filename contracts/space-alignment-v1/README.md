# Space Alignment v1 candidate package

DRAFT_PENDING_OWNER_RULING. New SDK25 namespace; NOT the historical frozen architecture/contracts tree. Six referenced prior Space documents, actual suggested-ruling source, prior draft and official PRE-03 format are unavailable. These NEW proposed assets do not replace those originals, constitute full calibration or claim approvals.

See SDK_SPACE_LIFECYCLE.md, SDK_SCHEMA_V7_MIGRATION_PROPOSAL.md, status.json and acceptance/source gap register. All four authorization flags FALSE; PRE01–04 UNSIGNED; all8exitgates NOT_MET; all formal T-01–27 NOT_RUN_NOT_ACCEPTED. Five deliverable states/eight action names/numeric SLAs are PROPOSED_PENDING_OWNER_RULING.

Run Python: `python contracts/space-alignment-v1/validate.py`.
Run TS: `npm ci --ignore-scripts --no-audit --no-fund --prefix contracts/space-alignment-v1`, `contracts/space-alignment-v1/node_modules/.bin/tsc -p contracts/space-alignment-v1/tsconfig.json`, then `node contracts/space-alignment-v1/ts-generated/check.js contracts/space-alignment-v1/openapi.json contracts/space-alignment-v1/fixtures.json`.
Official OpenAPI structural check (development-only dependency, not SDK runtime): `python -m openapi_spec_validator --schema 3.1 contracts/space-alignment-v1/openapi.json` using openapi-spec-validator0.9.0; documentation https://openapi-spec-validator.readthedocs.io/en/latest/cli.html . Passing this is syntax/spec compliance, not security review/approval or mounted runtime.

Proposed API /v3/spaces is draft only; /v2/knowledge-spaces remains alternative. No endpoint mounted, no src/deploy/migration changed, no OpenBot favorite writer implementation. Fixtures contain synthetic pseudonyms only; denied hydration has no display/source/content data; external refs carry scoped freshness/tombstone, never source credentials. Candidate schema/TS validators cover supplied schema vocabulary plus explicit tenant/Deny/stale-generation/external-freshness invariants, not a general JSON Schema implementation.

Candidate PRE03 row fields: pseudonymized legacy_kb_id, nullable tenant_id/proposed_space_id/proposed_kb_id/alias_token, non-null name_token. See pre03-candidate.schema.json. A future official input requires a reviewed adapter, not relabeling this schema. File analyzer reports only supplied mappings, never fills null tenant or migrates data.

Vector freshness clock100 is a synthetic fixture clock only; no live SLA/current-time authority is claimed. Production trust/signature distribution and final state/action semantics require separate owner review.
