from __future__ import annotations
import base64
import hashlib
import hmac
import importlib.util
import json
import secrets
import unittest

from knowledge_sdk import (Actor, AgentIdentity, Purpose, PolicyAction, PolicyContext, ResourceRights,
    LocalKnowledgeClient, DocumentACL, RedactionRegistry, RegexRedactionHook, GeneratedAnswer, ValidationError)
from knowledge_sdk.contracts.models import encode, decode
from knowledge_sdk.client.http_client import OPERATIONS
from knowledge_sdk.server.auth import signed_headers

AVAILABLE=all(importlib.util.find_spec(m) is not None for m in ('fastapi','httpx'))


@unittest.skipUnless(AVAILABLE,'optional HTTP dependencies unavailable')
class PolicyHTTPTests(unittest.TestCase):
    def setUp(self):
        from knowledge_sdk.server.app import create_app
        from fastapi.testclient import TestClient
        self.local=LocalKnowledgeClient();self.addCleanup(self.local.store.close)
        self.secret=secrets.token_hex(32);self.admin=Actor('admin','org',org_roles=('admin',));self.user=Actor('user','org')
        self.ka=self.local.create_kb(self.admin,'A',kb_id='kb-a',space_type='enterprise_public')
        self.kb=self.local.create_kb(self.admin,'B',kb_id='kb-b',space_type='enterprise_public')
        self.va=self.local.ingest(self.admin,'kb-a','alpha 123-45-6789',doc_id='doc-a')
        self.vb=self.local.ingest(self.admin,'kb-b','beta knowledge',doc_id='doc-b')
        self.spy=HTTPGeneratorSpy()
        self.http=TestClient(create_app(self.local,auth_secret=self.secret,answer_generator=self.spy,ui_prefix='/kb/ui'))
        self.addCleanup(self.http.close)
    def request(self,operation,params=None,*,actor=None,agent=None,purpose=None,nonce=None):
        method,path=OPERATIONS[operation]
        if method=='GET':
            from urllib.parse import urlencode
            path+='?'+urlencode({'params':json.dumps(encode(params or {}),separators=(',',':'))})
            body=b''
        else:body=json.dumps({'params':encode(params or {})},separators=(',',':')).encode()
        headers=signed_headers(actor or self.user,self.secret,method,path,body,agent=agent.to_dict() if isinstance(agent,AgentIdentity) else agent,purpose=purpose,nonce=nonce)
        return self.http.request(method,path,content=body if method!='GET' else None,headers={'Content-Type':'application/json',**headers})
    def external(self):
        return ResourceRights(allowed_purposes=tuple(Purpose),allow_external_llm=True,allow_eval_and_train=True)

    def test_signed_external_default_prohibited_then_admin_explicit_rights(self):
        denied=self.request('retrieve',{'doc_id':'doc-a'},purpose='ground_external_llm')
        self.assertEqual(denied.status_code,403);self.assertEqual(denied.json()['message'],'external_llm_prohibited')
        allowed=self.request('set_document_rights',{'doc_id':'doc-a','rights':self.external()},actor=self.admin)
        self.assertEqual(allowed.status_code,200)
        response=self.request('retrieve',{'doc_id':'doc-a'},purpose='ground_external_llm')
        self.assertEqual(response.status_code,200)
        self.assertIn('alpha',response.json()['text'])
        self.assertEqual(self.spy.calls,0)  # No model or external request in retrieve.
    def test_external_boolean_does_not_override_explicit_purpose_list(self):
        self.local.set_document_rights(self.admin,'doc-a',ResourceRights(allow_external_llm=True))
        r=self.request('retrieve',{'doc_id':'doc-a'},purpose='ground_external_llm')
        self.assertEqual(r.status_code,403);self.assertEqual(r.json()['message'],'purpose_not_permitted')
    def test_agent_scope_on_search_read_inspection_and_alias(self):
        agent=AgentIdentity('agent','org',allowed_kb_ids=('kb-a',))
        for operation in ('retrieve','preview','get_document','inspect_document','reference','create_ref'):
            r=self.request(operation,{'doc_id':'doc-b'},agent=agent)
            self.assertEqual(r.status_code,403,(operation,r.text))
        self.assertEqual(decode(self.request('search',{'query':'beta'},agent=agent).json()).hits,[])
        self.assertEqual([d.doc_id for d in decode(self.request('list_documents',agent=agent).json())],['doc-a'])
        path='/v1/documents/doc-b/versions/1';headers=signed_headers(self.user,self.secret,'GET',path,agent=agent.to_dict())
        self.assertEqual(self.http.get(path,headers=headers).status_code,403)
    def test_agent_purpose_narrows_resource_rights(self):
        self.local.set_document_rights(self.admin,'doc-a',self.external())
        denied=self.request('retrieve',{'doc_id':'doc-a'},agent=AgentIdentity('a','org'),purpose='ground_external_llm')
        self.assertEqual(denied.status_code,403);self.assertEqual(denied.json()['message'],'agent_purpose_denied')
        agent=AgentIdentity('a','org',allowed_purposes=(Purpose.GROUND_EXTERNAL_LLM,))
        self.assertEqual(self.request('retrieve',{'doc_id':'doc-a'},agent=agent,purpose='ground_external_llm').status_code,200)
    def test_reserved_body_claim_injection_rejected(self):
        for name,value in (('purpose','ground_external_llm'),('agent',{'agent_id':'a','org_id':'org'}),('policy_context',{}),('actor',{}),('self',{})):
            for operation,params in (('retrieve',{'doc_id':'doc-a'}),('ask',{'question':'alpha'})):
                r=self.request(operation,{**params,name:value})
                self.assertEqual(r.status_code,400,(operation,name,r.text));self.assertEqual(r.json()['message'],'Invalid parameters')
        self.assertEqual(self.spy.calls,0)
    def test_reserved_get_params_injection_rejected(self):
        self.assertEqual(self.request('list_documents',{'purpose':'export'}).status_code,400)
    def test_signed_agent_strict_unknown_types_and_missing_fields_401(self):
        for change in ({'unknown_admin':True},{'allowed_kb_ids':'kb-a'},{'allowed_purposes':'read'},
                       {'max_clearance_level':True},{'app_id':[]},{'allowed_purposes':['invalid']}):
            agent={'agent_id':'a','org_id':'org',**change}
            # v1.1 low-level signer accepts forward-compatible objects; the
            # Phase 2 HTTP trust boundary must strictly type-check them.
            self.assertEqual(self.request('retrieve',{'doc_id':'doc-a'},agent=agent).status_code,401)
    def test_invalid_strict_agent_does_not_poison_nonce(self):
        nonce=secrets.token_hex(16)
        bad={'agent_id':'a','org_id':'org','unknown':True}
        self.assertEqual(self.request('retrieve',{'doc_id':'doc-a'},agent=bad,nonce=nonce).status_code,401)
        self.assertEqual(self.request('retrieve',{'doc_id':'doc-a'},agent=AgentIdentity('a','org'),nonce=nonce).status_code,200)
    def test_signed_extensions_tampered_removed_or_duplicated_401(self):
        method,path=OPERATIONS['retrieve'];body=json.dumps({'params':{'doc_id':'doc-a'}}).encode()
        h=signed_headers(self.user,self.secret,method,path,body,purpose='read')
        changed=dict(h);changed['X-KB-Purpose']='export'
        self.assertEqual(self.http.post(path,content=body,headers=changed).status_code,401)
        removed=dict(h);removed.pop('X-KB-Purpose')
        self.assertEqual(self.http.post(path,content=body,headers=removed).status_code,401)
        self.assertEqual(self.http.post(path,content=body,headers=list(h.items())+[('x-kb-purpose','export')]).status_code,401)
    def test_agent_scope_applies_to_management_and_rights_updates(self):
        agent=AgentIdentity('admin-agent','org',allowed_kb_ids=('kb-a',))
        r=self.request('set_document_rights',{'doc_id':'doc-b','rights':ResourceRights(revoked=True)},actor=self.admin,agent=agent)
        self.assertEqual(r.status_code,403)
        self.assertIsNone(self.local.store.get_document('doc-b').rights)
    def test_missing_hook_retrieve_consume_and_ask_fail_closed(self):
        ref=self.local.reference(self.user,'doc-a',excerpt='alpha')
        self.local.set_document_rights(self.admin,'doc-a',ResourceRights(redaction_profile='missing'))
        r=self.request('retrieve',{'doc_id':'doc-a'});self.assertEqual(r.status_code,403);self.assertEqual(r.json()['message'],'redaction_hook_missing')
        receipt=decode(self.request('consume',{'ref':ref}).json());self.assertEqual((receipt.status,receipt.reason_code),('denied','redaction_hook_missing'))
        answer=decode(self.request('ask',{'question':'alpha'}).json())
        self.assertEqual((answer.status,answer.model_called,self.spy.calls),('refused',False,0))
    def test_masked_http_search_retrieve_reference_and_generator(self):
        self.local.redaction_registry.register('pii',RegexRedactionHook([(r'123-45-6789','[MASK]')]))
        self.local.set_document_rights(self.admin,'doc-a',ResourceRights(redaction_profile='pii'))
        for operation,params in (('retrieve',{'doc_id':'doc-a'}),('inspect_document',{'doc_id':'doc-a'}),('get_document',{'doc_id':'doc-a','version':1})):
            r=self.request(operation,params);self.assertEqual(r.status_code,200)
            self.assertNotIn('123-45-6789',r.text)
        hit=decode(self.request('search',{'query':'alpha'}).json()).hits[0]
        self.assertEqual(hit.excerpt_hash,hashlib.sha256(hit.excerpt.encode()).hexdigest())
        ref=decode(self.request('reference',{'doc_id':'doc-a','excerpt':hit.excerpt}).json())
        receipt=decode(self.request('consume',{'ref':ref}).json());self.assertIn(receipt.status,('partial','consumed'))
        answer=decode(self.request('ask',{'question':'alpha'}).json());self.assertEqual(answer.status,'answered')
        self.assertNotIn('123-45-6789',self.spy.text);self.assertIn('[MASK]',self.spy.text)
    def test_ask_absent_purpose_infers_internal_but_explicit_read_respected(self):
        self.local.set_document_rights(self.admin,'doc-a',ResourceRights(allowed_purposes=(Purpose.READ,)))
        self.assertEqual(decode(self.request('ask',{'question':'alpha'}).json()).status,'refused')
        self.assertEqual(self.spy.calls,0)
        self.assertEqual(decode(self.request('ask',{'question':'alpha'},purpose='read').json()).status,'answered')
        self.assertEqual(self.spy.calls,1)
    def test_no_model_call_for_signed_external_denial_then_offline_stub_allowed(self):
        self.assertEqual(decode(self.request('ask',{'question':'alpha'},purpose='ground_external_llm').json()).status,'refused')
        self.assertEqual(self.spy.calls,0)
        self.local.set_document_rights(self.admin,'doc-a',self.external())
        answer=decode(self.request('ask',{'question':'alpha'},purpose='ground_external_llm').json())
        self.assertEqual(answer.status,'answered');self.assertEqual(self.spy.calls,1)  # local spy only
    def test_new_policy_endpoints_and_no_body_context_override(self):
        r=self.request('evaluate_policy',{'doc_id':'doc-a'})
        self.assertEqual(r.status_code,200);self.assertTrue(decode(r.json()).allowed)
        self.assertEqual(self.request('evaluate_policy',{'doc_id':'doc-a','policy_context':PolicyContext(policy_generation='fake')}).status_code,400)
    def test_subpath_ui_dynamic_version_and_production_signer_stay_closed(self):
        config=self.http.get('/kb/ui/config').json()
        self.assertEqual(config['version'],'1.2.0');self.assertFalse(config['demo_enabled'])
        self.assertEqual(self.http.get('/kb/ui/assets/i18n.js').status_code,200)
        for path in ('/ui/demo/sign','/kb/ui/demo/sign'):
            self.assertEqual(self.http.post(path,headers={'X-KB-Demo':'1','Origin':'http://testserver'}).status_code,404)


class HTTPGeneratorSpy:
    def __init__(self):self.calls=0;self.text=''
    def generate(self,question,hits,scope,actor):
        self.calls+=1;self.text=' '.join(h.excerpt for h in hits)
        return GeneratedAnswer(self.text,False)  # offline stub, never an external model
