"""Actual signed loopback v2 captures. No fabricated algorithm-vector wire events."""
import copy
import importlib.util
import io
import json
import logging
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import ExitStack,closing
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from unittest.mock import patch
from knowledge_sdk import Actor,LocalKnowledgeClient,DocumentACL
from knowledge_sdk.contracts.identity import IdentityPrincipal
from knowledge_sdk.storage.sqlite_store import SQLiteStore
from knowledge_sdk.storage.migration_v6 import upgrade_v6

HTTP=importlib.util.find_spec('fastapi') is not None and importlib.util.find_spec('uvicorn') is not None
SECRET='WAVE2-TEST-ONLY-PSEUDO-SECRET-DO-NOT-USE-REAL'
ISSUER='https://gateway.example.invalid'
ROOT=Path(__file__).resolve().parents[2]


def context(user='owner',tenant='enterprise-a',agent='bound-agent',generation=1):
    return dict(request_id='wave2-test',tenant_id=tenant,
        actor=dict(issuer=ISSUER,subject_id=user,actor_type='human',roles=[],department_ids=[],ancestor_department_ids=[],org_roles=['admin'] if user=='owner' else [],clearance_level='internal',clearance_tags=[],policy_generation=generation,session_id='test-session'),
        agent=dict(agent_id=agent,profile_generation=1,task_id=''),purpose='read')


class RuntimeCases:
    pg=False
    def setUp(self):
        from knowledge_sdk.server.app import create_app
        from tests.foundation.helpers import live
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.temp=self.stack.enter_context(tempfile.TemporaryDirectory())
        if self.pg:
            from tests.pg_helpers import PgSandbox
            from knowledge_sdk.server.postgres import postgres_client
            self.sandbox=PgSandbox();self.stack.callback(self.sandbox.close)
            self.client=postgres_client(self.sandbox.dsn,pgvector_dims=32)
            self.store=self.client.store
        else:
            self.store=SQLiteStore(Path(self.temp)/'runtime.sqlite');self.client=LocalKnowledgeClient(self.store)
        self.stack.callback(self.store.close)
        self.owner=Actor('owner','enterprise-a',org_roles=('admin',),clearance_level='internal',policy_generation='1')
        self.reader=Actor('reader','enterprise-a',clearance_level='internal',policy_generation='1')
        for tenant in ('enterprise-a','enterprise-b'):
            for user in ('owner','reader','outsider'):
                self.store.upsert_principal(IdentityPrincipal(tenant,user,org_roles=('admin',) if user=='owner' else (),clearance_level='internal'))
            admin=Actor('owner',tenant,org_roles=('admin',),policy_generation='1')
            self.client.register_agent_profile(admin,'bound-agent',allowed_kb_ids=('primary','controlled'),max_clearance_level='internal')
        self.client.create_kb(self.owner,'primary','private',kb_id='primary',space_type='personal',owner_user_id='owner')
        self.client.create_kb(self.owner,'controlled','private',kb_id='controlled',space_type='personal',owner_user_id='owner',governance_tier='l2_controlled')
        self.client.grant_kb_member(self.owner,'primary','reader','viewer')
        upgrade_v6(self.store,owned_nonproduction=True)
        self.app=create_app(self.client,auth_secret=SECRET,enable_ui=False,enable_v2=True,v2_issuer=ISSUER,enable_mcp=True)
        self.base=self.stack.enter_context(live(self.app))
        self.events=[]

    def wire(self,method,path,payload=None,*,ctx=None,headers=None,expected=200):
        from knowledge_sdk.server.v2_auth import signed_v2_headers
        ctx=context() if ctx is None else copy.deepcopy(ctx)
        raw=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode() if payload is not None else b''
        signed=signed_v2_headers(ctx,SECRET,method,path,raw)
        signed.update({'Content-Type':'application/json'});signed.update(headers or {})
        request=Request(self.base+path,data=raw if method=='POST' else None,method=method,headers=signed)
        try:response=urlopen(request,timeout=15)
        except HTTPError as exc:response=exc
        with response:
            status=response.status;data=response.read();self.assertEqual(response.headers.get('Cache-Control'),'no-store')
        parsed=json.loads(data)
        self.events.append(dict(method=method,target=path,request_headers=signed,request_body=payload,response_status=status,response_body=parsed))
        self.assertEqual(status,expected,(path,status,parsed))
        return parsed

    def ingest(self,key='ingest',kb='primary',content='alpha evidence',**kwargs):
        return self.wire('POST','/v2/assets',dict(kb_id=kb,content=content,filename='fixture.txt',asset_type='document',idempotency_key=key),headers={'Idempotency-Key':key},**kwargs)

    def search(self,ctx=None):
        return self.wire('POST','/v2/retrieval:search',dict(query='alpha',mode='keyword',limit=10,scope={'mode':'all'},filters={'asset_types':[],'tags':[],'lifecycle_states':[]},rerank={'enabled':False,'reranker_id':'','top_k':40},calibration={'enabled':False,'min_calibrated_score':0}),ctx=ctx)

    def test_ten_frozen_minimum_assertions_real_http(self):
        summary=[]
        v=self.ingest();doc=v['doc_id'];path='/v2/assets/'+doc
        self.client.set_document_acl(self.owner,doc,DocumentACL(allow_users=['reader']))
        self.wire('GET',path,ctx=context('reader'))
        with self.subTest(assertion='A01'):
            self.wire('GET',path,ctx=context('outsider'),expected=403);summary.append('A01')
        with self.subTest(assertion='A02'):
            self.wire('GET',path,ctx=context('reader',agent='unbound-agent'),expected=403);summary.append('A02')
        with self.subTest(assertion='A03'):
            missing=context();del missing['actor']['policy_generation']
            self.wire('GET',path,ctx=missing,expected=400)
            self.wire('GET',path,headers={'X-Tenant-Id':''},expected=403);summary.append('A03')
        with self.subTest(assertion='A04'):
            self.wire('GET',path,ctx=context(tenant='enterprise-b'),expected=403);summary.append('A04')
        with self.subTest(assertion='A05'):
            self.client.revoke_kb_member(self.owner,'primary','reader')
            self.wire('GET',path,ctx=context('reader'),expected=403)
            self.client.grant_kb_member(self.owner,'primary','reader','viewer')
            self.store.upsert_principal(IdentityPrincipal('enterprise-a','reader',active=False,clearance_level='internal'))
            self.wire('GET',path,ctx=context('reader'),expected=403)
            self.store.upsert_principal(IdentityPrincipal('enterprise-a','reader',clearance_level='internal'))
            self.client.update_agent_profile(self.owner,'bound-agent',active=False)
            self.wire('GET',path,ctx=context('reader'),expected=403)
            self.client.update_agent_profile(self.owner,'bound-agent',active=True)
            # Restore fixture through the authoritative current generation, not a stale token.
            profile=self.store.get_agent_profile('enterprise-a','bound-agent')
            self.ctx=context();self.ctx['agent']['profile_generation']=profile.profile_generation
            summary.append('A05')
        # Subsequent contexts deliberately carry the actual current generation.
        ctx=self.ctx
        with self.subTest(assertion='A06'):
            with patch.object(self.store,'get_principal',side_effect=RuntimeError('backend unavailable')):
                self.wire('GET',path,ctx=ctx,expected=503)
            summary.append('A06')
        with self.subTest(assertion='A07'):
            hit=self.search(ctx)['hits'][0]
            chunks=self.store.get_chunks(doc,1);chunk=next(c for c in chunks if c.chunk_id==hit['chunk_id'])
            evidence=dict(evidence_id='test-evidence',tenant_id='enterprise-a',kb_id='primary',doc_id=doc,version=1,version_id=v['version_id'],chunk_id=hit['chunk_id'],anchor_id='',title=hit['title'],section_path=chunk.section_path,excerpt=hit['excerpt'],excerpt_hash=hit['excerpt_hash'],canonical_uri=hit['source_uri'],locator=dict(page=0,char_start=chunk.start_offset,char_end=chunk.end_offset,table_cell=None),masking_summary=hit['masking_summary'],verification_status='unverified',hash_algorithm='sha256')
            verified=self.wire('POST','/v2/citations:verify',evidence,ctx=ctx)
            self.assertEqual(verified['verification_status'],'verified');self.assertEqual(hit['version_id'],v['version_id'])
            tampered=dict(evidence,excerpt='tampered',excerpt_hash='0'*64)
            self.assertEqual(self.wire('POST','/v2/citations:verify',tampered,ctx=ctx,expected=400)['error']['code'],'TAMPERED_EXCERPT')
            # Both frozen selector forms, not a guessed anchor/section conversion.
            anchor=self.client.list_anchors(self.owner,doc)[0]
            from knowledge_sdk.contracts.uri import build_uri
            import hashlib
            anchored=dict(evidence,anchor_id=anchor.anchor_id,canonical_uri=build_uri('enterprise-a',doc,1,anchor_id=anchor.anchor_id),excerpt=anchor.quote.exact,excerpt_hash=hashlib.sha256(anchor.quote.exact.encode()).hexdigest(),section_path=list(anchor.section_quote.section_path),locator=dict(page=0,char_start=anchor.section_quote.start_offset,char_end=anchor.section_quote.end_offset,table_cell=None))
            self.assertEqual(self.wire('POST','/v2/citations:verify',anchored,ctx=ctx)['verification_status'],'verified')
            self.wire('POST','/v2/citations:verify',dict(evidence,title='forged-title'),ctx=ctx,expected=400)
            self.wire('POST','/v2/citations:verify',dict(evidence,locator=dict(evidence['locator'],char_end=999999)),ctx=ctx,expected=400)
            summary.append('A07')
        with self.subTest(assertion='A08'):
            missing=dict(evidence,version_id='unknown-history')
            self.assertEqual(self.wire('POST','/v2/citations:verify',missing,ctx=ctx,expected=404)['error']['code'],'ANCHOR_UNRESOLVABLE');summary.append('A08')
        with self.subTest(assertion='A09'):
            draft=self.ingest('draft',kb='controlled',ctx=ctx)
            self.assertEqual(draft['lifecycle_state'],'draft');self.assertFalse(draft['activated']);summary.append('A09')
        with self.subTest(assertion='A10'):
            self.assertEqual(self.ingest(ctx=ctx),v)  # generation changes are not payload changes
            # Original agent profile generation was1, now3: payload identity fingerprint
            # deliberately uses the current agent binding, so fresh key for this check.
            first=self.ingest('retry',ctx=ctx);again=self.ingest('retry',ctx=ctx)
            self.assertEqual(first,again);self.assertEqual(self.store.latest_version(first['doc_id']),1)
            self.assertEqual(self.ingest('retry',content='different',ctx=ctx,expected=409)['error']['code'],'IDEMPOTENCY_CONFLICT')
            summary.append('A10')
        self.assertEqual(summary,['A%02d'%n for n in range(1,11)])
        output=os.environ.get('WAVE2_CAPTURE_OUTPUT')
        if output:
            directory=Path(output);directory.mkdir(parents=True,exist_ok=True)
            (directory/('postgres' if self.pg else 'sqlite')).with_suffix('.json').write_text(json.dumps(dict(engine='postgres' if self.pg else 'sqlite',runtime_captured=True,test_only_pseudo_secret=SECRET,assertions=summary,events=self.events),ensure_ascii=False,indent=2)+'\n')

    def test_policy_generation_all_frozen_cases_and_service_rejection(self):
        cases=json.loads((ROOT/'docs/architecture/knowledge-sdk-alignment/contracts/contract-fixtures/policy-generation-cases.json').read_text())['cases']
        for case in cases:
            self.store.upsert_principal(IdentityPrincipal('enterprise-a','owner',policy_generation=case['stored_generation'],org_roles=('admin',),clearance_level='internal'))
            ctx=context();ctx['actor'].pop('policy_generation');ctx['actor'].update(case['submitted'])
            response=self.wire('GET','/v2/spaces',ctx=ctx,expected=case['expected']['http_status'])
            if case['expected']['code']:self.assertEqual(response['error']['code'],case['expected']['code'])
        self.store.upsert_principal(IdentityPrincipal('enterprise-a','owner',org_roles=('admin',),clearance_level='internal'))
        for invalid in (1.0,-1,False,None,'1',9007199254740992):
            self.wire('GET','/v2/spaces',ctx=context(generation=invalid),expected=400)
        for tenant,expected in [(None,400),('',403)]:
            self.wire('GET','/v2/spaces',ctx=context(tenant=tenant),headers={'X-Tenant-Id':'enterprise-a'},expected=expected)
        missing_tenant=context();del missing_tenant['tenant_id']
        self.wire('GET','/v2/spaces',ctx=missing_tenant,expected=400)
        service=context();service['actor']['actor_type']='service'
        self.wire('GET','/v2/spaces',ctx=service,expected=403)

    def test_create_space_exact_json_metadata_survives_v1_update_and_replay(self):
        # A separately registered, unrestricted profile is an explicit binding;
        # empty allowlists mean no EXTRA narrowing, as the frozen decision specifies.
        self.client.register_agent_profile(self.owner,'creator',max_clearance_level='internal')
        ctx=context(agent='creator')
        payload=dict(kb_id='created',tenant_id='enterprise-a',name='created',description='persisted description',space_type='personal',visibility='private',governance_tier='l1_agile',owner_user_id='owner',owner_department_id='',tags=['fixture'],status='active',metadata={'category':'test','literal':{'__type__':'Actor','arbitrary':'data'}},created_at='2026-11-25T12:00:00Z',updated_at='2026-11-25T12:00:00Z')
        first=self.wire('POST','/v2/spaces',payload,ctx=ctx,headers={'Idempotency-Key':'create'})
        self.assertEqual(first,self.wire('POST','/v2/spaces',payload,ctx=ctx,headers={'Idempotency-Key':'create'}))
        self.client.update_kb(self.owner,'created',name='renamed')
        current=self.wire('GET','/v2/spaces/created',ctx=ctx)
        self.assertEqual(current['name'],'renamed');self.assertEqual(current['description'],'persisted description');self.assertEqual(current['metadata'],payload['metadata'])
        self.assertNotIn('_v2_space',self.client.get_kb(self.owner,'created').__dict__)

    def test_current_task_document_scope_cannot_create_unbound_asset(self):
        from knowledge_sdk.contracts.models import KnowledgeScope
        from knowledge_sdk.contracts.policy import Purpose
        original=self.ingest('task-source')
        task=self.client.create_task_context(self.owner,'bound-agent',purpose=Purpose.READ,scope=KnowledgeScope('documents',doc_ids=(original['doc_id'],)))
        ctx=context();ctx['agent']['task_id']=task.task_id
        self.wire('GET','/v2/assets/'+original['doc_id'],ctx=ctx)
        before=len(self.store.list_documents('enterprise-a'))
        self.wire('POST','/v2/assets',dict(kb_id='primary',content='scope must not expand',filename='new.txt',asset_type='document',idempotency_key='scope-denial'),ctx=ctx,headers={'Idempotency-Key':'scope-denial'},expected=403)
        self.assertEqual(len(self.store.list_documents('enterprise-a')),before)
        with self.store.tenant_scope('enterprise-a') if self.pg else self.store.transaction():
            rows=self.store._execute("SELECT count(*) FROM idempotency_records WHERE idempotency_key='scope-denial'")
        self.assertEqual(rows[0][0],0)
        allowed=self.client.create_task_context(self.owner,'bound-agent',purpose=Purpose.READ,scope=KnowledgeScope('spaces',kb_ids=('primary',)))
        ctx['agent']['task_id']=allowed.task_id
        created=self.ingest('task-space',ctx=ctx)
        self.wire('GET','/v2/assets/'+created['doc_id'],ctx=ctx)

    def test_full_logs_zero_content_pii_secrets_on_validation_and_deny(self):
        stream=io.StringIO();handler=logging.StreamHandler(stream);logger=logging.getLogger();old=logger.level;logger.setLevel(logging.INFO);logger.addHandler(handler)
        try:
            v=self.ingest('logs',content='WAVE2-CONTENT-SENTINEL test-pii@example.invalid')
            path='/v2/assets/'+v['doc_id']
            self.wire('GET',path,ctx=context('outsider'),expected=403)
            self.wire('POST','/v2/assets',{'unknown-secret-field':'WAVE2-SECRET-SENTINEL'},expected=400)
        finally:logger.removeHandler(handler);logger.setLevel(old);handler.close()
        full=stream.getvalue();stream.close()
        self.assertTrue(full)
        for sentinel in ('WAVE2-CONTENT-SENTINEL','test-pii@example.invalid','WAVE2-SECRET-SENTINEL',SECRET,'X-KB-Actor','X-KB-Signature'):
            self.assertNotIn(sentinel,full)
        for line in full.splitlines():self.assertIsInstance(json.loads(line),dict)

    def test_http_reopen_restart_exact_replay_and_published_rollback_security(self):
        from knowledge_sdk.server.app import create_app
        from tests.foundation.helpers import live
        from knowledge_sdk.storage.postgres_store import PostgresStore
        v=self.ingest('restart');doc=v['doc_id']
        location=self.sandbox.dsn if self.pg else str(Path(self.temp)/'runtime.sqlite')
        with closing(PostgresStore(location,migrate=False) if self.pg else SQLiteStore(location)) as reopened:
            fresh=LocalKnowledgeClient(reopened)
            app=create_app(fresh,auth_secret=SECRET,enable_ui=False,enable_v2=True,v2_issuer=ISSUER)
            oldbase=self.base
            with live(app) as base:
                try:self.base=base;self.assertEqual(self.ingest('restart'),v)
                finally:self.base=oldbase
        self.assertEqual(self.store.latest_version(doc),1)
        self.client.ingest(self.owner,'primary','revised content','revised.txt',doc_id=doc,metadata={'current_business':'retained'})
        self.client.set_document_acl(self.owner,doc,DocumentACL(deny_users=['outsider']))
        before=self.store.get_document(doc);acl=self.store.get_acl(doc)
        result=self.wire('POST','/v2/assets/'+doc+':rollback',{'target_version':1})
        self.assertEqual(result['created_version'],3);self.assertTrue(result['activated'])
        after=self.store.get_document(doc)
        self.assertEqual(after.metadata,before.metadata);self.assertEqual(after.rights,before.rights);self.assertEqual(self.store.get_acl(doc),acl)
        self.assertEqual(result['rollback_scope'],'content_and_filename_only')

    def test_explicit_deny_owner_private_robot_ready_and_metrics_boundaries(self):
        from knowledge_sdk.server.auth import signed_headers
        from knowledge_sdk.client.http_client import OPERATIONS
        self.assertEqual(len(OPERATIONS),70)
        v=self.ingest('deny');self.client.set_document_acl(self.owner,v['doc_id'],DocumentACL(deny_users=['owner']))
        ctx=context();ctx['actor']['roles']=['private_robot','admin']
        self.wire('GET','/v2/assets/'+v['doc_id'],ctx=ctx,expected=403)
        self.ingest('deny',ctx=ctx,expected=403)
        for path,actor,expected in [('/v1/ready',None,200),('/v1/metrics',self.owner,403),('/v1/metrics',Actor('owner','enterprise-a',org_roles=('metrics_admin',),policy_generation='1'),200)]:
            headers=signed_headers(actor,SECRET,'GET',path) if actor else {}
            try:r=urlopen(Request(self.base+path,headers=headers),timeout=15)
            except HTTPError as exc:r=exc
            with r:self.assertEqual(r.status,expected);r.read()
        self.store._execute('DROP TABLE ingestion_jobs')
        try:r=urlopen(self.base+'/v1/ready',timeout=15)
        except HTTPError as exc:r=exc
        with r:self.assertEqual(r.status,503);r.read()


@unittest.skipUnless(HTTP,'HTTP optional dependencies required')
class SQLiteRuntime(RuntimeCases,unittest.TestCase):pass


@unittest.skipUnless(HTTP and os.environ.get('KNOWLEDGE_SDK_TEST_PG_DSN'),'real PostgreSQL and HTTP required')
class PostgresRuntime(RuntimeCases,unittest.TestCase):pg=True
