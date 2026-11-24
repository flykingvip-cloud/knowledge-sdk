"""Build, AST3.9 syntax, wheel RECORD integrity, isolated extracted-wheel M3."""
from __future__ import annotations
import ast
import base64
import csv
import hashlib
import io
import os
from pathlib import Path
import subprocess
import sys
import zipfile

root=Path(__file__).resolve().parents[3]
artifacts=Path('/workspace/knowledge-sdk-q2m3-artifacts');artifacts.mkdir(exist_ok=True)
for folder in ('src','tests/benchmark'):
    files=list((root/folder).rglob('*.py'))
    for path in files:ast.parse(path.read_text(),feature_version=(3,9))
    print('AST3.9 syntax PASS',folder,len(files),flush=True)
print('Python3.9 runtime NOT_RUN: this interpreter is',sys.version.split()[0],flush=True)
subprocess.run([sys.executable,'-m','build','--outdir',str(artifacts)],cwd=root,check=True)
wheel=next(artifacts.glob('*.whl'));target=artifacts/'extracted-wheel';target.mkdir(exist_ok=True)
with zipfile.ZipFile(wheel) as archive:
    archive.extractall(target)
    required=['knowledge_sdk/'+p for p in ('governance/workflow.py','governance/issues.py','governance/cli.py','packs/service.py','packs/export.py','contracts/governance.py','contracts/packs.py','storage/postgres_schema.sql')]
    assert set(required)<=set(archive.namelist())
    metadata=archive.read('knowledge_sdk-1.2.0.dist-info/METADATA').decode()
    assert all('extra ==' in line for line in metadata.splitlines() if line.startswith('Requires-Dist:'))
    entry=archive.read('knowledge_sdk-1.2.0.dist-info/entry_points.txt').decode()
    assert 'knowledge-sdk-governance = knowledge_sdk.governance.cli:main' in entry
    records=list(csv.reader(io.StringIO(archive.read('knowledge_sdk-1.2.0.dist-info/RECORD').decode())))
    for path,digest,size in records:
        if not digest:continue
        data=archive.read(path);algorithm,expected=digest.split('=',1)
        assert algorithm=='sha256' and base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip('=')==expected
        assert len(data)==int(size)
print('WHEEL RECORD SHA256/size integrity PASS',len(records),'entries; not a publisher cryptographic signature',flush=True)
print('WHEEL SHA256',hashlib.sha256(wheel.read_bytes()).hexdigest(),flush=True)
code='''import os,sys,json,base64,io,zipfile
import knowledge_sdk
assert '/extracted-wheel/' in knowledge_sdk.__file__
from knowledge_sdk import Actor,LocalKnowledgeClient,ResourceRights,PermissionDeniedError
if os.environ.get('WHEEL_M3_PG_DSN'):
 from knowledge_sdk.server.postgres import postgres_client
 c=postgres_client(os.environ['WHEEL_M3_PG_DSN'],pgvector_dims=32)
else:c=LocalKnowledgeClient()
a=Actor('a','wheel',org_roles=('admin',));r=Actor('r','wheel',org_roles=('admin',));p=Actor('p','wheel',org_roles=('admin',))
try:
 c.create_kb(a,'k','enterprise',kb_id='k',space_type='enterprise_public',governance_tier='l2_controlled')
 c.ingest(a,'k','wheel evidence',doc_id='d',rights=ResourceRights(allow_export=True))
 c.submit_for_review(a,'d',expected_version=1);c.approve_release(r,'d',version=1,expected_version=1);c.publish_release(p,'d',version=1,expected_version=1)
 pack=c.create_evidence_pack(a,'sealed',[{'doc_id':'d','version':1,'stance':'negative'}])
 assert c.verify_evidence_pack(a,pack.pack_id).digest_valid
 exported=c.export_evidence_pack(a,pack.pack_id,format='ro_crate')
 with zipfile.ZipFile(io.BytesIO(base64.b64decode(exported.content))) as archive:assert 'ro-crate-metadata.json' in archive.namelist()
 c.set_document_rights(a,'d',ResourceRights(revoked=True))
 try:c.export_evidence_pack(a,pack.pack_id)
 except PermissionDeniedError:pass
 else:raise AssertionError('Revoked pack exported')
finally:c.store.close()
print('EXTRACTED WHEEL M3 PASS', 'postgres' if os.environ.get('WHEEL_M3_PG_DSN') else 'stdlib SQLite')
'''
env=dict(os.environ,PYTHONPATH=str(target))
subprocess.run([sys.executable,'-S','-W','error::ResourceWarning','-c',code],cwd='/workspace',env=env,check=True)
assert not os.environ.get('WHEEL_M3_PG_DSN')
if os.environ.get('KNOWLEDGE_SDK_TEST_PG_DSN'):
    sys.path.insert(0,str(root));from tests.pg_helpers import PgSandbox
    sandbox=PgSandbox()
    try:
        env['WHEEL_M3_PG_DSN']=sandbox.dsn
        subprocess.run([sys.executable,'-W','error::ResourceWarning','-c',code],cwd='/workspace',env=env,check=True)
    finally:sandbox.close()
print('BUILD / RECORD / EXTRACTED WHEEL PASS',flush=True)
