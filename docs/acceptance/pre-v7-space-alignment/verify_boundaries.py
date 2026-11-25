"""Exact baseline-byte guard plus unchanged historical28 verification."""
import hashlib,importlib.util,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE='9940818b962ccb186c0dfb0158de6bd9bd49057b'
def git(*args):return subprocess.check_output(['git']+list(args),cwd=ROOT)
def verify():
    changed=[];count=0
    for line in git('ls-tree','-r',BASE).decode().splitlines():
        header,path=line.split('\t',1);mode,kind,digest=header.split()
        if kind!='blob':continue
        raw=(ROOT/path).read_bytes()
        if path=='.github/workflows/tests.yml':
            assert raw.startswith(git('show',BASE+':'+path)),'Existing36job workflow bytes changed'
            continue
        actual=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        if actual!=digest:changed.append(path)
        count+=1
    assert not changed,changed
    allowed=('contracts/space-alignment-v1/','sandbox/space_alignment_v1/','docs/acceptance/pre-v7-space-alignment/')
    additions=git('diff','--name-only','--diff-filter=A',BASE).decode().splitlines()
    assert all(path.startswith(allowed)for path in additions),additions
    spec=importlib.util.spec_from_file_location('historical',ROOT/'docs/acceptance/v2.2-align-wave2/verify_frozen.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);frozen=m.verify()
    status=json.loads((ROOT/'contracts/space-alignment-v1/status.json').read_text())
    for flag in('schema_v7_ddl_authorized','migration_authorized','prod_shadow_or_cutover_authorized','final_alignment_frozen'):assert status[flag]is False
    assert all(v=='NOT_MET'for v in status['exit_gates'].values())
    return dict(status='DESIGN_PROTOTYPE_ONLY',base_sha=BASE,baseline_files_byte_checked=count,baseline_file_drift=0,schema6_and_runtime_byte_drift=0,historical=frozen,authorization_flags={k:status[k]for k in('schema_v7_ddl_authorized','migration_authorized','prod_shadow_or_cutover_authorized','final_alignment_frozen')})
if __name__=='__main__':print(json.dumps(verify(),indent=2,sort_keys=True))
