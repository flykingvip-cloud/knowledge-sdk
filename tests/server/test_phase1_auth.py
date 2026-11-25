from __future__ import annotations
from contextlib import closing
import base64
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import hashlib
import hmac
import importlib.util
import json
import multiprocessing
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from knowledge_sdk import Actor
from knowledge_sdk.contracts.models import encode, decode
from knowledge_sdk.exceptions import ValidationError
from knowledge_sdk.server.auth import (InMemoryReplayStore, SQLiteReplayStore,
                                      signed_headers, verify_headers, extension_claims)

SECRET = 'phase1-test-key-not-a-real-secret-' + 'x' * 32
OLD = 'phase1-old-test-key-not-a-real-secret-' + 'y' * 32
ACTOR = Actor('u1', 'org1')


def worker_consume(path, event, results):
    store = SQLiteReplayStore(path)
    event.wait(10)
    results.put(store.check_and_record('same-nonce', 100, now=100))


class ActorPhase1Tests(unittest.TestCase):
    def test_defaults_and_legacy_json(self):
        actor = Actor('u1', 'org1')
        self.assertEqual((actor.policy_generation, actor.session_id), ('0', ''))
        self.assertEqual(decode({'__type__': 'Actor', 'user_id': 'u1', 'org_id': 'org1'}), actor)

    def test_new_claims_json_roundtrip(self):
        actor = Actor('u1', 'org1', policy_generation='rev-8', session_id='session-a')
        self.assertEqual(decode(json.loads(json.dumps(encode(actor)))), actor)
        h = signed_headers(actor, SECRET, 'GET', '/v1/kbs')
        self.assertEqual(verify_headers(h, SECRET, 'GET', '/v1/kbs'), actor)

    def test_claims_must_be_strings(self):
        for field in ('policy_generation', 'session_id'):
            for value in (None, True, 1, [], {}):
                with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                    Actor('u', 'o', **{field: value})


class MemoryReplayTests(unittest.TestCase):
    def test_first_replay_and_expiry(self):
        store = InMemoryReplayStore()
        self.assertTrue(store.check_and_record('a', 10, now=100))
        self.assertFalse(store.check_and_record('a', 10, now=109.99))
        self.assertTrue(store.check_and_record('a', 10, now=110))

    def test_capacity_and_cleanup(self):
        store = InMemoryReplayStore(1)
        self.assertTrue(store.check_and_record('a', 10, now=100))
        self.assertFalse(store.check_and_record('b', 10, now=101))
        self.assertTrue(store.check_and_record('b', 10, now=111))

    def test_concurrent_single_winner(self):
        store = InMemoryReplayStore()
        with ThreadPoolExecutor(max_workers=16) as pool:
            results = list(pool.map(lambda _: store.check_and_record('n', 10, now=1), range(64)))
        self.assertEqual(results.count(True), 1)

    def test_reject_bad_capacity_and_ttl(self):
        with self.assertRaises(ValidationError):
            InMemoryReplayStore(0)
        store = InMemoryReplayStore()
        for ttl in (0, -1, 1.5):
            self.assertFalse(store.check_and_record('a', ttl, now=100))
        self.assertFalse(store.check_and_record('a', 10, now=float('nan')))


class SQLiteReplayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = str(Path(self.tmp.name) / 'replay.sqlite3')

    def test_cross_instance_and_ttl(self):
        a, b = SQLiteReplayStore(self.path), SQLiteReplayStore(self.path)
        self.assertTrue(a.check_and_record('nonceA', 10, now=100))
        self.assertFalse(b.check_and_record('nonceA', 10, now=109))
        self.assertTrue(b.check_and_record('nonceA', 10, now=110))
        with closing(sqlite3.connect(self.path)) as conn, conn:
            self.assertEqual(conn.execute('PRAGMA journal_mode').fetchone()[0], 'wal')
            self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], 0)

    def test_capacity_cleanup(self):
        a = SQLiteReplayStore(self.path, max_entries=1)
        self.assertTrue(a.check_and_record('a', 10, now=1))
        self.assertFalse(a.check_and_record('b', 10, now=2))
        self.assertTrue(a.check_and_record('b', 10, now=11))

    def test_threads(self):
        a = SQLiteReplayStore(self.path)
        with ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(lambda _: a.check_and_record('n', 10, now=1), range(32)))
        self.assertEqual(results.count(True), 1)

    def test_real_process_single_winner(self):
        SQLiteReplayStore(self.path)
        ctx = multiprocessing.get_context('spawn')
        event, queue = ctx.Event(), ctx.Queue()
        procs = [ctx.Process(target=worker_consume, args=(self.path, event, queue)) for _ in range(6)]
        try:
            for process in procs:
                process.start()
            event.set()
            results = [queue.get(timeout=30) for _ in procs]
            for process in procs:
                process.join(30)
                self.assertEqual(process.exitcode, 0)
            self.assertEqual(results.count(True), 1)
        finally:
            for process in procs:
                if process.is_alive():
                    process.terminate()
                    process.join()
            queue.close()

    def test_database_error_fails_closed(self):
        a = SQLiteReplayStore(self.path)
        os.remove(self.path)
        os.mkdir(self.path)
        self.assertFalse(a.check_and_record('n', 10))

    def test_refuse_business_database(self):
        from knowledge_sdk.storage.sqlite_store import SQLiteStore
        business = SQLiteStore(self.path)
        business.close()
        with self.assertRaises(ValidationError):
            SQLiteReplayStore(self.path)
        with closing(sqlite3.connect(self.path)) as conn, conn:
            self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], 5)
            self.assertNotIn('auth_replay', [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")])

    def test_dedicated_on_disk_required(self):
        for value in ('', ':memory:', 'file::memory:?cache=shared'):
            with self.assertRaises(ValidationError):
                SQLiteReplayStore(value)


class SignaturePhase1Tests(unittest.TestCase):
    def headers(self, **kwargs):
        return signed_headers(ACTOR, SECRET, 'POST', '/v1/kbs?z=%2F&a=1', b'{}', **kwargs)

    def verify(self, headers, **kwargs):
        return verify_headers(headers, SECRET, 'POST', '/v1/kbs?z=%2F&a=1', b'{}', **kwargs)

    def test_six_line_golden_v11(self):
        # Independent old dataclass wire schema and six-line HMAC construction.
        old = {'user_id':'u1','org_id':'org1','roles':[],'department_ids':[],
               'ancestor_department_ids':[],'org_roles':[],'clearance_level':'',
               'clearance_tags':[],'managed_department_ids':[],'public_kb_admin':False}
        payload = base64.urlsafe_b64encode(json.dumps(old, sort_keys=True, separators=(',', ':')).encode()).decode()
        message = '\n'.join(('POST', '/v1/kbs?z=%2F&a=1', payload, '1700000000', 'a'*32, hashlib.sha256(b'{}').hexdigest()))
        actual = self.headers(timestamp=1700000000, nonce='a'*32)
        self.assertEqual(actual['X-KB-Actor'], payload)
        self.assertEqual(actual['X-KB-Signature'], hmac.new(SECRET.encode(), message.encode(), hashlib.sha256).hexdigest())
        self.assertEqual(len(message.splitlines()), 6)
        with patch('knowledge_sdk.server.auth.time.time', return_value=1700000000):
            self.assertEqual(self.verify(actual), ACTOR)

    def test_primary_and_fallback_rotation(self):
        self.assertEqual(self.verify(self.headers(), fallback_secrets=(OLD,)), ACTOR)
        headers = signed_headers(ACTOR, OLD, 'POST', '/v1/kbs?z=%2F&a=1', b'{}')
        self.assertEqual(self.verify(headers, fallback_secrets=(OLD,)), ACTOR)
        with self.assertRaises(ValidationError):
            self.verify(headers)

    def test_short_and_invalid_secrets(self):
        for key in ('tiny', '', None, 12):
            with self.assertRaises(ValidationError):
                signed_headers(ACTOR, key, 'GET', '/')
        for fallback in (('tiny',), (None,), 'abc'):
            with self.assertRaises(ValidationError):
                self.verify(self.headers(), fallback_secrets=fallback)
        with self.assertRaises(ValidationError):
            verify_headers(self.headers(), 'tiny', 'POST', '/v1/kbs?z=%2F&a=1', b'{}', fallback_secrets=(SECRET,))

    def test_failed_signatures_do_not_consume_nonce(self):
        store = InMemoryReplayStore()
        h = self.headers()
        tampered = dict(h, **{'X-KB-Signature':'0'*64})
        with self.assertRaises(ValidationError):
            self.verify(tampered, replay_store=store)
        self.assertEqual(self.verify(h, replay_store=store), ACTOR)
        with self.assertRaises(ValidationError):
            self.verify(h, replay_store=store)

    def test_replay_shared_across_rotation(self):
        store = InMemoryReplayStore()
        h = self.headers(nonce='a'*32)
        self.verify(h, replay_store=store)
        old = signed_headers(ACTOR, OLD, 'POST', '/v1/kbs?z=%2F&a=1', b'{}', nonce='a'*32)
        with self.assertRaises(ValidationError):
            self.verify(old, replay_store=store, fallback_secrets=(OLD,))

    def test_legacy_seen_and_precedence(self):
        seen = {}
        h = self.headers()
        self.verify(h, seen=seen)
        with self.assertRaises(ValidationError):
            self.verify(h, seen=seen)
        self.assertEqual(self.verify(h, seen=seen, replay_store=InMemoryReplayStore()), ACTOR)

    def test_future_timestamp_retained_entire_window(self):
        store = InMemoryReplayStore()
        h = self.headers(timestamp=1300, nonce='f'*32)
        with patch('knowledge_sdk.server.auth.time.time', return_value=1000):
            self.verify(h, replay_store=store)
        with patch('knowledge_sdk.server.auth.time.time', return_value=1600):
            with self.assertRaises(ValidationError):
                self.verify(h, replay_store=store)
        self.assertFalse(store.check_and_record('f'*32, 1, now=1600))

    def test_expired_and_mismatched_target(self):
        h = self.headers(timestamp=1)
        with self.assertRaises(ValidationError):
            self.verify(h)
        h = self.headers()
        with self.assertRaises(ValidationError):
            verify_headers(h, SECRET, 'POST', '/v1/kbs?a=1&z=%2F', b'{}')

    def test_agent_purpose_roundtrip(self):
        agent = {'agent_id': 'agent1', 'org_id': 'org1', 'extension': {'id': 1}}
        h = self.headers(agent=agent, purpose='export')
        self.assertEqual(self.verify(h), ACTOR)
        self.assertEqual(extension_claims({k.lower():v for k,v in h.items()}, ACTOR), (agent, 'export'))
        self.assertEqual(extension_claims({}, ACTOR), (None, 'read'))
        for purpose in ('read', 'ground_internal_llm', 'ground_external_llm', 'export', 'eval_and_train'):
            self.assertEqual(self.verify(self.headers(purpose=purpose)), ACTOR)

    def test_extension_add_remove_tamper(self):
        for kw in ({'purpose':'read'}, {'agent':{'agent_id':'a', 'org_id':'org1'}},
                   {'agent':{'agent_id':'a', 'org_id':'org1'},'purpose':'export'}):
            h = self.headers(**kw)
            for name in ('X-KB-Purpose', 'X-KB-Agent'):
                if name in h:
                    removed = dict(h); del removed[name]
                    with self.assertRaises(ValidationError):
                        self.verify(removed)
            changed = dict(h, **{'X-KB-Purpose':'eval_and_train'})
            with self.assertRaises(ValidationError):
                self.verify(changed)
        h = self.headers()
        with self.assertRaises(ValidationError):
            self.verify(dict(h, **{'X-KB-Purpose':'read'}))
        with self.assertRaises(ValidationError):
            self.verify(dict(h, **{'X-KB-Agent':base64.urlsafe_b64encode(b'{"agent_id":"a","org_id":"org1"}').decode()}))

    def test_bad_purpose(self):
        for purpose in ('', 'train', 'READ', 1):
            with self.assertRaises(ValidationError):
                self.headers(purpose=purpose)
            h = dict(self.headers(), **{'X-KB-Purpose':purpose})
            with self.assertRaises(ValidationError):
                self.verify(h)

    def test_bad_agent_claims_and_size(self):
        values = ({'agent_id':'a', 'org_id':'other'}, {'agent_id':'', 'org_id':'org1'},
                  {'agent_id':1, 'org_id':'org1'}, {'org_id':'org1'},
                  {'agent_id':'  ', 'org_id':'org1'}, {'agent_id':'a','org_id':None},
                  'not-base64!', 'A'*8193, base64.urlsafe_b64encode(b'[]').decode(),
                  base64.urlsafe_b64encode(b'1').decode(),
                  base64.urlsafe_b64encode(b'null').decode(),
                  base64.urlsafe_b64encode(b'"a"').decode(),
                  base64.urlsafe_b64encode(b'\xff').decode())
        for agent in values:
            with self.subTest(agent=str(agent)[:40]), self.assertRaises(ValidationError):
                self.headers(agent=agent)
            if isinstance(agent, str):
                h = dict(self.headers(), **{'X-KB-Agent': agent})
                with self.assertRaises(ValidationError):
                    self.verify(h)

    def test_invalid_claims_before_nonce_consumption(self):
        store = InMemoryReplayStore()
        h = self.headers()
        bad = dict(h, **{'X-KB-Agent': 'bad'})
        with self.assertRaises(ValidationError):
            self.verify(bad, replay_store=store)
        self.assertEqual(self.verify(h, replay_store=store), ACTOR)
