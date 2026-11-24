from contextlib import closing
from datetime import datetime, timezone, timedelta
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from pathlib import Path
from knowledge_sdk import *
from knowledge_sdk.contracts.events import WebhookSubscription
from knowledge_sdk.events.outbox import OutboxDispatcher
from knowledge_sdk.impact.webhook import (validate_webhook_url, sign_webhook,
    verify_webhook_signature, WebhookDispatcher, deliver_http)

SECRET='test-only-key-not-a-real-credential-12345'


class Receiver:
    def __init__(self,code=204,location=None):
        self.requests=[]
        owner=self
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body=self.rfile.read(int(self.headers['Content-Length']))
                owner.requests.append((dict(self.headers),body))
                self.send_response(code)
                if location:self.send_header('Location',location)
                self.send_header('Content-Length','0');self.end_headers()
            def log_message(self,*args):pass
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever);self.thread.start()
        self.url='http://127.0.0.1:%d/hook'%self.server.server_address[1]
    def close(self):
        self.server.shutdown();self.server.server_close();self.thread.join()


class OutboxWebhookTests(unittest.TestCase):
    def setUp(self):
        self.c=LocalKnowledgeClient();self.addCleanup(self.c.store.close)
        self.a=Actor('owner','org',org_roles=('admin',));self.k=self.c.create_kb(self.a,'k')
        self.v=self.c.ingest(self.a,self.k.kb_id,'old snapshot',doc_id='d')

    def events(self):return [self.c.store._outbox_from_row(r) for r in self.c.store._execute('SELECT * FROM outbox_events ORDER BY created_at')]

    def test_all_authoritative_changes_emit_and_payload_contains_no_body(self):
        self.c.ingest(self.a,self.k.kb_id,'new snapshot',doc_id='d')
        self.c.archive(self.a,'d');self.c.restore(self.a,'d')
        self.c.set_document_acl(self.a,'d',DocumentACL())
        self.c.set_document_rights(self.a,'d',ResourceRights())
        self.c.set_document_rights(self.a,'d',ResourceRights(revoked=True))
        self.assertTrue({'doc.ingested','doc.revised','doc.archived','doc.restored','acl.updated','rights.updated','doc.revoked'}<={e.event_type for e in self.events()})
        self.assertNotIn('snapshot',json.dumps([e.to_dict() for e in self.events()]))

    def test_outbox_failure_rolls_back_document_version_acl_and_anchors(self):
        store=self.c.store
        before={t:store._execute('SELECT * FROM '+t) for t in ('documents','document_versions','document_acls','evidence_anchors','outbox_events')}
        with patch.object(store,'enqueue_outbox',side_effect=RuntimeError('abort')):
            for run in (lambda:self.c.ingest(self.a,self.k.kb_id,'revision',doc_id='d'),
                        lambda:self.c.archive(self.a,'d'),lambda:self.c.restore(self.a,'d'),
                        lambda:self.c.set_document_acl(self.a,'d',DocumentACL(deny_users=['x'])),
                        lambda:self.c.set_document_rights(self.a,'d',ResourceRights(revoked=True))):
                with self.assertRaises(RuntimeError):run()
                for table,rows in before.items():self.assertEqual(store._execute('SELECT * FROM '+table),rows)

    def test_idempotent_enqueue_conflict_and_dispatch_replay(self):
        event=self.events()[0];self.c.store.enqueue_outbox(event)
        self.assertEqual(len(self.events()),1)
        with self.assertRaises(ConflictError):self.c.store.enqueue_outbox(replace(event,org_id='other'))
        dispatcher=OutboxDispatcher(self.c.store)
        self.assertEqual(dispatcher.drain_outbox().dispatched,1)
        self.assertEqual(dispatcher.drain_outbox().claimed,0)

    def test_exponential_retry_and_dead_letter(self):
        class Fail:
            def dispatch(self,event):raise OSError('unavailable')
        dispatcher=OutboxDispatcher(self.c.store,webhook=Fail())
        now=datetime.now(timezone.utc)
        for i in range(5):
            result=dispatcher.drain_outbox(now=now)
            self.assertEqual(result.claimed,1)
            event=self.events()[0];self.assertEqual(event.attempts,i+1)
            self.assertEqual(event.available_at,(now+timedelta(seconds=2**(i+1))).isoformat())
            self.assertEqual(dispatcher.drain_outbox(now=now).claimed,0)
            now+=timedelta(seconds=2**(i+1))
        self.assertEqual(self.events()[0].status,'dead_letter')
        self.assertEqual(dispatcher.drain_outbox(now=now+timedelta(days=1)).claimed,0)

    def test_claim_serialization_and_expired_worker_lease(self):
        now=datetime.now(timezone.utc)
        self.assertEqual(len(self.c.store.claim_outbox_batch(now.isoformat())),1)
        self.assertEqual(self.c.store.claim_outbox_batch(now.isoformat()),[])
        self.assertEqual(len(self.c.store.claim_outbox_batch((now+timedelta(seconds=61)).isoformat())),1)
        self.assertEqual(self.events()[0].attempts,2)

    def test_multi_connection_claim_no_overlap(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'store.db'
            with closing(SQLiteStore(path)) as one,closing(SQLiteStore(path)) as two:
                for i in range(20):one.enqueue_outbox(replace(self.events()[0],event_id=str(i)))
                ids=[];errors=[]
                def claim(store):
                    try:ids.extend(e.event_id for e in store.claim_outbox_batch(datetime.now(timezone.utc).isoformat()))
                    except Exception as exc:errors.append(exc)
                threads=[threading.Thread(target=claim,args=(s,)) for s in (one,two)]
                for t in threads:t.start()
                for t in threads:t.join()
                self.assertEqual(errors,[]);self.assertEqual(len(ids),20);self.assertEqual(len(set(ids)),20)

    def test_real_loopback_signature_and_delivery_idempotence(self):
        receiver=Receiver();self.addCleanup(receiver.close)
        public=self.c.register_webhook_subscription(self.a,receiver.url,SECRET,['doc.ingested'],allow_insecure_local=True)
        self.assertNotIn('secret',public)
        webhook=WebhookDispatcher(self.c.store,allow_insecure_local_webhook=True)
        start=time.monotonic();result=OutboxDispatcher(self.c.store,webhook=webhook).drain_outbox()
        self.assertEqual(result.dispatched,1);self.assertLess(time.monotonic()-start,60)
        headers,body=receiver.requests[0]
        args=(SECRET,body,headers['X-KB-Webhook-Id'],headers['X-KB-Event-Id'],headers['X-KB-Webhook-Timestamp'],headers['X-KB-Webhook-Signature'])
        self.assertTrue(verify_webhook_signature(*args))
        self.assertFalse(verify_webhook_signature(SECRET,body+b'x',*args[2:]))
        self.assertFalse(verify_webhook_signature(*args,now=int(args[4])+301))
        webhook.dispatch(self.events()[0]);self.assertEqual(len(receiver.requests),1)
        self.assertEqual(self.c.store._execute('SELECT status FROM webhook_deliveries'),[('delivered',)])

    def test_redirect_is_not_followed_even_to_loopback(self):
        target=Receiver();self.addCleanup(target.close)
        redirect=Receiver(302,location=target.url);self.addCleanup(redirect.close)
        self.assertEqual(deliver_http(redirect.url,b'{}',{},allow_insecure_local=True),302)
        self.assertEqual(target.requests,[])

    def test_failed_sub_does_not_repeat_successful_delivery(self):
        good=Receiver();self.addCleanup(good.close)
        bad=Receiver(503);self.addCleanup(bad.close)
        for url in (good.url,bad.url):self.c.register_webhook_subscription(self.a,url,SECRET,['doc.ingested'],allow_insecure_local=True)
        worker=OutboxDispatcher(self.c.store,webhook=WebhookDispatcher(self.c.store,allow_insecure_local_webhook=True))
        worker.drain_outbox()
        worker.drain_outbox(now=datetime.now(timezone.utc)+timedelta(seconds=10))
        # A failing subscription cannot starve another; a delivered subscription
        # is not POSTed again when retrying the failed one.
        successful=self.c.store._execute("SELECT COUNT(*) FROM webhook_deliveries WHERE status='delivered'")[0][0]
        self.assertEqual(len(good.requests),1)
        self.assertEqual(successful,1)
        self.assertEqual(len(bad.requests),2)

    def test_ssrf_registration_denies_metadata_private_loopback_and_userinfo(self):
        for url in ('http://example.com','https://169.254.169.254/a','https://10.1.2.3',
                    'https://172.16.0.1','https://192.168.1.1','https://127.0.0.1',
                    'https://[::1]','https://[fc00::1]','https://[::ffff:127.0.0.1]',
                    'https://user:pass@example.com','https://example.com/#fragment'):
            with self.subTest(url=url),self.assertRaises(ValidationError):
                self.c.register_webhook_subscription(self.a,url,SECRET,['doc.ingested'])
        for url in ('http://10.0.0.1','https://169.254.169.254'):
            with self.assertRaises(ValidationError):validate_webhook_url(url,allow_insecure_local=True)
        with self.assertRaises(PermissionDeniedError):
            self.c.register_webhook_subscription(Actor('u','org'),'https://example.com',SECRET,['doc.ingested'])

    def test_dns_mixed_and_rebinding_blocked_at_delivery(self):
        def answer(address):return (socket.AF_INET,socket.SOCK_STREAM,6,'',(address,443))
        with patch('socket.getaddrinfo',return_value=[answer('93.184.216.34'),answer('127.0.0.1')]):
            with self.assertRaises(ValidationError):validate_webhook_url('https://safe.example')
        with patch('socket.getaddrinfo',return_value=[answer('93.184.216.34')]):
            self.c.register_webhook_subscription(self.a,'https://safe.example',SECRET,['doc.ingested'])
        calls=[]
        with patch('socket.getaddrinfo',return_value=[answer('169.254.169.254')]):
            worker=OutboxDispatcher(self.c.store,webhook=WebhookDispatcher(self.c.store,transport=lambda *a,**k:calls.append(a)))
            self.assertEqual(worker.drain_outbox().failed,1)
        self.assertEqual(calls,[])

    def test_signature_binds_all_headers_and_body(self):
        stamp=str(int(time.time()));signature=sign_webhook(SECRET,b'bytes','delivery','event',stamp)
        self.assertTrue(verify_webhook_signature(SECRET,b'bytes','delivery','event',stamp,signature))
        for delivery,event,ts in (('other','event',stamp),('delivery','other',stamp),('delivery','event',str(int(stamp)-1))):
            self.assertFalse(verify_webhook_signature(SECRET,b'bytes',delivery,event,ts,signature))

    def test_insecure_sub_needs_explicit_dispatcher_test_switch(self):
        receiver=Receiver();self.addCleanup(receiver.close)
        self.c.register_webhook_subscription(self.a,receiver.url,SECRET,['doc.ingested'],allow_insecure_local=True)
        self.assertEqual(OutboxDispatcher(self.c.store,webhook=WebhookDispatcher(self.c.store)).drain_outbox().failed,1)
        self.assertEqual(receiver.requests,[])
