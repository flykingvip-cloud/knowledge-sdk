"""Real prior-version layouts, byte-for-byte rows and DDL rollback."""
from contextlib import closing
from pathlib import Path
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from knowledge_sdk import (Actor, LocalKnowledgeClient, SQLiteStore, KnowledgeBase,
                           Document, DocumentVersion, DocumentACL, build_uri)
from knowledge_sdk.contracts.models import encode
from tests.storage.test_phase3_sqlite_v2_and_fetch import legacy_database

TABLES = ('outbox_events', 'audit_events', 'usage_events', 'impact_alerts',
          'webhook_subscriptions', 'webhook_deliveries', 'review_decisions',
          'evidence_packs', 'connector_sync_state')


def v2_database(path):
    """Create actual Q1 DDL independently, without starting a v3 store."""
    with closing(sqlite3.connect(str(path))) as db:
        for statement in SQLiteStore._BASE_SCHEMA.split(';'):
            if statement.strip(): db.execute(statement)
        for name, kind in SQLiteStore._DERIVED:
            db.execute('ALTER TABLE documents ADD COLUMN ' + name + ' ' + kind)
        for statement in SQLiteStore._V2_SCHEMA.split(';'):
            if statement.strip(): db.execute(statement)
        db.execute('PRAGMA user_version=2')
        db.commit()
    # Populate every old table using Q1's exact implementation (v3 disabled).
    with patch.object(SQLiteStore, '_V3_SCHEMA', ''), patch.object(LocalKnowledgeClient, '_audit_operation', lambda *a, **k: None), patch.object(LocalKnowledgeClient, '_emit_event', lambda *a, **k: None):
        with closing(SQLiteStore(path)) as store:
            client = LocalKnowledgeClient(store=store)
            actor = Actor('owner', 'org')
            kb = client.create_kb(actor, 'space')
            v = client.ingest(actor, kb.kb_id, 'Original immutable evidence.',
                              doc_id='doc', acl=DocumentACL(allow_users=['reader']))
            client.report_evidence_issue(actor, build_uri('org', 'doc', 1), 'outdated', 'Please review')
            store.db.execute('PRAGMA user_version=2')


def snapshot(db):
    return {table: db.execute('SELECT * FROM ' + table).fetchall() for table in
            ('knowledge_bases','kb_members','documents','document_versions',
             'document_acls','chunks','evidence_anchors','evidence_issues','policy_rules')}


class SchemaV3Tests(unittest.TestCase):
    def test_real_v2_to_v3_byte_preservation_and_reopen(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'old.db'
            v2_database(path)
            with closing(sqlite3.connect(str(path))) as db:
                self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 2)
                before = snapshot(db)
                self.assertTrue(before['evidence_anchors'])
                self.assertTrue(before['evidence_issues'])
            for _ in range(2):
                with closing(SQLiteStore(path)) as store:
                    self.assertEqual(store.db.execute('PRAGMA user_version').fetchone()[0], 5)
                    self.assertEqual(snapshot(store.db), before)
                    for table in TABLES:
                        self.assertEqual(store.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0], 0)

    def test_failed_v3_ddl_rolls_back_entire_v3_and_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'old.db'; v2_database(path)
            with closing(sqlite3.connect(str(path))) as db: before = snapshot(db)
            with patch.object(SQLiteStore, '_V3_SCHEMA', SQLiteStore._V3_SCHEMA + ';INVALID SQL'):
                with self.assertRaises(sqlite3.OperationalError): SQLiteStore(path)
            with closing(sqlite3.connect(str(path))) as db:
                self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 2)
                self.assertEqual(snapshot(db), before)
                for table in TABLES:
                    self.assertFalse(db.execute('SELECT name FROM sqlite_master WHERE name=?', (table,)).fetchall())

    def test_real_v0_v1_upgrade(self):
        with tempfile.TemporaryDirectory() as tmp:
            for version in (0, 1):
                path = Path(tmp) / ('old%d.db' % version); legacy_database(path)
                with closing(sqlite3.connect(str(path))) as db:
                    db.execute('PRAGMA user_version=%d' % version)
                    before = db.execute('SELECT doc_id,data FROM documents').fetchall()
                with closing(SQLiteStore(path)) as store:
                    self.assertEqual(store.db.execute('PRAGMA user_version').fetchone()[0], 5)
                    self.assertEqual(store.db.execute('SELECT doc_id,data FROM documents').fetchall(), before)
