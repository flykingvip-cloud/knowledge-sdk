from __future__ import annotations
import unittest
from unittest.mock import patch
from knowledge_sdk import *
from knowledge_sdk.retrieval.hybrid import search,scope_constraints


class ScopePushdownTests(unittest.TestCase):
    def setUp(self):
        self.c=LocalKnowledgeClient();self.addCleanup(self.c.store.close)
        self.a=Actor('admin','o',org_roles=('admin',),managed_department_ids=('dep',));self.u=Actor('reader','o')
        self.c.create_kb(self.a,'noise','enterprise',kb_id='noise',space_type='enterprise_public')
        self.c.create_kb(self.a,'legal','enterprise',kb_id='legal',space_type='enterprise_public')
    def seed(self,count=600):
        for i in range(count):self.c.ingest(self.a,'noise','same signal',doc_id='a%04d'%i)
        ids=['z%d'%i for i in range(5)]
        for doc in ids:self.c.ingest(self.a,'legal','same signal',doc_id=doc)
        return ids
    def test_documents_are_really_sql_filtered_before_500_budget(self):
        ids=self.seed()
        with patch.object(self.c.store,'keyword_search_pushdown',wraps=self.c.store.keyword_search_pushdown) as spy:
            hits=self.c.search(self.u,'same',limit=5,scope=KnowledgeScope('documents',doc_ids=ids)).hits
            self.assertEqual({h.doc_id for h in hits},set(ids));self.assertEqual(spy.call_args.kwargs['doc_ids'],ids)
            self.assertEqual(spy.call_args.args[2],41)
    def test_binding_space_and_document_intersection_is_forwarded(self):
        ids=self.seed(70);scope=KnowledgeScope('spaces',kb_ids=('legal',),space_types=('enterprise_public',))
        binding=ConsumerBinding('agent','consumer',KnowledgeScope('documents',doc_ids=ids))
        with patch.object(self.c.store,'keyword_search_pushdown',wraps=self.c.store.keyword_search_pushdown) as spy:
            answer=self.c.ask(self.u,'same',scope=scope,binding=binding)
            self.assertEqual(answer.status,'answered')
            self.assertEqual(spy.call_args.kwargs,{'kb_ids':['legal'],'doc_ids':ids,'space_types':['enterprise_public']})
    def test_empty_intersection_short_circuits_and_empty_selectors_rejected(self):
        one=KnowledgeScope('spaces',kb_ids=('one',));two=KnowledgeScope('spaces',kb_ids=('two',))
        with patch.object(self.c.store,'keyword_search_pushdown',side_effect=AssertionError('must not query')):
            self.assertEqual(search(self.c.store,self.u,'same',scope=one,additional_scope=two).hits,[])
        with self.assertRaises(ValidationError):KnowledgeScope('documents')
        with self.assertRaises(ValidationError):KnowledgeScope('spaces')
        self.assertEqual(scope_constraints({},KnowledgeScope()),{'kb_ids':None,'doc_ids':None,'space_types':None})
    def test_space_type_is_bound_sql_not_only_post_filter(self):
        self.c.create_kb(self.a,'department','team',kb_id='department',space_type='department',owner_department_id='dep')
        self.c.ingest(self.a,'department','same signal',doc_id='department-doc')
        self.c.ingest(self.a,'legal','same signal',doc_id='legal-doc')
        captured=[];original=self.c.store._execute
        def execute(sql,args=()):
            if 'chunks_fts JOIN documents' in sql:captured.append((sql,list(args)))
            return original(sql,args)
        with patch.object(self.c.store,'_execute',side_effect=execute):
            result=search(self.c.store,self.u,'same',scope=KnowledgeScope('spaces',space_types=('enterprise_public',)))
        self.assertEqual([h.doc_id for h in result.hits],['legal-doc'])
        self.assertIn('d.space_type IN (?)',captured[0][0]);self.assertIn('enterprise_public',captured[0][1])
        self.assertEqual(self.c.store.keyword_search_pushdown('same','o',space_types=["x') OR 1=1 --"]),[])
    def test_custom_store_fallback_preserves_python_intersection(self):
        ids=self.seed(5)
        class Legacy:
            def __getattr__(inner,key):
                if key=='keyword_search_pushdown':raise AttributeError(key)
                return getattr(self.c.store,key)
        result=search(Legacy(),self.u,'same',limit=5,scope=KnowledgeScope('spaces',kb_ids=('legal',)),additional_scope=KnowledgeScope('documents',doc_ids=ids))
        self.assertEqual({h.doc_id for h in result.hits},set(ids))
    def test_old_pushdown_signature_remains_compatible_with_space_filter(self):
        self.seed(1)
        class OldPushdown:
            def keyword_search_pushdown(inner,query,org_id,limit=100,*,kb_ids=None,doc_ids=None):
                return self.c.store.keyword_search_pushdown(query,org_id,limit,kb_ids=kb_ids,doc_ids=doc_ids)
            def __getattr__(inner,key):return getattr(self.c.store,key)
        self.assertEqual(len(search(OldPushdown(),self.u,'same',scope=KnowledgeScope('spaces',space_types=('enterprise_public',))).hits),6)
