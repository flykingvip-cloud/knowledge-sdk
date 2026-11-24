"""Phase4 optional marker, wheel resources and core-only extracted wheel runtime."""
from __future__ import annotations
from pathlib import Path
from email.parser import Parser
import ast,hashlib,os,subprocess,sys,tempfile,zipfile
ROOT=Path(__file__).resolve().parents[3];wheel=ROOT/'dist/knowledge_sdk-1.2.0-py3-none-any.whl'
files=sorted((ROOT/'src').rglob('*.py'))
for path in files:ast.parse(path.read_text(),filename=str(path),feature_version=(3,9))
print('Python3.9 AST syntax PASS:',len(files),'src files; not actual Python3.9 runtime')
with zipfile.ZipFile(wheel) as archive:
    metadata=Parser().parsestr(archive.read('knowledge_sdk-1.2.0.dist-info/METADATA').decode())
    deps=metadata.get_all('Requires-Dist',[]);assert all('extra ==' in dep for dep in deps)
    optional=[dep for dep in deps if dep.startswith('mcp')];assert len(optional)==1 and '3.10' in optional[0] and 'mcp' in optional[0]
    assert metadata['Version']=='1.2.0' and metadata['Requires-Python']=='>=3.9'
    from packaging.requirements import Requirement
    marker=Requirement(optional[0]).marker
    assert not marker.evaluate({'python_version':'3.9','extra':'mcp'})
    assert marker.evaluate({'python_version':'3.13','extra':'mcp'})
    print('Core zero dependencies / mcp optional Python>=3.10 marker PASS:',optional[0])
    for member in ('__init__.py','__main__.py','gateway.py','handlers.py','transport.py'):assert 'knowledge_sdk/mcp/'+member in archive.namelist()
    for member in ('index.html','workbench.css','workbench.js','i18n.js'):assert 'knowledge_sdk/ui/static/'+member in archive.namelist()
    with tempfile.TemporaryDirectory(prefix='kb-phase4-wheel-') as directory:
        archive.extractall(directory)
        code='''import importlib.abc,importlib.machinery,sys,sysconfig,os
stdlib=os.path.realpath(sysconfig.get_path('stdlib'))
class Block(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname.startswith('knowledge_sdk'):return
  spec=importlib.machinery.PathFinder.find_spec(fullname,path)
  origin=spec.origin if spec else None
  if origin and origin not in ('built-in','frozen'):
   origin=os.path.realpath(origin)
   if not origin.startswith(stdlib+os.sep) or 'site-packages' in origin:raise AssertionError('Third party import '+fullname)
sys.meta_path.insert(0,Block())
from knowledge_sdk import *
from knowledge_sdk.mcp import *
import knowledge_sdk
assert 'src/knowledge_sdk' not in knowledge_sdk.__file__
c=LocalKnowledgeClient();a=Actor('u','o');ag=AgentIdentity('g','o');ctx=GatewayContext(a,ag,Purpose.GROUND_INTERNAL_LLM)
try:
 k=c.create_kb(a,'k');c.ingest(a,k.kb_id,'wheel alpha',doc_id='d');t=EvidenceTools(c)
 out=t.call('search_evidence',{'query':'alpha'},ctx);assert out['hits']
 uri=out['hits'][0]['source_uri'];assert t.call('verify_citation',{'source_uri':uri},ctx)['valid']
 assert t.call('get_evidence_pack',{'source_uris':[uri]},ctx)['status']=='ok'
 assert t.call('report_evidence_issue',{'source_uri':uri,'issue_type':'inaccuracy','description':'fixture'},ctx)['status']=='queued_for_review'
 assert c.store.db.execute('PRAGMA user_version').fetchone()[0]==2
finally:c.store.close()
assert not any(k=='mcp' or k.startswith('mcp.') for k in sys.modules)
print('Wheel-only python -S four-tool runtime with third-party import blocker PASS')
'''
        subprocess.run([sys.executable,'-S','-W','error::ResourceWarning','-c',code],cwd=directory,env=dict(os.environ,PYTHONPATH=directory),check=True)
print('Wheel resources / optional module inclusion PASS')
print('Wheel:',wheel.name,'SHA256:',hashlib.sha256(wheel.read_bytes()).hexdigest())
