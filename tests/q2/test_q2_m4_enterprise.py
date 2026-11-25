"""Adversarial M4 contracts, identically run on SQLite and non-superuser PG."""
from __future__ import annotations
from dataclasses import replace,FrozenInstanceError
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext,closing
import base64,hashlib,hmac,importlib.util,json,os,sqlite3,tempfile,time,unittest
from unittest.mock import patch
from knowledge_sdk import Actor,LocalKnowledgeClient,DocumentACL,ResourceRights
from knowledge_sdk.storage.sqlite_store import SQLiteStore
from knowledge_sdk.contracts.identity import IdentityPrincipal,ConnectorSyncState
from knowledge_sdk.server.scim import SCIMService
from knowledge_sdk.server.oidc import OIDCAuthenticator,JWKSProvider
from knowledge_sdk.permissions.engine import DefaultPolicyEngine
from knowledge_sdk.connectors import ControlledFilesystemConnector,WebhookSyncConnector,ConnectorSyncRunner
from knowledge_sdk.connectors.webhook_sync import sign_sync
from knowledge_sdk.exceptions import ValidationError,PermissionDeniedError,ConflictError,NotFoundError
from knowledge_sdk.mcp import EvidenceTools,GatewayContext
from tests.benchmark.g7_g8 import token,authenticator,TEST_KEY

class EnterpriseContracts:
    engine='sqlite'
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        if self.engine=='postgres':
            from tests.pg_helpers import PgSandbox
            from knowledge_sdk.server.postgres import postgres_client
            self.pg=PgSandbox();self.addCleanup(self.pg.close);self.c=postgres_client(self.pg.dsn,pgvector_dims=32)
        else:self.c=LocalKnowledgeClient(SQLiteStore(Path(self.tmp.name)/'db'))
        self.s=self.c.store;self.addCleanup(self.s.close);self.a=Actor('admin','org',org_roles=('admin',));self.u=Actor('reader','org',policy_generation='1')
        self.c.create_kb(self.a,'Space','enterprise',space_type='enterprise_public',kb_id='kb');self.c.ingest(self.a,'kb','alpha evidence',doc_id='d',rights=ResourceRights(allow_export=True));self.scim=SCIMService(self.c)
    def create(self,**data):return self.scim.write(self.a,dict(id='reader',userName='reader',**data))
    def test_generation_deactivate_all_local_actor_methods(self):
        self.create(org_roles=['admin']);p=self.c.create_evidence_pack(self.u,'pack',[{'doc_id':'d','version':1}]);ref=self.c.reference(self.u,'d',excerpt='alpha')
        stale=replace(self.u,org_roles=('admin',),public_kb_admin=True,clearance_level='restricted')
        self.scim.write(self.a,{'active':False},'reader')
        calls=[lambda:self.c.search(stale,'alpha'),lambda:self.c.retrieve(stale,'d'),lambda:self.c.list_kbs(stale),lambda:self.c.list_documents(stale),lambda:self.c.create_kb(stale,'bad'),lambda:self.c.query_audit_events(stale),lambda:self.c.list_impact_alerts(stale),lambda:self.c.get_evidence_pack(stale,p.pack_id),lambda:self.c.export_evidence_pack(stale,p.pack_id),lambda:self.c.consume(stale,ref),lambda:self.c.set_document_acl(stale,'d',DocumentACL()),lambda:self.c.drain_outbox(stale),lambda:EvidenceTools(self.c).call('search_evidence',{'query':'alpha'},GatewayContext(stale))]
        for call in calls:
            with self.assertRaisesRegex(PermissionDeniedError,'principal_session_stale'):call()
        denied=[e for e in self.s.list_audit_events('org',actor_id='reader',limit=1000) if e.decision_effect.value=='deny'];self.assertGreaterEqual(len(denied),len(calls))
    def test_role_department_clearance_changes_bump_noop_does_not(self):
        self.create(roles=['manager'],department_ids=['old'],clearance_level='restricted')
        for n,v in [('roles',[]),('department_ids',['new']),('clearance_level','public')]:
            old=self.s.get_principal('org','reader');self.scim.write(self.a,{n:v},'reader');self.assertEqual(self.s.get_principal('org','reader').policy_generation,old.policy_generation+1)
            self.scim.write(self.a,{n:v},'reader');self.assertEqual(self.s.get_principal('org','reader').policy_generation,old.policy_generation+1)
        with self.assertRaises(PermissionDeniedError):self.c.retrieve(self.u,'d')
        fresh=replace(self.u,policy_generation='4');self.assertTrue(self.c.retrieve(fresh,'d').text)
    def test_no_client_generation_or_tenant_override(self):
        self.create()
        for data,exc in [({'policy_generation':999},ValidationError),({'org_id':'foreign'},PermissionDeniedError)]:
            with self.assertRaises(exc):self.scim.write(self.a,data,'reader')
        self.assertEqual(self.s.get_principal('org','reader').policy_generation,1)
    def test_scim_principal_audit_outbox_transaction_rollback(self):
        self.create();before=self.s.count_outbox_events('org')
        with patch.object(self.s,'enqueue_outbox',side_effect=RuntimeError('injected storage failure')):
            with self.assertRaises(RuntimeError):self.scim.write(self.a,{'active':False},'reader')
        self.assertTrue(self.s.get_principal('org','reader').active);self.assertEqual(self.s.get_principal('org','reader').policy_generation,1);self.assertEqual(self.s.count_outbox_events('org'),before);self.assertTrue(self.c.verify_audit_chain(self.a).valid)
    def test_scim_group_member_linkage_atomic_generation(self):
        self.create();g=self.scim.group_write(self.a,{'id':'department','displayName':'research','members':[{'value':'reader'}]})
        self.assertEqual(self.s.get_principal('org','reader').department_ids,('research',));self.assertEqual(self.s.get_principal('org','reader').policy_generation,2)
        self.scim.group_write(self.a,{'Operations':[{'op':'remove','path':'members','value':[{'value':'reader'}]}]},'department')
        self.assertEqual(self.s.get_principal('org','reader').department_ids,());self.assertEqual(self.s.get_principal('org','reader').policy_generation,3)
        before=self.s.get_principal('org','reader')
        with self.assertRaises(NotFoundError):self.scim.group_write(self.a,{'id':'bad','members':[{'value':'reader'},{'value':'missing'}]})
        self.assertEqual(self.s.get_principal('org','reader'),before)
        with self.assertRaises(NotFoundError):self.s.get_scim_group('org','bad')
    def test_scim_nonadmin_cross_tenant_and_delete(self):
        self.create()
        with self.assertRaises(PermissionDeniedError):self.scim.users(self.u)
        other=Actor('admin','foreign',org_roles=('admin',));self.assertEqual(self.scim.users(other),[])
        with self.assertRaises(NotFoundError):self.scim.get(other,'reader')
        self.scim.write(self.a,{},'reader',delete=True);self.assertFalse(self.s.get_principal('org','reader').active)
        self.assertTrue(self.s.get_principal('org','reader').policy_generation==2)
    def test_principal_directory_required_and_direct_policy_engine(self):
        self.c.require_principal=True
        with self.assertRaises(PermissionDeniedError):self.c.retrieve(self.u,'d')
        self.c.require_principal=False;self.create();self.scim.write(self.a,{'active':False},'reader')
        engine=DefaultPolicyEngine(principal_store=self.s)
        self.assertFalse(engine.evaluate(self.u,None,self.s.get_kb('kb')).allowed)
    def test_generations_concurrent_increment(self):
        self.create()
        with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(lambda _:self.s.bump_policy_generation('org','reader'),range(16)))
        self.assertEqual(self.s.get_principal('org','reader').policy_generation,17)
    def test_cursor_crud_isolation_and_reopen(self):
        self.s.put_connector_sync_state(ConnectorSyncState('org','sync','a'));self.s.put_connector_sync_state(ConnectorSyncState('org','sync','b'))
        self.assertIsNone(self.s.get_connector_sync_state('foreign','sync'));self.assertEqual(self.s.list_connector_sync_states('org')[0].cursor,'b')
        self.assertEqual(self.s.list_connector_sync_states('foreign'),[])
    def fs(self,action='revoke'):
        root=Path(self.tmp.name)/'source';root.mkdir(exist_ok=True);return root,ControlledFilesystemConnector('filesystem',root,org_id='org',missing_action=action),ConnectorSyncRunner(self.c)
    def test_filesystem_content_acl_idempotence_and_tombstone_impact(self):
        root,conn,runner=self.fs();unseen=root/'unseen.txt';unseen.write_text('not synchronized');unseen_side=root/'unseen.txt.acl.json';unseen_side.write_text(json.dumps({'deleted':True}))
        self.assertEqual(runner.run_once(self.a,conn,org_id='org',kb_id='kb').applied_upserts,0);unseen.unlink();unseen_side.unlink();self.assertEqual(runner.run_once(self.a,conn,org_id='org',kb_id='kb').applied_tombstones,0)
        file=root/'source.txt';file.write_text('alpha external evidence');side=root/'source.txt.acl.json';side.write_text(json.dumps({'rights':{'allow_export':True}}))
        self.assertEqual(runner.run_once(self.a,conn,org_id='org',kb_id='kb').applied_upserts,1)
        doc=next(d for d in self.s.list_documents('org') if d.doc_id!='d');p=self.c.create_evidence_pack(self.u,'external',[{'doc_id':doc.doc_id,'version':1}])
        self.assertEqual(runner.run_once(self.a,conn,org_id='org',kb_id='kb').applied_upserts,0)
        side.write_text(json.dumps({'rights':{'allow_export':True},'acl':{'deny_users':['reader']}}));report=runner.run_once(self.a,conn,org_id='org',kb_id='kb');self.assertEqual(report.applied_acls,1);self.assertEqual(self.s.latest_version(doc.doc_id),1)
        file.write_text('alpha revised external evidence');runner.run_once(self.a,conn,org_id='org',kb_id='kb');self.assertEqual(self.s.latest_version(doc.doc_id),2)
        file.unlink();report=runner.run_once(self.a,conn,org_id='org',kb_id='kb');self.assertEqual(report.applied_tombstones,1);self.assertEqual(report.outbox_events,1)
        self.c.drain_outbox(self.a);self.assertEqual(self.s.get_evidence_pack('org',p.pack_id).status,'impacted')
    def test_filesystem_symlinks_traversal_fifo_fail_closed(self):
        root,conn,runner=self.fs();outside=Path(self.tmp.name)/'outside';outside.write_text('DO NOT READ');(root/'escape.txt').symlink_to(outside)
        with self.assertRaises(ValidationError):runner.run_once(self.a,conn,org_id='org',kb_id='kb')
        self.assertIsNone(self.s.get_connector_sync_state('org','filesystem'));(root/'escape.txt').unlink()
        for path in ('../outside','/etc/passwd'):
            with self.assertRaises(ValidationError):conn._read(path)
        os.mkfifo(root/'pipe')
        with self.assertRaises(ValidationError):conn._read('pipe')
    def test_connector_batch_failure_rolls_back_document_audit_cursor(self):
        root,conn,runner=self.fs();(root/'a.txt').write_text('alpha external first evidence resource');(root/'b.txt').write_text('alpha two');(root/'b.txt.acl.json').write_text(json.dumps({'governance_tier':'l2_controlled'}))
        before=len(self.s.list_documents('org'));events=self.s.count_outbox_events('org')
        with self.assertRaises(PermissionDeniedError):runner.run_once(self.a,conn,org_id='org',kb_id='kb')
        self.assertEqual(len(self.s.list_documents('org')),before);self.assertEqual(self.s.count_outbox_events('org'),events);self.assertIsNone(self.s.get_connector_sync_state('org','filesystem'));self.assertTrue(self.c.verify_audit_chain(self.a).valid)
    def test_webhook_replay_timestamp_body_digest_and_tenant(self):
        conn=WebhookSyncConnector('wiki','offline-unit-test-key-not-production-000',org_id='org');runner=ConnectorSyncRunner(self.c)
        body=json.dumps({'upserts':[{'external_id':'wiki-1','doc_id':'wiki1','content':'alpha wiki'}]}).encode();stamp=str(int(time.time()));headers={'x-kb-event-id':'event','x-kb-webhook-timestamp':stamp,'x-kb-webhook-signature':sign_sync(conn._secret,body,'event',stamp)}
        self.assertEqual(runner.run_once(self.a,conn,org_id='org',kb_id='kb',webhook=(body,headers)).applied_upserts,1)
        self.assertEqual(runner.run_once(self.a,conn,org_id='org',kb_id='kb',webhook=(body,headers)).outbox_events,0)
        for bad in (dict(headers,**{'x-kb-webhook-timestamp':'1'}),dict(headers,**{'x-kb-webhook-signature':'sha256=bad'})):
            with self.assertRaises(PermissionDeniedError):runner.run_once(self.a,conn,org_id='org',kb_id='kb',webhook=(body,bad))
        conflicting=body+b' ';signed=dict(headers,**{'x-kb-webhook-signature':sign_sync(conn._secret,conflicting,'event',stamp)})
        with self.assertRaises(ValidationError):runner.run_once(self.a,conn,org_id='org',kb_id='kb',webhook=(conflicting,signed))
        with self.assertRaises(PermissionDeniedError):runner.run_once(self.u,conn,org_id='org',kb_id='kb')
        with self.assertRaises(PermissionDeniedError):runner.run_once(self.a,conn,org_id='foreign',kb_id='kb')
    def test_connector_contracts_deeply_immutable(self):
        from knowledge_sdk.contracts.connectors import ConnectorDocument,ConnectorSyncBatch
        d=ConnectorDocument('x','x','kb','text',metadata={'nested':['x']},acl={'deny_users':['reader']})
        with self.assertRaises((TypeError,AttributeError)):d.metadata['nested'].append('bad')
        with self.assertRaises((TypeError,AttributeError)):d.acl['deny_users'].append('bad')
        with self.assertRaises(FrozenInstanceError):d.doc_id='bad'
        self.assertIsInstance(ConnectorSyncBatch([d]).upserts,tuple)
    def test_pack_sql_digest_cross_check_both_directions(self):
        p=self.c.create_evidence_pack(self.u,'pack',[{'doc_id':'d','version':1}]);q='%s' if self.engine=='postgres' else '?'
        scope=self.s.tenant_scope('org') if self.engine=='postgres' else nullcontext()
        with scope:self.s._execute('UPDATE evidence_packs SET pack_sha256='+q+' WHERE org_id='+q+' AND pack_id='+q,('0'*64,'org',p.pack_id))
        for read in (lambda:self.s.get_evidence_pack('org',p.pack_id),lambda:self.c.get_evidence_pack(self.u,p.pack_id),lambda:self.c.export_evidence_pack(self.u,p.pack_id)):
            with self.assertRaisesRegex(ConflictError,'Pack digest mismatch'):read()
    def test_rls_new_directory_tables(self):
        self.create();self.s.put_scim_group('org','g',{'members':['reader']});self.s.put_connector_sync_state(ConnectorSyncState('org','sync','a'))
        self.assertEqual(self.s.list_principals('foreign'),[]);self.assertEqual(self.s.list_scim_groups('foreign'),[])
        if self.engine=='postgres':
            self.assertEqual(self.s._execute('SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user')[0],(False,False))
            for t in ('identity_principals','scim_groups','scim_group_members','connector_sync_state'):
                self.assertEqual(self.s._execute('SELECT * FROM '+t),[])
                with self.s.tenant_scope('foreign'):self.assertEqual(self.s._execute('SELECT * FROM '+t),[])
                flags=self.s._execute('SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=to_regclass(%s)',(t,))[0];self.assertEqual(flags,(True,True))

class SQLiteEnterprise(EnterpriseContracts,unittest.TestCase):pass
@unittest.skipUnless(os.environ.get('KNOWLEDGE_SDK_TEST_PG_DSN'),'Requires explicit disposable PostgreSQL DSN')
class PostgresEnterprise(EnterpriseContracts,unittest.TestCase):engine='postgres'

class OIDCSecurity(unittest.TestCase):
    def test_claim_types_and_missing_required_fields(self):
        for data in ({'exp':True},{'exp':'9999999999'},{'nbf':-1},{'nbf':int(time.time())+1000},{'sub':''},{'sub':'bad\nuser'},{'org_id':''},{'roles':'admin'},{'department_ids':None},{'policy_generation':True},{'policy_generation':'-1'},{'clearance_level':None},{'aud':'foreign'},{'iss':'foreign'}):
            with self.subTest(fields=list(data)):
                with self.assertRaises(ValidationError):authenticator().authenticate(token(**data))
    def test_signature_algorithms_and_public_key_confusion(self):
        for header in ({'alg':'none','kid':'test'},{'alg':'RS512','kid':'test'},{'alg':'HS256','kid':'unknown'},{'alg':'HS256','kid':'test','jku':'http://169.254.169.254'},{'alg':'HS256','kid':'test','crit':['bad']}):
            with self.assertRaises(ValidationError):authenticator().authenticate(token(_header=header))
        with self.assertRaises(ValidationError):OIDCAuthenticator('issuer','aud',algorithms=('HS256',),hs256_keys={'pem':b'-----BEGIN PUBLIC KEY-----'+b'x'*40})
    def test_replay_atomic_jti(self):
        auth=authenticator();t=token()
        def attempt(_):
            try:auth.authenticate(t);return True
            except ValidationError:return False
        with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(attempt,range(32)))
        self.assertEqual(sum(results),1)
    def test_jwks_ssrf_metadata_private_and_redirect_forbidden(self):
        for url in ('file:///etc/passwd','http://example.com/keys','https://169.254.169.254/latest','https://127.0.0.1/keys','https://10.0.0.1/k','https://[::1]/k','https://user:pass@example.com/k'):
            with self.assertRaises(ValidationError):JWKSProvider(url)
    def test_jwks_kid_ttl_cooldown_and_failed_refresh(self):
        clock=[100];provider=JWKSProvider('http://127.0.0.1:1/keys',allow_insecure_local=True,clock=lambda:clock[0],ttl_seconds=60,cooldown_seconds=10)
        with patch.object(provider,'_fetch',return_value={'keys':[{'kid':'a','kty':'RSA','n':'x','e':'AQAB'}]}) as fetch:
            self.assertEqual(provider.get_key('a')['kid'],'a');self.assertEqual(provider.get_key('a')['kid'],'a')
            for _ in range(10):
                with self.assertRaises(ValidationError):provider.get_key('unknown')
            self.assertEqual(fetch.call_count,1);clock[0]+=11;fetch.return_value={'keys':[{'kid':'b','kty':'EC'}]};self.assertEqual(provider.get_key('b')['kid'],'b');self.assertEqual(fetch.call_count,2)
            clock[0]+=61;fetch.side_effect=ValidationError('network unavailable')
            with self.assertRaises(ValidationError):provider.get_key('b')
            with self.assertRaises(ValidationError):provider.get_key('b')
            self.assertEqual(fetch.call_count,3)
    def test_duplicate_json_and_oversized_tokens(self):
        auth=authenticator()
        for t in ('a.b.c','x'*65537,'not-base64.not-json.'):
            with self.assertRaises(ValidationError):auth.authenticate(t)
    @unittest.skipUnless(importlib.util.find_spec('cryptography'),'Optional asymmetric crypto unavailable')
    def test_real_rs256_es256_and_confusion(self):
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import rsa,ec,padding,utils
        enc=lambda v:base64.urlsafe_b64encode(v).decode().rstrip('=')
        for alg in ('RS256','ES256'):
            if alg=='RS256':
                private=rsa.generate_private_key(public_exponent=65537,key_size=2048);pub=private.public_key().public_numbers();jwk={'kty':'RSA','n':enc(pub.n.to_bytes(256,'big')),'e':enc(pub.e.to_bytes(3,'big'))}
            else:
                private=ec.generate_private_key(ec.SECP256R1());pub=private.public_key().public_numbers();jwk={'kty':'EC','crv':'P-256','x':enc(pub.x.to_bytes(32,'big')),'y':enc(pub.y.to_bytes(32,'big'))}
            class Provider:
                def get_key(self,kid):return dict(jwk,kid='asym',alg=alg)
            auth=OIDCAuthenticator('https://test-issuer.invalid','sdk',Provider(),algorithms=(alg,));h,p,_=token(_header={'alg':alg,'kid':'asym'}).split('.');message=(h+'.'+p).encode()
            if alg=='RS256':signature=private.sign(message,padding.PKCS1v15(),hashes.SHA256())
            else:
                r,s=utils.decode_dss_signature(private.sign(message,ec.ECDSA(hashes.SHA256())));signature=r.to_bytes(32,'big')+s.to_bytes(32,'big')
            jwt=h+'.'+p+'.'+enc(signature);self.assertEqual(auth.authenticate(jwt).user_id,'reader')
            with self.assertRaises(ValidationError):auth.authenticate(token())

class MigrationV4(unittest.TestCase):
    def test_v0_v1_v2_v3_data_bytes_and_v4_reopen(self):
        for version in range(4):
            with tempfile.TemporaryDirectory() as d:
                path=Path(d)/'db';s=SQLiteStore(path);c=LocalKnowledgeClient(s);a=Actor('u','o');c.create_kb(a,'K',kb_id='k');c.ingest(a,'k','alpha evidence',doc_id='d');before=s._execute('SELECT * FROM documents');s.close()
                with closing(sqlite3.connect(path)) as db:
                    for table in ('identity_principals','scim_groups','scim_group_members'):db.execute('DROP TABLE '+table)
                    if version<3:
                        for table in ('outbox_events','audit_events','usage_events','impact_alerts','webhook_subscriptions','webhook_deliveries','review_decisions','evidence_packs','connector_sync_state'):db.execute('DROP TABLE '+table)
                    db.execute('PRAGMA user_version='+str(version))
                for _ in range(2):
                    s=SQLiteStore(path)
                    try:self.assertEqual(s._execute('SELECT * FROM documents'),before);self.assertEqual(s._execute('PRAGMA user_version')[0][0],5)
                    finally:s.close()

class GatewayConfiguration(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec('fastapi'),'Optional HTTP unavailable')
    def test_startup_rejects_oidc_demo_and_insecure(self):
        from knowledge_sdk.server.app import create_app
        c=LocalKnowledgeClient();self.addCleanup(c.store.close)
        for mode in ('oidc','dual'):
            for flag in ('dev_insecure','enable_demo_switcher'):
                with self.assertRaises(ValidationError):create_app(c,auth_secret='offline-unit-key-not-production-0000',auth_mode=mode,oidc_authenticator=authenticator(),**{flag:True})
        with self.assertRaises(ValidationError):create_app(c,auth_mode='unknown')
        app=create_app(c,auth_mode='oidc',oidc_authenticator=authenticator());self.assertEqual(app.state.auth_mode,'oidc')
    def test_core_enterprise_imports_without_site_packages(self):
        import subprocess,sys
        result=subprocess.run([sys.executable,'-S','-c','from knowledge_sdk import ConnectorSyncRunner, IdentityPrincipal; from knowledge_sdk.server.oidc import OIDCAuthenticator; from knowledge_sdk.server.scim import SCIMService; print("stdlib enterprise imports passed")'],capture_output=True,text=True,env=dict(os.environ,PYTHONPATH=str(Path(__file__).parents[2]/'src')))
        self.assertEqual(result.returncode,0,result.stderr)

class SQLiteMigrationAtomicity(unittest.TestCase):
    def test_v4_failed_ddl_rolls_back_and_old_payload_survives(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'db';s=SQLiteStore(path);s.close()
            with closing(sqlite3.connect(path)) as db:
                for table in ('identity_principals','scim_groups','scim_group_members'):db.execute('DROP TABLE '+table)
                db.execute('PRAGMA user_version=3')
            class Broken(SQLiteStore):_V4_SCHEMA=SQLiteStore._V4_SCHEMA+';INVALID SQL'
            with self.assertRaises(sqlite3.OperationalError):Broken(path)
            with closing(sqlite3.connect(path)) as db:
                self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],3);self.assertIsNone(db.execute("SELECT 1 FROM sqlite_master WHERE name='identity_principals'").fetchone())
            with closing(SQLiteStore(path)) as s:self.assertEqual(s._execute('PRAGMA user_version')[0][0],5)

@unittest.skipUnless(os.environ.get('KNOWLEDGE_SDK_TEST_PG_DSN'),'Requires explicit disposable PG')
class PostgresM4Concurrency(unittest.TestCase):
    def test_four_independent_connections_atomic_generation(self):
        from tests.pg_helpers import PgSandbox
        from knowledge_sdk.storage.postgres_store import PostgresStore
        pg=PgSandbox();self.addCleanup(pg.close);s=PostgresStore(pg.dsn);self.addCleanup(s.close);s.upsert_principal(IdentityPrincipal('org','user'))
        stores=[PostgresStore(pg.dsn,migrate=False) for _ in range(4)]
        for store in stores:self.addCleanup(store.close)
        def worker(store):return [store.bump_policy_generation('org','user').policy_generation for _ in range(10)]
        with ThreadPoolExecutor(max_workers=4) as pool:values=sum(pool.map(worker,stores),[])
        self.assertEqual(sorted(values),list(range(2,42)));self.assertEqual(s.get_principal('org','user').policy_generation,41)
    def test_real_v3_migration_preserves_all_existing_payload_bytes(self):
        from tests.pg_helpers import PgSandbox
        from knowledge_sdk.storage.postgres_store import PostgresStore
        from knowledge_sdk.storage.migrations import apply,status
        pg=PgSandbox();self.addCleanup(pg.close);s=PostgresStore(pg.dsn);self.addCleanup(s.close);c=LocalKnowledgeClient(s);a=Actor('owner','org');c.create_kb(a,'K',kb_id='k');c.ingest(a,'k','alpha migration evidence',doc_id='d')
        with s.tenant_scope('org'):before={t:s._execute('SELECT data FROM '+t) for t in ('knowledge_bases','documents','document_versions')}
        with s.transaction():
            for table in ('identity_principals','scim_groups','scim_group_members'):s._execute('DROP TABLE '+table)
            s._execute('DELETE FROM schema_migrations WHERE version=4');s._execute("INSERT INTO schema_migrations VALUES(3,'schema-v3','supplied-baseline')")
        apply(s.db);apply(s.db);self.assertEqual(status(s.db)['version'],5)
        with s.tenant_scope('org'):
            for t,rows in before.items():self.assertEqual(s._execute('SELECT data FROM '+t),rows)
