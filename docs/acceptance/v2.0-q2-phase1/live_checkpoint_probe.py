"""Real wire evidence for partial checkpoint (audit + signed Webhook only)."""
from __future__ import annotations
from contextlib import closing
from datetime import datetime
import json
import secrets
import socket
import threading
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import uvicorn
from knowledge_sdk import *
from knowledge_sdk.server.app import create_app
from knowledge_sdk.events.outbox import OutboxDispatcher
from knowledge_sdk.impact.webhook import WebhookDispatcher
from tests.q2.test_outbox_webhook import Receiver


def main():
    print(datetime.now().astimezone().isoformat(), 'Asia/Shanghai')
    secret=secrets.token_hex(32);hook_secret=secrets.token_hex(32)
    a=Actor('owner','wire',org_roles=('admin',));u=Actor('reader','wire')
    with closing(LocalKnowledgeClient().store) as store,closing(Receiver()) as receiver:
        local=LocalKnowledgeClient(store)
        kb=local.create_kb(a,'wire','enterprise')
        local.ingest(a,kb.kb_id,'Private fixture content',doc_id='wire-doc')
        local.register_webhook_subscription(a,receiver.url,hook_secret,['doc.ingested'],allow_insecure_local=True)
        app=create_app(local,auth_secret=secret,enable_ui=False)
        sock=socket.socket();sock.bind(('127.0.0.1',0));sock.listen(32)
        server=uvicorn.Server(uvicorn.Config(app,log_level='warning',proxy_headers=False,ws='none'))
        thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]});thread.start()
        try:
            deadline=time.monotonic()+10
            while not server.started:
                if not thread.is_alive() or time.monotonic()>deadline:raise RuntimeError('Server startup failed')
                threading.Event().wait(.01)
            http=HttpKnowledgeClient('http://127.0.0.1:%d'%sock.getsockname()[1],auth_secret=secret)
            http.retrieve(u,'wire-doc')
            events=http.query_audit_events(u)
            assert events and all(isinstance(e,AuditEvent) and e.org_id=='wire' and e.actor_id=='reader' for e in events)
            assert 'Private fixture content' not in json.dumps([e.to_dict() for e in events])
            assert http.verify_audit_chain(a).valid
            assert http.query_audit_events(Actor('other','other',org_roles=('admin',)))==[]
            try:http.verify_audit_chain(u)
            except PermissionDeniedError:pass
            else:raise AssertionError('Non-admin verified ledger')
            # Missing signature fails before invoking the business operation.
            try:
                with urlopen(Request(http.base_url+'/v1/audit/query',data=b'{"params":{}}',headers={'Content-Type':'application/json'})) as response:
                    raise AssertionError('Unsigned request accepted')
            except HTTPError as error:
                with error:assert error.code==401
            started=time.monotonic()
            result=OutboxDispatcher(store,webhook=WebhookDispatcher(store,allow_insecure_local_webhook=True)).drain_outbox()
            assert result.dispatched==1 and len(receiver.requests)==1
            headers,body=receiver.requests[0]
            assert verify_webhook_signature(hook_secret,body,headers['X-KB-Webhook-Id'],headers['X-KB-Event-Id'],headers['X-KB-Webhook-Timestamp'],headers['X-KB-Webhook-Signature'])
            assert time.monotonic()-started<60
            print('PASS: actual ephemeral signed HTTP audit/query + audit/verify, typed client parity, unsigned401, non-admin403, tenant isolation')
            print('PASS: actual ephemeral Webhook POST, all four headers, HMAC-SHA256 verification, <60s delivery, no secrets/source text logged')
            print('NOT_IMPLEMENTED: impact/alerts and impact/ack; usage lineage and ImpactRadar; no Q2-M1 completion claim')
        finally:
            server.should_exit=True;thread.join(timeout=15);sock.close()
            assert not thread.is_alive()
    print('All disposable listeners/connections closed; no paid/model/embedding/Qdrant calls')


if __name__=='__main__':main()
