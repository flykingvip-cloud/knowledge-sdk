from dataclasses import replace,FrozenInstanceError
from pathlib import Path
import json,os,unittest
from knowledge_sdk import *
from knowledge_sdk.retrieval.eval import OfflineBoundaryMonitor
from tests.retrieval.q3_m2_fixture import EvalFixture

class CaseContracts(unittest.TestCase):
    def case(self):return RetrievalEvalCase('case','family','query','keyword','reader','read',{'doc':3})
    def test_case_frozen_checked_roundtrip(self):
        c=self.case();self.assertEqual(c,RetrievalEvalCase.from_dict(c.to_dict()))
        with self.assertRaises(FrozenInstanceError):c.query='other'
        for kw in ({'top_k':True},{'purpose':'invalid'},{'expect_refusal':1},{'relevant_doc_ids':{'d':True}},{'forbidden_doc_ids':['doc']},{'split':'unknown'},{'relevant_doc_ids':{}},{'relevant_doc_ids':{'d':0}}):
            with self.assertRaises(ValidationError):replace(c,**kw)
    def test_config_strict_frozen_roundtrip(self):
        c=PairwiseEvalConfig();self.assertEqual(c,PairwiseEvalConfig.from_dict(c.to_dict()))
        for kw in ({'min_calibrated_score':True},{'rerank_top_k':True},{'rerank_top_k':501},{'calibrator_id':''}):
            with self.assertRaises(ValidationError):replace(c,**kw)
    def test_instrumentation_actual_negative_control(self):
        import urllib.request
        with OfflineBoundaryMonitor() as probe:
            with self.assertRaises(ValidationError):urllib.request.urlopen('https://must-not-connect.invalid')
            self.assertEqual(probe.implicit_model_calls,1)

class PairedCases:
    engine='sqlite'
    @classmethod
    def setUpClass(cls):
        cls.f=EvalFixture(cls.engine)
        try:cls.report=PairwiseRetrievalEvaluator(cls.f.c,{'reader':cls.f.reader,'foreign':cls.f.foreign},config=cls.f.config).evaluate(cls.f.cases,index_sha256=cls.f.index_hash())
        except BaseException:cls.f.close();raise
    @classmethod
    def tearDownClass(cls):cls.f.close()
    def test_real_dual_path_gate_and_citations(self):
        r=self.report.to_dict();self.assertTrue(r['gate_passed']);self.assertTrue(r['snapshot_consistent']);self.assertEqual(r['split_counts'],{'train':4,'calibration':4,'evaluation':24})
        self.assertGreater(r['pairwise_deltas']['ndcg_delta'],0);self.assertGreater(r['pairwise_deltas']['mrr_delta'],0)
        for arm in ('baseline','candidate'):
            self.assertEqual(r[arm]['acl_violations'],0);self.assertEqual(r[arm]['implicit_model_calls'],0);self.assertEqual(r[arm]['valid_authorized_citations'],r[arm]['returned_hits'])
        self.assertEqual(r['candidate']['false_refusal_rate'],0);self.assertEqual(r['instrumentation']['observed_provider_network_attempts'],0)
    def test_report_immutable_checked_roundtrip(self):
        d=self.report.to_dict();self.assertEqual(PairwiseEvalReport.from_dict(d),self.report);d['gate_passed']=False
        with self.assertRaises(ValidationError):PairwiseEvalReport.from_dict(d)
        with self.assertRaises(FrozenInstanceError):self.report.report_json='{}'
        self.assertTrue(self.report.to_dict()['gate_passed'])
    def test_family_split_leak_rejected(self):
        cases=self.f.cases+(replace(self.f.cases[0],case_id='leak',split='evaluation'),)
        with self.assertRaisesRegex(ValidationError,'split leakage'):PairwiseRetrievalEvaluator(self.f.c,{'reader':self.f.reader}).evaluate(cases,index_sha256=self.f.index_hash())
    def test_dataset_config_labels_frozen_untouched(self):self.f.verify_freeze()
    def test_provider_attempt_in_ranker_is_measured_and_fails_gate(self):
        from knowledge_sdk.retrieval.strategies import registries
        import urllib.request
        class Attempt:
            reranker_id='attempt'
            def score(self,query,candidates):
                try:urllib.request.urlopen('https://must-not-connect.invalid')
                except ValidationError:pass
                return DeterministicLexicalReranker().score(query,candidates)
        previous=self.f.c.reranker_registry
        try:
            self.f.c.reranker_registry,_=registries({'attempt':Attempt()})
            config=replace(self.f.config,reranker_id='attempt')
            report=PairwiseRetrievalEvaluator(self.f.c,{'reader':self.f.reader,'foreign':self.f.foreign},config=config).evaluate(self.f.cases,index_sha256=self.f.index_hash()).to_dict()
            self.assertFalse(report['gate_passed']);self.assertGreater(report['candidate']['implicit_model_calls'],0)
            self.assertEqual(report['candidate']['implicit_model_calls'],report['instrumentation']['observed_provider_network_attempts'])
        finally:self.f.c.reranker_registry=previous


class SQLitePaired(PairedCases,unittest.TestCase):pass
@unittest.skipUnless(os.environ.get('KNOWLEDGE_SDK_TEST_PG_DSN'),'Disposable PG required')
class PostgresPaired(PairedCases,unittest.TestCase):engine='postgres'
