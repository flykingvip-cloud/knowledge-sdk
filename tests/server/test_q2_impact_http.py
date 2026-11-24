from __future__ import annotations
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest


class ImpactWireTests(unittest.TestCase):
    @unittest.skipUnless(all(importlib.util.find_spec(m) is not None for m in ('fastapi','uvicorn')),'optional HTTP dependencies unavailable')
    def test_actual_signed_http_impact_and_real_webhook(self):
        root=Path(__file__).resolve().parents[2]
        import os
        env=dict(os.environ,PYTHONPATH=str(root/'src')+os.pathsep+str(root))
        result=subprocess.run([sys.executable,'-W','error::ResourceWarning',str(root/'docs/acceptance/v2.0-q2-phase1/live_impact_probe.py')],
            cwd=root,env=env,capture_output=True,text=True,timeout=90)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('14/14 impact alert IDs covered',result.stdout)
        self.assertIn('old source versions and receipts unchanged',result.stdout)
        self.assertNotIn('ResourceWarning:',result.stdout+result.stderr)

    @unittest.skipUnless(all(importlib.util.find_spec(m) is not None for m in ('fastapi','httpx')),'optional HTTP dependencies unavailable')
    def test_event_apis_never_accept_dev_insecure_identities(self):
        from fastapi.testclient import TestClient
        from knowledge_sdk import LocalKnowledgeClient
        from knowledge_sdk.server.app import create_app
        c=LocalKnowledgeClient();self.addCleanup(c.store.close)
        with TestClient(create_app(c,dev_insecure=True,enable_ui=False)) as http:
            for path in ('/v1/audit/query','/v1/audit/verify','/v1/impact/alerts','/v1/impact/ack','/v1/events/drain','/v1/outbox/drain'):
                self.assertEqual(http.post(path,json={'params':{}}).status_code,401)
            self.assertEqual(http.get('/v1/health').status_code,200)
