import os
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
from knowledge_sdk import Actor, LocalKnowledgeClient, DocumentACL, ResourceRights, PermissionDeniedError
from knowledge_sdk.storage.sqlite_store import SQLiteStore
from tests.foundation.test_ingestion import INPUTS


class EngineCases:
    engine='sqlite'
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='wave18-');self.addCleanup(self.tmp.cleanup)
        if self.engine=='postgres':
            from tests.pg_helpers import PgSandbox
            self.pg=PgSandbox();self.addCleanup(self.pg.close)
        self.c=self.client();self.addCleanup(self.c.store.close)
        self.a=Actor('owner','one',org_roles=('admin',))
    def client(self):
        if self.engine=='postgres':
            from knowledge_sdk.server.postgres import postgres_client
            return postgres_client(self.pg.dsn,pgvector_dims=32)
        return LocalKnowledgeClient(SQLiteStore(Path(self.tmp.name)/'db.sqlite'))
    def test_independent_connection_concurrent_tenant_crud_and_reindex(self):
        for tenant in ('one','two','three'):
            self.c.create_kb(Actor('owner',tenant,org_roles=('admin',)),tenant,'private',kb_id=tenant)
        barrier=threading.Barrier(3)
        def worker(tenant):
            c=self.client();a=Actor('owner',tenant,org_roles=('admin',))
            try:
                barrier.wait(timeout=10)
                for turn in range(3):
                    d=tenant+'-'+str(turn)
                    c.ingest(a,tenant,'unique'+tenant+' first evidence',doc_id=d)
                    c.ingest(a,tenant,'unique'+tenant+' revised evidence',doc_id=d) # existing update_document equivalent
                    c.rollback_document(a,d,1)
                    c.reindex(a,tenant)
                    self.assertEqual({h.doc_id for h in c.search(a,'unique'+tenant).hits},{tenant+'-'+str(n) for n in range(turn+1)})
                    self.assertFalse(c.search(a,'unique'+('two' if tenant=='one' else 'one')).hits)
                    c.archive(a,d);self.assertNotIn(d,{h.doc_id for h in c.search(a,'unique'+tenant).hits});c.restore(a,d)
                return tenant
            finally:c.store.close()
        with ThreadPoolExecutor(3) as pool:self.assertEqual(set(pool.map(worker,('one','two','three'))),{'one','two','three'})
        if self.engine=='postgres':
            with self.c.store.transaction():
                self.assertEqual(self.c.store._execute('SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user'),[(False,False)])
                self.assertEqual(self.c.store._execute("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid='documents'::regclass"),[(True,True)])
                self.c.store._execute("SELECT set_config('app.current_org_id','one',true)")
                self.assertEqual(self.c.store._execute('SELECT DISTINCT org_id FROM documents'),[('one',)])
        else:self.assertEqual(self.c.store._execute('PRAGMA journal_mode'),[('wal',)])
    def test_full_lifecycle_security_metadata_and_audit_chain(self):
        c=self.c;a=self.a;r=Actor('reader','one')
        c.create_kb(a,'k','private',kb_id='k');c.grant_kb_member(a,'k','reader','editor')
        c.ingest(a,'k','alpha evidence old',filename='old.txt',doc_id='d',visibility='team',rights=ResourceRights(allow_export=True))
        self.assertTrue(c.search(r,'alpha').hits);ref=c.reference(r,'d');self.assertIn(c.verify_ref(r,ref).status,('consumed','partial'))
        c.ingest(a,'k','alpha revised',filename='new.txt',doc_id='d')
        acl=DocumentACL(deny_users=['blocked']);c.set_document_acl(a,'d',acl)
        rights=c.store.get_document('d').rights;v=c.rollback_document(a,'d',1)
        self.assertEqual(v.version,3);self.assertEqual(v.text,'alpha evidence old');self.assertEqual(c.store.get_acl('d'),acl);self.assertEqual(c.store.get_document('d').rights,rights)
        event=c.store.list_audit_events('one',action='rollback_document',limit=10)[-1]
        self.assertEqual(event.details['rollback_scope'],'content_and_filename_only');self.assertTrue(event.details['security_metadata_preserved'])
        c.archive(a,'d');self.assertFalse(c.search(r,'alpha').hits)
        with self.assertRaises(PermissionDeniedError):c.get_document(r,'d')
        c.restore(a,'d');self.assertTrue(c.search(r,'alpha').hits)
        c.report_evidence_issue(r,c.reference(r,'d').source_uri,'outdated','fixture only')
        pack=c.create_evidence_pack(a,'fixture',[{'doc_id':'d','version':3}]);export=c.export_evidence_pack(a,pack.pack_id)
        self.assertTrue(export.content);self.assertTrue(c.verify_audit_chain(a).valid)


class SQLiteEngine(EngineCases,unittest.TestCase):pass
@unittest.skipUnless(os.environ.get('KNOWLEDGE_SDK_TEST_PG_DSN'),'Disposable PG unavailable')
class PostgresEngine(EngineCases,unittest.TestCase):engine='postgres'


@unittest.skipUnless(os.environ.get('KNOWLEDGE_SDK_TEST_PG_DSN'),'Disposable PG unavailable')
class CrossEngineDeterminism(unittest.TestCase):
    def test_exact_chunk_and_anchor_fields(self):
        from tests.pg_helpers import PgSandbox
        from knowledge_sdk.server.postgres import postgres_client
        pg=PgSandbox();self.addCleanup(pg.close)
        clients=[LocalKnowledgeClient(),postgres_client(pg.dsn,pgvector_dims=32)]
        for c in clients:self.addCleanup(c.store.close)
        a=Actor('owner','one',org_roles=('admin',));out=[]
        for c in clients:
            c.create_kb(a,'k',kb_id='k');rows=[]
            for n,(filename,text) in enumerate(INPUTS):
                doc='fixed-'+str(n);version=c.ingest(a,'k',text,filename=filename,doc_id=doc)
                chunks=c.store.get_chunks(doc,1);anchors=c.list_anchors(a,doc)
                # Runtime timestamps are not coordinates; compare every deterministic field.
                anchor_rows=[]
                for anchor in anchors:
                    d=asdict(anchor)
                    for key in ('created_at','updated_at'):d.pop(key,None)
                    anchor_rows.append(d)
                rows.append(dict(raw_hash=version.raw_hash,semantic_hash=version.semantic_hash,
                                 chunks=[asdict(x) for x in chunks],anchors=anchor_rows))
            out.append(rows)
        self.assertEqual(out[0],out[1])
