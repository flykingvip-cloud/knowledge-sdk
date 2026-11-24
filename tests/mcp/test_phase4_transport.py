from __future__ import annotations
import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path

class OptionalTransportTests(unittest.TestCase):
    def test_stdlib_module_imports_without_wire_dependencies(self):
        import knowledge_sdk.mcp
        self.assertTrue(callable(knowledge_sdk.mcp.EvidenceTools))
        code='''import importlib.abc,importlib.machinery,os,sys,sysconfig
stdlib=os.path.realpath(sysconfig.get_path('stdlib'))
class Block(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname.startswith('knowledge_sdk'):return None
  spec=importlib.machinery.PathFinder.find_spec(fullname,path)
  origin=spec.origin if spec else None
  if origin and origin not in ('built-in','frozen'):
   origin=os.path.realpath(origin)
   if not origin.startswith(stdlib+os.sep) or 'site-packages' in origin or 'dist-packages' in origin:
    raise AssertionError('Non-stdlib import '+fullname)
sys.meta_path.insert(0,Block())
import knowledge_sdk.mcp
from knowledge_sdk import LocalKnowledgeClient
c=LocalKnowledgeClient();c.store.close()
'''
        subprocess.run([sys.executable,'-S','-W','error::ResourceWarning','-c',code],check=True)
    def test_missing_extra_cli_fails_before_opening_databases(self):
        import os,secrets,tempfile
        with tempfile.TemporaryDirectory() as directory:
            db=Path(directory)/'must-not-exist.db';replay=Path(directory)/'must-not-exist-replay.db'
            result=subprocess.run([sys.executable,'-S','-m','knowledge_sdk.mcp','--db',str(db),'--replay-db',str(replay)],
                env=dict(os.environ,KNOWLEDGE_AUTH_SECRET=secrets.token_hex(32)),capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0);self.assertIn('identity is required',result.stderr)
            self.assertFalse(db.exists());self.assertFalse(replay.exists())
    @unittest.skipUnless(all(importlib.util.find_spec(m) is not None for m in ('fastapi','httpx','uvicorn')),'optional HTTP dependencies unavailable')
    def test_actual_jsonrpc_http_and_stdio_four_tools(self):
        root=Path(__file__).resolve().parents[2]
        result=subprocess.run([sys.executable,'-W','error::ResourceWarning',str(root/'docs/acceptance/v2.0-q2-phase1/live_mcp_probe.py')],cwd=root,capture_output=True,text=True,timeout=120)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('L3 actual JSON-RPC HTTP + stdio probe PASS',result.stdout)
        self.assertNotIn('ResourceWarning:',result.stdout+result.stderr)
