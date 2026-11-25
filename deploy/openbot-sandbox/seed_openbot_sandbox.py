"""Deterministic fixture corpus, current directory, no destructive repair/production target."""
from __future__ import annotations
import argparse,hashlib,json,os,re,sqlite3
from pathlib import Path
from contextlib import closing
from knowledge_sdk import Actor,LocalKnowledgeClient,DocumentACL,PermissionDeniedError
from knowledge_sdk.contracts.identity import IdentityPrincipal
FIXTURE='SDK22_ALIGN_WAVE1P5_SANDBOX_V1'
TENANTS=('fixture-tenant-a','fixture-tenant-b')

def actor(org,user='sandbox-owner',*,generation='1'):
    return Actor(user,org,roles=('member',),department_ids=('fixture-department',),org_roles=('admin','metrics_admin') if user=='sandbox-owner' else (),clearance_level='internal',managed_department_ids=('fixture-department',) if user=='sandbox-owner' else (),policy_generation=generation,session_id='sandbox-session-'+user)

class SandboxClient(LocalKnowledgeClient):
    def _check_principal(self,a):
        super()._check_principal(a);p=self.store.get_principal(a.org_id,a.user_id)
        if p is None or not p.active or str(p.policy_generation)!=a.policy_generation or a!=Actor(p.user_id,p.org_id,roles=p.roles,department_ids=p.department_ids,org_roles=p.org_roles,clearance_level=p.clearance_level,clearance_tags=p.clearance_tags,managed_department_ids=p.department_ids if 'admin' in p.org_roles else (),policy_generation=str(p.policy_generation),session_id='sandbox-session-'+p.user_id):
            raise PermissionDeniedError('principal_session_stale')

def marker(root):
    root=Path(root)
    if json.loads((root/'fixture-marker.json').read_text())!={'fixture':FIXTURE,'seed_revision':1}:raise ValueError('Unrecognized fixture directory')
    return root

def pg_target(dsn):
    import psycopg
    from psycopg.conninfo import conninfo_to_dict
    data=conninfo_to_dict(dsn)
    if set(data)-{'host','port','dbname','user','options','connect_timeout'} or data.get('dbname')!='openbot_fixture' or data.get('user')!='fixture_runtime':raise ValueError('Not an allowed disposable fixture target')
    host=data.get('host','');port=int(data.get('port','5432'));options=data.get('options','')
    if host not in ('fixture-postgres','127.0.0.1') and not host.startswith('/workspace/knowledge-sdk-align-wave1p5-pg'):raise ValueError('Non-fixture host refused')
    if host=='127.0.0.1' and (port<1024 or port in (3000,3001,8000,8002,8090,8091)):raise ValueError('Host fixture must use an isolated high port')
    m=re.fullmatch(r'-csearch_path=(fixture_sdk(?:_[0-9a-f]{32})?),public',options)
    if not m:raise ValueError('Explicit owned fixture schema required')
    conn=psycopg.connect(dsn,autocommit=True,connect_timeout=5)
    try:
        label=conn.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()").fetchone()[0]
        role=conn.execute('SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user').fetchone()
        if label!=FIXTURE or role!=(False,False):raise ValueError('Recognized isolated database and NOBYPASSRLS runtime role required')
        return conn,m[1]
    except BaseException:conn.close();raise

def schema_hash(conn,pg=False):
    if pg:
        rows=[list(r) for r in conn.execute('SELECT table_name,column_name,data_type,is_nullable,column_default FROM information_schema.columns WHERE table_schema=current_schema() ORDER BY table_name,ordinal_position').fetchall()]
        rows += [list(r) for r in conn.execute("SELECT relname,relrowsecurity,relforcerowsecurity FROM pg_class WHERE relnamespace=current_schema()::regnamespace AND relkind='r' ORDER BY relname").fetchall()]
    else:rows=conn.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name").fetchall()
    return hashlib.sha256(json.dumps(rows,separators=(',',':')).encode()).hexdigest()

def read_receipt(root,mode):
    file=root/'seed-receipt.json'
    if not file.exists():return None
    record=json.loads(file.read_text())
    if (set(record)!={'fixture','mode','seed_revision','business_sha256','physical_schema_sha256'} or
        record['fixture']!=FIXTURE or record['mode']!=mode or record['seed_revision']!=1 or
        any(not isinstance(record[k],str) or re.fullmatch('[0-9a-f]{64}',record[k]) is None for k in ('business_sha256','physical_schema_sha256'))):
        raise ValueError('Unrecognized fixture receipt; no repair/migration allowed')
    return record

def connect(root,mode,dsn=None):
    root=marker(root);record=read_receipt(root,mode)
    if mode=='sqlite':
        path=root/'knowledge.sqlite'
        if path.exists() and path.stat().st_size and record is None:raise ValueError('Nonempty/unrecognized database refused before initialization')
        if record is not None:
            if not path.is_file():raise ValueError('Seeded database missing; never recreate')
            with closing(sqlite3.connect(path.absolute().as_uri()+'?mode=ro',uri=True)) as raw:
                if raw.execute('PRAGMA user_version').fetchone()[0]!=5 or schema_hash(raw)!=record['physical_schema_sha256']:raise ValueError('Unrecognized seeded schema; never migrate/repair')
        from knowledge_sdk.storage.sqlite_store import SQLiteStore
        store=SQLiteStore(str(path))
    elif mode=='postgres':
        conn,schema=pg_target(dsn)
        try:
            actual=conn.execute('SELECT current_schema()').fetchone()[0]
            count=conn.execute("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND c.relkind IN ('r','p')",(schema,)).fetchone()[0]
            if actual!=schema or count and record is None:raise ValueError('Nonempty/unrecognized fixture schema refused before SDK initialization')
            if record is not None and schema_hash(conn,True)!=record['physical_schema_sha256']:raise ValueError('Unrecognized seeded schema; no migration/repair')
        finally:conn.close()
        from knowledge_sdk.storage.postgres_store import PostgresStore
        store=PostgresStore(dsn,enable_rls=True,migrate=record is None)
    else:raise ValueError('Unknown fixture mode')
    return SandboxClient(store,require_principal=True)

def stable(value):
    if isinstance(value,dict):return {k:stable(v) for k,v in value.items() if k not in ('created_at','updated_at','published_at')}
    if isinstance(value,(list,tuple)):return [stable(v) for v in value]
    return value

def fingerprint(c):
    from knowledge_sdk.contracts.models import encode
    rows=[]
    for org in TENANTS:
        # Only fixture-owned tenants are inspected. Idempotence never writes/repairs.
        with c.store.tenant_scope(org) if hasattr(c.store,'_pg') else __import__('contextlib').nullcontext():
            rows.append([encode(k) for k in c.store.list_kbs(org)])
            docs=sorted(c.store.list_documents(org),key=lambda d:d.doc_id)
            rows.append([encode(d) for d in docs]);rows.append([encode(c.store.get_acl(d.doc_id)) for d in docs])
            rows.append([[encode(c.store.get_version(d.doc_id,n)) for n in range(1,c.store.latest_version(d.doc_id)+1)] for d in docs])
            rows.append([__import__('dataclasses').asdict(p) for p in c.store.list_principals(org)])
            rows.append([p.to_dict() for p in c.store.list_agent_profiles(org)])
            rows.append([c.store.list_kb_members(org,k.kb_id) for k in c.store.list_kbs(org)])
    return hashlib.sha256(json.dumps(stable(rows),sort_keys=True,separators=(',',':')).encode()).hexdigest()

def seed(root,mode='sqlite',dsn=None):
    root=marker(root);receipt=root/'seed-receipt.json';c=connect(root,mode,dsn)
    try:
        if receipt.exists():
            record=json.loads(receipt.read_text())
            if record!={'fixture':FIXTURE,'mode':mode,'seed_revision':1,'business_sha256':fingerprint(c),'physical_schema_sha256':schema_hash(c.store.db,mode=='postgres')}:raise ValueError('Diverged/unrecognized fixture; never overwrite or auto-repair')
            return {'status':'IDEMPOTENT_NO_WRITES','business_sha256':record['business_sha256']}
        with c._lock,c.store.runtime_transaction():
            for org in TENANTS:
                for user in ('sandbox-owner','sandbox-reader','sandbox-inactive'):
                    a=actor(org,user);c.store.upsert_principal(IdentityPrincipal(org,user,active=user!='sandbox-inactive',policy_generation=1,roles=a.roles,department_ids=a.department_ids,org_roles=a.org_roles,clearance_level=a.clearance_level,updated_at='2026-11-25T00:00:00+00:00'))
                a=actor(org)
                for kind,visibility in (('enterprise','enterprise'),('team','team'),('private','private')):
                    kb=org+'-'+kind;c.create_kb(a,'Fixture '+kind,visibility,kb_id=kb,space_type={'enterprise':'enterprise_public','team':'department','private':'personal'}[kind],owner_department_id='fixture-department' if kind=='team' else '')
                    if kind=='team':c.grant_kb_member(a,kb,'sandbox-reader','viewer')
                    doc=kb+'-doc';c.ingest(a,kb,'fixture '+kind+' evidence version one',filename='one.txt',doc_id=doc,visibility=visibility)
                    c.ingest(a,kb,'fixture '+kind+' evidence version two',filename='two.txt',doc_id=doc,visibility=visibility)
                kb=org+'-enterprise';c.ingest(a,kb,'fixture explicit deny evidence',doc_id=org+'-deny');c.set_document_acl(a,org+'-deny',DocumentACL(deny_users=['sandbox-owner','sandbox-reader']))
                c.ingest(a,kb,'fixture archived evidence',doc_id=org+'-archived');c.archive(a,org+'-archived')
                c.register_agent_profile(a,'fixture-agent-private',allowed_kb_ids=(org+'-private',))
        digest=fingerprint(c);tmp=root/'seed-receipt.tmp';tmp.write_text(json.dumps({'fixture':FIXTURE,'mode':mode,'seed_revision':1,'business_sha256':digest,'physical_schema_sha256':schema_hash(c.store.db,mode=='postgres')},sort_keys=True)+'\n');tmp.chmod(0o600);tmp.replace(receipt)
        return {'status':'SEEDED_NEW_FIXTURE','tenants':2,'space_classes':3,'spaces':6,'documents':10,'business_sha256':digest,'security_audit_times_are_fresh_not_bit_identical':True}
    finally:c.store.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--state-dir',type=Path,required=True);p.add_argument('--mode',choices=('sqlite','postgres'),default='sqlite');a=p.parse_args()
    try:print(json.dumps(seed(a.state_dir,a.mode,os.environ.get('KNOWLEDGE_SDK_DSN'))))
    except Exception:raise SystemExit('Sandbox seed refused or failed; verify fresh fixture-only target/configuration (details withheld)') from None
