"""Authoritative optional-extra/entrypoint/wheel/core-only and Python3.9 syntax evidence."""
from __future__ import annotations
import ast,configparser,hashlib,os,subprocess,sys,tempfile,zipfile
from email.parser import Parser
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
for folder in ('src','tests/benchmark'):
    files=sorted((ROOT/folder).rglob('*.py'))
    for path in files:ast.parse(path.read_text(),filename=str(path),feature_version=(3,9))
    print('Python3.9 AST PASS',folder,len(files),'files; not an actual3.9 runtime',flush=True)
wheel=ROOT/'dist/knowledge_sdk-1.2.0-py3-none-any.whl'
with zipfile.ZipFile(wheel) as archive:
    metadata=Parser().parsestr(archive.read('knowledge_sdk-1.2.0.dist-info/METADATA').decode())
    deps=metadata.get_all('Requires-Dist',[]);assert all('extra ==' in value for value in deps)
    from packaging.requirements import Requirement
    from packaging.specifiers import SpecifierSet
    optional=[Requirement(d) for d in deps if Requirement(d).marker.evaluate({'extra':'mcp','python_version':'3.9'})]
    assert {d.name for d in optional}=={'fastapi','uvicorn'}
    assert {d.name:str(d.specifier) for d in optional}=={'fastapi':str(SpecifierSet('>=0.100,<1')),'uvicorn':str(SpecifierSet('>=0.23,<1'))}
    assert not any(Requirement(d).name=='mcp' for d in deps)
    assert metadata['Version']=='1.2.0' and metadata['Requires-Python']=='>=3.9'
    config=configparser.ConfigParser();config.read_string(archive.read('knowledge_sdk-1.2.0.dist-info/entry_points.txt').decode())
    assert config['console_scripts']['knowledge-sdk-mcp']=='knowledge_sdk.mcp.server:main'
    for member in ('__init__.py','__main__.py','gateway.py','tools.py','protocol.py','server.py'):assert 'knowledge_sdk/mcp/'+member in archive.namelist()
    for member in ('audit/ledger.py','events/outbox.py','impact/webhook.py','contracts/audit.py','contracts/events.py','contracts/impact.py','impact/radar.py'):
        assert 'knowledge_sdk/'+member in archive.namelist()
    assert 'knowledge_sdk/mcp/transport.py' not in archive.namelist() and 'knowledge_sdk/mcp/handlers.py' not in archive.namelist()
    for member in ('index.html','workbench.css','workbench.js','i18n.js'):assert 'knowledge_sdk/ui/static/'+member in archive.namelist()
    with tempfile.TemporaryDirectory(prefix='kb-phase4-wheel-') as directory:
        archive.extractall(directory)
        code=r'''import importlib.abc,importlib.machinery,sys,sysconfig,os,io,json
stdlib=os.path.realpath(sysconfig.get_path('stdlib'))
class Block(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname.startswith('knowledge_sdk'):return
  spec=importlib.machinery.PathFinder.find_spec(fullname,path);origin=spec.origin if spec else None
  if origin and origin not in ('built-in','frozen'):
   origin=os.path.realpath(origin)
   if not origin.startswith(stdlib+os.sep) or 'site-packages' in origin:raise AssertionError('Third-party import '+fullname)
sys.meta_path.insert(0,Block())
from knowledge_sdk import *
from knowledge_sdk.mcp import *
import knowledge_sdk
assert 'src/knowledge_sdk' not in knowledge_sdk.__file__
c=LocalKnowledgeClient();a=Actor('u','o');ctx=GatewayContext(a)
try:
 k=c.create_kb(a,'k');c.ingest(a,k.kb_id,'wheel alpha',doc_id='d');tools=EvidenceTools(c)
 out=tools.call('search_evidence',{'query':'alpha'},ctx);assert out['hits'];uri=out['hits'][0]['source_uri']
 assert tools.call('verify_citation',{'source_uri':uri},ctx)['valid']
 assert tools.call('get_evidence_pack',{'source_uris':[uri]},ctx)['status']=='ok'
 assert tools.call('report_evidence_issue',{'source_uri':uri,'issue_type':'inaccuracy','description':'data'},ctx)['status']=='queued_for_review'
 assert c.store.db.execute('PRAGMA user_version').fetchone()[0]==3
 assert c.verify_audit_chain(Actor('u','o',org_roles=('admin',))).valid
 assert c.store._execute('SELECT COUNT(*) FROM outbox_events')[0][0]>=1
 assert c.store.list_usage_events_for_doc('o','d')
 c.ingest(a,k.kb_id,'updated wheel alpha',doc_id='d')
 assert c.drain_outbox(Actor('u','o',org_roles=('admin',))).failed==0
 assert any(e.impact_reason==ImpactReason.SUPERSEDED for e in c.list_impact_alerts(a))
finally:c.store.close()
from importlib.metadata import distribution
ep=next(e for e in distribution('knowledge-sdk').entry_points if e.name=='knowledge-sdk-mcp')
os.environ['KNOWLEDGE_MCP_ACTOR_JSON']='{"user_id":"u","org_id":"o"}'
for key in ('KNOWLEDGE_MCP_AGENT_JSON','KNOWLEDGE_MCP_PURPOSE'):os.environ.pop(key,None)
source=sys.stdin;sink=sys.stdout
try:
 sys.stdin=io.StringIO('{"jsonrpc":"2.0","id":1,"method":"initialize"}\n{"jsonrpc":"2.0","id":2,"method":"tools/list"}\n');sys.stdout=io.StringIO()
 assert ep.load()([])==0
 result=[json.loads(line) for line in sys.stdout.getvalue().splitlines()];assert len(result)==2 and len(result[1]['result']['tools'])==4
finally:sys.stdin=source;sys.stdout=sink
assert not any(name=='mcp' or name.startswith(('mcp.','fastapi','uvicorn')) for name in sys.modules)
print('Extracted-wheel python -S / third-party blocker / four tools / real console entrypoint stdio PASS')
'''
        subprocess.run([sys.executable,'-S','-W','error::ResourceWarning','-c',code],cwd=directory,env=dict(os.environ,PYTHONPATH=directory),check=True)
print('Version/core zero dependencies/exact mcp HTTP extra/schema3/UI resources/entrypoint PASS')
print('Wheel',wheel.name,'SHA256',hashlib.sha256(wheel.read_bytes()).hexdigest())
