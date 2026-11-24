from __future__ import annotations
from contextlib import closing
import gc
import importlib.util
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import knowledge_sdk
from knowledge_sdk import Actor, LocalKnowledgeClient
from knowledge_sdk.exceptions import ValidationError
from knowledge_sdk.server.auth import InMemoryReplayStore, SQLiteReplayStore, extension_claims


class Phase1CloseoutTests(unittest.TestCase):
    def test_capacity_ttl_now_reject_bool(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / 'r.sqlite3')
            for factory in (lambda v: InMemoryReplayStore(v), lambda v: SQLiteReplayStore(path, v)):
                for value in (True, False):
                    with self.assertRaises(ValidationError): factory(value)
            for store in (InMemoryReplayStore(), SQLiteReplayStore(path)):
                for value in (True, False):
                    self.assertFalse(store.check_and_record('n', value, now=1))
                    self.assertFalse(store.check_and_record('n', 10, now=value))

    def test_case_insensitive_extension_claims_and_duplicates(self):
        actor = Actor('u','org')
        self.assertEqual(extension_claims({'X-KB-Purpose':'export'}, actor), (None,'export'))
        with self.assertRaises(ValueError):
            extension_claims({'X-KB-Purpose':'read','x-kb-purpose':'export'}, actor)

    def test_connections_close_for_success_replay_capacity_and_exception(self):
        original = sqlite3.connect
        calls = []
        def connection(*args, **kwargs):
            conn = original(*args, **kwargs); calls.append(conn); return conn
        with tempfile.TemporaryDirectory() as directory, patch('knowledge_sdk.server.auth.sqlite3.connect', connection):
            store = SQLiteReplayStore(str(Path(directory) / 'r.sqlite3'), 1)
            self.assertTrue(store.check_and_record('n', 10, now=1))
            self.assertFalse(store.check_and_record('n', 10, now=2))
            self.assertFalse(store.check_and_record('other', 10, now=2))
            with closing(original(store.path)) as conn, conn:
                conn.execute('DROP TABLE auth_replay')
            self.assertFalse(store.check_and_record('x',10,now=3))
            for conn in calls:
                with self.assertRaises(sqlite3.ProgrammingError): conn.execute('SELECT 1')
            calls.clear(); gc.collect()

    def test_resource_warning_subprocess(self):
        code = '''import gc,tempfile
from pathlib import Path
from knowledge_sdk.server.auth import SQLiteReplayStore
with tempfile.TemporaryDirectory() as d:
    s=SQLiteReplayStore(str(Path(d)/'r.sqlite3'))
    for _ in range(5): s.check_and_record('nonce',10)
    del s
    gc.collect()
'''
        p = subprocess.run([sys.executable,'-W','error::ResourceWarning','-c',code],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertNotIn('ResourceWarning',p.stderr)
        self.assertNotIn('Exception ignored',p.stderr)

    def test_health_dynamic_and_no_stale_version(self):
        from knowledge_sdk.storage.sqlite_store import SQLiteStore
        store = SQLiteStore(':memory:'); self.addCleanup(store.close)
        client = LocalKnowledgeClient(store)
        with patch.object(knowledge_sdk,'__version__','1.2.0-test'):
            self.assertEqual(client.health()['version'],'1.2.0-test')
        for path in Path('src').rglob('*.py'):
            self.assertNotIn('1.1.0', path.read_text())

    @unittest.skipUnless(importlib.util.find_spec('fastapi'), 'optional HTTP dependencies unavailable')
    def test_routes_docstring(self):
        from knowledge_sdk.ui import routes
        self.assertIn('Static shell',routes.__doc__)
