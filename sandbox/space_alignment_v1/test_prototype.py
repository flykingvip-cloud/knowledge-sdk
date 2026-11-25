"""P_SPACE identifiers only. These are NOT formal T-01–27 acceptance tests."""
import os,json,unittest
from model import Prototype,ACTIONS,TABLES
from owned_pg import OwnedPostgres
DSN=os.environ.get('SDK25_PROVISION_DSN')
if os.environ.get('SDK25_REQUIRE_PG')=='1'and not DSN:raise RuntimeError('OWNED_PG_REQUIRED_NO_SKIP')
class Cases:
    pg=False
    def setUp(self):
        if self.pg:
            self.owned=OwnedPostgres.create(DSN);self.addCleanup(self.owned.close);self.p=Prototype(self.owned)
        else:self.p=Prototype()
        self.addCleanup(self.p.close);self.p.seed('syn_org_a');self.p.seed('syn_org_b')
    def test_P_SPACE_personal_admin_has_no_read_bypass(self):
        self.assertTrue(self.p.allow('syn_org_a','syn_employee','syn_private'))
        self.assertFalse(self.p.allow('syn_org_a','syn_admin','syn_private',admin=True))
        with self.p.scope('syn_org_a'):self.p.sql('INSERT INTO p_grant VALUES(?,?,?,?,1)',('syn_org_a','syn_private','syn_admin','read_content'))
        self.assertFalse(self.p.allow('syn_org_a','syn_admin','syn_private',admin=True))
    def test_P_SPACE_collaboration_groups_same_tenant_isolated(self):
        self.assertTrue(self.p.allow('syn_org_a','syn_alice','syn_group_a'))
        self.assertFalse(self.p.allow('syn_org_a','syn_alice','syn_group_b'))
        self.assertTrue(self.p.allow('syn_org_a','syn_bob','syn_group_b'))
        self.assertFalse(self.p.allow('syn_org_a','syn_bob','syn_group_a'))
    def test_P_SPACE_tenant_boundary_and_foreign_key(self):
        with self.p.scope('syn_org_b'):
            self.p.sql('INSERT INTO p_space VALUES(?,?,?,?,?,1)',('syn_org_b','syn_foreign_only','team','syn_bob','active'))
            self.p.sql('INSERT INTO p_kb VALUES(?,?,?,?,0)',('syn_org_b','syn_foreign_kb','syn_foreign_only','syn_foreign_only'))
        self.assertFalse(self.p.allow('syn_org_a','syn_bob','syn_foreign_kb'))
        with self.assertRaises(Exception):
            with self.p.scope('syn_org_a'):self.p.sql('INSERT INTO p_kb VALUES(?,?,?,?,0)',('syn_org_a','syn_bad','syn_foreign_only','syn_foreign_only'))
    def test_P_SPACE_detach_never_archives(self):
        self.p.detach('syn_org_a','syn_group_a')
        with self.p.scope('syn_org_a'):self.assertEqual(self.p.sql('SELECT space_id,archived FROM p_kb WHERE org_id=? AND kb_id=?',('syn_org_a','syn_group_a')),[(None,0)])
        self.assertFalse(self.p.allow('syn_org_a','syn_alice','syn_group_a'))
    def test_P_SPACE_no_cross_space_move_by_detach_reattach(self):
        self.p.detach('syn_org_a','syn_group_a')
        with self.assertRaises(Exception):self.p.attach('syn_org_a','syn_group_a','syn_group_b')
        with self.assertRaises(Exception):
            with self.p.scope('syn_org_a'):self.p.sql('UPDATE p_kb SET home_space_id=?,space_id=? WHERE org_id=? AND kb_id=?',('syn_group_b','syn_group_b','syn_org_a','syn_group_a'))
        self.p.attach('syn_org_a','syn_group_a','syn_group_a')
        self.assertTrue(self.p.allow('syn_org_a','syn_alice','syn_group_a'))
    def test_P_SPACE_all_eight_independent_actions_and_deny(self):
        for action in ACTIONS:self.assertTrue(self.p.allow('syn_org_a','syn_alice','syn_group_a',action=action))
        self.p.revoke('syn_org_a','syn_group_a','syn_alice','freeze_archive')
        for action in ACTIONS:self.assertEqual(self.p.allow('syn_org_a','syn_alice','syn_group_a',action=action,policy_generation=2),action!='freeze_archive')
        self.assertFalse(self.p.allow('syn_org_a','syn_alice','syn_group_a',action='admin'))
    def test_P_SPACE_revocation_outbox_generation_atomic_rollback(self):
        with self.assertRaises(RuntimeError):self.p.revoke('syn_org_a','syn_group_a','syn_alice',inject_failure=True)
        self.assertTrue(self.p.allow('syn_org_a','syn_alice','syn_group_a'))
        with self.p.scope('syn_org_a'):self.assertEqual(self.p.sql('SELECT count(*) FROM p_outbox WHERE org_id=?',('syn_org_a',)),[(0,)])
        self.p.revoke('syn_org_a','syn_group_a','syn_alice')
        self.assertFalse(self.p.allow('syn_org_a','syn_alice','syn_group_a'))
        with self.p.scope('syn_org_a'):self.assertEqual(self.p.sql('SELECT generation FROM p_outbox WHERE org_id=?',('syn_org_a',)),[(2,)])
    def test_P_SPACE_stale_generation_and_invalid_claims_fail_closed(self):
        for generation in [None,True,0,-1,1.0,'1',9007199254740992,2]:self.assertFalse(self.p.allow('syn_org_a','syn_alice','syn_group_a',policy_generation=generation))
    def assertion(self):return dict(tenant_id='syn_org_a',subject_id='syn_admin',asset_id='syn_external_asset',valid_until=110,generation=1)
    def test_P_SPACE_external_missing_expired_provider_failure_deny(self):
        args=('syn_org_a','syn_admin','syn_enterprise');kw=dict(asset='syn_external_asset')
        self.assertTrue(self.p.allow(*args,provider=self.assertion,**kw))
        self.assertFalse(self.p.allow(*args,**kw))
        def unavailable():raise RuntimeError('PROTOTYPE_PROVIDER_FAILURE')
        self.assertFalse(self.p.allow(*args,provider=unavailable,**kw))
        for key,value in [('valid_until',99),('generation',2),('tenant_id','syn_org_b'),('subject_id','syn_other'),('asset_id','syn_other')]:
            self.assertFalse(self.p.allow(*args,provider=lambda k=key,v=value:dict(self.assertion(),**{k:v}),**kw))
    def test_P_SPACE_external_revoked_cached_assertion_denies(self):
        self.assertTrue(self.p.allow('syn_org_a','syn_admin','syn_enterprise',asset='syn_external_asset',provider=self.assertion))
        with self.p.scope('syn_org_a'):self.p.sql('UPDATE p_external SET revoked=1,generation=2 WHERE org_id=?',('syn_org_a',))
        self.assertFalse(self.p.allow('syn_org_a','syn_admin','syn_enterprise',asset='syn_external_asset',provider=self.assertion))
    def test_P_SPACE_source_revocation_linearizes_with_inflight_read(self):
        if not self.pg:
            self.test_P_SPACE_external_revoked_cached_assertion_denies();return
        import threading
        entered=threading.Event();attempted=threading.Event();committed=threading.Event();errors=[]
        def revoke_source():
            try:
                entered.wait(3)
                with self.owned.connect()as c:
                    with c.transaction():
                        c.execute("SELECT set_config('app.current_org_id','syn_org_a',true)")
                        attempted.set();c.execute("UPDATE p_external SET revoked=1,generation=2 WHERE org_id='syn_org_a'")
                    committed.set()
            except BaseException as exc:errors.append(exc)
        thread=threading.Thread(target=revoke_source);thread.start()
        def provider():
            entered.set();self.assertTrue(attempted.wait(3));self.assertFalse(committed.wait(0.05));return self.assertion()
        try:self.assertTrue(self.p.allow('syn_org_a','syn_admin','syn_enterprise',asset='syn_external_asset',provider=provider))
        finally:entered.set();thread.join(5)
        self.assertFalse(thread.is_alive());self.assertEqual(errors,[]);self.assertTrue(committed.is_set())
        self.assertFalse(self.p.allow('syn_org_a','syn_admin','syn_enterprise',asset='syn_external_asset',provider=self.assertion))
    def test_P_SPACE_profile_ceiling_fine_scope_and_current_user_intersection(self):
        args=('syn_org_a','syn_alice','syn_group_a');kw=dict(asset='syn_group_a',agent='syn_agent')
        self.assertTrue(self.p.allow(*args,**kw))
        self.assertFalse(self.p.allow('syn_org_a','syn_bob','syn_group_a',**kw))
        for field,value in [('spaces','[]'),('fine_scope','{}'),('active',0)]:
            with self.p.scope('syn_org_a'):self.p.sql('UPDATE p_profile SET '+field+'=? WHERE org_id=?',(value,'syn_org_a'))
            self.assertFalse(self.p.allow(*args,**kw))
            with self.p.scope('syn_org_a'):self.p.sql('UPDATE p_profile SET spaces=?,fine_scope=?,active=1 WHERE org_id=?',(json.dumps(['syn_group_a']),json.dumps({'kb_ids':['syn_group_a']}),'syn_org_a'))
        for scope in [{'knowledge_file_ids':['syn_group_a']},{'folder_ids':['syn_folder']}]:
            with self.p.scope('syn_org_a'):self.p.sql('UPDATE p_profile SET fine_scope=? WHERE org_id=?',(json.dumps(scope),'syn_org_a'))
            self.assertTrue(self.p.allow(*args,**kw))
        self.assertFalse(self.p.allow(*args,profile_generation=2,**kw))
        self.p.revoke('syn_org_a','syn_group_a','syn_alice');self.assertFalse(self.p.allow(*args,policy_generation=2,**kw))
    def test_P_SPACE_deliverable_fine_scope_requires_current_user(self):
        with self.p.scope('syn_org_a'):self.p.sql('UPDATE p_profile SET spaces=?,fine_scope=? WHERE org_id=?',(json.dumps(['syn_enterprise']),json.dumps({'deliverable_ids':['syn_external_asset']}),'syn_org_a'))
        self.assertTrue(self.p.allow('syn_org_a','syn_admin','syn_enterprise',asset='syn_external_asset',agent='syn_agent',provider=self.assertion))
        self.assertFalse(self.p.allow('syn_org_a','syn_alice','syn_enterprise',asset='syn_external_asset',agent='syn_agent',provider=self.assertion))
    def test_P_SPACE_polymorphic_hydration_never_leaks_denied_metadata(self):
        targets=[dict(target_type=t,target_id=i)for t,i in [('kb','syn_group_a'),('asset','syn_group_a'),('kb','syn_private'),('asset','syn_private')]]
        result=self.p.hydrate('syn_org_a','syn_alice',targets)
        self.assertEqual([x['state']for x in result],['available','available','unavailable','unavailable'])
        for item in result[2:]:self.assertEqual(set(item),{'target_type','target_id','state'})
        self.p.revoke('syn_org_a','syn_group_a','syn_alice')
        self.assertTrue(all(x['state']=='unavailable'for x in self.p.hydrate('syn_org_a','syn_alice',targets)))
    def test_P_SPACE_resource_deny_overrides_owner_profile_and_folder(self):
        with self.p.scope('syn_org_a'):self.p.sql('INSERT INTO p_deny VALUES(?,?,?,?,?,?)',('syn_org_a','user','syn_alice','kb','syn_group_a','read_content'))
        self.assertFalse(self.p.allow('syn_org_a','syn_alice','syn_group_a',asset='syn_group_a',agent='syn_agent'))
        hidden=self.p.hydrate('syn_org_a','syn_alice',[dict(target_type='asset',target_id='syn_group_a')],agent='syn_agent')
        self.assertEqual(hidden,[dict(target_type='asset',target_id='syn_group_a',state='unavailable')])
        with self.p.scope('syn_org_a'):
            self.p.sql('DELETE FROM p_deny WHERE org_id=?',('syn_org_a',))
            self.p.sql('INSERT INTO p_deny VALUES(?,?,?,?,?,?)',('syn_org_a','agent','syn_agent','asset','syn_group_a','*'))
        self.assertTrue(self.p.allow('syn_org_a','syn_alice','syn_group_a',asset='syn_group_a'))
        self.assertFalse(self.p.allow('syn_org_a','syn_alice','syn_group_a',asset='syn_group_a',agent='syn_agent'))
    def test_P_SPACE_frozen_archived_fail_closed(self):
        for state in ('frozen','archived'):
            with self.p.scope('syn_org_a'):self.p.sql('UPDATE p_space SET state=? WHERE org_id=? AND space_id=?',(state,'syn_org_a','syn_group_a'))
            self.assertFalse(self.p.allow('syn_org_a','syn_alice','syn_group_a'))
    def test_P_SPACE_real_force_rls_owner_and_non_superuser(self):
        if not self.pg:
            with self.p.scope('syn_org_a'):self.assertEqual(len(self.p.sql('SELECT * FROM p_kb WHERE org_id=?',('syn_org_a',))),4)
            return
        self.assertEqual(self.p.sql('SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user'),[(False,False)])
        rows=self.p.sql("SELECT relname,relrowsecurity,relforcerowsecurity,pg_get_userbyid(relowner)=current_user FROM pg_class WHERE relnamespace=current_schema()::regnamespace AND relname LIKE 'p_%' AND relkind='r'")
        self.assertEqual({r[0]for r in rows},set(TABLES));self.assertTrue(all(r[1:]==(True,True,True)for r in rows))
        for table in TABLES:self.assertEqual(self.p.sql('SELECT count(*) FROM '+table),[(0,)])
        with self.p.scope('syn_org_a'):self.assertEqual(self.p.sql('SELECT count(*) FROM p_kb WHERE org_id=?',('syn_org_b',)),[(0,)])
        import psycopg
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with self.p.scope('syn_org_a'):self.p.sql('INSERT INTO p_tenant VALUES(?)',('syn_wrong',))
class SQLitePrototype(Cases,unittest.TestCase):pass
@unittest.skipUnless(DSN,'Owned SDK25 control database not supplied')
class PostgreSQLPrototype(Cases,unittest.TestCase):pg=True
class ProvisionGuards(unittest.TestCase):
    def test_P_GUARD_arbitrary_dsn_refused_before_connection(self):
        for dsn in ['host=127.0.0.1 dbname=postgres user=postgres','host=example.invalid dbname=sdk25_control_fake','host=127.0.0.1 port=8000 dbname=sdk25_control_fake','host=127.0.0.1 dbname=sdk25_control_fake passfile=/not/read']:
            with self.assertRaises(ValueError):OwnedPostgres.create(dsn)
    def test_P_GUARD_capability_cannot_be_constructed(self):
        with self.assertRaises(ValueError):OwnedPostgres(None)
