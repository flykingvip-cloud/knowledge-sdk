"""Reproducible AST, wheel RECORD and extracted-wheel standard-library checks."""
from __future__ import annotations
import ast,base64,csv,hashlib,io,json,os,subprocess,sys,zipfile
from pathlib import Path

def main():
    root=Path(__file__).parents[3];artifacts=Path(sys.argv[1]);paths=list((root/'src').rglob('*.py'))+list((root/'tests/benchmark').rglob('*.py'))
    for p in paths:ast.parse(p.read_text(),filename=str(p),feature_version=(3,9))
    print('Python 3.9 AST passed:',len(paths),'files')
    import tomllib
    assert tomllib.loads((root/'pyproject.toml').read_text())['project']['dependencies']==[]
    print('Core dependencies = [] verified')
    wheel=next((artifacts/'packages').glob('*.whl'));destination=artifacts/'extracted-wheel';count=0
    with zipfile.ZipFile(wheel) as z:
        names=z.namelist();record=next(n for n in names if n.endswith('.dist-info/RECORD'))
        for name,digest,length in csv.reader(io.StringIO(z.read(record).decode())):
            if not digest:continue
            alg,value=digest.split('=',1);raw=z.read(name);assert alg=='sha256' and base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).decode().rstrip('=')==value;assert len(raw)==int(length);count+=1
        for required in ('knowledge_sdk/server/oidc.py','knowledge_sdk/server/scim.py','knowledge_sdk/connectors/filesystem.py','knowledge_sdk/connectors/webhook_sync.py','knowledge_sdk/ui/static/enterprise.html','knowledge_sdk/ui/static/enterprise.js'):assert required in names
        z.extractall(destination)
    result={'wheel':wheel.name,'sha256':hashlib.sha256(wheel.read_bytes()).hexdigest(),'record_hashes_verified':count,'enterprise_modules_and_assets':True}
    (artifacts/'wheel-record.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,sort_keys=True))
    code='''
import knowledge_sdk
from knowledge_sdk import Actor,LocalKnowledgeClient
from knowledge_sdk.server.oidc import OIDCAuthenticator
from knowledge_sdk.server.scim import SCIMService
assert 'extracted-wheel' in knowledge_sdk.__file__
c=LocalKnowledgeClient()
try:
 a=Actor('admin','wheel',org_roles=('admin',));c.create_kb(a,'Wheel','enterprise',kb_id='k');c.ingest(a,'k','alpha wheel evidence',doc_id='d');SCIMService(c).write(a,{'id':'reader'});u=Actor('reader','wheel',policy_generation='1');assert c.retrieve(u,'d').text
 SCIMService(c).write(a,{'active':False},'reader')
 try:c.retrieve(u,'d')
 except knowledge_sdk.PermissionDeniedError:pass
 else:raise AssertionError('Wheel stale identity allowed')
 print('Extracted-wheel -S schema4 retrieval SCIM immediate revocation passed')
finally:c.store.close()
'''
    subprocess.run([sys.executable,'-S','-W','error::ResourceWarning','-c',code],cwd=artifacts,env=dict(os.environ,PYTHONPATH=str(destination)),check=True)
if __name__=='__main__':main()
