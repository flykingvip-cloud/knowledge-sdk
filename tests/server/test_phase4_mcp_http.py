from __future__ import annotations
import importlib.util,json,secrets,unittest
from knowledge_sdk import *
from knowledge_sdk.server.auth import signed_headers
AVAILABLE=all(importlib.util.find_spec(name) is not None for name in ('fastapi','httpx','uvicorn'))

@unittest.skipUnless(AVAILABLE,'optional HTTP dependencies unavailable')
class MCPHTTPTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from knowledge_sdk.server.app import create_app
        self.c=LocalKnowledgeClient();self.addCleanup(self.c.store.close);self.a=Actor('admin','o',org_roles=('admin',));self.u=Actor('u','o');self.ag=AgentIdentity('g','o',allowed_purposes=tuple(Purpose));self.secret=secrets.token_hex(32)
        self.c.create_kb(self.a,'k',visibility='enterprise',kb_id='k');self.c.ingest(self.a,'k','alpha evidence',doc_id='d')
        self.factory=create_app;self.TestClient=TestClient;self.http=TestClient(create_app(self.c,self.secret,enable_mcp=True));self.addCleanup(self.http.close)
    def rpc(self,method='tools/call',params=None,purpose=None):
        body=json.dumps({'jsonrpc':'2.0','id':1,'method':method,'params':params or {'name':'search_evidence','arguments':{'query':'alpha'}}}).encode()
        return body,{'Content-Type':'application/json',**signed_headers(self.u,self.secret,'POST','/v1/mcp',body,agent=self.ag.to_dict(),purpose=purpose)}
    def test_opt_in_unsigned_and_shared_nonce_no_store(self):
        with self.TestClient(self.factory(self.c,self.secret)) as disabled:self.assertEqual(disabled.post('/v1/mcp',json={}).status_code,404)
        self.assertEqual(self.http.post('/v1/mcp',json={}).status_code,401)
        body,headers=self.rpc();first=self.http.post('/v1/mcp',content=body,headers=headers)
        self.assertEqual(first.status_code,200);self.assertEqual(first.headers['cache-control'],'no-store')
        repeated=self.http.post('/v1/mcp',content=body,headers=headers);self.assertEqual(repeated.status_code,401);self.assertEqual(repeated.headers['cache-control'],'no-store')
    def test_internal_default_external_config_and_explicit_signed_purpose(self):
        body,headers=self.rpc();out=self.http.post('/v1/mcp',content=body,headers=headers).json()['result']['structuredContent'];self.assertTrue(out['hits']);self.assertEqual(out['purpose_applied'],'ground_internal_llm')
        with self.TestClient(self.factory(self.c,self.secret,enable_mcp=True,default_mcp_purpose=Purpose.GROUND_EXTERNAL_LLM)) as cloud:
            body,headers=self.rpc();out=cloud.post('/v1/mcp',content=body,headers=headers).json()['result']['structuredContent'];self.assertEqual(out['hits'],[]);self.assertEqual(out['purpose_applied'],'ground_external_llm')
        body,headers=self.rpc(purpose='ground_external_llm');self.assertEqual(self.http.post('/v1/mcp',content=body,headers=headers).json()['result']['structuredContent']['hits'],[])
    def test_identity_injection_bad_agent_and_origin(self):
        for key in ('actor','agent','purpose','policy_context','self','user_id','org_id'):
            body,headers=self.rpc(params={'name':'search_evidence','arguments':{'query':'alpha',key:'admin'}})
            self.assertEqual(self.http.post('/v1/mcp',content=body,headers=headers).json()['error']['code'],-32602)
        body,headers=self.rpc();headers.update(signed_headers(self.u,self.secret,'POST','/v1/mcp',body,agent=dict(self.ag.to_dict(),admin=True)))
        self.assertEqual(self.http.post('/v1/mcp',content=body,headers=headers).status_code,401)
        body,headers=self.rpc();headers['Origin']='https://untrusted.example';self.assertEqual(self.http.post('/v1/mcp',content=body,headers=headers).status_code,403)
    def test_typed_feedback_http_and_reserved_claims(self):
        for name,path,params in [('report_evidence_issue','/v1/issues',{'source_uri':build_uri('o','d',1),'issue_type':'outdated','description':'data'}),('list_evidence_issues','/v1/issues/list',{})]:
            for key in ('actor','self','agent','purpose','policy_context'):
                body=json.dumps({'params':dict(params,**{key:{}})}).encode();headers={'Content-Type':'application/json',**signed_headers(self.u,self.secret,'POST',path,body)}
                self.assertEqual(self.http.post(path,content=body,headers=headers).status_code,400)
        with self.assertRaises(ValidationError):self.factory(self.c,None,dev_insecure=True,enable_mcp=True)
