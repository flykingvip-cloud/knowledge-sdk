"""Non-demo HTTP/MCP-only container entry point; secrets are mounted files."""
from __future__ import annotations
import os
from pathlib import Path
from ..client.local import LocalKnowledgeClient
from ..storage.sqlite_store import SQLiteStore
from .app import create_app
from .auth import SQLiteReplayStore


def main():
    import uvicorn
    owned=None;replay=None;app=None
    try:
        secret=Path(os.environ.get('KNOWLEDGE_AUTH_SECRET_FILE','/run/secrets/knowledge_auth_secret')).read_text().strip()
        if len(secret)<32:raise ValueError()
        dsn=os.environ.get('KNOWLEDGE_SDK_DSN')
        if dsn:
            app=create_app(auth_secret=secret,dsn=dsn,enable_ui=False,enable_mcp=True)
        else:
            owned=LocalKnowledgeClient(SQLiteStore('/data/knowledge.sqlite'))
            replay=SQLiteReplayStore('/data/replay.sqlite')
            app=create_app(owned,auth_secret=secret,replay_store=replay,enable_ui=False,enable_mcp=True)
        uvicorn.run(app,host='0.0.0.0',port=8088,proxy_headers=False,access_log=False)
    except Exception:raise SystemExit('Service startup failed; verify mounted configuration and storage (details withheld)') from None
    finally:
        if replay is not None:replay.close()
        if owned is not None:owned.store.close()

if __name__=='__main__':main()
