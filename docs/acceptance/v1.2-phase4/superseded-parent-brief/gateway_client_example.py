"""Explicit trusted gateway example, not a model tool or production login hook."""
from __future__ import annotations
import asyncio,json,os,sys
from knowledge_sdk import Actor,AgentIdentity,Purpose
from knowledge_sdk.server.auth import signed_headers

async def main(url):
    # These sandbox claims match QUICKSTART.md. In production replace this code
    # with the host's authenticated/authorized session->Actor/Agent mapping.
    # Never fill either object from LLM tool arguments or browser role headers.
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client
    import httpx
    actor=Actor('sandbox-user','sandbox')
    agent=AgentIdentity('sandbox-agent','sandbox',allowed_purposes=(Purpose.GROUND_EXTERNAL_LLM,))
    secret=os.environ['KNOWLEDGE_AUTH_SECRET']
    async def sign(request):
        body=await request.aread()
        request.headers.update(signed_headers(actor,secret,request.method,request.url.raw_path.decode(),body,
                                             agent=agent.to_dict(),purpose=Purpose.GROUND_EXTERNAL_LLM.value))
    async with httpx.AsyncClient(event_hooks={'request':[sign]}) as http:
        async with streamable_http_client(url,http_client=http) as (read,write,_):
            async with ClientSession(read,write) as session:
                await session.initialize()
                print([tool.name for tool in (await session.list_tools()).tools])
                result=await session.call_tool('search_evidence',{'query':'sandbox','mode':'keyword'})
                print(json.dumps(result.structuredContent,ensure_ascii=False,indent=2))

if __name__=='__main__':asyncio.run(main(sys.argv[1]))
