from __future__ import annotations
import json
import unittest
from knowledge_sdk import *
from knowledge_sdk.contracts.models import encode, decode
from knowledge_sdk.server.auth import signed_headers
from tests.server import test_http as legacy_http
AVAILABLE = legacy_http.AVAILABLE
SECRET = legacy_http.SECRET


@unittest.skipUnless(AVAILABLE,'Optional HTTP dependencies unavailable')
class V11HTTPTests(unittest.TestCase):
    setUpClass = classmethod(legacy_http.HTTPTests.setUpClass.__func__)
    tearDownClass = classmethod(legacy_http.HTTPTests.tearDownClass.__func__)
    def setUp(self):
        self.admin=Actor('a','org',org_roles=('admin',))
        self.user=Actor('u','org',department_ids=('child',),ancestor_department_ids=('parent',),org_roles=('analyst',),clearance_level='internal')
        self.k=self.remote.create_kb(self.admin,'Public',space_type='enterprise_public')
        self.v=self.remote.ingest(self.admin,self.k.kb_id,'Remote maintenance evidence with oil inspection.')
    def test_expanded_signed_claims_roundtrip(self):
        self.remote.set_document_acl(self.admin,self.v.doc_id,DocumentACL(access_level='department',allowed_department_ids=['parent'],include_sub_departments=True))
        self.assertTrue(self.remote.retrieve(self.user,self.v.doc_id).text)
        with self.assertRaises(PermissionDeniedError): self.remote.retrieve(Actor('u','org',department_ids=('child',)),self.v.doc_id)
    def test_ask_and_refusal(self):
        answer=self.remote.ask(self.user,'maintenance')
        self.assertEqual(answer.status,'answered'); self.assertFalse(answer.model_called)
        self.assertTrue(self.remote.verify_receipt(self.user,answer.citations[0],answer.receipts[0]))
        self.assertEqual(self.remote.ask(self.user,'nonexistentzzz').status,'refused')
    def test_scopes_and_bindings(self):
        scope=KnowledgeScope('documents',doc_ids=(self.v.doc_id,))
        binding=ConsumerBinding('cycle','http',scope,'background')
        self.assertEqual(self.remote.bind_consumer(self.user,binding),binding)
        self.assertEqual(self.remote.get_consumer_binding(self.user,'cycle','http'),binding)
        answer=self.remote.ask(self.user,'maintenance',binding=binding)
        self.assertEqual(answer.receipts[0].used_by_stage,'background')
        self.assertEqual(self.remote.validate_scope(self.user,scope),scope)
    def test_attach_verify_roundtrip(self):
        ref=self.remote.create_ref(self.user,self.v.doc_id,excerpt='Remote')
        item=self.remote.attach(self.user,ref)
        self.assertEqual(item.reference,ref)
        self.assertEqual(self.remote.verify_ref(self.user,ref),item.receipt)
    def test_space_permission_endpoints(self):
        self.assertTrue(self.remote.can_manage_kb(self.admin,self.k.kb_id))
        self.assertFalse(self.remote.can_upload_to_kb(self.user,self.k.kb_id))
    def test_remote_generator_objects_refused(self):
        with self.assertRaises(ValidationError): self.remote.ask(self.user,'maintenance',generator=ExtractiveAnswerGenerator())
    def test_server_generator_configuration_and_no_hit_no_call(self):
        from fastapi.testclient import TestClient
        from knowledge_sdk.server.app import create_app
        class Spy:
            calls=0
            def generate(self, question, evidence_hits, scope, actor):
                self.calls+=1; return GeneratedAnswer(evidence_hits[0].excerpt,True)
        spy=Spy(); app=create_app(self.local,auth_secret=SECRET,answer_generator=spy)
        def ask(client, query, extras=None):
            path='/v1/ask'; body=json.dumps({'params':{'question':query,**(extras or {})}}).encode()
            return client.post(path,content=body,headers=signed_headers(self.user,SECRET,'POST',path,body))
        with TestClient(app) as client:
            answer=decode(ask(client,'maintenance').json())
            self.assertTrue(answer.model_called); self.assertEqual(spy.calls,1)
            self.assertEqual(decode(ask(client,'missingzz').json()).status,'refused')
            self.assertEqual(spy.calls,1)
            self.assertEqual(ask(client,'maintenance',{'generator':'evil'}).status_code,400)
    def test_no_permission_explicit_doc_ask_is_refused(self):
        self.remote.set_document_acl(self.admin,self.v.doc_id,DocumentACL(access_level='personal_only'))
        a=self.remote.ask(self.user,'maintenance',scope=KnowledgeScope('documents',doc_ids=(self.v.doc_id,)))
        self.assertEqual(a.status,'refused')
    def test_raw_contract_camelcase(self):
        from fastapi.testclient import TestClient
        scope=KnowledgeScope('documents',doc_ids=(self.v.doc_id,))
        path='/v1/ask'; body=json.dumps({'params':{'question':'maintenance','scope':scope.to_dict(True)}}).encode()
        with TestClient(self.app) as client:
            answer=client.post(path,content=body,headers=signed_headers(self.user,SECRET,'POST',path,body))
        self.assertEqual(answer.status_code,200); self.assertEqual(decode(answer.json()).status,'answered')
    def test_openapi_v11_paths(self):
        paths=self.app.openapi()['paths']
        for path in ['/v1/ask','/v1/bindings','/v1/references/attach','/v1/references/verify','/v1/receipts/verify','/v1/scopes/validate']:
            self.assertIn(path,paths)
