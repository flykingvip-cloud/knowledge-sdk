from __future__ import annotations
from contextlib import closing
from dataclasses import replace, FrozenInstanceError
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json,os,sqlite3,tempfile,unittest
from unittest.mock import patch
from knowledge_sdk import *
from knowledge_sdk.contracts.models import encode,decode
from knowledge_sdk.contracts.identity import IdentityPrincipal
from knowledge_sdk.server.scim import SCIMService
from knowledge_sdk.storage.sqlite_store import SQLiteStore
from knowledge_sdk.mcp import EvidenceTools,GatewayContext
from tests.benchmark.runner import Fixture,Observation
from tests.benchmark.g9 import SCENARIOS

class StrictContracts(unittest.TestCase):
    def test_budget_bool_negative_unknown(self):
        for name in ContextBudget().__dict__:
            for value in (True,-1,1.0,'2',None):
                with self.assertRaises(ValidationError):ContextBudget(**{name:value})
        with self.assertRaises(ValidationError):ContextBudget.from_dict({'extra':1})
    def test_profiles_strict_and_deep_frozen(self):
        for kw in ({'org_id':''},{'agent_id':''},{'profile_generation':True},{'profile_generation':0},{'active':1},{'allowed_purposes':['unknown']},{'default_budget':{'max_items':True}},{'allowed_kb_ids':'kb'},{'allowed_space_types':['unknown']},{'max_clearance_level':'unknown'}):
            with self.assertRaises(ValidationError):AgentProfile(**dict({'org_id':'o','agent_id':'a'},**kw))
        source=['kb'];p=AgentProfile('o','a',allowed_kb_ids=source);source.append('evil');self.assertEqual(p.allowed_kb_ids,('kb',))
        with self.assertRaises(FrozenInstanceError):p.default_budget.max_items=999
        self.assertEqual(AgentProfile.from_dict(p.to_dict()),p);self.assertEqual(decode(encode(p)),p)
        with self.assertRaises(ValidationError):AgentProfile('o','a',updated_at=False)
        with self.assertRaises(ValidationError):SnapshotItem('d',1,'text','kb://org/o/doc/d@1',excerpt_hash=False)
        with self.assertRaises(ValidationError):ContextSnapshot('s','t','o',1,(),'2026-11-25T10:00:00+08:00',snapshot_sha256=False)
    def test_empty_scope_distinct_from_none(self):
        self.assertNotEqual(KnowledgeScope(),KnowledgeScope('none'))
        with self.assertRaises(ValidationError):KnowledgeScope('none',kb_ids=['kb'])

class RuntimeCases:
    engine='sqlite'
    def setUp(self):
        self.f=Fixture({'expected':{}},self.engine);self.addCleanup(self.f.close)
        self.c=self.f.c;self.s=self.c.store;self.a=self.f.a;self.u=self.f.u
        self.f.doc('alpha evidence secret',filename='fixture.md')
        self.c.register_agent_profile(self.a,'agent')
    def task(self,**kw):return self.c.create_task_context(self.u,'agent',**kw)
    def snapshot(self,task,**entry):return self.c.create_context_snapshot(self.u,task.task_id,[dict(doc_id='doc',**entry)])
    def test_roundtrip_all_runtime_contracts(self):
        t=self.task();s=self.snapshot(t)
        for obj in (t,s,*s.items):
            self.assertEqual(decode(encode(obj)),obj);self.assertEqual(type(obj).from_dict(obj.to_dict()),obj)
            with self.assertRaises(FrozenInstanceError):obj.org_id='bad' if hasattr(obj,'org_id') else setattr(obj,'text','bad')
        self.c.update_agent_profile(self.a,'agent',active=False)
        r=self.s.list_task_revocations('org',t.task_id)[0]
        self.assertEqual(decode(encode(r)),r);self.assertEqual(type(r).from_dict(r.to_dict()),r)
    def test_snapshot_content_and_linked_usage(self):
        t=self.task();s=self.snapshot(t);self.assertEqual(s.items[0].text,'alpha evidence secret')
        e=self.s.list_usage_events_for_doc('org','doc')[-1]
        self.assertEqual((e.task_id,e.consumer_id,e.consumer_type,e.receipt_hash),(t.task_id,s.snapshot_id,'context_snapshot',s.snapshot_sha256))
    def test_query_snapshot_scope_none_and_empty(self):
        t=self.task(scope=KnowledgeScope('none'));self.assertFalse(self.c.create_context_snapshot(self.u,t.task_id,'alpha').items)
        t=self.task(scope={});self.assertTrue(self.c.create_context_snapshot(self.u,t.task_id,'alpha').items)
    def test_scope_space_profile_and_task_intersection(self):
        self.c.update_agent_profile(self.a,'agent',allowed_space_types=['department']);t=self.task();self.assertFalse(self.snapshot(t).items)
        self.c.update_agent_profile(self.a,'agent',allowed_space_types=[]);t=self.task(scope=KnowledgeScope('documents',doc_ids=['absent']));self.assertFalse(self.snapshot(t).items)
    def test_register_and_update_admin_only_and_no_controlled_fields(self):
        with self.assertRaises(PermissionDeniedError):self.c.register_agent_profile(self.u,'evil')
        with self.assertRaises(PermissionDeniedError):self.c.update_agent_profile(self.u,'agent',active=False)
        with self.assertRaises(TypeError):self.c.update_agent_profile(self.a,'agent',profile_generation=900)
        with self.assertRaises(TypeError):self.c.create_task_context(self.u,'agent',policy_generation=999)
    def test_mutation_failure_rolls_back_profile_and_outbox_and_revoke(self):
        t=self.task();s=self.snapshot(t);old=self.c.get_agent_profile(self.a,'agent')
        with patch.object(self.s,'put_task_revocation',side_effect=RuntimeError('injected')):
            with self.assertRaises(RuntimeError):self.c.update_agent_profile(self.a,'agent',active=False)
        self.assertEqual(self.c.get_agent_profile(self.a,'agent'),old);self.assertEqual(self.c.read_task_snapshot(self.u,t.task_id,s.snapshot_id),s)
        self.assertTrue(self.c.verify_audit_chain(self.a).valid)
    def test_snapshot_insert_only_and_sql_json_redundancy(self):
        t=self.task();s=self.snapshot(t)
        with self.assertRaises(ConflictError):self.s.put_context_snapshot(s)
        with self.s.transaction():
            ctx=self.s.tenant_scope('org') if self.engine=='postgres' else __import__('contextlib').nullcontext()
            with ctx:self.s._rt_execute('UPDATE context_snapshots SET total_chars=total_chars+1 WHERE snapshot_id=?',(s.snapshot_id,))
        with self.assertRaises(ConflictError):self.c.read_task_snapshot(self.u,t.task_id,s.snapshot_id)
    def test_snapshot_json_tamper_failclosed(self):
        t=self.task();s=self.snapshot(t);data=encode(s);data['items'][0]['text']='forged'
        with self.s.transaction():
            ctx=self.s.tenant_scope('org') if self.engine=='postgres' else __import__('contextlib').nullcontext()
            with ctx:self.s._rt_execute('UPDATE context_snapshots SET data=? WHERE snapshot_id=?',(json.dumps(data),s.snapshot_id))
        with self.assertRaises(ConflictError):self.c.read_task_snapshot(self.u,t.task_id,s.snapshot_id)
    def test_real_redaction_and_changed_redactor_revokes(self):
        self.c.redaction_registry.register('hide',__import__('knowledge_sdk.permissions.redaction',fromlist=['RegexRedactionHook']).RegexRedactionHook([('secret','MASK')]))
        self.c.set_document_rights(self.a,'doc',ResourceRights(redaction_profile='hide'));t=self.task();s=self.snapshot(t)
        self.assertNotIn('secret',s.items[0].text);self.assertIn('MASK',s.items[0].text)
        self.c.redaction_registry.register('hide',__import__('knowledge_sdk.permissions.redaction',fromlist=['RegexRedactionHook']).RegexRedactionHook([('secret','REDACTED')]))
        with self.assertRaises(PermissionDeniedError):self.c.read_task_snapshot(self.u,t.task_id,s.snapshot_id)
    def test_missing_redactor_cannot_leak(self):
        self.c.set_document_rights(self.a,'doc',ResourceRights(redaction_profile='missing'));t=self.task();self.assertFalse(self.snapshot(t).items)
    def test_instant_deny_before_dispatcher_on_direct_principal_bump(self):
        self.s.upsert_principal(IdentityPrincipal('org','reader'));self.u=replace(self.u,policy_generation='1');t=self.task();s=self.snapshot(t)
        self.s.bump_policy_generation('org','reader')
        with self.assertRaisesRegex(PermissionDeniedError,'mid_task_revocation'):self.c.read_task_snapshot(self.u,t.task_id,s.snapshot_id)
        self.assertTrue(self.s.list_task_revocations('org',t.task_id));self.assertTrue(any(e.task_id==t.task_id and e.decision_effect.value=='deny' for e in self.s.list_audit_events('org',actor_id='reader')))
    def test_future_directory_generation_is_not_a_task_or_admin_grant(self):
        self.s.upsert_principal(IdentityPrincipal('org','reader'))
        future=replace(self.u,policy_generation='999',org_roles=('admin',))
        with self.assertRaises(PermissionDeniedError):self.c.create_task_context(future,'agent')
        with self.assertRaises(PermissionDeniedError):self.c.update_agent_profile(future,'agent',active=False)
        self.assertTrue(self.c.get_agent_profile(self.a,'agent').active)
    def test_direct_acl_change_real_time_create_denies(self):
        t=self.task();self.snapshot(t);self.s.set_acl('doc',DocumentACL(deny_users=['reader']))
        with self.assertRaisesRegex(PermissionDeniedError,'mid_task_revocation'):self.snapshot(t)
        self.assertEqual(self.s.get_task_context('org',t.task_id).status,'revoked')
    def test_direct_profile_generation_change_and_reenable_cannot_revive(self):
        t=self.task();s=self.snapshot(t);p=self.c.get_agent_profile(self.a,'agent');self.s.upsert_agent_profile(replace(p,profile_generation=2))
        with self.assertRaises(PermissionDeniedError):self.c.read_task_snapshot(self.u,t.task_id,s.snapshot_id)
        self.s.upsert_agent_profile(p)
        with self.assertRaises(PermissionDeniedError):self.c.read_task_snapshot(self.u,t.task_id,s.snapshot_id)
    def test_snapshot_id_cannot_cross_task(self):
        t=self.task();s=self.snapshot(t);t2=self.task()
        with self.assertRaisesRegex(PermissionDeniedError,'runtime_resource_unavailable'):self.c.read_task_snapshot(self.u,t2.task_id,s.snapshot_id)
    def test_terminal_and_zero_budgets(self):
        t=self.task(budget=ContextBudget(0,0,0,0));self.assertFalse(self.snapshot(t).items)
        self.c.complete_task_context(self.u,t.task_id)
        with self.assertRaises(PermissionDeniedError):self.c.complete_task_context(self.u,t.task_id)
        for ttl in (True,-1,1.0):
            with self.assertRaises(ValidationError):self.task(ttl_seconds=ttl)
    def test_proactive_principal_deactivation_and_profile_generation(self):
        self.s.upsert_principal(IdentityPrincipal('org','reader'));self.u=replace(self.u,policy_generation='1');t=self.task();self.snapshot(t)
        SCIMService(self.c).write(self.a,{'active':False},'reader')
        self.assertEqual(self.s.get_task_context('org',t.task_id).status,'revoked')
        t=self.c.create_task_context(self.a,'agent');self.c.update_agent_profile(self.a,'agent',allowed_purposes=[Purpose.READ])
        self.assertEqual(self.s.get_task_context('org',t.task_id).status,'revoked')
    def test_mcp_profile_task_scope_and_snapshot_validation(self):
        t=self.task(scope=KnowledgeScope('none'));ctx=GatewayContext(self.u,purpose=Purpose.GROUND_INTERNAL_LLM)
        self.assertFalse(EvidenceTools(self.c).call('search_evidence',{'query':'alpha','task_id':t.task_id},ctx)['hits'])
        with self.assertRaises(PermissionDeniedError):EvidenceTools(self.c).call('verify_citation',{'source_uri':'kb://org/org/doc/doc@1','task_id':t.task_id,'snapshot_id':'missing'},ctx)
        with self.assertRaises(ValidationError):EvidenceTools(self.c).call('search_evidence',{'query':'alpha','snapshot_id':'missing'},ctx)
    def test_concurrent_profiles_monotonic_generation(self):
        with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(lambda _:self.c.update_agent_profile(self.a,'agent',display_name='changed'),range(12)))
        self.assertEqual(sorted(p.profile_generation for p in results),list(range(2,14)))
    def test_old_queued_profile_events_do_not_revoke_new_task(self):
        self.c.update_agent_profile(self.a,'agent',display_name='new')
        t=self.task();s=self.snapshot(t);self.c.drain_outbox(self.a)
        self.assertEqual(self.c.read_task_snapshot(self.u,t.task_id,s.snapshot_id),s)

class SQLiteRuntime(RuntimeCases,unittest.TestCase):pass
@unittest.skipUnless(os.environ.get('KNOWLEDGE_SDK_TEST_PG_DSN'),'Disposable PostgreSQL DSN required')
class PostgresRuntime(RuntimeCases,unittest.TestCase):engine='postgres'

# Same executable G9 scenarios on both engines; no false stdlib PG passes.
def golden_method(name):
    def test(self):
        f=Fixture({'expected':{}},self.engine)
        try:SCENARIOS[name](f,Observation())
        finally:f.close()
    return test
for cls in (SQLiteRuntime,PostgresRuntime):
    for name in SCENARIOS:setattr(cls,'test_g9_'+name,golden_method(name))
del cls

class SQLiteV5Migrations(unittest.TestCase):
    def test_versions_zero_through_four_lossless(self):
        for version in range(5):
            with self.subTest(version=version),tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'db'
                with closing(SQLiteStore(path)) as s:
                    c=LocalKnowledgeClient(s);a=Actor('owner','org');c.create_kb(a,'k',kb_id='k');c.ingest(a,'k','original',doc_id='d');before=s._execute('SELECT data FROM documents')
                    for table in ('agent_profiles','task_contexts','context_snapshots','task_revocations'):s._execute('DROP TABLE '+table)
                    s._execute('PRAGMA user_version='+str(version))
                with closing(SQLiteStore(path)) as s:
                    self.assertEqual(s._execute('PRAGMA user_version')[0][0],5);self.assertEqual(s._execute('SELECT data FROM documents'),before)
    def test_v4_interrupted_ddl_rolls_back(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'db'
            with closing(SQLiteStore(path)) as s:
                for t in ('agent_profiles','task_contexts','context_snapshots','task_revocations'):s._execute('DROP TABLE '+t)
                s._execute('PRAGMA user_version=4')
            with patch.object(SQLiteStore,'_V5_SCHEMA',SQLiteStore._V5_SCHEMA+' INVALID DDL;'):
                with self.assertRaises(sqlite3.OperationalError):SQLiteStore(path)
            with closing(sqlite3.connect(path)) as db:
                self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],4);self.assertFalse(db.execute("SELECT name FROM sqlite_master WHERE name='agent_profiles'").fetchall())
            with closing(SQLiteStore(path)) as s:self.assertEqual(s._execute('PRAGMA user_version')[0][0],5)

@unittest.skipUnless(os.environ.get('KNOWLEDGE_SDK_TEST_PG_DSN'),'Disposable PostgreSQL DSN required')
class IndependentConnectionRaces(unittest.TestCase):
    def race(self,scim):
        import threading
        from knowledge_sdk.storage.postgres_store import PostgresStore
        from tests.pg_helpers import PgSandbox
        box=PgSandbox();self.addCleanup(box.close)
        s1=PostgresStore(box.dsn);self.addCleanup(s1.close)
        s2=PostgresStore(box.dsn,migrate=False);self.addCleanup(s2.close)
        c1=LocalKnowledgeClient(s1);c2=LocalKnowledgeClient(s2)
        a=Actor('admin','org',org_roles=['admin']);u=Actor('reader','org',policy_generation='1')
        s1.upsert_principal(IdentityPrincipal('org','reader'));c1.create_kb(a,'kb','enterprise',kb_id='kb');c1.ingest(a,'kb','alpha race evidence',doc_id='doc')
        c1.register_agent_profile(a,'agent');task=c1.create_task_context(u,'agent')
        entered=threading.Event();release=threading.Event();attempted=threading.Event()
        original=c1._runtime_reference
        def pause(*args,**kwargs):
            entered.set();self.assertTrue(release.wait(8));return original(*args,**kwargs)
        def mutate():
            attempted.set()
            if scim:return SCIMService(c2).write(a,{'active':False},'reader')
            return c2.update_agent_profile(a,'agent',active=False)
        with ThreadPoolExecutor(2) as pool,patch.object(c1,'_runtime_reference',side_effect=pause):
            first=pool.submit(c1.create_context_snapshot,u,task.task_id,[{'doc_id':'doc'}])
            self.assertTrue(entered.wait(5));second=pool.submit(mutate);self.assertTrue(attempted.wait(5))
            self.assertFalse(second.done());release.set();snapshot=first.result(timeout=10);second.result(timeout=10)
        self.assertTrue(snapshot.items)
        with self.assertRaises(PermissionDeniedError):c1.read_task_snapshot(u,task.task_id,snapshot.snapshot_id)
        self.assertEqual(s1.get_task_context('org',task.task_id).status,'revoked');self.assertTrue(s1.list_task_revocations('org',task.task_id))
    def test_profile_mutation_serializes_with_snapshot_insert(self):self.race(False)
    def test_scim_mutation_serializes_with_snapshot_insert(self):self.race(True)
    def test_profile_updates_multiple_connections_no_lost_generations(self):
        from knowledge_sdk.storage.postgres_store import PostgresStore
        from tests.pg_helpers import PgSandbox
        box=PgSandbox();self.addCleanup(box.close);stores=[PostgresStore(box.dsn,migrate=i==0) for i in range(4)]
        for s in stores:self.addCleanup(s.close)
        clients=[LocalKnowledgeClient(s) for s in stores];a=Actor('admin','org',org_roles=['admin']);clients[0].register_agent_profile(a,'agent')
        with ThreadPoolExecutor(4) as pool:results=list(pool.map(lambda i:clients[i%4].update_agent_profile(a,'agent',display_name=str(i)),range(16)))
        self.assertEqual(sorted(p.profile_generation for p in results),list(range(2,18)))
