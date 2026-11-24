from __future__ import annotations
import io,json,unittest
from knowledge_sdk import *
from knowledge_sdk.mcp import *
from knowledge_sdk.mcp.server import run_stdio,stdio_context

class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.c=LocalKnowledgeClient();self.addCleanup(self.c.store.close);self.a=Actor('u','o');self.ctx=GatewayContext(self.a);self.p=MCPProtocol(self.c)
    def test_initialize_list_ping_notifications(self):
        init=self.p.dispatch({'jsonrpc':'2.0','id':1,'method':'initialize'},self.ctx);self.assertEqual(init['result']['serverInfo']['version'],'1.2.0')
        self.assertEqual(len(self.p.dispatch({'jsonrpc':'2.0','id':2,'method':'tools/list'},self.ctx)['result']['tools']),4)
        self.assertIsNone(self.p.dispatch({'jsonrpc':'2.0','method':'notifications/initialized'},self.ctx))
        self.assertEqual(self.p.dispatch({'jsonrpc':'2.0','id':3,'method':'ping'},self.ctx)['result'],{})
    def test_parse_invalid_duplicates_unknown_method_and_request_ids(self):
        for raw in ('{','{"jsonrpc":"2.0","jsonrpc":"1.0"}','NaN'):
            self.assertIn('error',self.p.handle(raw,self.ctx))
        self.assertEqual(self.p.dispatch({'jsonrpc':'2.0','id':True,'method':'ping'},self.ctx)['error']['code'],-32600)
        self.assertEqual(self.p.dispatch({'jsonrpc':'2.0','id':1,'method':'missing'},self.ctx)['error']['code'],-32601)
        self.assertEqual(self.p.dispatch({'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'search_evidence','arguments':{'query':'alpha','purpose':'read'}}},self.ctx)['error']['code'],-32602)
    def test_batch_mixed_and_no_shared_identity(self):
        request={'jsonrpc':'2.0','id':1,'method':'ping'}
        self.assertEqual(len(self.p.dispatch([request,dict(jsonrpc='2.0',method='notifications/initialized')],self.ctx)),1)
        self.assertEqual(self.p.dispatch([],self.ctx)['error']['code'],-32600)
        self.assertEqual(self.p.dispatch(request,None)['error']['code'],-32600)
    def test_stdio_requires_valid_actor_and_never_defaults_admin(self):
        for env in ({},{'KNOWLEDGE_MCP_ACTOR_JSON':'{}'},{'KNOWLEDGE_MCP_ACTOR_JSON':'{"user_id":"u","org_id":"o","admin":true}'},{'KNOWLEDGE_MCP_ACTOR_JSON':'{"user_id":"u","org_id":"o"}','KNOWLEDGE_MCP_AGENT_JSON':'{"agent_id":"g","org_id":"wrong"}'}):
            with self.assertRaises(ValidationError):stdio_context(env)
        ctx=stdio_context({'KNOWLEDGE_MCP_ACTOR_JSON':'{"user_id":"u","org_id":"o"}'})
        self.assertEqual(ctx.purpose,Purpose.GROUND_INTERNAL_LLM);self.assertFalse(ctx.actor.org_roles);self.assertIsNone(ctx.agent)
    def test_newline_transport_json_only_and_size_limit(self):
        source=io.StringIO(json.dumps({'jsonrpc':'2.0','id':1,'method':'ping'})+'\n'+'x'*70000+'\n');sink=io.StringIO()
        run_stdio(self.c,self.ctx,source,sink);replies=[json.loads(s) for s in sink.getvalue().splitlines()]
        self.assertEqual(len(replies),2);self.assertEqual(replies[0]['result'],{});self.assertIn('error',replies[1])
