from __future__ import annotations
import base64
import importlib.util
import inspect
import json
import socket
import threading
import time
import unittest
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from knowledge_sdk import *
from knowledge_sdk.client.http_client import OPERATIONS
from knowledge_sdk.contracts.models import encode
from knowledge_sdk.server.auth import signed_headers
AVAILABLE=all(importlib.util.find_spec(m) is not None for m in ("fastapi","uvicorn","httpx"))
SECRET="unit-test-only-secret-32-characters-minimum"

@unittest.skipUnless(AVAILABLE,"Optional HTTP extra not installed")
class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import uvicorn
        from knowledge_sdk.server.app import create_app
        cls.local=LocalKnowledgeClient(); cls.app=create_app(cls.local,auth_secret=SECRET)
        sock=socket.socket(); sock.bind(("127.0.0.1",0)); sock.listen(128)
        cls.url="http://127.0.0.1:"+str(sock.getsockname()[1])
        cls.server=uvicorn.Server(uvicorn.Config(cls.app,log_level="error",lifespan="off"))
        cls.thread=threading.Thread(target=cls.server.run,kwargs={"sockets":[sock]},daemon=True); cls.thread.start()
        deadline=time.monotonic()+10
        while not cls.server.started:
            if not cls.thread.is_alive() or time.monotonic()>deadline: raise RuntimeError("HTTP test server failed to start")
            threading.Event().wait(.01)
        cls.remote=HttpKnowledgeClient(cls.url,SECRET); cls.actor=Actor("owner","org")
    @classmethod
    def tearDownClass(cls):
        cls.server.should_exit=True; cls.thread.join(timeout=10)
        cls.local.store.close()
    def create(self):
        kb=self.remote.create_kb(self.actor,"Remote KB","team")
        v=self.remote.ingest(self.actor,kb.kb_id,"HTTP knowledge 知识库 document")
        return kb,v
    def request(self,path,body,headers=None,method="POST"):
        req=Request(self.url+path,data=body if method!="GET" else None,headers=headers or {},method=method)
        return urlopen(req,timeout=5)
    def status(self,path,body,headers=None,method="POST"):
        try:
            with self.request(path,body,headers,method) as r: return r.status
        except HTTPError as e: return e.code
    def test_health(self): self.assertEqual(self.remote.health()["status"],"ok")
    def test_missing_signature_401(self):
        self.assertEqual(self.status("/v1/search",b'{"params":{"query":"x"}}'),401)
    def test_tampered_signature_401(self):
        path="/v1/search"; body=b'{"params":{"query":"x"}}'
        headers=signed_headers(self.actor,SECRET,"POST",path,body); headers["X-KB-Signature"]="0"*64
        self.assertEqual(self.status(path,body,headers),401)
    def test_tampered_body_401(self):
        path="/v1/search"; body=b'{"params":{"query":"x"}}'
        headers=signed_headers(self.actor,SECRET,"POST",path,body)
        self.assertEqual(self.status(path,body+b" ",headers),401)
    def test_stale_signature_401(self):
        path="/v1/search"; body=b'{"params":{"query":"x"}}'
        headers=signed_headers(self.actor,SECRET,"POST",path,body,timestamp=int(time.time())-1000)
        self.assertEqual(self.status(path,body,headers),401)
    def test_replay_401(self):
        path="/v1/search"; body=b'{"params":{"query":"x"}}'
        headers=signed_headers(self.actor,SECRET,"POST",path,body)
        self.assertEqual(self.status(path,body,headers),200)
        self.assertEqual(self.status(path,body,headers),401)
    def test_tampered_actor_401(self):
        path="/v1/search"; body=b'{"params":{"query":"x"}}'
        headers=signed_headers(self.actor,SECRET,"POST",path,body)
        headers["X-KB-Actor"]=base64.urlsafe_b64encode(json.dumps(Actor("attacker","org").__dict__).encode()).decode()
        self.assertEqual(self.status(path,body,headers),401)
    def test_cross_tenant_403(self):
        kb,v=self.create()
        with self.assertRaises(PermissionDeniedError): self.remote.retrieve(Actor("owner","other"),v.doc_id)
        path="/v1/retrieve"; body=json.dumps({"params":{"doc_id":v.doc_id}}).encode()
        self.assertEqual(self.status(path,body,signed_headers(Actor("owner","other"),SECRET,"POST",path,body)),403)
    def test_local_http_contract_equivalence(self):
        kb,v=self.create()
        self.assertEqual(self.remote.get_document(self.actor,v.doc_id),self.local.get_document(self.actor,v.doc_id))
        self.assertEqual(self.remote.get_document(self.actor,v.doc_id,1),self.local.get_document(self.actor,v.doc_id,1))
        self.assertEqual(self.remote.search(self.actor,"HTTP"),self.local.search(self.actor,"HTTP"))
        self.assertEqual(self.remote.retrieve(self.actor,v.doc_id,offset=2,limit=7),self.local.retrieve(self.actor,v.doc_id,offset=2,limit=7))
        self.assertEqual(self.remote.preview(self.actor,v.doc_id),self.local.preview(self.actor,v.doc_id))
        self.assertEqual(self.remote.list_kbs(self.actor),self.local.list_kbs(self.actor))
        self.assertEqual(self.remote.list_documents(self.actor,kb.kb_id),self.local.list_documents(self.actor,kb.kb_id))
        ref=self.remote.reference(self.actor,v.doc_id,excerpt="HTTP")
        self.assertEqual(self.remote.consume(self.actor,ref),self.local.consume(self.actor,ref))
        self.assertEqual(self.remote.batch_consume(self.actor,[ref]),self.local.batch_consume(self.actor,[ref]))
    def test_archive_restore_remote(self):
        kb,v=self.create(); self.remote.archive(self.actor,v.doc_id)
        self.assertEqual(self.remote.list_documents(self.actor,kb.kb_id),[])
        self.remote.restore(self.actor,v.doc_id); self.assertEqual(len(self.remote.list_documents(self.actor,kb.kb_id)),1)
    def test_acl_and_members_remote(self):
        kb,v=self.create(); viewer=Actor("viewer","org")
        self.remote.grant_kb_member(self.actor,kb.kb_id,"viewer","viewer")
        self.assertTrue(self.remote.retrieve(viewer,v.doc_id).text)
        self.remote.set_document_acl(self.actor,v.doc_id,DocumentACL(deny_users=["viewer"]))
        with self.assertRaises(PermissionDeniedError): self.remote.retrieve(viewer,v.doc_id)
        self.remote.reindex(self.actor,kb.kb_id)
    def test_binary_upload(self):
        kb,_=self.create(); v=self.remote.ingest(self.actor,kb.kb_id,b"binary UTF8 "+"知识".encode())
        self.assertEqual(self.remote.retrieve(self.actor,v.doc_id).text,"binary UTF8 知识")
    def test_resource_version_alias(self):
        kb,v=self.create(); path="/v1/documents/{}/versions/1".format(v.doc_id)
        headers=signed_headers(self.actor,SECRET,"GET",path)
        with self.request(path,b"",headers,"GET") as r: self.assertEqual(json.load(r)["text"],v.text)
    def test_openapi_routes(self):
        from fastapi.testclient import TestClient
        with TestClient(self.app) as client:
            data=client.get("/openapi.json").json()
        for path in ("/v1/health","/v1/kbs","/v1/documents","/v1/documents/{doc_id}/versions/{version}","/v1/documents/{doc_id}/archive","/v1/documents/{doc_id}/acl","/v1/search","/v1/retrieve","/v1/references/consume","/v1/references/batch-consume"):
            self.assertIn(path,data["paths"])
    def test_default_auth_is_fail_closed(self):
        from knowledge_sdk.server.app import create_app
        with self.assertRaises(ValidationError): create_app(self.local)
        with self.assertRaises(ValidationError): HttpKnowledgeClient(self.url)
    def test_local_dev_mode_explicit(self):
        from fastapi.testclient import TestClient
        from knowledge_sdk.server.app import create_app
        app=create_app(self.local,dev_insecure=True)
        actor=base64.urlsafe_b64encode(json.dumps(self.actor.__dict__).encode()).decode()
        with TestClient(app) as client:
            self.assertEqual(client.get("/v1/kbs",headers={"X-KB-Actor":actor}).status_code,200)
            self.assertEqual(client.get("/v1/kbs").status_code,401)
    def test_method_signatures_match(self):
        for name in OPERATIONS:
            self.assertEqual(inspect.signature(getattr(LocalKnowledgeClient,name)),inspect.signature(getattr(HttpKnowledgeClient,name)))
    def test_parameter_actor_cannot_override_signed_actor(self):
        path="/v1/search"; body=json.dumps({"params":{"query":"x","actor":encode(self.actor)}}).encode()
        self.assertEqual(self.status(path,body,signed_headers(self.actor,SECRET,"POST",path,body)),400)
