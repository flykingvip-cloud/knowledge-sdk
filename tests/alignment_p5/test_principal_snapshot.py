import os,threading,unittest
from dataclasses import replace
from unittest.mock import patch
from knowledge_sdk import Actor,LocalKnowledgeClient,PermissionDeniedError,Purpose
from knowledge_sdk.contracts.identity import IdentityPrincipal

class PrincipalCases:
    engine='sqlite'
    def setUp(self):
        self.sandbox=None
        if self.engine=='postgres':
            from tests.pg_helpers import PgSandbox,golden_client
            self.sandbox=PgSandbox();self.c=golden_client(self.sandbox.dsn)
        else:self.c=LocalKnowledgeClient()
        self.addCleanup(self.cleanup);self.a=Actor('owner','fixture-org',org_roles=('admin',),policy_generation='1')
        self.p=IdentityPrincipal('fixture-org','owner',policy_generation=1,org_roles=('admin',));self.c.store.upsert_principal(self.p);self.c.require_principal=True
        self.c.create_kb(self.a,'space',kb_id='space')
        for n in range(15):self.c.ingest(self.a,'space','shared evidence '+str(n),doc_id='d'+str(n))
    def cleanup(self):
        try:self.c.store.close()
        finally:
            if self.sandbox:self.sandbox.close()
    def test_single_request_only_principal_reuse_and_full_policy_audit(self):
        for enhanced in (False,True):
            with patch.object(self.c.store,'get_principal',wraps=self.c.store.get_principal) as reads:
                hits=self.c.search(self.a,'shared',rerank=enhanced).hits
                self.assertEqual(len(hits),15);self.assertEqual(reads.call_count,4 if enhanced else 3)
            self.assertIsNone(self.c._retrieval_identity)
        self.assertGreaterEqual(len(self.c.store.list_audit_events('fixture-org',action='evaluate_policy',limit=100)),30)
        self.c.store.upsert_principal(replace(self.p,active=False))
        with self.assertRaises(PermissionDeniedError):self.c.search(self.a,'shared',rerank=True)
        self.assertTrue(any(e.decision_effect.value=='deny' for e in self.c.store.list_audit_events('fixture-org',action='search',limit=100)))
    def test_reentrant_mutation_before_ranking_denies_and_external_boundary_not_called(self):
        original=self.c.policy_engine.delegate.evaluate;invoked=[];first=[True]
        def revoke(*args,**kwargs):
            decision=original(*args,**kwargs)
            if first[0]:first[0]=False;self.c.store.upsert_principal(replace(self.p,active=False))
            return decision
        class Ranker:
            reranker_id='fixture-spy'
            def score(inner,query,candidates):invoked.append(True);return tuple(0.0 for _ in candidates)
        with patch.object(self.c.policy_engine.delegate,'evaluate',side_effect=revoke):
            with self.assertRaises(PermissionDeniedError):self.c.search(self.a,'shared',reranker=Ranker())
        self.assertFalse(invoked);self.assertIsNone(self.c._retrieval_identity)
    def test_reentrant_reranker_mutation_cannot_return_pre_revocation_result(self):
        c=self.c;p=self.p;case=self
        from knowledge_sdk.mcp.gateway import GatewayContext
        c.register_agent_profile(self.a,'fixture-task-profile')
        task=c.create_task_context(self.a,'fixture-task-profile',purpose=Purpose.READ)
        class Ranker:
            reranker_id='fixture-reentrant'
            def score(inner,query,candidates):
                # The SAME user reenters while the outer identity memo is live.
                # Runtime task ownership/purpose validation must never reuse it.
                wrong_org=replace(case.a,org_id='other-org')
                for who,purpose in ((case.a,Purpose.GROUND_INTERNAL_LLM),(wrong_org,Purpose.READ)):
                    with case.assertRaises(PermissionDeniedError):c._runtime_mcp(who,task.task_id,None,'search_evidence',{'query':'shared'},GatewayContext(who,purpose=purpose))
                nested=c._runtime_mcp(case.a,task.task_id,None,'search_evidence',{'query':'shared','limit':1},GatewayContext(case.a,purpose=Purpose.READ))
                case.assertEqual(len(nested['hits']),1)
                c.store.upsert_principal(replace(p,policy_generation=2));return tuple(0.0 for _ in candidates)
        with self.assertRaises(PermissionDeniedError):c.search(self.a,'shared',reranker=Ranker())
        self.assertIsNone(c._retrieval_identity)
    def test_actor_purpose_and_policy_stay_separate_and_deny_is_not_cached(self):
        c=self.c;kb=c.store.get_kb('space');d=c.store.get_document('d0');acl=c.store.get_acl('d0')
        with self.assertRaises(PermissionDeniedError):
            with c._lock,c.store.runtime_transaction(),c._retrieval_principal_snapshot(self.a,None,Purpose.READ,None):
                with patch.object(c.store,'get_principal',wraps=c.store.get_principal) as reads:
                    c.policy_engine.evaluate(self.a,None,kb,d,acl,purpose=Purpose.READ)
                    self.assertEqual(reads.call_count,0)
                    c.policy_engine.evaluate(self.a,None,kb,d,acl,purpose=Purpose.GROUND_INTERNAL_LLM)
                    self.assertEqual(reads.call_count,1)
                    with self.assertRaises(PermissionDeniedError):c.policy_engine.evaluate(replace(self.a,org_id='other'),None,kb,d,acl)
                    self.assertEqual(reads.call_count,2)
                    from knowledge_sdk import DocumentACL
                    denied=c.policy_engine.evaluate(self.a,None,kb,d,DocumentACL(deny_users=['owner']))
                    self.assertFalse(denied.allowed)
                    allowed=c.policy_engine.evaluate(self.a,None,kb,d,acl)
                    self.assertTrue(allowed.allowed)
                    c.store.upsert_principal(replace(self.p,active=False))
                    for _ in range(2):
                        with self.assertRaises(PermissionDeniedError):c.policy_engine.evaluate(self.a,None,kb,d,acl)
                    self.assertGreaterEqual(reads.call_count,4)
    def test_two_postgres_connections_linearize_revocation_and_next_request_denies(self):
        if self.engine!='postgres':self.skipTest('Independent PG connection test')
        from tests.pg_helpers import golden_client
        other=golden_client(self.sandbox.dsn);entered=threading.Event();release=threading.Event();mutated=threading.Event();errors=[];result=[]
        class Ranker:
            reranker_id='fixture-blocking'
            def score(inner,query,candidates):
                entered.set()
                if not release.wait(5):raise AssertionError('Bounded fixture synchronization expired')
                return tuple(0.0 for _ in candidates)
        def read():
            try:result.append(self.c.search(self.a,'shared',reranker=Ranker()))
            except BaseException as e:errors.append(type(e).__name__)
        def revoke():
            try:other.store.bump_policy_generation('fixture-org','owner',active=False);mutated.set()
            except BaseException as e:errors.append(type(e).__name__)
        reader=threading.Thread(target=read);writer=threading.Thread(target=revoke)
        try:
            reader.start();self.assertTrue(entered.wait(5));writer.start();self.assertFalse(mutated.wait(.1));release.set();reader.join(10);writer.join(10)
            self.assertFalse(reader.is_alive());self.assertFalse(writer.is_alive());self.assertFalse(errors);self.assertTrue(result[0].hits);self.assertTrue(mutated.is_set())
            with self.assertRaises(PermissionDeniedError):self.c.search(self.a,'shared',rerank=True)
        finally:
            release.set();reader.join(10)
            if writer.ident is not None:writer.join(10)
            other.store.close()
class SQLitePrincipal(PrincipalCases,unittest.TestCase):pass
@unittest.skipUnless(os.environ.get('KNOWLEDGE_SDK_TEST_PG_DSN'),'Disposable PG unavailable')
class PostgresPrincipal(PrincipalCases,unittest.TestCase):engine='postgres'
