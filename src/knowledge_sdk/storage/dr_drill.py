"""Explicit disposable-database backup/restore drill, never a production command.

Requires two caller-provisioned *empty* databases named sdk_dr_*. Provision the
vector extension in each as a DBA first. Application role remains NOSUPERUSER.
No database is dropped, no credentials printed, and no existing data accepted.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from .pg_support import connect,driver
from .postgres_store import PostgresStore
from .migrations import apply
from ..exceptions import ValidationError


def fingerprint(conn):
    pg=driver();result={}
    with conn.transaction():
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
        tables=[r[0] for r in conn.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")]
        # A table-owning DR operator temporarily removes FORCE inside this
        # transaction for a complete tenant snapshot. Rollback restores it; the
        # backup itself uses pg_dump --enable-row-security after the same owner
        # operation below. No payload is logged or written as JSON evidence.
        for table in tables:
            name=pg.sql.Identifier(table)
            conn.execute(pg.sql.SQL('ALTER TABLE {} NO FORCE ROW LEVEL SECURITY').format(name))
            rows=[json.loads(r[0]) for r in conn.execute(pg.sql.SQL('SELECT row_to_json(t)::text FROM {} t').format(name))]
            canonical=sorted(json.dumps(r,sort_keys=True,separators=(',',':'),ensure_ascii=False) for r in rows)
            result[table]={'rows':len(rows),'sha256':hashlib.sha256(('\n'.join(canonical)).encode()).hexdigest()}
        # Restore default protection before COMMIT (also restored on exceptions).
        for table in tables:
            if table not in ('resource_directory','schema_migrations'):
                conn.execute(pg.sql.SQL('ALTER TABLE {} FORCE ROW LEVEL SECURITY').format(pg.sql.Identifier(table)))
    return result


def _tool(name,dsn,path):
    pg=driver();params=pg.conninfo.conninfo_to_dict(dsn);env=dict(os.environ)
    password=params.pop('password',None)
    if password is not None:env['PGPASSWORD']=password
    safe=pg.conninfo.make_conninfo(**params)
    command=[name,'--dbname',safe,'--no-owner','--no-acl']
    if name.endswith('pg_dump'):command+=['--format=custom','--schema=public','--file',str(path)]
    else:
        # pg_dump includes CREATE SCHEMA public, already present (and holding the
        # DBA-provisioned vector extension) in the empty destination. Exclude only
        # that schema shell, not any data/table/index/policy/constraint entry.
        toc=subprocess.run([name,'--list',str(path)],capture_output=True,timeout=30)
        if toc.returncode:raise ValidationError('DR archive manifest failed')
        lines=toc.stdout.decode().splitlines()
        import re
        manifest=path.with_suffix('.list')
        manifest.write_text('\n'.join(line for line in lines if not re.search(r' SCHEMA - public(?: |$)| COMMENT - SCHEMA public(?: |$)',line))+'\n')
        command+=['--exit-on-error','--use-list',str(manifest),str(path)]
    try:r=subprocess.run(command,env=env,capture_output=True,timeout=120)
    except (OSError,subprocess.TimeoutExpired):raise ValidationError('DR database tool unavailable or timed out') from None
    if r.returncode:raise ValidationError('DR database tool failed (details withheld)')


def seed(store):
    from .. import Actor,LocalKnowledgeClient,ConsumerBinding,KnowledgeScope,DocumentACL
    from ..retrieval.adapters.pgvector_index import PgVectorIndex
    from ..retrieval.adapters.hash_embedder import HashEmbedder
    c=LocalKnowledgeClient(store,vector_index=PgVectorIndex(store=store),embedder=HashEmbedder())
    for org in ('alpha','beta'):
        from ..contracts.identity import IdentityPrincipal,ConnectorSyncState
        store.upsert_principal(IdentityPrincipal(org,'directory-user',policy_generation=3,active=False))
        store.put_connector_sync_state(ConnectorSyncState(org,'dr-connector','cursor-v4'))
        store.put_scim_group(org,'dr-group',{'members':['directory-user']})
        a=Actor('owner',org,org_roles=('admin',));u=Actor('reader',org)
        c.create_kb(a,'dr-fixture',visibility='enterprise',kb_id=org+'-kb')
        doc=org+'-doc';c.ingest(a,org+'-kb','# H\n\nalpha evidence',filename='fixture.md',doc_id=doc)
        ref=c.reference(u,doc,excerpt='alpha')
        binding=ConsumerBinding('task',org+'-task',KnowledgeScope('documents',doc_ids=(doc,)))
        c.bind_consumer(u,binding);c.attach(u,ref,binding)
        c.ingest(a,org+'-kb','# H\n\nalpha revised evidence',filename='fixture.md',doc_id=doc)
        c.drain_outbox(a)
        c.set_document_acl(a,doc,DocumentACL(deny_users=('reader',)))
    return c


def check_restored(store):
    from .. import Actor,LocalKnowledgeClient,PermissionDeniedError
    from ..audit.ledger import verify_audit_chain
    c=LocalKnowledgeClient(store);result={}
    for org in ('alpha','beta'):
        assert store.get_principal(org,'directory-user').policy_generation==3
        assert not store.get_principal(org,'directory-user').active
        assert store.get_connector_sync_state(org,'dr-connector').cursor=='cursor-v4'
        assert store.get_scim_group(org,'dr-group')['members']==['directory-user']
        report=verify_audit_chain(store,org)
        if not report.valid:raise ValidationError('Restored audit chain failed')
        doc=org+'-doc';u=Actor('reader',org);a=Actor('owner',org,org_roles=('admin',))
        # Reading metadata does not append new audit records to the compared data.
        assert store.get_version(doc,1).version==1
        assert store.get_anchors(org,doc,1)
        assert store.get_binding(u,'task',org+'-task')
        alerts=store.list_impact_alerts(org,doc_id=doc)
        assert alerts and store.list_usage_events_for_doc(org,doc)
        try:c.retrieve(u,doc)
        except PermissionDeniedError:denied=True
        else:denied=False
        if not denied:raise ValidationError('Restored ACL failed')
        result[org]={'audit_valid':True,'audit_checked':report.checked,'acl_denied':True,'alerts':len(alerts),'pinned_version':1}
    return result


def run(source_dsn,restore_dsn,*,dump_tool='pg_dump',restore_tool='pg_restore'):
    pg=driver()
    source=pg.conninfo.conninfo_to_dict(source_dsn);dest=pg.conninfo.conninfo_to_dict(restore_dsn)
    if source==dest or not all(d.get('dbname','').startswith('sdk_dr_') for d in (source,dest)):
        raise ValidationError('Two distinct disposable sdk_dr_* databases required')
    for dsn in (source_dsn,restore_dsn):
        with connect(dsn) as conn:
            if conn.execute("SELECT 1 FROM pg_tables WHERE schemaname='public'").fetchone():raise ValidationError('DR databases must be empty')
    s=PostgresStore(source_dsn);target=None
    try:
        seed(s)
        before=fingerprint(s.db)
        # Transactional migration-interruption rollback, not a destructive
        # schema downgrade: committed v4 business history must never be dropped.
        try:
            with s.transaction():
                s._execute('CREATE TABLE migration_rollback_probe(id INTEGER)')
                s._execute("DELETE FROM schema_migrations WHERE version=4")
                raise RuntimeError('simulated migration interruption')
        except RuntimeError:pass
        assert s._execute("SELECT to_regclass('migration_rollback_probe')")[0][0] is None
        apply(s.db);apply(s.db)
        if fingerprint(s.db)!=before:raise ValidationError('Migration rollback fingerprint differs')
        # A consistent dump needs table-owner RLS bypass, not application access.
        # This operator-only drill owns a new disposable DB. Always restore FORCE.
        tables=list(before)
        try:
            for t in tables:s.db.execute(pg.sql.SQL('ALTER TABLE {} NO FORCE ROW LEVEL SECURITY').format(pg.sql.Identifier(t)))
            with tempfile.TemporaryDirectory(prefix='sdk-dr-') as directory:
                path=Path(directory)/'snapshot.dump'
                _tool(dump_tool,source_dsn,path)
                _tool(restore_tool,restore_dsn,path)
        finally:
            for t in tables:
                if t not in ('resource_directory','schema_migrations'):s.db.execute(pg.sql.SQL('ALTER TABLE {} FORCE ROW LEVEL SECURITY').format(pg.sql.Identifier(t)))
        target=PostgresStore(restore_dsn)
        after=fingerprint(target.db)
        if after!=before:raise ValidationError('Backup/restore fingerprint differs')
        restored=check_restored(target)
        return {'passed':True,'migration_interruption_rollback':True,'idempotent_reapply':True,
                'all_table_fingerprints_equal':True,'fingerprints':before,'restored_contracts':restored,
                'boundary':'Disposable databases only; table-owner backup operation, no production topology/failover claim'}
    finally:
        s.close()
        if target:target.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-dsn',default=os.environ.get('KNOWLEDGE_SDK_DR_SOURCE_DSN'))
    p.add_argument('--restore-dsn',default=os.environ.get('KNOWLEDGE_SDK_DR_RESTORE_DSN'))
    p.add_argument('--confirm-disposable',action='store_true',required=True)
    p.add_argument('--json-output')
    a=p.parse_args()
    if not a.source_dsn or not a.restore_dsn:p.error('Two disposable DSNs required')
    result=run(a.source_dsn,a.restore_dsn)
    data=json.dumps(result,sort_keys=True,indent=2)
    if a.json_output:Path(a.json_output).write_text(data+'\n')
    print(data)

if __name__=='__main__':main()
