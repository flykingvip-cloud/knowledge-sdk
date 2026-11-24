from __future__ import annotations
import argparse
import os
import secrets
from ..client.local import LocalKnowledgeClient
from ..storage.sqlite_store import SQLiteStore
from .app import create_app
from .auth import SQLiteReplayStore

def main():
    parser=argparse.ArgumentParser(description="Run the optional knowledge-sdk HTTP service")
    parser.add_argument("--db",default=":memory:"); parser.add_argument("--host",default="127.0.0.1"); parser.add_argument("--port",type=int,default=8088)
    parser.add_argument("--dev-insecure",action="store_true",help="Local development only: trust unsigned Actor headers")
    parser.add_argument("--demo-seed",action="store_true",help="Isolated local demo with identity switcher; never use with production data")
    parser.add_argument("--no-ui",action="store_true",help="Disable the optional Workbench")
    parser.add_argument("--replay-db", help="Dedicated SQLite replay database shared by all workers")
    parser.add_argument("--ui-prefix", default="/ui", help="Workbench path (not the API base)")
    args=parser.parse_args()
    if args.demo_seed and args.host not in ("127.0.0.1", "localhost", "::1"): parser.error("Demo must bind loopback")
    if args.demo_seed and (args.dev_insecure or args.no_ui): parser.error("Demo requires signed API and UI")
    if args.demo_seed and args.db != ":memory:": parser.error("Demo seed uses an isolated in-memory database only")
    if args.dev_insecure and args.host not in ("127.0.0.1","localhost","::1"): parser.error("Insecure mode must bind loopback")
    import uvicorn
    client=LocalKnowledgeClient(SQLiteStore(args.db))
    if args.demo_seed:
        from ..ui.demo import seed_demo
        seed_demo(client)
    app=create_app(client,auth_secret=secrets.token_hex(32) if args.demo_seed else os.environ.get("KNOWLEDGE_AUTH_SECRET"),
                   dev_insecure=args.dev_insecure,enable_ui=not args.no_ui,enable_demo_switcher=args.demo_seed,
                   replay_store=SQLiteReplayStore(args.replay_db) if args.replay_db else None,
                   fallback_secrets=tuple(v.strip() for v in os.environ.get("KNOWLEDGE_AUTH_FALLBACK_SECRETS", "").split(",") if v.strip()),
                   ui_prefix=args.ui_prefix)
    try: uvicorn.run(app,host=args.host,port=args.port,proxy_headers=False)
    finally: client.store.close()
if __name__=="__main__": main()
