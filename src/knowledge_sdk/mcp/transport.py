"""Official SDK Streamable HTTP, stateless per-request HMAC authentication."""
from __future__ import annotations
import json
import sys
from contextlib import asynccontextmanager
from ..exceptions import ValidationError
from .gateway import GatewayAuthenticator
from .handlers import EvidenceTools,tool_definitions


def create_app(client,*,auth_secret,replay_store=None,fallback_secrets=(),bound_purpose='ground_external_llm',
               path='/mcp',allowed_hosts=('127.0.0.1:*','localhost:*','[::1]:*'),allowed_origins=()):
    if sys.version_info<(3,10):raise RuntimeError('MCP wire requires Python >=3.10; core supports Python >=3.9')
    try:
        from mcp.server import Server
        from mcp import types
        from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
        from mcp.server.transport_security import TransportSecuritySettings
        from starlette.applications import Starlette
        from starlette.routing import Route
    except ImportError:raise RuntimeError("Install 'knowledge-sdk[mcp]' on Python >=3.10 for official MCP wire support") from None
    if not isinstance(path,str) or not path.startswith('/') or path=='/' or any(c.isspace() for c in path) or '..' in path or '?' in path or '#' in path:
        raise ValidationError('Invalid MCP path')
    auth=GatewayAuthenticator(auth_secret,replay_store=replay_store,fallback_secrets=fallback_secrets,bound_purpose=bound_purpose)
    from .. import __version__
    tools=EvidenceTools(client);server=Server('knowledge-sdk',version=__version__)
    @server.list_tools()
    async def list_tools():return [types.Tool(**definition) for definition in tool_definitions()]
    @server.call_tool(validate_input=False)
    async def call_tool(name,arguments):
        request=server.request_context.request
        context=request.scope.get('knowledge_sdk.mcp_context') if request is not None else None
        try:result=tools.call(name,arguments,context)
        except ValidationError:return types.CallToolResult(content=[types.TextContent(type='text',text=json.dumps({'status':'denied','error':'invalid_arguments'}))],isError=True)
        except Exception:
            # Fail closed at the wire boundary; never log raw arguments/headers,
            # signing secrets, descriptions or unhandled exception text.
            return types.CallToolResult(content=[types.TextContent(type='text',text='{"status":"denied"}')],isError=True)
        return types.CallToolResult(content=[types.TextContent(type='text',text=json.dumps(result,ensure_ascii=False))],structuredContent=result)
    settings=TransportSecuritySettings(enable_dns_rebinding_protection=True,allowed_hosts=list(allowed_hosts),allowed_origins=list(allowed_origins))
    manager=StreamableHTTPSessionManager(server,stateless=True,json_response=True,security_settings=settings,max_request_body_size=65536)
    @asynccontextmanager
    async def lifespan(app):
        async with manager.run():yield
    # Route uses the ASGI wrapper, not an invented JSON-RPC implementation.
    class MCPRoute:
        async def __call__(self,scope,receive,send):await manager.handle_request(scope,receive,send)
    app=Starlette(routes=[Route(path,endpoint=MCPRoute(),methods=['POST','GET','DELETE'])],lifespan=lifespan)
    class Gateway:
        async def __call__(self,scope,receive,send):
            if scope['type']!='http':return await app(scope,receive,send)
            async def error(code):
                await send({'type':'http.response.start','status':code,'headers':[(b'content-type',b'application/json'),(b'cache-control',b'no-store'),(b'x-content-type-options',b'nosniff')]})
                await send({'type':'http.response.body','body':b'{"status":"denied"}'})
            if scope.get('path')!=path:return await error(404)
            # No browser/cross-origin fallback: absent Origin is allowed for
            # gateways; present Origin must exactly match trusted configuration.
            raw_headers=[(k.decode('latin1'),v.decode('latin1')) for k,v in scope.get('headers',())]
            origins=[v for k,v in raw_headers if k.lower()=='origin']
            if len(origins)>1 or origins and origins[0] not in allowed_origins:return await error(403)
            body=bytearray()
            while True:
                message=await receive()
                if message['type']=='http.disconnect':return
                body.extend(message.get('body',b''))
                if len(body)>65536:return await error(413)
                if not message.get('more_body',False):break
            target=scope.get('raw_path',scope['path'].encode()).decode('ascii')
            if scope.get('query_string'):target+='?'+scope['query_string'].decode('ascii')
            try:context=auth.authenticate(raw_headers,scope['method'],target,bytes(body))
            except ValidationError:return await error(401)
            scoped=dict(scope);scoped['knowledge_sdk.mcp_context']=context
            sent=False
            async def replay():
                nonlocal sent
                if not sent:sent=True;return {'type':'http.request','body':bytes(body),'more_body':False}
                return await receive()
            async def safe_send(message):
                if message['type']=='http.response.start':
                    message=dict(message);message['headers']=[*message.get('headers',()),(b'cache-control',b'no-store'),(b'x-content-type-options',b'nosniff')]
                await send(message)
            await app(scoped,replay,safe_send)
    return Gateway()
