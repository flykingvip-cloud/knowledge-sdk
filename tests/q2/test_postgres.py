"""Live non-superuser tests and dependency-free SQL/packaging guardrails."""
import ast
import concurrent.futures
from contextlib import contextmanager
from datetime import datetime,timezone,timedelta
from dataclasses import replace
import importlib.util
import json
import os
from pathlib import Path
import secrets
import threading
import time
import unittest
from unittest.mock import patch
from knowledge_sdk import Actor,LocalKnowledgeClient,DocumentACL,ResourceRights,ValidationError,ConflictError
from knowledge_sdk.contracts.models import encode
from knowledge_sdk.storage.postgres_store import PostgresStore
from knowledge_sdk.storage.sqlite_store import SQLiteStore
from knowledge_sdk.storage.pg_support import redact_dsn
from knowledge_sdk.storage.migrations import DDL,TENANT_TABLES,status,apply
from knowledge_sdk.audit.ledger import append,verify_audit_chain
from knowledge_sdk.contracts.events import OutboxEvent,WebhookSubscription
from knowledge_sdk.events.outbox import OutboxDispatcher
from knowledge_sdk.impact.radar import ImpactRadar
from knowledge_sdk.impact.webhook import WebhookDispatcher,verify_webhook_signature
from tests.pg_helpers import PgSandbox


class OfflinePostgresGuards(unittest.TestCase):
    def test_lazy_optional_import(self):
        import sys
        with patch.dict(sys.modules,{'psycopg':None}):
            with self.assertRaisesRegex(ValidationError,r'knowledge-sdk\[postgres\]'):PostgresStore('not-a-connection')
        self.assertEqual(ast.literal_eval("[]"),[])

    def test_ddl_and_metadata_surface(self):
        for table in TENANT_TABLES:self.assertIn('CREATE TABLE IF NOT EXISTS '+table,DDL)
        for name in ('review_decisions','evidence_packs','connector_sync_state','search_vector TSVECTOR','USING GIN'):self.assertIn(name,DDL)
        methods={n for n in dir(SQLiteStore) if not n.startswith('_')}
        self.assertFalse(methods-set(dir(PostgresStore)))

    def test_password_redaction(self):
        for dsn in ('postgresql://alice:danger@localhost/db','host=local password=danger user=u',"password='d anger' host=x",'password="danger"'):
            cleaned=redact_dsn(dsn)
            self.assertNotIn('danger',cleaned);self.assertNotIn('d anger',cleaned);self.assertIn('***',cleaned)

    def test_bound_rls_and_skip_locked_sql_without_driver(self):
        # Construction-only recorder; live acceptance below never uses this.
        from types import SimpleNamespace
        from contextlib import nullcontext
        statements=[]
        class Recorder(PostgresStore):
            def __init__(self):
                self.lock=threading.RLock();self._tenant=None;self.org_id=None
                self.db=SimpleNamespace(transaction=nullcontext,info=SimpleNamespace(transaction_status=0))
                self._pg=SimpleNamespace(pq=SimpleNamespace(TransactionStatus=SimpleNamespace(INERROR=3)),IntegrityError=type('IntegrityError',(Exception,),{}),Error=type('PGError',(Exception,),{}))
            def _execute(self,sql,args=()):
                if sql.count('%s')!=len(args):raise AssertionError('placeholder mismatch')
                statements.append((sql,args));return []
        s=Recorder()
        self.assertEqual(s.claim_outbox_batch('2026-11-25T00:00:00+00:00',org_id="tenant';DROP TABLE documents;--"),[])
        self.assertTrue(any('FOR UPDATE SKIP LOCKED' in sql for sql,args in statements))
        self.assertTrue(any('set_config' in sql and args[0].startswith('tenant') for sql,args in statements))
        self.assertFalse(any('DROP TABLE' in sql for sql,args in statements))

    def test_connection_exception_never_keeps_cause(self):
        class PG:
            @staticmethod
            def connect(*a,**k):raise ValueError('password=danger')
        from knowledge_sdk.storage import pg_support
        with patch.object(pg_support,'driver',return_value=PG):
            value='password='+'danger'
            try:pg_support.connect(value)
            except ValidationError as e:
                import traceback
                self.assertNotIn('danger',''.join(traceback.format_exception(type(e),e,e.__traceback__)))


@unittest.skipUnless(os.environ.get('KNOWLEDGE_SDK_TEST_PG_DSN'),'Real PostgreSQL DSN not configured')
class LivePostgres(unittest.TestCase):
    def setUp(self):
        self.box=PgSandbox();self.s=PostgresStore(self.box.dsn);self.a=Actor('owner','org',org_roles=('admin',));self.c=LocalKnowledgeClient(self.s,allow_insecure_local_webhook=True)
    def tearDown(self):
        self.s.close();self.box.close()

    def test_non_superuser_force_rls_and_context_reset(self):
        self.c.create_kb(self.a,'one',visibility='enterprise',kb_id='one')
        self.c.create_kb(Actor('b','foreign'),'two',visibility='enterprise',kb_id='two')
        role=self.s._execute('SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user')[0]
        self.assertEqual(role,(False,False))
        rows=self.s._execute('SELECT relname,relrowsecurity,relforcerowsecurity FROM pg_class WHERE relnamespace=current_schema()::regnamespace AND relname=ANY(%s)',(list(TENANT_TABLES),))
        self.assertEqual(len(rows),len(TENANT_TABLES));self.assertTrue(all(r[1] and r[2] for r in rows))
        self.assertEqual(self.s._execute('SELECT data FROM knowledge_bases'),[])
        with self.s.tenant_scope('org'):
            self.assertEqual([r[0] for r in self.s._execute('SELECT kb_id FROM knowledge_bases')],['one'])
            self.assertEqual(self.s._execute('SELECT data FROM knowledge_bases WHERE org_id=%s',('foreign',)),[])
            with self.assertRaises(ValidationError):
                with self.s.transaction():self.s._execute('INSERT INTO knowledge_bases VALUES(%s,%s,%s)',('evil','foreign','{}'))
            self.assertEqual(len(self.s.list_kbs('org')),1)
            with self.assertRaises(ConflictError):self.s.list_kbs('foreign')
        self.assertEqual(self.s._execute('SELECT data FROM knowledge_bases'),[])
        print('REAL RLS: NOSUPERUSER NOBYPASSRLS; FORCE RLS all tenant tables; raw cross-tenant read/write blocked')

    def test_transactions_savepoints_migration_and_roundtrip(self):
        k=self.c.create_kb(self.a,'original',visibility='enterprise',kb_id='kb')
        with self.s.transaction():
            self.s.put_kb(replace(k,name='outer'))
            with self.assertRaises(RuntimeError):
                with self.s.transaction():
                    self.s.put_kb(replace(k,name='inner'));raise RuntimeError('rollback savepoint')
            self.assertEqual(self.s.get_kb('kb').name,'outer')
        before=encode(self.s.get_kb('kb'))
        apply(self.s.db);apply(self.s.db)
        self.assertEqual(encode(self.s.get_kb('kb')),before);self.assertEqual(status(self.s.db)['version'],3)
        with self.assertRaises(RuntimeError):
            with self.s.transaction():
                self.c.ingest(self.a,'kb','phantom',doc_id='ghost');raise RuntimeError('rollback outer')
        self.assertFalse(self.s.list_documents('org'))
        self.assertFalse(self.s.claim_outbox_batch(datetime.now(timezone.utc).isoformat(),org_id='org'))

    def test_concurrent_audit_no_holes_after_rollback(self):
        self.c.create_kb(self.a,'kb',visibility='enterprise',kb_id='kb')
        barrier=threading.Barrier(4)
        def worker(i):
            s=PostgresStore(self.box.dsn,migrate=False)
            try:
                barrier.wait(timeout=10)
                for j in range(40):
                    if j==10:
                        try:
                            with s.transaction():append(s,self.a,'rolled-back');raise RuntimeError()
                        except RuntimeError:pass
                    append(s,self.a,'worker-'+str(i))
            finally:s.close()
        with concurrent.futures.ThreadPoolExecutor(4) as pool:list(pool.map(worker,range(4)))
        rows=list(self.s.iter_audit_chain('org'));self.assertEqual([r[2] for r in rows],list(range(1,len(rows)+1)))
        self.assertEqual(len(rows),161);self.assertTrue(verify_audit_chain(self.s,'org').valid)
        print('REAL audit concurrency: 4 connections, 160 worker commits + 1 setup event, 4 rolled-back appends; no conflicts, gaps or forks')

    def test_nonce_concurrency_shared_ttl(self):
        from knowledge_sdk.server.replay_pg import PostgresReplayStore
        stores=[PostgresReplayStore(self.box.dsn,migrate=False) for _ in range(4)]
        try:
            barrier=threading.Barrier(4)
            def use(i):
                barrier.wait(timeout=10);return stores[i].check_and_record('org','same-nonce',110.,now=100.)
            with concurrent.futures.ThreadPoolExecutor(4) as pool:results=list(pool.map(use,range(4)))
            self.assertEqual(sum(results),1)
            self.assertTrue(stores[1].check_and_record('foreign','same-nonce',110.,now=100.))
            self.assertFalse(stores[2].check_and_record('org','same-nonce',120.,now=105.))
            self.assertTrue(stores[3].check_and_record('org','same-nonce',130.,now=111.))
            self.assertFalse(stores[0].check_and_record('org','expired',99.,now=100.))
            print('REAL nonce concurrency: 4 independent connections exactly 1 winner; cross-tenant namespace and TTL expiry passed')
        finally:
            for s in stores:s.close()

    def test_pgvector_stale_payload_rechecks_redaction_rights_and_tenant(self):
        from knowledge_sdk.retrieval.adapters.pgvector_index import PgVectorIndex
        from knowledge_sdk.retrieval.adapters.hash_embedder import HashEmbedder
        from knowledge_sdk import RegexRedactionHook
        index=PgVectorIndex(store=self.s);self.c.vector_index=index;self.c.embedder=HashEmbedder()
        self.c.create_kb(self.a,'k',visibility='enterprise',kb_id='kb')
        self.c.ingest(self.a,'kb','alpha SECRET',doc_id='doc')
        user=Actor('reader','org')
        self.assertTrue(self.c.search(user,'alpha',mode='vector').hits)
        self.c.set_document_rights(self.a,'doc',ResourceRights(redaction_profile='missing'))
        self.assertFalse(self.c.search(user,'alpha',mode='vector').hits)
        self.c.redaction_registry.register('missing',RegexRedactionHook([('SECRET','[MASK]')]))
        hits=self.c.search(user,'alpha',mode='vector').hits
        self.assertTrue(hits);self.assertNotIn('SECRET',json.dumps(encode(hits)))
        self.c.set_document_rights(self.a,'doc',ResourceRights(revoked=True))
        with self.s.tenant_scope('org'):
            self.assertGreater(self.s._execute('SELECT COUNT(*) FROM chunk_embeddings WHERE org_id=%s',('org',))[0][0],0)
        self.assertFalse(self.c.search(user,'alpha',mode='vector').hits)
        self.assertFalse(self.c.search(Actor('reader','foreign'),'alpha',mode='vector').hits)
        cols=self.s._execute("SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='chunk_embeddings'")
        self.assertFalse({'text','title','data','payload','clearance'} & {r[0] for r in cols})
        print('REAL pgvector: exact cosine candidates; stale revocation, live redactor fail-closed and tenant checks passed')

    def test_fence_expired_claim_and_skip_locked(self):
        now=datetime.now(timezone.utc);event=OutboxEvent('e','org','document','doc','doc.ingested',{},available_at=now.isoformat(),created_at=now.isoformat())
        self.s.enqueue_outbox(event)
        first=self.s.claim_outbox_batch(now.isoformat(),org_id='org')[0]
        other=PostgresStore(self.box.dsn,migrate=False)
        try:
            with self.s.outbox_processing_scope(first) as valid:
                self.assertTrue(valid)
                with concurrent.futures.ThreadPoolExecutor(1) as pool:
                    self.assertEqual(pool.submit(other.claim_outbox_batch,(now+timedelta(seconds=61)).isoformat(),org_id='org').result(timeout=3),[])
            second=other.claim_outbox_batch((now+timedelta(seconds=61)).isoformat(),org_id='org')[0]
            with self.s.outbox_processing_scope(first) as valid:self.assertFalse(valid)
            with other.outbox_processing_scope(second) as valid:self.assertTrue(valid)
        finally:other.close()
        print('REAL SKIP LOCKED + attempt fence: locked expired row skipped; reclaimed attempt rejects stale worker')

    def test_four_worker_real_loopback_webhook_healthy_run(self):
        from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
        received=[];guard=threading.Lock();key=secrets.token_hex(32)
        class Handler(BaseHTTPRequestHandler):
            def do_POST(h):
                body=h.rfile.read(int(h.headers['Content-Length']))
                valid=verify_webhook_signature(key,body,h.headers['X-KB-Webhook-Id'],h.headers['X-KB-Event-Id'],h.headers['X-KB-Webhook-Timestamp'],h.headers['X-KB-Webhook-Signature'])
                with guard:received.append((h.headers['X-KB-Webhook-Id'],h.headers['X-KB-Event-Id'],valid))
                h.send_response(204);h.end_headers()
            def log_message(*a):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            self.c.create_kb(self.a,'k',visibility='enterprise',kb_id='kb')
            for i in range(32):
                doc='doc-'+str(i);self.c.ingest(self.a,'kb','alpha evidence',doc_id=doc)
                self.c.consume(self.a,self.c.reference(self.a,doc,excerpt='alpha'))
                self.c.ingest(self.a,'kb','alpha revised',doc_id=doc)
            url='http://127.0.0.1:'+str(server.server_port)+'/hook'
            for i in range(2):self.s.put_webhook_subscription(WebhookSubscription('sub-'+str(i),'org',url,key,('doc.revised',),allow_insecure_local=True))
            with self.s.tenant_scope('org'):
                expected_events=self.s._execute('SELECT COUNT(*) FROM outbox_events WHERE org_id=%s',('org',))[0][0]
            barrier=threading.Barrier(4)
            def worker(i):
                s=PostgresStore(self.box.dsn,migrate=False);client=LocalKnowledgeClient(s)
                dispatcher=OutboxDispatcher(s,radar=ImpactRadar(client),webhook=WebhookDispatcher(s,allow_insecure_local_webhook=True))
                total=0
                try:
                    barrier.wait(timeout=10)
                    for _ in range(100):
                        summary=dispatcher.drain_outbox(limit=3,org_id='org');total+=summary.dispatched
                        if summary.claimed==0:break
                    return total
                finally:s.close()
            with concurrent.futures.ThreadPoolExecutor(4) as pool:counts=list(pool.map(worker,range(4)))
            self.assertTrue(all(n>0 for n in counts));self.assertEqual(sum(counts),expected_events)
            self.assertEqual(len(received),64);self.assertEqual(len({r[0] for r in received}),64);self.assertTrue(all(r[2] for r in received))
            with self.s.tenant_scope('org'):
                self.assertEqual(self.s._execute('SELECT status,COUNT(*) FROM outbox_events WHERE org_id=%s GROUP BY status',('org',)),[('dispatched',expected_events)])
                self.assertEqual(self.s._execute('SELECT COUNT(*) FROM impact_alerts WHERE org_id=%s',('org',))[0][0],32)
            self.assertTrue(verify_audit_chain(self.s,'org').valid)
            print('REAL healthy-run loopback stress: 4 workers counts='+str(counts)+'; '+str(expected_events)+' events, 64 signed subscription POSTs, 64 unique delivery IDs, 32 impact alerts, no deadlocks. NOT universal exactly-once.')
        finally:server.shutdown();server.server_close();thread.join()
