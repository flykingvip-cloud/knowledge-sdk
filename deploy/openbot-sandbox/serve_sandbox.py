"""Fixture-only signed HTTP/MCP host; not enterprise integration or a deployment."""
from __future__ import annotations
import os
from pathlib import Path
from seed_openbot_sandbox import connect
from knowledge_sdk.server.app import create_app

def main(state_dir="/data",secret_file="/run/secrets/knowledge_auth_secret",mode=None):
    import uvicorn
    root=Path(state_dir);mode=mode or os.environ.get('SANDBOX_MODE','sqlite');secret=Path(secret_file).read_text().strip()
    if len(secret)<32 or os.getuid()==0 or not (root/'seed-receipt.json').is_file():raise SystemExit('Prepared nonroot fixture with mounted key required')
    c=connect(root,mode,os.environ.get('KNOWLEDGE_SDK_DSN'))
    from knowledge_sdk.server.auth import SQLiteReplayStore
    try:
        replay=SQLiteReplayStore(str(root/'http-replay.sqlite'))
        uvicorn.run(create_app(c,auth_secret=secret,replay_store=replay,enable_ui=False,enable_mcp=True),host='0.0.0.0',port=8088,proxy_headers=False,access_log=False)
    # Replay store owns no persistent connection (per-call closing); no close API.
    finally:c.store.close()
if __name__=='__main__':
    try:main()
    except Exception:raise SystemExit('Fixture service failed; details withheld') from None
