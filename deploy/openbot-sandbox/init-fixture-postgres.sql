-- ONLY executed by postgres initdb on a NEW isolated fixture volume.
COMMENT ON DATABASE openbot_fixture IS 'SDK22_ALIGN_WAVE1P5_SANDBOX_V1';
CREATE EXTENSION IF NOT EXISTS vector;
CREATE ROLE fixture_migrator NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
CREATE ROLE fixture_runtime LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
GRANT fixture_migrator TO fixture_runtime;
CREATE SCHEMA fixture_sdk AUTHORIZATION fixture_migrator;
GRANT CREATE ON DATABASE openbot_fixture TO fixture_migrator;
-- Current v5 bootstrap needs inherited ownership on its OWN fixture schema.
-- This is NOT a claim of a DML-only runtime role; FORCE RLS still applies.
