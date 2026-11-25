"""Read-only exact historical-byte guard; emits no approval or runtime assertion."""
import hashlib,json,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
BASE='07f5d39f05ef4c7952be48b83025b9c86ea2458e'
PREDECESSOR='5a139e574ef68bcc045b70af32aee67f92c172b3'
def git(*args):return subprocess.check_output(['git']+list(args),cwd=ROOT)
def verify():
    manifest='docs/architecture/knowledge-sdk-alignment/m1-freeze-manifest.json'
    m=json.loads((ROOT/manifest).read_text())
    hashes=m['contract_asset_hashes'];assert len(hashes)==28
    checked={}
    for path,digest in hashes.items():
        actual=hashlib.sha256((ROOT/path).read_bytes()).hexdigest();assert actual==digest,path
        assert (ROOT/path).read_bytes()==git('show',BASE+':'+path),path
        checked[path]=actual
    paths=git('ls-tree','-r','--name-only',BASE,'docs/architecture/knowledge-sdk-alignment').decode().splitlines()
    for path in paths:assert (ROOT/path).read_bytes()==git('show',BASE+':'+path),path
    for tree in ['docs/architecture/knowledge-sdk-alignment/contracts','tests/benchmark']:
        assert not git('diff',BASE,'--',tree),tree
        assert not git('ls-files','--others','--exclude-standard','--',tree),tree
    assert (ROOT/'pyproject.toml').read_bytes()==git('show',PREDECESSOR+':pyproject.toml')
    assert re.search(r'^dependencies\s*=\s*\[\s*\]',(ROOT/'pyproject.toml').read_text(),re.M)
    return dict(passed=True,historical_baseline_sha=BASE,predecessor_sha=PREDECESSOR,contract_asset_count=len(checked),contract_asset_sha256=checked,architecture_tree_files_checked=len(paths),architecture_tree_byte_diff=0,benchmark_tree_byte_diff=0,pyproject_byte_diff=0,historical_status=m['status'],historical_manifest_sha256=hashlib.sha256((ROOT/manifest).read_bytes()).hexdigest())
if __name__=='__main__':print(json.dumps(verify(),indent=2,sort_keys=True))
