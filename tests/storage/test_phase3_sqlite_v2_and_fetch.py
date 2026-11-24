import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from contextlib import closing
from dataclasses import replace
from unittest.mock import patch
from knowledge_sdk import *
from knowledge_sdk.storage.sqlite_store import SQLiteStore
from knowledge_sdk.contracts.models import encode
from knowledge_sdk.permissions.engine import DefaultPolicyEngine
from knowledge_sdk.retrieval.base import VectorHit


def legacy_database(path):
    """Construct the real four-column v1 schema, not v2 mislabeled as v1."""
    with closing(sqlite3.connect(str(path))) as db:
        for statement in SQLiteStore._BASE_SCHEMA.split(';'):
            if statement.strip():db.execute(statement)
        for i,space in enumerate(('enterprise_public','department','personal')):
            kb=KnowledgeBase('k'+str(i),'o','space','owner','enterprise',space_type=space,owner_department_id='dep',owner_user_id='owner')
            db.execute('INSERT INTO knowledge_bases VALUES(?,?,?)',(kb.kb_id,'o',json.dumps(encode(kb))))
            for j in range(2):
                d=Document('d%d%d'%(i,j),'o',kb.kb_id,'owner','title','enterprise',archived=bool(j),rights=ResourceRights(revoked=bool(i==1)),lifecycle_state='draft' if i==2 else 'published',valid_from='2020-01-01T00:00:00Z')
                acl=DocumentACL(access_level='department',allowed_department_ids=('dep',))
                db.execute('INSERT INTO documents VALUES(?,?,?,?)',(d.doc_id,'o',kb.kb_id,json.dumps(encode(d))))
                db.execute('INSERT INTO document_acls VALUES(?,?)',(d.doc_id,json.dumps(encode(acl))))
        db.execute('PRAGMA user_version=1');db.commit()


class MigrationTests(unittest.TestCase):
    def test_v1_atomic_backfill_zero_loss_and_idempotence(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'v1.db';legacy_database(path)
            with closing(sqlite3.connect(str(path))) as db:before=db.execute('SELECT doc_id,data FROM documents ORDER BY doc_id').fetchall()
            with closing(SQLiteStore(path)) as store:
                self.assertEqual(store.db.execute('pragma user_version').fetchone()[0],3)
                self.assertEqual(store._execute('SELECT doc_id,data FROM documents ORDER BY doc_id'),before)
                for doc in store.list_documents('o'):
                    row=store._execute('SELECT space_type,governance_tier,access_level,lifecycle_state,archived,revoked,valid_from,valid_to FROM documents WHERE doc_id=?',(doc.doc_id,))[0]
                    kb=store.get_kb(doc.kb_id)
                    self.assertEqual(row,(kb.space_type,'l1_agile','department',doc.lifecycle_state,int(doc.archived),int(doc.rights.revoked),doc.valid_from,None))
                self.assertEqual(len(store._execute("SELECT name FROM sqlite_master WHERE name IN ('evidence_anchors','policy_rules','evidence_issues','idx_docs_pushdown','idx_anchors_lookup','idx_policy_org_scope')")),6)
            with closing(SQLiteStore(path)) as store:self.assertEqual(store._execute('SELECT doc_id,data FROM documents ORDER BY doc_id'),before)
    def test_migration_failure_rolls_back_ddl_rows_version(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'v1.db';legacy_database(path)
            def fail(store):store._sync_document('d00');raise RuntimeError('injected migration failure')
            with patch.object(SQLiteStore,'_backfill',fail),self.assertRaises(RuntimeError):SQLiteStore(path)
            with closing(sqlite3.connect(str(path))) as db:
                self.assertEqual(db.execute('pragma user_version').fetchone()[0],1)
                self.assertEqual(len(db.execute('pragma table_info(documents)').fetchall()),4)
                self.assertEqual(db.execute("SELECT name FROM sqlite_master WHERE name='evidence_anchors'").fetchall(),[])
                self.assertEqual(db.execute('SELECT count(*) FROM documents').fetchone()[0],6)
            with closing(SQLiteStore(path)) as store:self.assertEqual(store.db.execute('pragma user_version').fetchone()[0],3)
    def test_unknown_schema_refused_and_connection_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'future.db'
            with closing(sqlite3.connect(str(path))) as db:db.execute('pragma user_version=4')
            with self.assertRaisesRegex(ConflictError,'^Unsupported database schema version$'):SQLiteStore(path)
            with closing(sqlite3.connect(str(path))) as db:self.assertEqual(db.execute('pragma user_version').fetchone()[0],4)
    def test_write_paths_keep_all_derived_columns_current(self):
        c=LocalKnowledgeClient();self.addCleanup(c.store.close);a=Actor('owner','o');k=c.create_kb(a,'space','enterprise');v=c.ingest(a,k.kb_id,'indexable content')
        c.store.set_acl(v.doc_id,DocumentACL(access_level='personal_only'))
        d=replace(c.store.get_document(v.doc_id),rights=ResourceRights(revoked=True),lifecycle_state='revoked',archived=True,valid_to='2030-01-01T00:00:00Z');c.store.put_document(d)
        c.store.put_kb(replace(k,governance_tier='l2_controlled'))
        self.assertEqual(c.store._execute('SELECT governance_tier,access_level,lifecycle_state,archived,revoked,valid_to FROM documents')[0],('l2_controlled','personal_only','revoked',1,1,d.valid_to))
    def test_rule_storage_tenant_scoped_and_not_implicitly_loaded(self):
        with closing(SQLiteStore()) as store:
            rule=PolicyRule('rule','o',DecisionEffect.DENY);store.put_policy_rule(rule)
            self.assertEqual(store.list_policy_rules('other'),[])
            with self.assertRaises(ConflictError):store.put_policy_rule(replace(rule,org_id='other'))
            store.delete_policy_rule('other','rule');self.assertEqual(store.list_policy_rules('o'),[rule])
            store.delete_policy_rule('o','rule');self.assertEqual(store.list_policy_rules('o'),[])
    def test_anchor_fk_and_tenant_identity(self):
        c=LocalKnowledgeClient();self.addCleanup(c.store.close);a=Actor('u','o');k=c.create_kb(a,'k');v=c.ingest(a,k.kb_id,'content');anchor=c.list_anchors(a,v.doc_id)[0]
        with self.assertRaises(ConflictError):c.store.put_anchors([replace(anchor,org_id='other')])
        with self.assertRaises(ConflictError):c.store.put_anchors([replace(anchor,version=99)])
        self.assertEqual(c.store.get_anchors('other',v.doc_id,1),[])


class CountEngine:
    def __init__(self):self.calls=0;self.delegate=DefaultPolicyEngine()
    def evaluate(self,*args,**kwargs):self.calls+=1;return self.delegate.evaluate(*args,**kwargs)


class FetchTests(unittest.TestCase):
    def setUp(self):
        self.engine=CountEngine();self.c=LocalKnowledgeClient(policy_engine=self.engine);self.addCleanup(self.c.store.close)
        self.a=Actor('admin','o');self.reader=Actor('reader','o');self.k=self.c.create_kb(self.a,'k','enterprise',kb_id='kb')
    def doc(self,index,*,denied=False):
        return self.c.ingest(self.a,'kb','dense signal',doc_id='d%04d'%index,acl=DocumentACL(deny_users=('reader',)) if denied else None)
    def test_b07_120_first105_excluded_then15_visible(self):
        for i in range(120):
            v=self.doc(i,denied=i<35)
            if 35<=i<70:self.c.archive(self.a,v.doc_id)
            if 70<=i<105:self.c.set_document_rights(self.a,v.doc_id,ResourceRights(revoked=True))
        self.engine.calls=0;r=self.c.search(self.reader,'dense',limit=10)
        self.assertEqual(len(r.hits),10);self.assertFalse(r.candidate_budget_exhausted)
        self.assertTrue(all(int(h.doc_id[1:])>=105 for h in r.hits));self.assertLessEqual(self.engine.calls,120)
    def test_more_than500_denied_bounded_and_exact500_exhaustion(self):
        for i in range(501):self.doc(i,denied=i<500)
        self.engine.calls=0;r=self.c.search(self.reader,'dense',limit=10)
        self.assertEqual(r.hits,[]);self.assertTrue(r.candidate_budget_exhausted);self.assertEqual(self.engine.calls,500)
        self.c.store._execute("DELETE FROM chunks_fts WHERE doc_id='d0500'");self.engine.calls=0
        exact=self.c.search(self.reader,'dense',limit=10);self.assertEqual(exact.hits,[]);self.assertFalse(exact.candidate_budget_exhausted);self.assertEqual(self.engine.calls,500)
    def test_pushdown_filters_bound_values_and_preserve_drafts(self):
        v=self.doc(1);self.c.store.put_document(replace(self.c.store.get_document(v.doc_id),lifecycle_state='draft'))
        self.assertEqual(len(self.c.store.keyword_search_pushdown('dense','o',kb_ids=['kb'])),1)
        self.assertEqual(self.c.store.keyword_search_pushdown('dense','o',kb_ids=["kb') OR 1=1 --"]),[])
        self.assertEqual(self.c.store.keyword_search_pushdown('dense','o',doc_ids=[]),[])
        self.assertEqual(self.c.store.keyword_search_pushdown('dense','other'),[])
        self.assertEqual(len(self.c.store.keyword_search('dense','o',100)),1)
    def test_custom_store_legacy_keyword_fallback(self):
        self.doc(1)
        class LegacyStore:
            def __getattr__(inner,name):
                if name=='keyword_search_pushdown':raise AttributeError(name)
                return getattr(self.c.store,name)
        from knowledge_sdk.retrieval.hybrid import search
        self.assertEqual(len(search(LegacyStore(),self.reader,'dense').hits),1)
    def test_vector_payload_current_authoritative_cross_tenant_stale_revoked(self):
        v=self.doc(1);chunk=self.c.store.get_chunks(v.doc_id,1)[0];other=Actor('evil','other');k=self.c.create_kb(other,'other');ov=self.c.ingest(other,k.kb_id,'dense forged')
        oc=self.c.store.get_chunks(ov.doc_id,1)[0]
        class Embed:
            def embed(self,texts):return [[1.0] for _ in texts]
        class Index:
            def search(inner,vector,limit):return [VectorHit(v.doc_id,1,chunk.chunk_id,1),VectorHit(v.doc_id,99,chunk.chunk_id,.9),VectorHit(ov.doc_id,1,oc.chunk_id,.8),VectorHit('missing',1,'forged',.7)][:limit]
        self.c.vector_index=Index();self.c.embedder=Embed();self.c.set_document_rights(self.a,v.doc_id,ResourceRights(revoked=True))
        self.assertEqual(self.c.search(self.reader,'dense',mode='vector').hits,[])
    def test_hybrid_union_budget_deduplicates_evaluation(self):
        self.doc(1,denied=True);d=self.c.store.get_document('d0001');ch=self.c.store.get_chunks(d.doc_id,1)[0]
        class Embed:
            def embed(self,texts):return [[1]]
        class Index:
            def search(self,*args):return [VectorHit(d.doc_id,1,ch.chunk_id,1)]
        self.c.vector_index=Index();self.c.embedder=Embed();self.engine.calls=0
        self.assertEqual(self.c.search(self.reader,'dense',mode='hybrid').hits,[]);self.assertEqual(self.engine.calls,1)
