"""Same trusted identities over real loopback HTTP, Python, and all four MCP tools."""
import importlib.util,json,os,secrets,unittest,tempfile
from pathlib import Path
from dataclasses import replace
from knowledge_sdk import *
HAS_HTTP=all(importlib.util.find_spec(m) is not None for m in ('fastapi','uvicorn'))


def run_wave1_wire(engine):
    from urllib.request import Request,urlopen
    from urllib.error import HTTPError
    from knowledge_sdk.server.app import create_app
    from knowledge_sdk.server.auth import signed_headers
    from knowledge_sdk.contracts.models import encode
    from knowledge_sdk.contracts.identity import IdentityPrincipal
    from knowledge_sdk.retrieval.strategies import registries
    from knowledge_sdk.permissions.redaction import RegexRedactionHook
    from tests.benchmark.runner import Fixture
    from tests.retrieval.q3_m2_fixture import MemoryCosineIndex
    from knowledge_sdk.retrieval.adapters.hash_embedder import HashEmbedder
    path=Path(__file__).parents[2]/'docs/acceptance/v2.1-q3-phase1/live_runtime_probe.py'
    spec=importlib.util.spec_from_file_location('align_live',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    f=Fixture({'expected':{}},engine);c=f.c;a=f.a;secret=secrets.token_hex(32);rows=[];checks=0;directory=tempfile.TemporaryDirectory(prefix='align-plan-')
    class Probe:
        reranker_id='wave-probe'
        calls=0
        def score(self,q,cs):
            self.calls+=1
            assert all('FORBIDDEN_RAW' not in x.excerpt and 'RAW_SECRET' not in x.excerpt for x in cs)
            return DeterministicLexicalReranker().score(q,cs)
    probe=Probe();c.reranker_registry,c.calibrator_registry=registries({'wave-probe':probe})
    if c.vector_index is None:c.vector_index=MemoryCosineIndex(c.store);c.embedder=HashEmbedder()
    options=dict(reranker_id='wave-probe',calibrator_id='default-v1',min_calibrated_score=.6,rerank_top_k=100)
    try:
        c.create_kb(a,'wave private','private',kb_id='private');reader=Actor('reader','org',policy_generation='1');c.grant_kb_member(a,'private',reader.user_id,'editor')
        c.ingest(a,'private','wavecommon authorized',title='wavecommon',doc_id='allowed',visibility='team')
        c.ingest(a,'private','wavecommon FORBIDDEN_RAW',title='wavecommon',doc_id='deny',visibility='team')
        c.set_document_acl(a,'deny',DocumentACL(deny_users=[a.user_id,reader.user_id]))
        c.redaction_registry.register('mask',RegexRedactionHook([('RAW_SECRET','MASK')]))
        c.ingest(a,'private','wavecommon RAW_SECRET',title='wavecommon',doc_id='masked',visibility='team',rights=ResourceRights(redaction_profile='mask'))
        class Exploding:
            def redact(self,*args):raise RuntimeError('RAW_SECRET exception credential=do-not-log')
        c.redaction_registry.register('broken',Exploding());c.ingest(a,'private','wavecommon FORBIDDEN_RAW',title='wavecommon',doc_id='broken',visibility='team',rights=ResourceRights(redaction_profile='broken'))
        c.register_agent_profile(a,'bound-profile',allowed_kb_ids=['private'])
        stale=replace(reader,user_id='stale');disabled=replace(reader,user_id='disabled')
        for actor in (stale,disabled):c.grant_kb_member(a,'private',actor.user_id,'viewer')
        c.store.upsert_principal(IdentityPrincipal('org','stale',policy_generation=2));c.store.upsert_principal(IdentityPrincipal('org','disabled',active=False))
        from knowledge_sdk.connectors import ControlledFilesystemConnector
        source=Path(directory.name)/'plan.txt';source.write_text('read only fixture')
        connectors={'fs':(ControlledFilesystemConnector('fs',directory.name,org_id='org'),'private')}
        app=create_app(c,auth_secret=secret,enable_ui=False,enable_mcp=True,connectors=connectors)
        with module.live(app) as base:
            h=HttpKnowledgeClient(base,secret)
            def wire(path,body=None,actor=None,*,agent=None,mcp=False,method='POST'):
                nonlocal checks
                data=None if method=='GET' else json.dumps(body if mcp else {'params':encode(body or {})},separators=(',',':')).encode()
                headers={'Content-Type':'application/json'}
                if actor is not None:headers.update(signed_headers(actor,secret,method,path,data or b'',agent=agent.to_dict() if agent else None,purpose=Purpose.GROUND_INTERNAL_LLM.value if mcp else Purpose.READ.value))
                try:r=urlopen(Request(base+path,data=data,headers=headers,method=method),timeout=15)
                except HTTPError as exc:r=exc
                with r:
                    raw=r.read();status=r.status;assert r.headers.get('Cache-Control')=='no-store'
                checks+=1;assert b'credential=' not in raw and b'RAW_SECRET exception' not in raw
                return status,json.loads(raw)
            assert wire('/v1/kbs/get',{'kb_id':True},a)[0]==400
            assert wire('/v1/kbs/update',{'kb_id':'private','org_id':'forbidden'},a)[0]==400
            assert wire('/v1/documents/versions/diff',{'doc_id':'allowed','from_version':True,'to_version':1},a)[0]==400
            before=c.store.count_outbox_events('org');audit=len(c.store.list_audit_events('org',limit=1000));mtime=source.stat().st_mtime_ns
            assert h.plan_sync(a,'fs')==c.plan_sync(a,'fs')
            for bad_actor,bad_agent in ((reader,None),(a,AgentIdentity('limited','org',allowed_kb_ids=('other',)))):
                try:h.plan_sync(bad_actor,'fs',agent=bad_agent)
                except PermissionDeniedError:checks+=1
                else:raise AssertionError('Plan agent/admin intersection bypass')
            assert c.store.count_outbox_events('org')==before and len(c.store.list_audit_events('org',limit=1000))==audit and source.stat().st_mtime_ns==mtime;checks+=1
            assert h.get_kb(reader,'private').kb_id=='private';h.update_kb(a,'private',name='wave renamed');assert h.list_kb_members(a,'private')==c.list_kb_members(a,'private');checks+=3
            c.ingest(a,'private','wavecommon version two',title='wavecommon',doc_id='allowed')
            assert [v.version for v in h.list_document_versions(reader,'allowed')]==[1,2];assert h.diff_document_versions(reader,'allowed',1,2)==c.diff_document_versions(reader,'allowed',1,2);assert h.rollback_document(a,'allowed',1).version==3;checks+=3
            for actor in (reader,Actor('no-member','org'),Actor('reader','foreign')):
                failures=[]
                for kb in ('missing','private'):
                    status,body=wire('/v1/kbs/get',{'kb_id':kb},actor)
                    if actor!=reader:failures.append((status,body))
                if actor!=reader:assert failures[0]==failures[1]
            cases=[('authorized',reader,'allowed',None,True),('explicit_deny_admin_owner',a,'deny',None,False),('explicit_deny_reader',reader,'deny',None,False),('cross_tenant',Actor('reader','foreign'),'allowed',None,False),('agent_does_not_grant_membership',Actor('no-member','org'),'allowed',AgentIdentity('bound-profile','org',allowed_kb_ids=('private',)),False),('stale_generation',stale,'allowed',None,False),('inactive_scim',disabled,'allowed',None,False),('redaction_failclosed',reader,'broken',None,False),('redacted_delivery',reader,'masked',None,True)]
            def matrix(label,actor,doc,agent,allowed):
                nonlocal checks
                ctx=dict(agent=agent,purpose=Purpose.READ)
                try:
                    v=c.get_document(actor,doc,c.store.get_document(doc).current_version,**ctx);local_read=True;assert 'RAW_SECRET' not in v.text
                except (PermissionDeniedError,NotFoundError):local_read=False
                assert local_read==allowed
                try:local_search=bool(c.search(actor,'wavecommon','hybrid',scope=KnowledgeScope('documents',doc_ids=[doc]),**options,**ctx).hits)
                except (PermissionDeniedError,NotFoundError):local_search=False
                assert local_search==allowed
                status,body=wire('/v1/documents/get',{'doc_id':doc,'version':c.store.get_document(doc).current_version},actor,agent=agent);assert (status==200)==allowed
                status,body=wire('/v1/search',dict(query='wavecommon',mode='hybrid',scope=KnowledgeScope('documents',doc_ids=[doc]),**options),actor,agent=agent)
                assert (status==200 and bool(body.get('hits')))==allowed
                rows.extend([dict(case=label,transport=t,allowed=allowed) for t in ('python','http')]);checks+=2
                uri='kb://org/org/doc/'+doc+'@'+str(c.store.get_document(doc).current_version)
                args={'search_evidence':dict(query='wavecommon',mode='hybrid',doc_ids=[doc],**options),'verify_citation':dict(source_uri=uri),'get_evidence_pack':dict(source_uris=[uri]),'report_evidence_issue':dict(source_uri=uri,issue_type='outdated',description='fixture correction')}
                for tool,params in args.items():
                    status,body=wire('/v1/mcp',{'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':tool,'arguments':params}},actor,agent=agent,mcp=True)
                    if status==200:
                        content=body.get('result',{}).get('structuredContent',{});is_error=body.get('result',{}).get('isError',False) or 'error' in body
                        if tool=='search_evidence':ok=bool(content.get('hits'))
                        elif tool=='get_evidence_pack':ok=bool(content.get('items'))
                        elif tool=='verify_citation':ok=content.get('valid') is True
                        else:ok=not is_error and content.get('status')!='denied'
                        assert ok==allowed,(label,tool,body)
                    else:assert not allowed and status==401
                    assert 'RAW_SECRET' not in json.dumps(body) and 'FORBIDDEN_RAW' not in json.dumps(body)
                    rows.append(dict(case=label,transport='mcp',tool=tool,allowed=allowed))
            for case in cases:matrix(*case)
            # A profile-bound nonmember task cannot turn a robot binding into a grant.
            outsider=Actor('no-member','org');t=h.create_task_context(outsider,'bound-profile',purpose=Purpose.READ)
            assert not h.create_context_snapshot(outsider,t.task_id,'wavecommon',**options).items;checks+=1
            # Revoke using real HTTP; no drain/dispatcher call is made.
            task=h.create_task_context(reader,'bound-profile',purpose=Purpose.GROUND_INTERNAL_LLM)
            snapshot=h.create_context_snapshot(reader,task.task_id,[{'doc_id':'allowed'}]);assert snapshot.items
            h.revoke_kb_member(a,'private','reader');before=probe.calls;matrix('member_revoked',reader,'allowed',None,False)
            for operation in (lambda:h.read_task_snapshot(reader,task.task_id,snapshot.snapshot_id),lambda:h.create_context_snapshot(reader,task.task_id,'wavecommon',**options)):
                try:operation()
                except PermissionDeniedError:checks+=1
                else:raise AssertionError('Revoked snapshot became readable')
            status,body=wire('/v1/mcp',{'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'search_evidence','arguments':dict(query='wavecommon',task_id=task.task_id,snapshot_id=snapshot.snapshot_id,**options)}},reader,mcp=True)
            assert 'authorized' not in json.dumps(body) and probe.calls==before
            revs=c.store.list_task_revocations('org',task.task_id);assert revs and c.store.get_task_context('org',task.task_id).status=='revoked';checks+=1
            assert wire('/v1/health',actor=None,method='GET')[0]==200;assert wire('/v1/ready',actor=None,method='GET')==(200,{'status':'ready'})
            assert wire('/v1/metrics',actor=None,method='GET')[0]==401;assert wire('/v1/metrics',actor=reader,method='GET')[0]==403
            operator=replace(a,org_roles=('admin','metrics_admin'));status,metrics=wire('/v1/metrics',actor=operator,method='GET');assert status==200
            assert set(metrics['counters'])=={'http_requests_total','http_responses_2xx_total','http_responses_3xx_total','http_responses_4xx_total','http_responses_5xx_total'}
            assert all(type(v) is int and v>=0 for v in metrics['counters'].values());checks+=1
            if engine=='postgres':
                with c.store.transaction():
                    with c.store.db.cursor() as cursor:
                        cursor.execute('SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user');assert cursor.fetchone()==(False,False)
                        cursor.execute("SELECT set_config('app.current_org_id','org',true)");cursor.execute('SELECT COUNT(*) FROM documents');assert cursor.fetchone()[0]>0
                        cursor.execute("SELECT set_config('app.current_org_id','foreign',true)");cursor.execute('SELECT COUNT(*) FROM documents');assert cursor.fetchone()[0]==0
                checks+=3
            c.store.close();assert wire('/v1/ready',actor=None,method='GET')==(503,{'status':'not_ready'});checks+=1
        return dict(engine=engine,wire_assertion_groups=checks,permission_rows=rows,case_count=10,protocols=['python','http','mcp-four-tools'],member_revoke_before_dispatch=True,no_denied_rank_inputs=True,ready_real_closed_connection_503=True,metrics_fixed_no_labels=True,non_superuser_rls=engine=='postgres')
    finally:
        try:f.close()
        finally:directory.cleanup()

@unittest.skipUnless(HAS_HTTP,'Optional HTTP dependencies unavailable')
class Wave1Wire(unittest.TestCase):
    def test_sqlite_live_three_protocols(self):self.assertEqual(run_wave1_wire('sqlite')['case_count'],10)
    @unittest.skipUnless(os.environ.get('KNOWLEDGE_SDK_TEST_PG_DSN'),'Disposable PostgreSQL DSN unavailable')
    def test_postgres_live_three_protocols(self):self.assertTrue(run_wave1_wire('postgres')['non_superuser_rls'])
