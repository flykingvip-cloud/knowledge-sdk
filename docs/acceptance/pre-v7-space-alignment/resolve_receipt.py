"""SDK25 design/prototype final-source gate; no formal alignment approval."""
import argparse,datetime,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
PROTECTED={'refs/heads/feat/align-wave2-m2-min-slice':'9940818b962ccb186c0dfb0158de6bd9bd49057b','refs/heads/main':'b953c9922cc1096e0e88455dab6746c01a9d27f9','refs/heads/feat/align-wave1p8-pre-m2-foundation':'5a139e574ef68bcc045b70af32aee67f92c172b3','refs/heads/feat/align-wave1p5-m1-readiness':'0d2f172c2ca1c79483257953b5388098b7cdacaf','refs/heads/feat/align-wave1-core-compat':'60b6436ed9fccb4b49ae32e30f1664412e505888','refs/tags/v2.0.0':'4afc1d71f9f5583d93c28f3f4380544a4e5fcc46','refs/tags/v2.0.0^{}':'b953c9922cc1096e0e88455dab6746c01a9d27f9'}
def cmd(*args):return subprocess.check_output(list(args),cwd=ROOT,text=True)
def main():
    p=argparse.ArgumentParser();p.add_argument('--run-id',required=True);p.add_argument('--output',required=True);p.add_argument('--run-json');p.add_argument('--jobs-json');a=p.parse_args()
    output=Path(a.output).resolve();assert ROOT not in output.parents,'Receipt must be external to repository'
    sha=cmd('git','rev-parse','HEAD').strip();branch=cmd('git','branch','--show-current').strip();assert branch=='feat/space-alignment-v1-design-proto'
    run=json.loads(Path(a.run_json).read_text()) if a.run_json else json.loads(cmd('gh','api','repos/flykingvip-cloud/knowledge-sdk/actions/runs/'+a.run_id))
    jobs=json.loads(Path(a.jobs_json).read_text()) if a.jobs_json else json.loads(cmd('gh','api','repos/flykingvip-cloud/knowledge-sdk/actions/runs/'+a.run_id+'/jobs?per_page=100'))
    assert run['head_sha']==sha and run['head_branch']==branch and run['status']=='completed' and run['conclusion']=='success',run
    assert len(jobs['jobs'])==jobs['total_count']==37
    def dt(s):return datetime.datetime.fromisoformat(s.replace('Z','+00:00'))
    evidence=[]
    for job in jobs['jobs']:
        seconds=(dt(job['completed_at'])-dt(job['started_at'])).total_seconds()
        assert job['status']=='completed' and job['conclusion']=='success' and 0<=seconds<1080,(job['name'],seconds,job['conclusion'])
        evidence.append(dict(id=job['id'],name=job['name'],status=job['status'],conclusion=job['conclusion'],seconds=seconds,url=job['html_url'],started_at_cst=dt(job['started_at']).astimezone(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),completed_at_cst=dt(job['completed_at']).astimezone(datetime.timezone(datetime.timedelta(hours=8))).isoformat()))
    actual={ref:obj for obj,ref in (line.split() for line in cmd('git','ls-remote','origin',*PROTECTED).splitlines())};assert actual==PROTECTED,actual
    assert cmd('git','ls-remote','origin','refs/heads/'+branch).split()[0]==sha
    import importlib.util
    spec=importlib.util.spec_from_file_location('frozen',Path(__file__).with_name('verify_boundaries.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    result=dict(work_item='SDK-25',final_sha=sha,base_sha='9940818b962ccb186c0dfb0158de6bd9bd49057b',branch=branch,ci_run_id=int(a.run_id),ci_url=run['html_url'],conclusion='success',job_count=len(evidence),jobs=evidence,max_job_seconds=max(j['seconds'] for j in evidence),protected_remote_refs=actual,frozen=m.verify(),independent_acceptance='design_review_preparation_only',team_b_nomination=False,nonproduction_only=True,generated_at_cst=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat())
    output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(str(output))
if __name__=='__main__':main()
