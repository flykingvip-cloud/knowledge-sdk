"""SDK-side deterministic fixtures only, never touches an existing database/service."""
import importlib.util,json,os,socket,sqlite3,sys,tempfile,unittest,uuid
from pathlib import Path
from contextlib import closing
ROOT=Path(__file__).parents[2];SCRIPTS=ROOT/'deploy/openbot-sandbox'
def load(name):
    spec=importlib.util.spec_from_file_location(name,SCRIPTS/(name+'.py'));m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
prepare=load('prepare_sandbox').prepare;seedmod=load('seed_openbot_sandbox');probe=load('probe_openbot_sandbox').probe
HAS_HTTP=all(importlib.util.find_spec(m) is not None for m in ('fastapi','uvicorn'))
def unused():
    with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
class FixtureCases:
    mode='sqlite'
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='sdk22-sandbox-test-');self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)/'new';prepare(self.root,unused());self.data=self.root/'data';self.dsn=None
        if self.mode=='postgres':
            import psycopg
            from psycopg.conninfo import make_conninfo
            from psycopg import sql
            self.base=os.environ['KNOWLEDGE_SDK_SANDBOX_TEST_DSN'];self.schema='fixture_sdk_'+uuid.uuid4().hex
            with psycopg.connect(self.base,autocommit=True) as c:c.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(self.schema)))
            self.dsn=make_conninfo(self.base,options='-csearch_path='+self.schema+',public');self.addCleanup(self.drop_owned_schema)
    def drop_owned_schema(self):
        import psycopg
        from psycopg import sql
        with psycopg.connect(self.base,autocommit=True) as c:c.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)))
    def seed(self):return seedmod.seed(self.data,self.mode,self.dsn)
    def connect(self):return seedmod.connect(self.data,self.mode,self.dsn)
    def test_deterministic_business_corpus_idempotence_and_current_identity(self):
        from dataclasses import replace
        from knowledge_sdk import PermissionDeniedError
        first=self.seed();self.assertEqual(first['documents'],10);self.assertEqual(first['tenants'],2)
        c=self.connect()
        try:
            before=[len(c.store.list_audit_events(org,limit=1000)) for org in seedmod.TENANTS];digest=seedmod.fingerprint(c)
            if self.mode=='postgres':
                self.assertEqual(c.store._execute('SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user')[0],(False,False))
                rows=c.store._execute("SELECT c.relname,c.relrowsecurity,c.relforcerowsecurity FROM pg_class c JOIN pg_attribute a ON a.attrelid=c.oid WHERE c.relnamespace=current_schema()::regnamespace AND c.relkind='r' AND a.attname='org_id'");self.assertGreaterEqual(len(rows),20);self.assertTrue(all(row[1:] == (True,True) for row in rows))
            self.assertEqual(self.seed(),{'status':'IDEMPOTENT_NO_WRITES','business_sha256':digest})
            self.assertEqual(before,[len(c.store.list_audit_events(org,limit=1000)) for org in seedmod.TENANTS])
            a=seedmod.actor(seedmod.TENANTS[0]);c.get_kb(a,a.org_id+'-team')
            for bad in (replace(a,policy_generation='0'),replace(a,org_roles=()),seedmod.actor(a.org_id,'sandbox-inactive'),seedmod.actor('unknown-tenant')):
                with self.assertRaises(PermissionDeniedError):c.get_kb(bad,a.org_id+'-team')
            c.store.upsert_principal(replace(c.store.get_principal(a.org_id,a.user_id),active=False,policy_generation=2))
            with self.assertRaises(PermissionDeniedError):c.search(a,'fixture')
            with self.assertRaises(ValueError):self.seed()
        finally:c.store.close()
    def test_unrecognized_nonempty_refused_before_initialization(self):
        if self.mode=='sqlite':
            path=self.data/'knowledge.sqlite'
            with closing(sqlite3.connect(path)) as c,c:c.execute('CREATE TABLE unrelated(value TEXT)');c.execute("INSERT INTO unrelated VALUES('untouched')")
            before=path.read_bytes()
            with self.assertRaises(ValueError):self.seed()
            self.assertEqual(path.read_bytes(),before)
        else:
            conn,_=seedmod.pg_target(self.dsn)
            try:
                conn.execute('CREATE TABLE unrelated(value TEXT)');conn.execute("INSERT INTO unrelated VALUES('untouched')")
                with self.assertRaises(ValueError):self.seed()
                self.assertEqual(conn.execute('SELECT value FROM unrelated').fetchall(),[('untouched',)])
                self.assertIsNone(conn.execute("SELECT to_regclass('documents')").fetchone()[0])
            finally:conn.close()
    def test_invalid_and_forged_receipt_never_initializes_nonfixture_data(self):
        receipt=self.data/'seed-receipt.json'
        for record in ({'fixture':seedmod.FIXTURE},{'fixture':seedmod.FIXTURE,'mode':self.mode,'seed_revision':1,'business_sha256':'0'*64,'physical_schema_sha256':'0'*64}):
            receipt.write_text(json.dumps(record))
            with self.assertRaises(ValueError):self.seed()
            if self.mode=='sqlite':self.assertFalse((self.data/'knowledge.sqlite').exists())
            else:
                conn,_=seedmod.pg_target(self.dsn)
                try:self.assertIsNone(conn.execute("SELECT to_regclass('documents')").fetchone()[0])
                finally:conn.close()
    @unittest.skipUnless(HAS_HTTP,'Optional HTTP dependencies unavailable')
    def test_real_signed_api_mcp_runtime_probe(self):
        self.seed();c=self.connect()
        try:
            from knowledge_sdk.server.app import create_app
            path=ROOT/'docs/acceptance/v2.1-q3-phase1/live_runtime_probe.py';spec=importlib.util.spec_from_file_location('sdk22_sandbox_live',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
            secret=(self.root/'secrets/hmac').read_text().strip()
            with m.live(create_app(c,auth_secret=secret,enable_ui=False,enable_mcp=True)) as base:
                result=probe(base,self.root/'secrets/hmac');self.assertGreaterEqual(result['assertion_groups'],15)
        finally:c.store.close()
class SQLiteSandbox(FixtureCases,unittest.TestCase):pass
@unittest.skipUnless(os.environ.get('KNOWLEDGE_SDK_SANDBOX_TEST_DSN'),'Owned non-superuser fixture database not configured')
class PostgresSandbox(FixtureCases,unittest.TestCase):mode='postgres'
class Preparation(unittest.TestCase):
    def test_refuses_existing_and_unsafe_port_without_mutation(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'new'
            for port in (3000,3001,8000,8002,8090,8091,80,65536):
                with self.assertRaises(ValueError):prepare(root,port)
                self.assertFalse(root.exists())
            prepare(root,unused());key=root/'secrets/hmac';self.assertEqual(key.stat().st_mode&0o777,0o600);before=key.read_bytes()
            with self.assertRaises(ValueError):prepare(root,unused())
            self.assertEqual(key.read_bytes(),before)
