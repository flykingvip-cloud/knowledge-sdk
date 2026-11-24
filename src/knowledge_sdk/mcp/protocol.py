"""Dependency-free newline/HTTP JSON-RPC 2.0 MCP protocol dispatcher."""
from __future__ import annotations
import json,math
from .tools import EvidenceTools,tool_definitions,plain
from .gateway import GatewayContext
from ..exceptions import KnowledgeSDKError,ValidationError

def strict_json(data):
    def pairs(items):
        out={}
        for k,v in items:
            if k in out:raise ValueError('Duplicate JSON key')
            out[k]=v
        return out
    return json.loads(data,object_pairs_hook=pairs,parse_constant=lambda value:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))

class MCPProtocol:
    def __init__(self,client):self.tools=EvidenceTools(client)
    @staticmethod
    def error(identifier,code,message):return {'jsonrpc':'2.0','id':identifier,'error':{'code':code,'message':message}}
    def dispatch(self,request,context):
        if isinstance(request,list):
            if not request or len(request)>20:return self.error(None,-32600,'Invalid Request')
            replies=[self.dispatch(item,context) for item in request]
            return [r for r in replies if r is not None] or None
        if not isinstance(request,dict):return self.error(None,-32600,'Invalid Request')
        identifier=request.get('id');notification='id' not in request
        valid_id=identifier is None or isinstance(identifier,str) or type(identifier) is int or type(identifier) is float and math.isfinite(identifier)
        if request.get('jsonrpc')!='2.0' or not isinstance(request.get('method'),str) or not valid_id or set(request)-{'jsonrpc','id','method','params'}:
            return self.error(None,-32600,'Invalid Request')
        if not isinstance(context,GatewayContext):return self.error(identifier,-32600,'Verified context required')
        method=request['method'];params=request.get('params',{})
        try:
            if not isinstance(params,dict):raise ValidationError('Invalid params')
            if method=='initialize':
                import knowledge_sdk
                versions=('2024-11-05','2025-03-26','2025-06-18','2025-11-25')
                result={'protocolVersion':params.get('protocolVersion') if params.get('protocolVersion') in versions else versions[-1],
                        'capabilities':{'tools':{'listChanged':False}},'serverInfo':{'name':'knowledge-sdk','version':knowledge_sdk.__version__}}
            elif method=='notifications/initialized':result={}
            elif method=='ping':
                if params:raise ValidationError('Invalid params')
                result={}
            elif method=='tools/list':
                if params:raise ValidationError('Invalid params')
                result={'tools':tool_definitions()}
            elif method=='tools/call':
                if set(params)-{'name','arguments'} or not isinstance(params.get('name'),str):raise ValidationError('Invalid params')
                data=self.tools.call(params['name'],params.get('arguments',{}),context)
                result={'content':[{'type':'text','text':json.dumps(data,ensure_ascii=False)}],'structuredContent':data,'isError':data.get('status')=='denied'}
            else:return None if notification else self.error(identifier,-32601,'Method not found')
            return None if notification else {'jsonrpc':'2.0','id':identifier,'result':result}
        except ValidationError:return None if notification else self.error(identifier,-32602,'Invalid params')
        except KnowledgeSDKError:return None if notification else self.error(identifier,-32603,'Controlled evidence operation failed')
        except Exception:return None if notification else self.error(identifier,-32603,'Internal error')
    def handle(self,data,context):
        try:request=strict_json(data)
        except (ValueError,TypeError,UnicodeError):return self.error(None,-32700,'Parse error')
        return self.dispatch(request,context)
