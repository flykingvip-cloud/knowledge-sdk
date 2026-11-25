"""Stdlib package integrity / extracted-wheel runtime smoke. Run from repo root."""
from __future__ import annotations
import argparse,ast,base64,csv,hashlib,io,os
from pathlib import Path
import subprocess,sys,tempfile,zipfile


def main():
    parser=argparse.ArgumentParser();parser.add_argument('wheel',type=Path);args=parser.parse_args()
    root=Path.cwd();files=list(root.glob('src/**/*.py'))+list(root.glob('tests/benchmark/*.py'))
    for p in files:ast.parse(p.read_text(),filename=str(p),feature_version=(3,9))
    print('Python 3.9 AST passed:',len(files))
    for name in ('golden_cases_v1.jsonl','golden_cases_v2.jsonl','g6.py','golden_cases_v3_enterprise.jsonl','g7_g8.py'):
        p=Path('tests/benchmark')/name;old=subprocess.check_output(['git','show','a5d1432:'+str(p)])
        assert old==p.read_bytes();print(name,'byte-identical',hashlib.sha256(old).hexdigest())
    old=subprocess.check_output(['git','show','a5d1432:tests/benchmark/runner.py']).decode();new=(root/'tests/benchmark/runner.py').read_text();count=0
    for n in ast.parse(old).body:
        if isinstance(n,ast.FunctionDef) and n.name.startswith('g') and n.name[1:].isdigit():
            m=next(v for v in ast.parse(new).body if isinstance(v,ast.FunctionDef) and v.name==n.name)
            assert ast.get_source_segment(old,n)==ast.get_source_segment(new,m);count+=1
    assert count==60;print('Original runner scenario sources unchanged:',count)
    with tempfile.TemporaryDirectory(prefix='q3-wheel-verify-') as directory:
        with zipfile.ZipFile(args.wheel) as z:
            record=next(n for n in z.namelist() if n.endswith('/RECORD'))
            for name,digest,size in csv.reader(io.StringIO(z.read(record).decode())):
                if digest:
                    alg,value=digest.split('=');body=z.read(name)
                    assert base64.urlsafe_b64encode(hashlib.new(alg,body).digest()).rstrip(b'=').decode()==value
                    assert len(body)==int(size)
            z.extractall(directory)
        code='''from knowledge_sdk import *
from knowledge_sdk.contracts.models import encode,decode
c=LocalKnowledgeClient();a=Actor('a','o',org_roles=['admin'])
try:
 c.register_agent_profile(a,'agent');c.create_kb(a,'kb','enterprise',kb_id='kb');c.ingest(a,'kb','alpha original',doc_id='doc')
 t=c.create_task_context(a,'agent');s=c.create_context_snapshot(a,t.task_id,[{'doc_id':'doc'}]);assert s.items[0].text=='alpha original';assert decode(encode(s))==s
 c.update_agent_profile(a,'agent',active=False)
 try:c.read_task_snapshot(a,t.task_id,s.snapshot_id)
 except PermissionDeniedError:pass
 else:raise AssertionError('revoked wheel snapshot leaked')
finally:c.store.close()
print('Extracted wheel -S strict runtime smoke passed')'''
        subprocess.run([sys.executable,'-S','-W','error::ResourceWarning','-c',code],env=dict(os.environ,PYTHONPATH=directory),cwd=directory,check=True)
    assert 'dependencies = []' in (root/'pyproject.toml').read_text()
    print('Wheel RECORD verified; dependencies=[] unchanged')
    print(args.wheel.name,hashlib.sha256(args.wheel.read_bytes()).hexdigest())

if __name__=='__main__':main()
