"""Explicit optional MCP server; no .env loading, demo signer or stdio admin."""
from __future__ import annotations
import argparse
import importlib.util
import sys
import os
from pathlib import Path
from ..client.local import LocalKnowledgeClient
from ..storage.sqlite_store import SQLiteStore
from ..server.auth import SQLiteReplayStore
from . import create_app


def main():
    parser=argparse.ArgumentParser(description='Trusted-gateway MCP Streamable HTTP server (optional extra)')
    parser.add_argument('--db',required=True);parser.add_argument('--replay-db',required=True)
    parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--path',default='/mcp')
    parser.add_argument('--bound-purpose',choices=('ground_external_llm','ground_internal_llm'),default='ground_external_llm')
    parser.add_argument('--allowed-host',action='append');parser.add_argument('--allowed-origin',action='append',default=[])
    args=parser.parse_args()
    if Path(args.db).resolve()==Path(args.replay_db).resolve():parser.error('Replay database must be separate from business database')
    secret=os.environ.get('KNOWLEDGE_AUTH_SECRET','')
    fallbacks=tuple(part.strip() for part in os.environ.get('KNOWLEDGE_AUTH_FALLBACK_SECRETS','').split(',') if part.strip())
    if len(secret)<32 or any(len(part)<32 for part in fallbacks):parser.error('Configure strong authentication secrets in the trusted server environment')
    if sys.version_info<(3,10):parser.error("MCP wire requires Python >=3.10; Python 3.9 core remains supported")
    if importlib.util.find_spec('mcp') is None:parser.error("Install 'knowledge-sdk[mcp]' on Python >=3.10")
    try:import uvicorn
    except ImportError:parser.error("Install 'knowledge-sdk[mcp]' on Python >=3.10")
    client=LocalKnowledgeClient(SQLiteStore(args.db))
    try:
        app=create_app(client,auth_secret=secret,replay_store=SQLiteReplayStore(args.replay_db),fallback_secrets=fallbacks,
                       bound_purpose=args.bound_purpose,path=args.path,
                       allowed_hosts=args.allowed_host or ('127.0.0.1:*','localhost:*','[::1]:*'),allowed_origins=args.allowed_origin)
        uvicorn.run(app,host=args.host,port=args.port,proxy_headers=False)
    finally:client.store.close()

if __name__=='__main__':main()
