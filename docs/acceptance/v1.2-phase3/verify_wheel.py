"""Additional Phase3 wheel-only -S runtime check, using a temporary extraction."""
from __future__ import annotations
from pathlib import Path
import hashlib,os,subprocess,sys,tempfile,zipfile
ROOT=Path(__file__).resolve().parents[3]
wheel=ROOT/'dist/knowledge_sdk-1.2.0-py3-none-any.whl'
with tempfile.TemporaryDirectory(prefix='kb-wheel-phase3-') as directory:
    with zipfile.ZipFile(wheel) as archive:
        for member in ('knowledge_sdk/contracts/anchors.py','knowledge_sdk/contracts/reanchor.py',
                       'knowledge_sdk/ingestion/parsers/layout.py','knowledge_sdk/client/anchors.py'):
            assert member in archive.namelist(),member
        archive.extractall(directory)
    code='''from knowledge_sdk import *
import knowledge_sdk
from knowledge_sdk.contracts.models import encode,decode
import json
from knowledge_sdk.contracts.uri import parse_uri_v2
assert "src/knowledge_sdk" not in knowledge_sdk.__file__
c=LocalKnowledgeClient();a=Actor("wheel-admin","wheel-org")
try:
    k=c.create_kb(a,"wheel")
    v=c.ingest(a,k.kb_id,"compound,activity,units\\nA,>10000,nM",filename="assay.csv")
    anchor=c.list_anchors(a,v.doc_id)[0]
    assert anchor.table_cell.unit_hint=="nM"
    assert decode(json.loads(json.dumps(encode(anchor))))==anchor
    ref=c.reference(a,v.doc_id,anchor_id=anchor.anchor_id)
    assert parse_uri_v2(ref.source_uri).anchor_id==anchor.anchor_id
    assert c.consume(a,ref).evidence_kind=="anchor_excerpt"
    assert c.store.db.execute("PRAGMA user_version").fetchone()[0]==2
    assert knowledge_sdk.__version__=="1.2.0"
finally:c.store.close()
print("Extracted wheel -S CSV/anchors/JSON/ref/schema2 runtime: PASS")
'''
    subprocess.run([sys.executable,'-S','-W','error::ResourceWarning','-c',code],cwd=directory,
                   env=dict(os.environ,PYTHONPATH=directory),check=True)
print('Phase3 wheel module inclusion: PASS')
print('Wheel:',wheel.name,'SHA256:',hashlib.sha256(wheel.read_bytes()).hexdigest())
