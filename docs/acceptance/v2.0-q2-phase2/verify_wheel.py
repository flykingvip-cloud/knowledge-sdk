"""Build/AST/extracted-wheel smoke: stdlib SQLite plus real optional PG modules."""
from pathlib import Path
import ast
import hashlib
import json
import os
import subprocess
import sys
import zipfile

root=Path(__file__).resolve().parents[3]
artifacts=Path('/workspace/knowledge-sdk-q2m2-artifacts');artifacts.mkdir(exist_ok=True)
for folder in ('src','tests/benchmark'):
    files=list((root/folder).rglob('*.py'))
    for path in files:ast.parse(path.read_text(),feature_version=(3,9))
    print('AST Python 3.9 PASS',folder,len(files))
subprocess.run([sys.executable,'-m','build','--outdir',str(artifacts)],cwd=root,check=True)
wheel=next(artifacts.glob('*.whl'));target=artifacts/'extracted-wheel';target.mkdir(exist_ok=True)
with zipfile.ZipFile(wheel) as archive:
    archive.extractall(target)
    expected=['knowledge_sdk/storage/postgres_store.py','knowledge_sdk/storage/migrations.py','knowledge_sdk/storage/pg_support.py','knowledge_sdk/storage/postgres_schema.sql','knowledge_sdk/storage/dr_drill.py','knowledge_sdk/retrieval/adapters/pgvector_index.py','knowledge_sdk/server/replay_pg.py','knowledge_sdk/server/postgres.py']
    assert set(expected)<=set(archive.namelist())
    metadata=archive.read('knowledge_sdk-1.2.0.dist-info/METADATA').decode()
    assert all('extra ==' in line for line in metadata.splitlines() if line.startswith('Requires-Dist:'))
    entry=archive.read('knowledge_sdk-1.2.0.dist-info/entry_points.txt').decode()
    assert 'knowledge-sdk-migrate = knowledge_sdk.storage.migrations:main' in entry
print('WHEEL SHA256',hashlib.sha256(wheel.read_bytes()).hexdigest())
env=dict(os.environ,PYTHONPATH=str(target))
stdlib='''import sys
import knowledge_sdk
assert '/extracted-wheel/' in knowledge_sdk.__file__
from knowledge_sdk import Actor,LocalKnowledgeClient
from knowledge_sdk.storage.postgres_store import PostgresStore
from knowledge_sdk.retrieval.adapters.pgvector_index import PgVectorIndex
from knowledge_sdk.server.replay_pg import PostgresReplayStore
from knowledge_sdk.exceptions import ValidationError
c=LocalKnowledgeClient();a=Actor('a','org');k=c.create_kb(a,'k',visibility='enterprise');c.ingest(a,k.kb_id,'知识库 alpha');assert c.search(a,'知识库').hits;c.store.close()
try:PostgresStore('not-a-connection')
except ValidationError as e:assert 'knowledge-sdk[postgres]' in str(e)
else:raise AssertionError('Driver must not be available under -S')
assert 'psycopg' not in sys.modules
print('Extracted wheel stdlib SQLite / optional lazy imports PASS')
'''
subprocess.run([sys.executable,'-S','-W','error::ResourceWarning','-c',stdlib],cwd='/workspace',env=env,check=True)
# Instantiate all new optional classes against a real disposable schema.
sys.path.insert(0,str(root))
from tests.pg_helpers import PgSandbox
sandbox=PgSandbox()
try:
    env['KNOWLEDGE_SDK_DSN']=sandbox.dsn
    code='''import os, knowledge_sdk
assert '/extracted-wheel/' in knowledge_sdk.__file__
from knowledge_sdk.storage.postgres_store import PostgresStore
from knowledge_sdk.retrieval.adapters.pgvector_index import PgVectorIndex
from knowledge_sdk.server.replay_pg import PostgresReplayStore
from knowledge_sdk.storage.migrations import status
s=PostgresStore(os.environ['KNOWLEDGE_SDK_DSN']);v=PgVectorIndex(store=s,dimensions=3);r=PostgresReplayStore(os.environ['KNOWLEDGE_SDK_DSN'])
assert status(s.db)['version']==3
assert r.check_and_record('wheel','nonce',110.,now=100.)
assert not r.check_and_record('wheel','nonce',110.,now=100.)
r.close();s.close()
print('Extracted wheel real PostgreSQL / pgvector / replay PASS')
'''
    subprocess.run([sys.executable,'-W','error::ResourceWarning','-c',code],cwd='/workspace',env=env,check=True)
finally:sandbox.close()
print('BUILD AND EXTRACTED WHEEL PASS')
