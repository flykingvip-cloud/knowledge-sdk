import io
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from knowledge_sdk import Actor, KnowledgeSDKError, ValidationError, ConflictError, NotFoundError
from knowledge_sdk.contracts.idempotency import InMemoryIdempotencyStore, IdempotencyDecision as D, request_fingerprint
from knowledge_sdk.contracts.ingestion_jobs import InMemoryIngestionJobStore, IngestionJobState as S, ALLOWED_TRANSITIONS
from knowledge_sdk.client.http_client import HttpKnowledgeClient


class IdempotencyTests(unittest.TestCase):
    def test_canonical_strict_and_unicode(self):
        self.assertEqual(request_fingerprint({'b':2,'a':'临床'}),request_fingerprint({'a':'临床','b':2}))
        for value in (float('nan'),float('inf'),{1:'a'},(1,),{'x':object()},'\ud800'):
            with self.subTest(value=repr(value)), self.assertRaises(ValidationError): request_fingerprint(value)
    def test_states_ttl_and_stale_claim_fencing(self):
        now=[1]; store=InMemoryIdempotencyStore(2,clock=lambda:now[0]);args=('t','POST','/v2/assets','k',{'x':1})
        decision,record=store.begin(*args);self.assertEqual(decision,D.NEW)
        self.assertEqual(store.begin(*args)[0],D.IN_PROGRESS)
        self.assertEqual(store.begin(*args[:-1],{'x':2})[0],D.CONFLICT_PAYLOAD_MISMATCH)
        result={'version':[1]};store.complete(record,result);result['version'].append(2)
        decision,replay=store.begin(*args);self.assertEqual(decision,D.REPLAY_EXACT);self.assertEqual(replay.result,{'version':[1]})
        replay.result['version'].append(3);self.assertEqual(store.begin(*args)[1].result,{'version':[1]})
        now[0]=3;fresh=store.begin(*args)[1]
        with self.assertRaises(ConflictError):store.complete(record,{})
        store.complete(fresh,{});now[0]=6;self.assertEqual(store.cleanup(),1)
    def test_composite_key_and_atomic_claim(self):
        store=InMemoryIdempotencyStore();barrier=threading.Barrier(16)
        def begin(_):barrier.wait();return store.begin('t','POST','/v2/assets','k',{})[0]
        with ThreadPoolExecutor(16) as pool: decisions=list(pool.map(begin,range(16)))
        self.assertEqual(decisions.count(D.NEW),1);self.assertEqual(decisions.count(D.IN_PROGRESS),15)
        for args in [('other','POST','/v2/assets','k',{}),('t','PUT','/v2/assets','k',{}),('t','POST','/v2/spaces','k',{}),('t','POST','/v2/assets','k2',{})]:self.assertEqual(store.begin(*args)[0],D.NEW)
    def test_validation(self):
        for ttl in (0,-1,True,float('inf'),'1'):
            with self.assertRaises(ValidationError):InMemoryIdempotencyStore(ttl)
        with self.assertRaises(ValidationError):InMemoryIdempotencyStore().begin('t','post','/x','k',{})
    def test_completion_conflict(self):
        s=InMemoryIdempotencyStore();_,r=s.begin('t','POST','/x','k',{});s.complete(r,1);self.assertEqual(s.complete(r,1).result,1)
        with self.assertRaises(ConflictError):s.complete(r,2)


class JobTests(unittest.TestCase):
    def setUp(self):self.s=InMemoryIngestionJobStore()
    def job(self):return self.s.submit('t','k',{'doc':'d'},max_attempts=2)
    def move(self,j,state,**stats):return self.s.transition('t',j.job_id,state,expected_revision=j.revision,**stats)
    def test_happy_path_and_payload(self):
        j=self.job()
        for state in (S.PARSING,S.CHUNKING,S.INDEXING):j=self.move(j,state)
        j=self.move(j,S.COMPLETED,chunks_total=2,chunks_indexed=2,anchors_created=1)
        self.assertEqual(j.progress_pct,100);self.assertEqual(j.payload()['stats']['anchors_created'],1)
        self.assertIsNone(j.payload()['error_message'])
        with self.assertRaises(ConflictError):self.move(j,S.CANCELLED)
    def test_all_transition_pairs(self):
        # Reach every source and check all 49 directed transitions, fresh store each time.
        for source in S:
            for target in S:
                self.s=InMemoryIngestionJobStore();j=self.job()
                if source in (S.PARSING,S.CHUNKING,S.INDEXING,S.COMPLETED):
                    for x in (S.PARSING,S.CHUNKING,S.INDEXING,S.COMPLETED):
                        j=self.move(j,x)
                        if x==source:break
                elif source in (S.FAILED,S.CANCELLED):j=self.move(j,source,**({'error_code':'PARSE_FAILED'} if source==S.FAILED else {}))
                with self.subTest(source=source,target=target):
                    if target in ALLOWED_TRANSITIONS[source]:self.move(j,target,**({'error_code':'PARSE_FAILED'} if target==S.FAILED else {}))
                    else:
                        with self.assertRaises(ConflictError):self.move(j,target)
    def test_retry_limit_and_error_sanitization(self):
        j=self.job()
        with self.assertRaises(ValidationError):self.move(j,S.FAILED,error_code='secret@example.com content')
        j=self.move(j,S.FAILED,error_code='PARSE_FAILED')
        j=self.s.retry('t',j.job_id,expected_revision=j.revision);self.assertEqual(j.attempts,2)
        j=self.move(j,S.FAILED,error_code='PARSE_FAILED')
        with self.assertRaises(ConflictError):self.s.retry('t',j.job_id,expected_revision=j.revision)
    def test_cancel_race_and_idempotent_submission(self):
        j=self.job();self.assertEqual(self.job(),j)
        with self.assertRaises(ConflictError):self.s.submit('t','k',{'doc':'other'},max_attempts=2)
        with self.assertRaises(NotFoundError):self.s.get('foreign',j.job_id)
        gate=threading.Barrier(2)
        def race(state):
            gate.wait()
            try:return self.move(j,state).status
            except ConflictError:return 'conflict'
        with ThreadPoolExecutor(2) as pool:r=list(pool.map(race,(S.PARSING,S.CANCELLED)))
        self.assertEqual(r.count('conflict'),1)
    def test_progress_fails_closed(self):
        j=self.job()
        for stats in ({'chunks_total':True},{'chunks_indexed':1},{'chunks_total':-1},{'content':'no'},{'error_code':'PARSE_FAILED'}):
            with self.subTest(stats=stats),self.assertRaises(ValidationError):self.move(j,S.PARSING,**stats)
        with self.assertRaises(ValidationError):self.move(j,'unknown')
        with self.assertRaises(ValidationError):self.s.submit('t','k',{},max_attempts=True)


class HttpCloseTests(unittest.TestCase):
    def test_all_error_responses_close(self):
        c=HttpKnowledgeClient('http://127.0.0.1:1',auth_secret='x'*32);actor=Actor('u','t')
        for body in (b'{"error":"PermissionDeniedError"}',b'bad',b'[]',b'\xff'):
            for _ in range(25):
                stream=io.BytesIO(body);error=HTTPError(c.base_url,403,'Forbidden',{},stream)
                with patch('knowledge_sdk.client.http_client.urlopen',side_effect=error),self.assertRaises(KnowledgeSDKError):c.list_kbs(actor)
                self.assertTrue(stream.closed)
    def test_health_and_network_failures(self):
        c=HttpKnowledgeClient('http://127.0.0.1:1',auth_secret='x'*32);stream=io.BytesIO(b'error');error=HTTPError(c.base_url,503,'Unavailable',{},stream)
        with patch('knowledge_sdk.client.http_client.urlopen',side_effect=error),self.assertRaises(HTTPError):c.health()
        self.assertTrue(stream.closed)
        for exc in (URLError('offline'),TimeoutError('timeout')):
            with patch('knowledge_sdk.client.http_client.urlopen',side_effect=exc),self.assertRaises(type(exc)):c.list_kbs(Actor('u','t'))
