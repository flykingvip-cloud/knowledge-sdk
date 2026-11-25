"""Real signed v1 loopback only. No v2 runtime, no persistent fixture services."""
import importlib.util
import json
import secrets
import socket
import threading
import time
import unittest
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone, timedelta
from urllib.request import Request, urlopen
from urllib.error import HTTPError

HAS_HTTP=all(importlib.util.find_spec(name) for name in ('fastapi','uvicorn'))

@contextmanager
def loopback(app):
    import uvicorn
    sock=socket.socket();sock.bind(('127.0.0.1',0))
    assert sock.getsockname()[1] not in (3000,3001,8000,8002,8090,8091)
    server=uvicorn.Server(uvicorn.Config(app,log_level='critical',access_log=False))
    thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
    try:
        deadline=time.monotonic()+15
        while not server.started:
            if not thread.is_alive() or time.monotonic()>deadline:raise RuntimeError('Owned loopback fixture startup failed')
            threading.Event().wait(.01)
        yield 'http://127.0.0.1:'+str(sock.getsockname()[1])
    finally:
        server.should_exit=True;thread.join(15);sock.close()
        if thread.is_alive():raise RuntimeError('Owned loopback fixture did not stop')

def capture_v1():
    from knowledge_sdk import LocalKnowledgeClient,Actor,Purpose
    from knowledge_sdk.contracts.models import encode
    from knowledge_sdk.contracts.identity import IdentityPrincipal
    from knowledge_sdk.server.app import create_app
    from knowledge_sdk.server.auth import signed_headers
    c=LocalKnowledgeClient();secret=secrets.token_hex(32);rows=[]
    try:
        owner=Actor('fixture-owner','fixture-tenant',org_roles=('admin',),policy_generation='1')
        outsider=Actor('fixture-outsider','fixture-tenant',policy_generation='1')
        for a in (owner,outsider):c.store.upsert_principal(IdentityPrincipal(a.org_id,a.user_id))
        c.create_kb(owner,'Fixture private',kb_id='fixture-space')
        c.ingest(owner,'fixture-space','Fixture content',doc_id='fixture-doc')
        ref=c.create_ref(owner,'fixture-doc',excerpt='Fixture content')
        app=create_app(c,auth_secret=secret,enable_ui=False)
        with loopback(app) as base:
            def request(path,params,actor,expected,label):
                body=json.dumps({'params':encode(params)},separators=(',',':')).encode('utf-8')
                headers=signed_headers(actor,secret,'POST',path,body,purpose=Purpose.READ.value)
                headers['Content-Type']='application/json'
                outgoing=Request(base+path,data=body,headers=headers,method='POST')
                try:response=urlopen(outgoing,timeout=15)
                except HTTPError as error:response=error
                with response:
                    status=response.status;raw=response.read().decode('utf-8');cache=response.headers.get('Cache-Control');response_headers=dict(response.headers.items());reason=response.reason
                assert status==expected,(label,status,raw)
                assert cache=='no-store'
                safe_headers={k:('[REDACTED_EPHEMERAL_TEST_SIGNATURE]' if k.lower()=='x-kb-signature' else v) for k,v in outgoing.header_items()}
                rows.append(dict(case=label,evidence_kind='v1_loopback_test_only',wire_protocol='v1_loopback_test_only',runtime_captured=True,
                    request=dict(method='POST',target=path,headers=safe_headers,body_utf8=body.decode()),
                    response=dict(status=status,headers=response_headers,reason=reason,body_utf8=raw)))
            request('/v1/documents/get',{'doc_id':'fixture-doc'},owner,200,'authorized')
            request('/v1/documents/get',{'doc_id':'fixture-doc'},outsider,403,'private_space_denial')
            request('/v1/kbs',{'name':'Fixture duplicate','kb_id':'fixture-space'},owner,409,'existing_identity_conflict_NOT_v2_idempotency')
            request('/v1/references/verify',{'ref':replace(ref,excerpt='TAMPERED')},owner,400,'tampered_excerpt_real_v1_mapping_NOT_v2_422')
        result=dict(evidence_kind='v1_loopback_test_only',wire_protocol='v1_loopback_test_only',runtime_captured=True,
            captured_at_asia_shanghai=datetime.now(timezone(timedelta(hours=8))).isoformat(),engine='sqlite',
            authentication='real HMAC; random ephemeral secret never persisted; signatures redacted',
            capture_format='Sanitized structured actual urllib request and HTTP response; not a byte-for-byte packet capture',
            limitations='Only implemented v1.409 is a KB identity conflict, not future Idempotency-Key.400 is actual TamperedExcerptError, not v2 422.',
            rows=rows,owned_loopback_stopped=True)
        assert secret not in json.dumps(result)
        return result
    finally:c.store.close()

@unittest.skipUnless(HAS_HTTP,'Optional real HTTP dependencies unavailable')
class V1Evidence(unittest.TestCase):
    def test_actual_signed_v1_statuses_and_error_stream_cleanup(self):
        evidence=capture_v1()
        self.assertEqual([row['response']['status'] for row in evidence['rows']],[200,403,409,400])
        self.assertTrue(all(row['request']['target'].startswith('/v1/') for row in evidence['rows']))
        self.assertTrue(evidence['owned_loopback_stopped'])
        self.assertIn('TamperedExcerptError',evidence['rows'][-1]['response']['body_utf8'])
