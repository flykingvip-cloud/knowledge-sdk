"""The same 75 executable contracts/redteam assertions run on both engines.

Case specifications and scenario assertions are unchanged. SQLite-specific
white-box SQL is adapted only in tests.pg_helpers; no driver/SQL mocks here.
"""
import os
import unittest
from tests.benchmark.runner import Fixture,Observation,SCENARIOS,load_cases

class SQLiteParity(unittest.TestCase):engine='sqlite'
@unittest.skipUnless(os.environ.get('KNOWLEDGE_SDK_TEST_PG_DSN'),'Set KNOWLEDGE_SDK_TEST_PG_DSN for real PG + pgvector parity')
class PostgresParity(unittest.TestCase):engine='postgres'


def contract(case):
    def test(self):
        fixture=Fixture(case,self.engine)
        try:SCENARIOS[case['scenario']](fixture,Observation(case['expected']))
        finally:fixture.close()
    return test

for case in load_cases():
    for cls in (SQLiteParity,PostgresParity):
        setattr(cls,'test_'+case['case_id'].replace('-','_')+'_'+case['scenario'],contract(case))

# Do not leave a TestCase alias for unittest to discover a second time.
del cls,case


def mixed_language_contract(self):
    from knowledge_sdk import Actor,DocumentACL,KnowledgeScope
    f=Fixture(load_cases()[0],self.engine)
    try:
        f.doc('知识库 alpha mixed-language evidence',id='expected')
        f.doc('知识库 alpha denied evidence',id='denied',acl=DocumentACL(deny_users=('reader',)))
        f.doc('finance beta unrelated',id='other')
        for query in ('知识库','知识库 alpha','alpha'):
            response=f.c.search(f.u,query,limit=1)
            self.assertEqual([h.doc_id for h in response.hits],['expected'])
            scoped=f.c.search(f.u,query,scope=KnowledgeScope('documents',doc_ids=('other',)))
            self.assertFalse(scoped.hits)
        self.assertEqual(f.c.store.get_version('expected',1).text,'知识库 alpha mixed-language evidence')
        self.assertFalse(f.c.search(Actor('reader','foreign'),'知识库 alpha').hits)
    finally:f.close()

SQLiteParity.test_shared_cjk_english_scope_and_authorized_fetch=mixed_language_contract
PostgresParity.test_shared_cjk_english_scope_and_authorized_fetch=mixed_language_contract
