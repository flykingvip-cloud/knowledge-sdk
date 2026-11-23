from __future__ import annotations
import ast
import os
from pathlib import Path
import subprocess
import sys
import unittest
class IsolationTests(unittest.TestCase):
    def test_core_end_to_end_without_site_packages(self):
        root=Path(__file__).resolve().parents[2]
        code="""
import sys
from knowledge_sdk import Actor, LocalKnowledgeClient
c=LocalKnowledgeClient(); a=Actor('u','o'); k=c.create_kb(a,'K'); v=c.ingest(a,k.kb_id,'independent 知识库')
assert c.search(a,'知识库').hits
assert c.retrieve(a,v.doc_id).text=='independent 知识库'
assert c.consume(a,c.reference(a,v.doc_id)).status=='consumed'
c.archive(a,v.doc_id); assert not c.search(a,'independent').hits
c.restore(a,v.doc_id); assert c.search(a,'independent').hits
assert not any(m.split('.')[0] in ('flask','stratai','openai','anthropic','qdrant_client','fastapi','pypdf') for m in sys.modules)
print('core isolation passed')
"""
        result=subprocess.run([sys.executable,"-S","-c",code],env={**os.environ,"PYTHONPATH":str(root/"src")},capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
    def test_python39_syntax(self):
        root=Path(__file__).resolve().parents[2]
        for path in (root/"src").rglob("*.py"):
            source=path.read_text(); ast.parse(source,feature_version=(3,9))
            self.assertIn("from __future__ import annotations",source,str(path))
    def test_no_business_or_model_imports(self):
        root=Path(__file__).resolve().parents[2]
        for path in (root/"src").rglob("*.py"):
            tree=ast.parse(path.read_text())
            for node in ast.walk(tree):
                names=[a.name for a in node.names] if isinstance(node,ast.Import) else ([node.module or ""] if isinstance(node,ast.ImportFrom) else [])
                self.assertFalse(any(n.split('.')[0] in ("flask","stratai","openai","anthropic","qdrant_client") for n in names),str(path))
