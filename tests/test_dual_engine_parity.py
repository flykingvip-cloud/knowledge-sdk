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
