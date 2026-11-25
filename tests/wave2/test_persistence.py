"""Real predecessor-v5 fixtures, in-place upgrades and durable process boundaries."""
import json
from contextlib import closing
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from knowledge_sdk import Actor, LocalKnowledgeClient, ConflictError, ValidationError, NotFoundError, PermissionDeniedError
from knowledge_sdk.storage.sqlite_store import SQLiteStore
from knowledge_sdk.storage.migration_v6 import upgrade_v6,schema_version,version_id,NEW_TABLES
from knowledge_sdk.storage.persistent_contracts import PersistentIdempotencyStore,PersistentIngestionJobStore
from knowledge_sdk.contracts.idempotency import IdempotencyDecision as D
from knowledge_sdk.contracts.ingestion_jobs import IngestionJobState as S,ALLOWED_TRANSITIONS


class PersistenceCases:
    pg=False
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        if self.pg:
            from tests.pg_helpers import PgSandbox
            self.sandbox=PgSandbox()
            self.addCleanup(self.sandbox.close)
            self.location=self.sandbox.dsn
            from knowledge_sdk.server.postgres import postgres_client
            self.client=postgres_client(self.location,pgvector_dims=32)
            self.store=self.client.store
        else:
            self.location=str(Path(self.temp.name)/'v5.sqlite')
            self.store=SQLiteStore(self.location)
            self.client=LocalKnowledgeClient(self.store)
        self.addCleanup(self.store.close)
        self.actor=Actor('owner','enterprise-a')
        self.kb=self.client.create_kb(self.actor,'predecessor',kb_id='existing-space')
        self.v1=self.client.ingest(self.actor,self.kb.kb_id,'原有 content alpha','v1.txt',doc_id='existing-doc')
        self.v2=self.client.ingest(self.actor,self.kb.kb_id,'原有 content beta','v2.txt',doc_id='existing-doc')
        self.assertEqual(schema_version(self.store),5)

    def connection(self):
        if self.pg:
            from knowledge_sdk.storage.postgres_store import PostgresStore
            return closing(PostgresStore(self.location,migrate=False))
        return closing(SQLiteStore(self.location))

    def upgrade(self):
        upgrade_v6(self.store,owned_nonproduction=True)
        self.assertEqual(schema_version(self.store),6)

    def snapshot(self):
        tables=['knowledge_bases','kb_members','documents','document_acls','chunks','evidence_anchors','audit_events','outbox_events','pending_indexes']
        data={}
        from contextlib import nullcontext
        with self.store.tenant_scope(self.actor.org_id) if self.pg else nullcontext():
            for table in tables:
                data[table]=sorted(self.store._execute('SELECT * FROM '+table),key=repr)
            cols='org_id,doc_id,version,data' if self.pg else 'doc_id,version,data'
            data['document_versions']=self.store._execute('SELECT '+cols+' FROM document_versions ORDER BY version')
            if self.pg:data['chunk_embeddings']=self.store._execute('SELECT * FROM chunk_embeddings ORDER BY doc_id,version,chunk_id')
        return data

    def test_byte_original_predecessor_writer_fixture_lossless_upgrade(self):
        import io,tarfile
        base='5a139e574ef68bcc045b70af32aee67f92c172b3'
        archive=subprocess.run(['git','archive',base,'src/knowledge_sdk'],check=True,capture_output=True).stdout
        predecessor=Path(self.temp.name)/'predecessor';predecessor.mkdir()
        with tarfile.open(fileobj=io.BytesIO(archive)) as files:
            for item in files:
                if item.isdir():continue
                self.assertTrue(item.isfile())
                target=predecessor/item.name
                target.resolve().relative_to(predecessor.resolve())
                target.parent.mkdir(parents=True,exist_ok=True)
                with files.extractfile(item) as stream:target.write_bytes(stream.read())
        program="""
import sys
from contextlib import closing
from knowledge_sdk import Actor,LocalKnowledgeClient,DocumentACL
from knowledge_sdk.storage.sqlite_store import SQLiteStore
from knowledge_sdk.server.postgres import postgres_client
pg,location=sys.argv[1:]
if pg=='1':c=postgres_client(location,pgvector_dims=32)
else:c=LocalKnowledgeClient(SQLiteStore(location))
try:
 a=Actor('owner','enterprise-a')
 c.create_kb(a,'original predecessor',kb_id='predecessor-space')
 c.ingest(a,'predecessor-space','predecessor historical alpha','old1.txt',doc_id='predecessor-doc')
 c.ingest(a,'predecessor-space','predecessor current beta','old2.txt',doc_id='predecessor-doc')
 c.set_document_acl(a,'predecessor-doc',DocumentACL(deny_users=['outsider']))
 query='SELECT MAX(version) FROM schema_migrations' if pg=='1' else 'PRAGMA user_version'
 assert c.store._execute(query)==[(5,)]
finally:c.store.close()
"""
        env=dict(os.environ,PYTHONPATH=str(predecessor/'src'))
        result=subprocess.run([sys.executable,'-W','error::ResourceWarning','-c',program,str(int(self.pg)),self.location],env=env,capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertNotIn('ResourceWarning',result.stderr)
        before=self.snapshot();self.upgrade();self.assertEqual(before,self.snapshot())
        self.assertEqual(self.store.get_document('predecessor-doc').current_version,2)
        self.assertTrue(version_id(self.store,self.actor.org_id,'predecessor-doc',1))
        self.assertTrue(self.client.search(self.actor,'predecessor'))

    def test_true_v5_lossless_upgrade_search_and_repeatability(self):
        old_search=self.client.search(self.actor,'beta')
        self.assertTrue(old_search)
        before=self.snapshot()
        self.upgrade()
        self.assertEqual(before,self.snapshot())
        self.assertEqual(old_search,self.client.search(self.actor,'beta'))
        ids=[version_id(self.store,self.actor.org_id,'existing-doc',v) for v in (1,2)]
        self.assertEqual(len(set(ids)),2)
        self.assertTrue(all(isinstance(v,str) and len(v)>=32 for v in ids))
        self.upgrade()
        self.assertEqual(ids,[version_id(self.store,self.actor.org_id,'existing-doc',v) for v in (1,2)])
        with self.connection() as reopened:
            self.assertEqual(ids[0],version_id(reopened,self.actor.org_id,'existing-doc',1))
        v3=self.client.ingest(self.actor,self.kb.kb_id,'new gamma','v3.txt',doc_id='existing-doc')
        self.assertEqual(v3.version,3)
        self.assertNotIn(version_id(self.store,self.actor.org_id,'existing-doc',3),ids)
        if self.pg:self.assertTrue(self.client.search(self.actor,'gamma',mode='vector'))

    def test_opt_in_and_missing_mapping_fail_closed(self):
        with self.assertRaises(ValidationError):upgrade_v6(self.store)
        with self.assertRaises(ConflictError):PersistentIdempotencyStore(self.store,self.actor.org_id)
        self.upgrade()
        for org,doc,v in [('foreign','existing-doc',1),(self.actor.org_id,'missing',1),(self.actor.org_id,'existing-doc',99)]:
            with self.assertRaises(NotFoundError):version_id(self.store,org,doc,v)
        with self.assertRaises(ValidationError):version_id(self.store,'','existing-doc',1)

    def test_atomic_migration_interruption_leaves_exact_v5_and_retry_succeeds(self):
        from unittest.mock import patch
        from knowledge_sdk.storage import migration_v6
        before=self.snapshot()
        with patch.object(migration_v6,'_tables',side_effect=RuntimeError('injected migration interruption')):
            with self.assertRaises(RuntimeError):upgrade_v6(self.store,owned_nonproduction=True)
        self.assertEqual(schema_version(self.store),5);self.assertEqual(self.snapshot(),before)
        self.upgrade()

    def test_independent_connections_concurrent_migration_serialized_and_idempotent(self):
        gate=threading.Barrier(4)
        def worker(_):
            with self.connection() as store:
                gate.wait();upgrade_v6(store,owned_nonproduction=True)
                return version_id(store,self.actor.org_id,'existing-doc',1)
        with ThreadPoolExecutor(4) as pool:ids=list(pool.map(worker,range(4)))
        self.assertEqual(len(set(ids)),1);self.assertEqual(schema_version(self.store),6)

    def test_version_id_sql_immutability(self):
        self.upgrade()
        from contextlib import nullcontext
        with self.store.tenant_scope(self.actor.org_id) if self.pg else nullcontext():
            for value in ('new-id',None):
                with self.assertRaises((ConflictError,ValidationError)):
                    with self.store.transaction():
                        self.store._execute('UPDATE document_versions SET version_id='+('%s' if self.pg else '?')+' WHERE doc_id='+('%s' if self.pg else '?'),(value,'existing-doc'))
        self.assertEqual(len(version_id(self.store,self.actor.org_id,'existing-doc',1)),32)

    def test_idempotency_all_decisions_ttl_cleanup_and_fence(self):
        self.upgrade();now=[100.0]
        s=PersistentIdempotencyStore(self.store,self.actor.org_id,2,clock=lambda:now[0])
        args=(self.actor.org_id,'POST','/v2/assets','key',{'content':'alpha'})
        decision,old=s.begin(*args);self.assertEqual(decision,D.NEW)
        self.assertEqual(s.begin(*args)[0],D.IN_PROGRESS)
        self.assertEqual(s.begin(*args[:-1],{'content':'beta'})[0],D.CONFLICT_PAYLOAD_MISMATCH)
        result={'version':[1]};s.complete(old,result);result['version'].append(2)
        decision,replay=s.begin(*args);self.assertEqual(decision,D.REPLAY_EXACT);self.assertEqual(replay.result,{'version':[1]})
        replay.result['version'].append(3);self.assertEqual(s.begin(*args)[1].result,{'version':[1]})
        now[0]=102;self.assertEqual(s.cleanup(),1)
        fresh=s.begin(*args)[1];self.assertGreater(fresh.claim_id,old.claim_id)
        with self.assertRaises(ConflictError):s.complete(old,{})
        s.complete(fresh,{})
        with self.assertRaises(ConflictError):s.complete(fresh,{'different':True})
        with self.assertRaises(PermissionDeniedError):s.begin('foreign',*args[1:])

    def test_composite_keys_and_tenant_isolation(self):
        self.upgrade();s=PersistentIdempotencyStore(self.store,self.actor.org_id)
        for method,path,key in [('POST','/v2/assets','k'),('POST','/v2/spaces','k'),('PUT','/v2/assets','k'),('POST','/v2/assets','k2')]:
            self.assertEqual(s.begin(self.actor.org_id,method,path,key,{})[0],D.NEW)
        other=PersistentIdempotencyStore(self.store,'enterprise-b')
        self.assertEqual(other.begin('enterprise-b','POST','/v2/assets','k',{})[0],D.NEW)
        self.assertEqual(s.cleanup(),0)

    def test_atomic_execute_reopen_and_authority_recheck(self):
        self.upgrade();s=PersistentIdempotencyStore(self.store,self.actor.org_id)
        def mutate():
            self.client.ingest(self.actor,self.kb.kb_id,'third','v3.txt',doc_id='existing-doc')
            return {'created_version':3,'nested':{'hash':'a'*64}}
        result=s.execute('POST','/v2/assets','atomic',{},authorize=lambda:None,mutate=mutate)
        with self.connection() as reopened:
            s2=PersistentIdempotencyStore(reopened,self.actor.org_id)
            self.assertEqual(s2.execute('POST','/v2/assets','atomic',{},authorize=lambda:None,mutate=lambda:self.fail('duplicate mutation')),result)
            def revoked():raise PermissionDeniedError('REVOKED')
            with self.assertRaises(PermissionDeniedError):s2.execute('POST','/v2/assets','atomic',{},authorize=revoked,mutate=lambda:None)
        self.assertEqual(self.store.get_document('existing-doc').current_version,3)

    def test_transaction_rollback_does_not_leave_claim_or_side_effect(self):
        self.upgrade();s=PersistentIdempotencyStore(self.store,self.actor.org_id)
        def fail():
            self.client.create_kb(self.actor,'not committed',kb_id='rolled-back')
            raise RuntimeError('synthetic interruption')
        with self.assertRaises(RuntimeError):s.execute('POST','/v2/spaces','rollback',{},authorize=lambda:None,mutate=fail)
        with self.assertRaises(NotFoundError):self.store.get_kb('rolled-back')
        self.assertEqual(s.begin(self.actor.org_id,'POST','/v2/spaces','rollback',{})[0],D.NEW)

    def test_independent_connections_concurrent_exactly_once(self):
        self.upgrade();barrier=threading.Barrier(6)
        def worker(_):
            with self.connection() as store:
                client=LocalKnowledgeClient(store)
                s=PersistentIdempotencyStore(store,self.actor.org_id)
                barrier.wait()
                return s.execute('POST','/v2/spaces','concurrent',{},authorize=lambda:None,mutate=lambda:{'kb_id':client.create_kb(self.actor,'once',kb_id='concurrent-space').kb_id})
        with ThreadPoolExecutor(6) as pool:results=list(pool.map(worker,range(6)))
        self.assertEqual(results,[{'kb_id':'concurrent-space'}]*6)
        self.assertEqual(len([k for k in self.store.list_kbs(self.actor.org_id) if k.kb_id=='concurrent-space']),1)

    def test_independent_process_death_then_retry_and_restart_replay(self):
        self.upgrade()
        program="""
import json,os,sys
from contextlib import closing
from knowledge_sdk import Actor,LocalKnowledgeClient
from knowledge_sdk.storage.sqlite_store import SQLiteStore
from knowledge_sdk.storage.postgres_store import PostgresStore
from knowledge_sdk.storage.persistent_contracts import PersistentIdempotencyStore
pg,location,mode=sys.argv[1:]
with closing(PostgresStore(location,migrate=False) if pg=='1' else SQLiteStore(location)) as store:
 c=LocalKnowledgeClient(store);a=Actor('owner','enterprise-a')
 s=PersistentIdempotencyStore(store,a.org_id)
 def mutate():
  kb=c.create_kb(a,'process',kb_id='process-space')
  if mode=='die':os._exit(23)
  if mode=='replay':raise RuntimeError('duplicate mutation after restart')
  return {'kb_id':kb.kb_id}
 print(json.dumps(s.execute('POST','/v2/spaces','process',{},authorize=lambda:None,mutate=mutate)))
"""
        def run(mode):return subprocess.run([sys.executable,'-W','error::ResourceWarning','-c',program,str(int(self.pg)),self.location,mode],capture_output=True,text=True,timeout=30)
        died=run('die');self.assertEqual(died.returncode,23,died.stderr)
        with self.assertRaises(NotFoundError):self.store.get_kb('process-space')
        first=run('commit');self.assertEqual(first.returncode,0,first.stderr)
        second=run('replay');self.assertEqual(second.returncode,0,second.stderr)
        self.assertEqual(json.loads(first.stdout),json.loads(second.stdout))

    def test_jobs_durable_submission_states_retry_and_cancel_race(self):
        self.upgrade();s=PersistentIngestionJobStore(self.store,self.actor.org_id)
        job=s.submit(self.actor.org_id,'job',{},max_attempts=2)
        self.assertEqual(s.submit(self.actor.org_id,'job',{},max_attempts=2),job)
        with self.assertRaises(ConflictError):s.submit(self.actor.org_id,'job',{'different':1},max_attempts=2)
        with self.connection() as reopened:self.assertEqual(PersistentIngestionJobStore(reopened,self.actor.org_id).get(self.actor.org_id,job.job_id),job)
        for state in (S.PARSING,S.CHUNKING,S.INDEXING,S.COMPLETED):
            job=s.transition(self.actor.org_id,job.job_id,state,expected_revision=job.revision)
        self.assertEqual(job.progress_pct,100)
        j=s.submit(self.actor.org_id,'retry',{},max_attempts=2)
        for attempt in (1,2):
            j=s.transition(self.actor.org_id,j.job_id,S.FAILED,expected_revision=j.revision,error_code='PARSE_FAILED')
            if attempt==1:j=s.retry(self.actor.org_id,j.job_id,expected_revision=j.revision)
        with self.assertRaises(ConflictError):s.retry(self.actor.org_id,j.job_id,expected_revision=j.revision)
        j=s.submit(self.actor.org_id,'race',{})
        gate=threading.Barrier(2)
        def race(state):
            with self.connection() as store:
                s2=PersistentIngestionJobStore(store,self.actor.org_id);gate.wait()
                try:return s2.transition(self.actor.org_id,j.job_id,state,expected_revision=0).status.value
                except ConflictError:return 'conflict'
        with ThreadPoolExecutor(2) as pool:r=list(pool.map(race,(S.PARSING,S.CANCELLED)))
        self.assertEqual(r.count('conflict'),1)

    def test_jobs_all_49_transition_pairs_and_tenant_denial(self):
        self.upgrade();s=PersistentIngestionJobStore(self.store,self.actor.org_id)
        for source in S:
            for target in S:
                j=s.submit(self.actor.org_id,source.value+target.value,{})
                for state in (S.PARSING,S.CHUNKING,S.INDEXING,S.COMPLETED) if source in (S.PARSING,S.CHUNKING,S.INDEXING,S.COMPLETED) else ():
                    j=s.transition(self.actor.org_id,j.job_id,state,expected_revision=j.revision)
                    if state==source:break
                if source in (S.FAILED,S.CANCELLED):j=s.transition(self.actor.org_id,j.job_id,source,expected_revision=j.revision,**({'error_code':'PARSE_FAILED'} if source==S.FAILED else {}))
                with self.subTest(source=source,target=target):
                    if target in ALLOWED_TRANSITIONS[source]:s.transition(self.actor.org_id,j.job_id,target,expected_revision=j.revision,**({'error_code':'PARSE_FAILED'} if target==S.FAILED else {}))
                    else:
                        with self.assertRaises(ConflictError):s.transition(self.actor.org_id,j.job_id,target,expected_revision=j.revision)
        with self.assertRaises(NotFoundError):s.get('foreign',j.job_id)
        with self.assertRaises(NotFoundError):PersistentIngestionJobStore(self.store,'enterprise-b').get('enterprise-b',j.job_id)

    def test_new_tables_pg_force_rls_and_non_superuser(self):
        self.upgrade()
        if not self.pg:
            self.assertEqual(len(self.store._execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('idempotency_records','ingestion_jobs')")),2)
            return
        role=self.store._execute('SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user')[0]
        self.assertEqual(role,(False,False))
        PersistentIdempotencyStore(self.store,self.actor.org_id).begin(self.actor.org_id,'POST','/v2/assets','secret',{})
        PersistentIngestionJobStore(self.store,self.actor.org_id).submit(self.actor.org_id,'secret',{})
        for table in NEW_TABLES:
            self.assertEqual(self.store._execute('SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=%s::regclass',(table,))[0],(True,True))
            self.assertEqual(self.store._execute('SELECT * FROM '+table),[])
            with self.store.tenant_scope('enterprise-b'):
                self.assertEqual(self.store._execute('SELECT * FROM '+table),[])
                with self.assertRaises(ValidationError):
                    with self.store.transaction():
                        self.store._execute('INSERT INTO '+table+(' (org_id,method,canonical_path,idempotency_key,fingerprint,expires_at) VALUES(%s,%s,%s,%s,%s,%s)' if table=='idempotency_records' else ' (org_id,job_id,idempotency_key,fingerprint,revision,status,data) VALUES(%s,%s,%s,%s,%s,%s,%s)'),(self.actor.org_id,'POST','/x','key','0'*64,1000) if table=='idempotency_records' else (self.actor.org_id,'foreign-write','key','0'*64,0,'queued','{}'))


class SQLitePersistence(PersistenceCases,unittest.TestCase):pass


@unittest.skipUnless(os.environ.get('KNOWLEDGE_SDK_TEST_PG_DSN'),'real PostgreSQL DSN required')
class PostgresPersistence(PersistenceCases,unittest.TestCase):pg=True
