"""Stdlib package integrity / extracted-wheel runtime smoke. Run from repo root."""
from __future__ import annotations
import argparse,ast,base64,csv,hashlib,io,os
from pathlib import Path
import subprocess,sys,tempfile,zipfile


def main():
    parser=argparse.ArgumentParser();parser.add_argument('wheel',type=Path);args=parser.parse_args()
    root=Path.cwd();files=list(root.glob('src/**/*.py'))+list(root.glob('tests/**/*.py'))+list((root/'docs/acceptance/v2.1-q3-phase2').glob('*.py'))
    for p in files:ast.parse(p.read_text(),filename=str(p),feature_version=(3,9))
    print('Python 3.9 AST passed:',len(files))
    for name in ('golden_cases_v1.jsonl','golden_cases_v2.jsonl','g6.py','golden_cases_v3_enterprise.jsonl','g7_g8.py','golden_cases_v4_runtime.jsonl','g9.py'):
        p=Path('tests/benchmark')/name;old=subprocess.check_output(['git','show','69b6c986251161ca02b1e77b0806e2c8861a30b6:'+str(p)])
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
 from knowledge_sdk.retrieval.calibration import ScoreCalibrator
 assert ScoreCalibrator.from_dict(ScoreCalibrator().to_dict())==ScoreCalibrator()
 c.register_agent_profile(a,'agent');c.create_kb(a,'kb','enterprise',kb_id='kb');c.ingest(a,'kb','alpha original',doc_id='doc')
 hit=c.search(a,'alpha original',rerank=True,calibrator_id='default-v1',min_calibrated_score=.6).hits[0];assert hit.reranker_id=='lexical-v1' and hit.calibrated_score>=.6
 assert not c.search(a,'unknown irrelevant query',rerank=True,min_calibrated_score=.6).hits
 t=c.create_task_context(a,'agent');s=c.create_context_snapshot(a,t.task_id,'alpha original',rerank=True,min_calibrated_score=.6);assert s.items[0].text=='alpha original';assert decode(encode(s))==s
 c.update_agent_profile(a,'agent',active=False)
 try:c.read_task_snapshot(a,t.task_id,s.snapshot_id)
 except PermissionDeniedError:pass
 else:raise AssertionError('revoked wheel snapshot leaked')
finally:c.store.close()
print('Extracted wheel -S strict rerank/calibration/refusal/runtime smoke passed')'''
        subprocess.run([sys.executable,'-S','-W','error::ResourceWarning','-c',code],env=dict(os.environ,PYTHONPATH=directory),cwd=directory,check=True)
    assert 'dependencies = []' in (root/'pyproject.toml').read_text()
    print('Wheel RECORD verified; dependencies=[] unchanged')
    print(args.wheel.name,hashlib.sha256(args.wheel.read_bytes()).hexdigest())

if __name__=='__main__':main()
