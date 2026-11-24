import importlib.util
import unittest
from knowledge_sdk import *
from knowledge_sdk.contracts.models import decode
import tests.server.test_phase2_policy_http as phase2

AVAILABLE=all(importlib.util.find_spec(m) is not None for m in ('fastapi','httpx'))

@unittest.skipUnless(AVAILABLE,'optional HTTP dependencies unavailable')
class AnchorHTTPTests(unittest.TestCase):
    setUp=phase2.PolicyHTTPTests.setUp
    request=phase2.PolicyHTTPTests.request
    def anchor(self,doc='doc-a'):
        return self.local.list_anchors(self.admin,doc)[0]
    def test_list_get_and_anchor_ref_consume(self):
        a=self.anchor();r=self.request('list_anchors',{'doc_id':'doc-a'});self.assertEqual(r.status_code,200)
        self.assertEqual(decode(r.json())[0],a)
        r=self.request('get_anchor',{'doc_id':'doc-a','anchor_id':a.anchor_id});self.assertEqual(r.status_code,200)
        ref=decode(self.request('reference',{'doc_id':'doc-a','anchor_id':a.anchor_id}).json())
        receipt=decode(self.request('consume',{'ref':ref}).json());self.assertEqual((receipt.status,receipt.evidence_kind),('consumed','anchor_excerpt'))
    def test_signed_external_denies_anchors_then_explicit_rights_allows(self):
        a=self.anchor()
        for operation,params in [('list_anchors',{'doc_id':'doc-a'}),('get_anchor',{'doc_id':'doc-a','anchor_id':a.anchor_id})]:
            r=self.request(operation,params,purpose='ground_external_llm');self.assertEqual(r.status_code,403);self.assertEqual(r.json()['message'],'external_llm_prohibited')
        self.local.set_document_rights(self.admin,'doc-a',ResourceRights(allowed_purposes=tuple(Purpose),allow_external_llm=True))
        self.assertEqual(self.request('list_anchors',{'doc_id':'doc-a'},purpose='ground_external_llm').status_code,200)
    def test_reserved_body_claims_rejected(self):
        a=self.anchor()
        for key in ('actor','self','agent','purpose','policy_context'):
            for operation,params in [('list_anchors',{'doc_id':'doc-a'}),('get_anchor',{'doc_id':'doc-a','anchor_id':a.anchor_id}),('confirm_anchor_reanchor',{'doc_id':'doc-a','version':1,'anchor_id':a.anchor_id})]:
                r=self.request(operation,{**params,key:{}});self.assertEqual(r.status_code,400,(operation,key,r.text))
    def test_strict_agent_401_and_scope_403(self):
        self.assertEqual(self.request('list_anchors',{'doc_id':'doc-a'},agent={'agent_id':'a','org_id':'org','unknown':True}).status_code,401)
        scoped=AgentIdentity('a','org',allowed_kb_ids=('kb-a',))
        self.assertEqual(self.request('list_anchors',{'doc_id':'doc-b'},agent=scoped).status_code,403)
    def test_missing_hook_and_regex_all_anchor_sidecars(self):
        a=self.anchor();ref=self.local.reference(self.user,'doc-a',anchor_id=a.anchor_id)
        self.local.set_document_rights(self.admin,'doc-a',ResourceRights(redaction_profile='pii'))
        r=self.request('list_anchors',{'doc_id':'doc-a'});self.assertEqual(r.status_code,403);self.assertEqual(r.json()['message'],'redaction_hook_missing')
        self.assertEqual(decode(self.request('consume',{'ref':ref}).json()).reason_code,'redaction_hook_missing')
        self.local.redaction_registry.register('pii',RegexRedactionHook([('123-45-6789','[MASK]')]))
        r=self.request('get_anchor',{'doc_id':'doc-a','anchor_id':a.anchor_id});self.assertEqual(r.status_code,200);self.assertNotIn('123-45-6789',r.text)
        self.assertEqual(decode(self.request('consume',{'ref':ref}).json()).status,'denied')
    def test_confirm_requires_write_read_and_signed_agent_intersection(self):
        a=self.anchor();self.local.ingest(self.admin,'kb-a','alpha 123-45-6789\n\nalpha 123-45-6789',doc_id='doc-a')
        params={'doc_id':'doc-a','version':2,'anchor_id':a.anchor_id}
        self.assertEqual(self.request('confirm_anchor_reanchor',params).status_code,403)
        agent=AgentIdentity('a','org',allowed_kb_ids=('kb-b',))
        self.assertEqual(self.request('confirm_anchor_reanchor',params,actor=self.admin,agent=agent).status_code,403)
        self.assertEqual(self.request('confirm_anchor_reanchor',params,actor=self.admin).status_code,200)
    def test_clearance_upper_bound_applies_anchor_delivery(self):
        self.local.set_document_acl(self.admin,'doc-a',DocumentACL(required_clearance='restricted'))
        agent=AgentIdentity('a','org',max_clearance_level='internal')
        r=self.request('list_anchors',{'doc_id':'doc-a'},actor=self.admin,agent=agent)
        self.assertEqual(r.status_code,403);self.assertEqual(r.json()['message'],'agent_clearance_exceeded')
