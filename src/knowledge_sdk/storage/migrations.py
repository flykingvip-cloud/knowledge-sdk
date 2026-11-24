"""Transactional, repeatable Schema v3 DDL. Provision extension as a DBA first.

Identifiers below come only from packaged DDL or catalog-checked hardcoded tables.
Never accepts a schema or identifier from a user. CLI never echoes its DSN.
"""
from __future__ import annotations
from pathlib import Path
import argparse
import json
import os
from .pg_support import connect
from ..exceptions import ValidationError

DDL = Path(__file__).with_name('postgres_schema.sql').read_text()
TABLES = tuple(__import__('re').findall(r'CREATE TABLE IF NOT EXISTS (\w+)', DDL))
TENANT_TABLES = tuple(t for t in TABLES if t != 'resource_directory')


def apply(conn, enable_rls=True, pgvector=False):
    try:
        with conn.transaction():
            conn.execute("SELECT pg_advisory_xact_lock(hashtext('knowledge-sdk:migrations'))")
            conn.execute('CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY,name TEXT NOT NULL,applied_at TEXT NOT NULL)')
            for sql in DDL.split(';'):
                if sql.strip():
                    conn.execute(sql)
            conn.execute("""CREATE OR REPLACE FUNCTION knowledge_review_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Append-only reviews'; END; $$""")
            conn.execute('DROP TRIGGER IF EXISTS review_immutable ON review_decisions')
            conn.execute('CREATE TRIGGER review_immutable BEFORE UPDATE OR DELETE ON review_decisions FOR EACH ROW EXECUTE FUNCTION knowledge_review_immutable()')
            if pgvector:
                conn.execute('CREATE EXTENSION IF NOT EXISTS vector')
            # A non-RLS adapter never silently disables protection established by
            # another instance. RLS is a schema-level deployment decision.
            if enable_rls:
                for table in TENANT_TABLES:
                    conn.execute('ALTER TABLE '+table+' ENABLE ROW LEVEL SECURITY')
                    conn.execute('ALTER TABLE '+table+' FORCE ROW LEVEL SECURITY')
                    conn.execute('DROP POLICY IF EXISTS tenant_isolation ON '+table)
                    conn.execute("CREATE POLICY tenant_isolation ON "+table+" USING (org_id = current_setting('app.current_org_id',true)) WITH CHECK (org_id = current_setting('app.current_org_id',true))")
            conn.execute("INSERT INTO schema_migrations VALUES(3,'schema-v3',CURRENT_TIMESTAMP::text) ON CONFLICT DO NOTHING")
    except Exception:
        raise ValidationError('PostgreSQL migration failed (details withheld)') from None


def status(conn):
    present = {r[0] for r in conn.execute("SELECT tablename FROM pg_tables WHERE schemaname=current_schema()")}
    version = conn.execute('SELECT COALESCE(MAX(version),0) FROM schema_migrations').fetchone()[0] if 'schema_migrations' in present else 0
    return {'version': version, 'missing_tables': sorted(set(TABLES)-present)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dsn', default=os.environ.get('KNOWLEDGE_SDK_DSN'))
    g = p.add_mutually_exclusive_group(required=True)
    for flag in ('check','status','apply'):g.add_argument('--'+flag, action='store_true')
    p.add_argument('--no-rls', action='store_true')
    p.add_argument('--pgvector', action='store_true')
    a=p.parse_args()
    if not a.dsn:p.error('DSN required')
    conn=connect(a.dsn)
    try:
        if a.apply:apply(conn, not a.no_rls, a.pgvector)
        result=status(conn);print(json.dumps(result, sort_keys=True))
        if a.check and (result['version']!=3 or result['missing_tables']):raise SystemExit(1)
    finally:conn.close()

if __name__=='__main__':main()
