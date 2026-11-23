from __future__ import annotations
import argparse
import os
from ..client.local import LocalKnowledgeClient
from ..storage.sqlite_store import SQLiteStore
from .app import create_app

def main():
    parser=argparse.ArgumentParser(description="Run the optional knowledge-sdk HTTP service")
    parser.add_argument("--db",required=True); parser.add_argument("--host",default="127.0.0.1"); parser.add_argument("--port",type=int,default=8088)
    parser.add_argument("--dev-insecure",action="store_true",help="Local development only: trust unsigned Actor headers")
    args=parser.parse_args()
    if args.dev_insecure and args.host not in ("127.0.0.1","localhost","::1"): parser.error("Insecure mode must bind loopback")
    import uvicorn
    app=create_app(LocalKnowledgeClient(SQLiteStore(args.db)),auth_secret=os.environ.get("KNOWLEDGE_AUTH_SECRET"),dev_insecure=args.dev_insecure)
    uvicorn.run(app,host=args.host,port=args.port)
if __name__=="__main__": main()
