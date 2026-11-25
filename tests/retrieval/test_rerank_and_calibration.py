import math,os,unittest
from dataclasses import replace,FrozenInstanceError,fields
from unittest.mock import Mock
from knowledge_sdk import *
from knowledge_sdk.retrieval.calibration import *
from knowledge_sdk.retrieval.adapters.reranker import CallableRerankerAdapter
from knowledge_sdk.retrieval.rerank import *
from knowledge_sdk.permissions.redaction import RegexRedactionHook
from tests.benchmark.runner import Fixture


def candidate(**kw):
    data=dict(doc_id='d',version=1,chunk_id='c',title='orbital recovery',excerpt='orbital recovery checklist',source_uri='kb://org/o/doc/d@1',base_score=.01,rank=1)
    data.update(kw);return RerankCandidate(**data)

class RerankContracts(unittest.TestCase):
    def test_exact_nine_frozen_fields_roundtrip(self):
        c=candidate();self.assertEqual(len(fields(c)),9);self.assertEqual(RerankCandidate.from_dict(c.to_dict()),c)
        with self.assertRaises(FrozenInstanceError):c.rank=2
        with self.assertRaises(ValidationError):RerankCandidate.from_dict(dict(c.to_dict(),body='forbidden'))
    def test_strict_candidate_values(self):
        for kw in ({'doc_id':''},{'chunk_id':''},{'source_uri':''},{'version':True},{'rank':False},{'version':0},{'rank':1.0},{'base_score':True},{'base_score':math.nan},{'base_score':math.inf},{'base_score':10**400},{'redacted':1},{'title':'x'*2001},{'excerpt':'x'*32001}):
            with self.subTest(kw=str(kw)[:60]),self.assertRaises(ValidationError):candidate(**kw)
    def test_bad_scores_fail_closed(self):
        for values in ([],[.1,.2],[1],[True],[math.nan],[math.inf],['.1'],iter([.1]),None):
            r=CallableRerankerAdapter('probe',lambda q,c:values)
            with self.assertRaises(ValidationError):apply_reranker('q',[candidate()],r)
    def test_empty_no_invocation(self):
        fn=Mock(side_effect=AssertionError('must not call'));self.assertEqual(apply_reranker('q',[],CallableRerankerAdapter('probe',fn)),());fn.assert_not_called()
    def test_exception_text_suppressed(self):
        def bad(q,c):raise RuntimeError('FORBIDDEN_SECRET')
        with self.assertRaises(ValidationError) as e:apply_reranker('q',[candidate()],CallableRerankerAdapter('probe',bad))
        self.assertNotIn('FORBIDDEN_SECRET',str(e.exception));self.assertIsNone(e.exception.__cause__)
    def test_bilingual_phrase_and_stable_prior(self):
        r=DeterministicLexicalReranker()
        for query,good,bad in [('orbital recovery','orbital recovery','recovery orbital'),('海桥应急恢复','海桥应急恢复','恢复应急海桥')]:
            scores=r.score(query,[candidate(title=good,excerpt=good,rank=5),candidate(title='index',excerpt=bad,rank=1)])
            self.assertGreater(scores[0],scores[1]);self.assertEqual(scores,r.score(query,[candidate(title=good,excerpt=good,rank=5),candidate(title='index',excerpt=bad,rank=1)]))
    def test_invalid_weights(self):
        for kw in ({'title_weight':True},{'rank_prior_weight':.5},{'coverage_weight':math.nan},{'title_weight':-.1},{'coverage_weight':.1}):
            with self.assertRaises(ValidationError):DeterministicLexicalReranker(**kw)

class CalibrationContracts(unittest.TestCase):
    def test_roundtrip_deep_frozen_independent_channels(self):
        c=ScoreCalibrator();self.assertEqual(c,ScoreCalibrator.from_dict(c.to_dict()));self.assertEqual(len({id(v) for v in c.config.channels}),4)
        self.assertNotEqual(c.calibrate('keyword',.01),c.calibrate('rerank',.01))
        with self.assertRaises(FrozenInstanceError):c.config.channels[0].channel='rerank'
    def test_monotone_three_methods_extremes(self):
        for method in ('minmax','sigmoid','piecewise_quantile'):
            c=CalibrationChannelConfig('rerank',method,anchors=[(-1e308,0),(0,.5),(1e308,1)])
            values=[c.map(v) for v in (-1e308,-1,0,.5,1,1e308)]
            self.assertEqual(values,sorted(values));self.assertTrue(all(type(x) is float and math.isfinite(x) and 0<=x<=1 for x in values))
        self.assertEqual(CalibrationChannelConfig('rerank',min_raw=-1e308,max_raw=1e308).map(0),.5)
    def test_native_cosine_channel_independent_from_rrf(self):
        self.assertEqual(ScoreCalibrator().calibrate('vector',-1),0.0)
        self.assertEqual(ScoreCalibrator().calibrate('vector',0),.5)
        self.assertEqual(ScoreCalibrator().calibrate('vector',1),1.0)
    def test_strict_configs_anchors_and_raw_scores(self):
        for kw in ({'min_raw':True},{'steepness':0},{'max_raw':0},{'midpoint':math.nan},{'channel':'bad'},{'method':'callback'},{'anchors':[(0,0),(0,1)]},{'anchors':[(0,1),(1,0)]},{'anchors':[(0,False),(1,1)]},{'anchors':[(0,0),(1,2)]},{'method':'piecewise_quantile'}):
            with self.assertRaises(ValidationError):CalibrationChannelConfig(**dict({'channel':'keyword'},**kw))
        for raw in (True,math.nan,math.inf,10**400):
            with self.assertRaises(ValidationError):ScoreCalibrator().calibrate('keyword',raw)
        with self.assertRaises(ValidationError):ScoreCalibrationConfig(channels=[CalibrationChannelConfig('keyword')]*4)
    def test_threshold_strict(self):
        for value in (True,-.1,1.1,math.nan,math.inf,'0.5'):
            with self.assertRaises(ValidationError):validate_threshold(value)

class SearchCases:
    engine='sqlite'
    def setUp(self):
        self.f=Fixture({'expected':{}},self.engine);self.addCleanup(self.f.close);self.c=self.f.c;self.a=self.f.a;self.u=self.f.u
    def test_raw_semantics_default_and_enhanced_fields(self):
        self.f.doc('alpha evidence')
        old=self.c.search(self.u,'alpha');new=self.c.search(self.u,'alpha',rerank=True,calibrator_id='default-v1')
        self.assertIsNone(old.hits[0].raw_score);self.assertEqual(new.hits[0].raw_score,old.hits[0].score)
        self.assertEqual(new.hits[0].score,new.hits[0].rerank_score);self.assertTrue(0<=new.hits[0].calibrated_score<=1)
    def test_malicious_observer_only_sanitized_allowed_bounded(self):
        self.f.doc('alpha SECRET_RAW_BODY',title='SECRET_RAW_TITLE',rights=ResourceRights(redaction_profile='hide'))
        self.f.doc('alpha FORBIDDEN_SENTINEL',id='denied',title='FORBIDDEN_TITLE',acl=DocumentACL(deny_users=['reader']))
        self.c.redaction_registry.register('hide',RegexRedactionHook([('SECRET_RAW_\\w+','MASK')]))
        seen=[]
        def observe(q,cs):
            seen.extend(cs)
            self.assertTrue(all(type(c) is RerankCandidate for c in cs))
            self.assertNotIn('SECRET_RAW',str(cs));self.assertNotIn('FORBIDDEN',str(cs));self.assertEqual({c.doc_id for c in cs},{'doc'})
            self.assertTrue(all(c.redacted and len(c.excerpt)<=32000 for c in cs))
            return [1.0]*len(cs)
        response=self.c.search(self.u,'alpha',reranker=CallableRerankerAdapter('observe',observe),min_calibrated_score=.9)
        self.assertEqual(len(seen),1);self.assertEqual(len(response.hits),1);self.assertEqual(response.filtered_by_threshold_count,0)
    def test_threshold_count_only_accepted_and_empty_no_calls(self):
        self.f.doc('alpha allowed');self.f.doc('alpha FORBIDDEN',id='denied',acl=DocumentACL(deny_users=['reader']))
        r=CallableRerankerAdapter('zero',lambda q,c:[0.0]*len(c));response=self.c.search(self.u,'alpha',reranker=r,min_calibrated_score=.8)
        self.assertFalse(response.hits);self.assertEqual(response.filtered_by_threshold_count,1)
        fn=Mock(side_effect=AssertionError('empty'));r=CallableRerankerAdapter('empty',fn)
        self.assertFalse(self.c.search(self.u,'alpha',scope=KnowledgeScope('none'),reranker=r).hits);fn.assert_not_called()
    def test_internal_search_threshold_and_window_are_strict(self):
        from knowledge_sdk.retrieval.hybrid import search
        self.f.doc('alpha evidence')
        result=search(self.c.store,self.u,'alpha',min_calibrated_score=1.0)
        self.assertTrue(result.calibration_applied)
        with self.assertRaises(ValidationError):search(self.c.store,self.u,'alpha',rerank_top_k=501)
    def test_options_rejected_even_empty(self):
        for kw in ({'rerank':1},{'reranker_id':'unknown'},{'calibrator_id':'unknown'},{'reranker_id':True},{'min_calibrated_score':True},{'min_calibrated_score':math.nan},{'min_calibrated_score':math.inf},{'rerank_top_k':501},{'rerank_top_k':True}):
            with self.subTest(kw=kw),self.assertRaises(ValidationError):self.c.search(self.u,'absent',scope=KnowledgeScope('none'),**kw)
    def test_deterministic_full_tie_key_and_candidate_window(self):
        self.f.doc('alpha '*20,id='z');self.f.doc('alpha filler extra information',id='a')
        constant=CallableRerankerAdapter('constant',lambda q,cs:[1.0]*len(cs))
        h=self.c.search(self.u,'alpha',limit=1,reranker=constant,rerank_top_k=40).hits
        self.assertEqual(h[0].doc_id,'a')
    def test_task_and_mcp_revoke_before_ranking_and_scope(self):
        from knowledge_sdk.mcp import EvidenceTools,GatewayContext
        self.f.doc('alpha evidence');self.c.register_agent_profile(self.a,'agent',allowed_purposes=(Purpose.READ,))
        t=self.c.create_task_context(self.u,'agent',purpose=Purpose.READ)
        s=self.c.create_context_snapshot(self.u,t.task_id,'alpha',rerank=True,min_calibrated_score=.6);self.assertTrue(s.items)
        self.c.update_agent_profile(self.a,'agent',active=False)
        fn=Mock(side_effect=AssertionError('revoked must not rank'))
        with self.assertRaises(PermissionDeniedError):self.c.create_context_snapshot(self.u,t.task_id,'alpha',reranker=CallableRerankerAdapter('probe',fn))
        with self.assertRaises(PermissionDeniedError):EvidenceTools(self.c).call('search_evidence',{'query':'alpha','task_id':t.task_id,'rerank':True},GatewayContext(self.u,purpose=Purpose.READ))
        fn.assert_not_called()
    def test_hidden_only_revision_has_identical_redacted_rank(self):
        self.c.redaction_registry.register('hide',RegexRedactionHook([('SECRET_RAW_\\w+','MASK')]))
        self.f.doc('alpha SECRET_RAW_FIRST',title='alpha',rights=ResourceRights(redaction_profile='hide'))
        one=self.c.search(self.u,'alpha',rerank=True).hits[0]
        self.f.doc('alpha SECRET_RAW_SECOND',title='alpha',rights=ResourceRights(redaction_profile='hide'))
        two=self.c.search(self.u,'alpha',rerank=True).hits[0]
        self.assertEqual((one.excerpt,one.score),(two.excerpt,two.score))
    def test_no_cross_request_or_tenant_cache(self):
        self.f.doc('alpha evidence');self.assertTrue(self.c.search(self.u,'alpha',rerank=True).hits)
        self.c.set_document_acl(self.a,'doc',DocumentACL(deny_users=['reader']))
        self.assertFalse(self.c.search(self.u,'alpha',rerank=True).hits)
        self.assertFalse(self.c.search(Actor('reader','other'),'alpha',rerank=True).hits)

class SQLiteSearchCases(SearchCases,unittest.TestCase):pass
@unittest.skipUnless(os.environ.get('KNOWLEDGE_SDK_TEST_PG_DSN'),'Disposable PG required')
class PostgresSearchCases(SearchCases,unittest.TestCase):engine='postgres'
