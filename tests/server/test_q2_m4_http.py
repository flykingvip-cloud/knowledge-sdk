from __future__ import annotations
import importlib.util,os,subprocess,sys,unittest
from pathlib import Path

class EnterpriseWireTests(unittest.TestCase):
    @unittest.skipUnless(all(importlib.util.find_spec(m) for m in ('fastapi','uvicorn','cryptography')),'Optional enterprise HTTP dependencies unavailable')
    def test_real_oidc_hmac_scim_connectors_and_jwks(self):
        root=Path(__file__).resolve().parents[2];result=subprocess.run([sys.executable,'-W','error::ResourceWarning',str(root/'docs/acceptance/v2.0-q2-phase4/live_enterprise_probe.py')],cwd=root,env=dict(os.environ,PYTHONPATH=str(root/'src')+os.pathsep+str(root)),capture_output=True,text=True,timeout=120)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr);self.assertNotIn('ResourceWarning',result.stderr)
        for engine in ('sqlite','postgres') if os.environ.get('KNOWLEDGE_SDK_TEST_PG_DSN') else ('sqlite',):self.assertIn('"engine": "'+engine+'"',result.stdout)
        self.assertIn('"stale_privileged_jwt_and_cookie_denied": true',result.stdout)
