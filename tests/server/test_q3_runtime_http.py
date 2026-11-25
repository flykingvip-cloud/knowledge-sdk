from __future__ import annotations
import importlib.util,os,subprocess,sys,unittest
from pathlib import Path

class RuntimeWire(unittest.TestCase):
    @unittest.skipUnless(all(importlib.util.find_spec(m) for m in ('fastapi','uvicorn')),'Optional HTTP dependencies unavailable')
    def test_actual_hmac_oidc_runtime_and_mcp_all_six_families(self):
        root=Path(__file__).resolve().parents[2]
        r=subprocess.run([sys.executable,'-W','error::ResourceWarning',str(root/'docs/acceptance/v2.1-q3-phase1/live_runtime_probe.py')],cwd=root,env=dict(os.environ,PYTHONPATH=str(root/'src')+os.pathsep+str(root)),capture_output=True,text=True,timeout=150)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr);self.assertNotIn('ResourceWarning',r.stderr)
        self.assertIn('"six_families": true',r.stdout)
        if os.environ.get('KNOWLEDGE_SDK_TEST_PG_DSN'):self.assertIn('"engine": "postgres"',r.stdout)
