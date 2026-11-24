"""Stdlib MCP stdio entry point; optional HTTP is a lazy host adapter."""
from __future__ import annotations
import argparse,json,os,sys
from dataclasses import fields
from .gateway import GatewayContext
from .protocol import MCPProtocol,strict_json
from ..contracts.models import Actor
from ..contracts.policy import AgentIdentity,Purpose
from ..exceptions import ValidationError

MAX_MESSAGE=65536

def stdio_context(environ=None):
    env=os.environ if environ is None else environ
    try:
        data=strict_json(env.get('KNOWLEDGE_MCP_ACTOR_JSON',''))
        if not isinstance(data,dict) or set(data)-{f.name for f in fields(Actor)}:raise ValueError()
        actor=Actor(**data)
        raw=env.get('KNOWLEDGE_MCP_AGENT_JSON','')
        agent=AgentIdentity.from_dict(strict_json(raw)) if raw else None
        purpose=Purpose(env.get('KNOWLEDGE_MCP_PURPOSE',Purpose.GROUND_INTERNAL_LLM.value))
        return GatewayContext(actor,agent,purpose)
    except (ValueError,TypeError,ValidationError):raise ValidationError('Valid trusted KNOWLEDGE_MCP_ACTOR_JSON/AGENT_JSON/PURPOSE required') from None

def run_stdio(client,context,source=None,sink=None):
    source=sys.stdin if source is None else source;sink=sys.stdout if sink is None else sink
    protocol=MCPProtocol(client)
    while True:
        line=source.readline(MAX_MESSAGE+1)
        if not line:break
        if len(line.encode('utf-8'))>MAX_MESSAGE:
            while line and not line.endswith('\n'):line=source.readline(MAX_MESSAGE+1)
            reply=protocol.error(None,-32600,'Message too large')
        else:reply=protocol.handle(line,context)
        if reply is not None:sink.write(json.dumps(reply,ensure_ascii=False)+'\n');sink.flush()

def create_app(client,auth_secret=None,*,default_mcp_purpose=Purpose.GROUND_INTERNAL_LLM,**kwargs):
    from ..server.app import create_app as host_app
    return host_app(client,auth_secret,enable_mcp=True,default_mcp_purpose=default_mcp_purpose,**kwargs)

def main(argv=None):
    parser=argparse.ArgumentParser(description='Trusted knowledge-sdk MCP stdio or optional HTTP')
    parser.add_argument('--transport',choices=('stdio','http'),default='stdio');parser.add_argument('--db',default=':memory:')
    parser.add_argument('--replay-db');parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=8766)
    parser.add_argument('--default-mcp-purpose',choices=[p.value for p in Purpose],default=Purpose.GROUND_INTERNAL_LLM.value)
    parser.add_argument('--dsn',default=os.environ.get('KNOWLEDGE_SDK_DSN'))
    args=parser.parse_args(argv)
    try:
        context=stdio_context() if args.transport=='stdio' else None
        if args.transport=='http':
            try:import uvicorn,fastapi
            except ImportError:raise ValidationError("Optional HTTP transport requires pip install 'knowledge-sdk[mcp]'") from None
        if args.replay_db and os.path.realpath(args.replay_db)==os.path.realpath(args.db):raise ValidationError('Replay database must be separate')
        from ..client.local import LocalKnowledgeClient
        from ..storage.sqlite_store import SQLiteStore
        if args.dsn:
            from ..server.postgres import postgres_client
            client=postgres_client(args.dsn)
        else:client=LocalKnowledgeClient(SQLiteStore(args.db))
        try:
            if context is not None:run_stdio(client,context)
            else:
                from ..server.auth import SQLiteReplayStore
                if args.dsn:
                    from ..server.replay_pg import PostgresReplayStore
                    replay=PostgresReplayStore(args.dsn)
                else:replay=SQLiteReplayStore(args.replay_db) if args.replay_db else None
                fallback=tuple(x.strip() for x in os.environ.get('KNOWLEDGE_AUTH_FALLBACK_SECRETS','').split(',') if x.strip())
                app=create_app(client,os.environ.get('KNOWLEDGE_AUTH_SECRET'),replay_store=replay,fallback_secrets=fallback,
                               default_mcp_purpose=Purpose(args.default_mcp_purpose),enable_demo_switcher=False)
                try:uvicorn.run(app,host=args.host,port=args.port,proxy_headers=False)
                finally:
                    if hasattr(replay,'close'):replay.close()
        finally:client.store.close()
    except (ValidationError,ValueError,TypeError):
        print("Invalid trusted MCP configuration; identity is required for stdio; HTTP requires a signing secret and pip install 'knowledge-sdk[mcp]'.",file=sys.stderr);return 2
    return 0
