"""The acceptance probe runs actual loopback HTTP, not ASGI TestClient mocks."""
from __future__ import annotations
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import unittest

class GovernanceWireTests(unittest.TestCase):
    @unittest.skipUnless(all(importlib.util.find_spec(m) for m in ('fastapi','uvicorn')),'Optional HTTP dependencies unavailable')
    def test_real_signed_three_identity_governance_and_pack_revocation(self):
        root=Path(__file__).resolve().parents[2]
        env=dict(os.environ,PYTHONPATH=str(root/'src')+os.pathsep+str(root))
        process=subprocess.run([sys.executable,'-W','error::ResourceWarning',str(root/'docs/acceptance/v2.0-q2-phase3/live_governance_probe.py')],cwd=root,env=env,capture_output=True,text=True,timeout=120)
        self.assertEqual(process.returncode,0,process.stdout+process.stderr)
        for engine in ('sqlite','postgres') if env.get('KNOWLEDGE_SDK_TEST_PG_DSN') else ('sqlite',):self.assertIn('PASS '+engine+' revoke -> get/json/zip 403',process.stdout)
        self.assertNotIn('ResourceWarning',process.stderr)
