"""Isolated Schema v7 sandbox package (Wave-V21-6).

Pure Python stdlib only. Disposable SQLite resources plus PostgreSQL
DDL / FORCE RLS semantic validation. This is not a production Schema v7
migration, not a live PostgreSQL connection, and not formal T-01–T-27
acceptance. schema_v7_prod_migration_authorized remains false.
EXPERIMENTAL_V3_ENABLED stays default false.
"""

SANDBOX_NAME = 'v21_schema_v7'
FORMAL_T01_T27_ACCEPTED = False
SCHEMA_V7_PROD_MIGRATION_AUTHORIZED = False
EXPERIMENTAL_V3_ENABLED_DEFAULT = False
