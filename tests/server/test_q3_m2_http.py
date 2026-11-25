"""Real signed loopback HTTP, not an ASGI-only stub. All fixtures disposable."""
import importlib.util,json,os,secrets,unittest
from dataclasses import replace
from types import MappingProxyType
from knowledge_sdk import *

HAS_HTTP=all(importlib.util.find_spec(m) is not None for m in ('fastapi','uvicorn'))

def run_http(engine):
    from urllib.request import Request,urlopen
    from urllib.error import HTTPError
    from knowledge_sdk.server.app import create_app
    from knowledge_sdk.server.auth import signed_headers
    from knowledge_sdk.contracts.models import encode
    from knowledge_sdk.contracts.identity import IdentityPrincipal
    from knowledge_sdk.retrieval.strategies import registries
    from knowledge_sdk.retrieval.adapters.hash_embedder import HashEmbedder
    from tests.retrieval.q3_m2_fixture import MemoryCosineIndex
    from tests.benchmark.runner import Fixture
    import importlib.util
    path=__import__('pathlib').Path(__file__).parents[2]/'docs/acceptance/v2.1-q3-phase1/live_runtime_probe.py'
    spec=importlib.util.spec_from_file_location('q3m1_live_helper',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    f=Fixture({'expected':{}},engine);c=f.c;a=f.a;secret=secrets.token_hex(32);checks=0;variants=[]
    if c.vector_index is None:c.vector_index=MemoryCosineIndex(c.store);c.embedder=HashEmbedder()
    class Probe:
        reranker_id='probe'
        def __init__(self):self.calls=0
        def score(self,q,cs):
            self.calls+=1
            assert 'FORBIDDEN_SENTINEL' not in str(cs) and 'SECRET_RAW' not in str(cs)
            return DeterministicLexicalReranker().score(q,cs)
    probe=Probe();c.reranker_registry,c.calibrator_registry=registries({'probe':probe})
    app=create_app(c,auth_secret=secret,enable_ui=False,enable_mcp=True)
    try:
        with module.live(app) as base:
            h=HttpKnowledgeClient(base,secret)
            def wire(path,params,actor,expected=200,method='POST',mcp=False):
                nonlocal checks
                raw=json.dumps(params if mcp else {'params':encode(params)},separators=(',',':')).encode()
                headers=signed_headers(actor,secret,method,path,raw,purpose=Purpose.GROUND_INTERNAL_LLM.value if mcp else Purpose.READ.value)
                headers['Content-Type']='application/json'
                try:r=urlopen(Request(base+path,data=raw,headers=headers,method=method),timeout=15)
                except HTTPError as exc:r=exc
                with r:
                    body=r.read();assert r.status==expected,(path,r.status,expected,body[:80]);assert r.headers.get('Cache-Control')=='no-store'
                checks+=1;return json.loads(body)
            user=Actor('reader','org',policy_generation='1');c.store.upsert_principal(IdentityPrincipal('org','reader'))
            f.doc('alpha evidence SECRET_RAW_BODY',title='alpha evidence SECRET_RAW_TITLE',rights=ResourceRights(redaction_profile='hide'))
            from knowledge_sdk.permissions.redaction import RegexRedactionHook
            c.redaction_registry.register('hide',RegexRedactionHook([('SECRET_RAW_\\w+','MASK')]))
            f.doc('alpha evidence FORBIDDEN_SENTINEL',id='forbidden',acl=DocumentACL(deny_users=['reader']))
            options=dict(reranker_id='probe',calibrator_id='default-v1',min_calibrated_score=.6,rerank_top_k=40)
            local=c.search(user,'alpha evidence','hybrid',**options);remote=h.search(user,'alpha evidence','hybrid',**options)
            assert [(v.doc_id,v.score,v.calibrated_score) for v in local.hits]==[(v.doc_id,v.score,v.calibrated_score) for v in remote.hits]
            assert remote.hits and all('SECRET_RAW' not in x.excerpt for x in remote.hits);checks+=2
            assert not h.search(user,'neverfound unusual protocol','hybrid',**options).hits;checks+=1
            for bad in ({'rerank':1},{'reranker_id':'unknown'},{'calibrator_id':'unknown'},{'reranker_id':True},{'min_calibrated_score':True},{'min_calibrated_score':float('nan')},{'min_calibrated_score':float('inf')},{'min_calibrated_score':1.1},{'rerank_top_k':501},{'reranker':{'url':'https://forbidden.invalid'}}):
                wire('/v1/search',dict(query='absent',scope=KnowledgeScope('none'),**bad),user,expected=400)
            for variant in ('doc_revoked','archive','acl','anchor_drift','anchor_orphan','profile_generation','profile_disabled','principal_generation','principal_disabled'):
                actor=user
                if variant.startswith('principal_'):
                    actor=replace(user,user_id=variant);c.store.upsert_principal(IdentityPrincipal('org',actor.user_id))
                doc='enhanced-'+variant;agent='agent-'+variant
                h.ingest(a,'kb','# H\n\nalpha evidence '+variant,title='alpha evidence '+variant,filename='fixture.md',doc_id=doc)
                h.register_agent_profile(a,agent,allowed_kb_ids=['kb'])
                t=h.create_task_context(actor,agent,purpose=Purpose.GROUND_INTERNAL_LLM,scope=KnowledgeScope('documents',doc_ids=[doc]))
                snap=h.create_context_snapshot(actor,t.task_id,'alpha evidence',**options);assert snap.items and {x.doc_id for x in snap.items}=={doc};checks+=1
                if variant.startswith('anchor_'):
                    anchor=c.list_anchors(actor,doc)[0]
                    snap=h.create_context_snapshot(actor,t.task_id,[{'doc_id':doc,'anchor_id':anchor.anchor_id}])
                request={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'search_evidence','arguments':dict(query='alpha evidence',task_id=t.task_id,snapshot_id=snap.snapshot_id,mode='hybrid',**options)}}
                good=wire('/v1/mcp',request,actor,mcp=True);assert good['result']['structuredContent']['hits']
                if variant=='doc_revoked':h.set_document_rights(a,doc,ResourceRights(revoked=True))
                elif variant=='archive':h.archive(a,doc)
                elif variant=='acl':h.set_document_acl(a,doc,DocumentACL(deny_users=[actor.user_id]))
                elif variant.startswith('anchor_'):
                    text='# H\n\nalpha evidence '+variant+'\n\nalpha evidence '+variant if variant=='anchor_drift' else '# H\n\nreplacement'
                    h.ingest(a,'kb',text,filename='fixture.md',doc_id=doc)
                elif variant=='profile_generation':h.update_agent_profile(a,agent,allowed_purposes=[Purpose.READ])
                elif variant=='profile_disabled':h.update_agent_profile(a,agent,active=False)
                else:
                    path='/scim/v2/Users/'+actor.user_id
                    payload={'Operations':[{'op':'replace','path':'active' if variant=='principal_disabled' else 'department_ids','value':False if variant=='principal_disabled' else ['changed']}]}
                    # SCIM has no params envelope.
                    raw=json.dumps(payload).encode();headers=signed_headers(a,secret,'PATCH',path,raw);headers['Content-Type']='application/json'
                    with urlopen(Request(base+path,data=raw,headers=headers,method='PATCH'),timeout=15) as response:assert response.status==200 and response.headers.get('Cache-Control')=='no-store'
                    checks+=1
                before=probe.calls
                for call in (lambda:h.read_task_snapshot(actor,t.task_id,snap.snapshot_id),lambda:h.create_context_snapshot(actor,t.task_id,'alpha evidence',**options)):
                    try:call()
                    except PermissionDeniedError:checks+=1
                    else:raise AssertionError('Revoked enhanced runtime returned content')
                bad=wire('/v1/mcp',request,actor,expected=401 if variant.startswith('principal_') else 200,mcp=True)
                assert 'alpha evidence' not in json.dumps(bad)
                assert probe.calls==before  # guard ran before scoring, without outbox flush
                assert c.store.get_task_context('org',t.task_id).status=='revoked';checks+=2
                variants.append(variant)
            c.register_agent_profile(a,'scope-agent')
            t=c.create_task_context(user,'scope-agent',purpose=Purpose.READ,scope=KnowledgeScope('none'))
            assert not h.create_context_snapshot(user,t.task_id,'alpha evidence',**options).items;checks+=1
            try:h.create_context_snapshot(Actor('other','org'),t.task_id,'alpha evidence',**options)
            except PermissionDeniedError:checks+=1
            else:raise AssertionError('Wrong owner ranked')
            rls={}
            if engine=='postgres':
                with c.store.transaction():
                    assert not c.store._execute('SELECT rolsuper FROM pg_roles WHERE rolname=current_user')[0][0]
                    with c.store.tenant_scope('foreign'):
                        for table in ('agent_profiles','task_contexts','context_snapshots','task_revocations'):
                            count=c.store._execute('SELECT COUNT(*) FROM '+table)[0][0];assert count==0
                            flags=c.store._execute('SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=%s::regclass',(table,))[0];assert all(flags)
                            rls[table]={'foreign_rows':count,'enable_force_rls':True}
            return {'engine':engine,'passed':True,'assertion_groups':checks,'revocation_variants':variants,'ranker_calls_measured':probe.calls,'before_dispatch_flush':True,'rls':rls,'transport':'real loopback signed HTTP, real MCP + task snapshot, no ASGI-only stub','vector':'pgvector' if engine=='postgres' else 'real in-memory cosine over offline hash embeddings'}
    finally:f.close()

@unittest.skipUnless(HAS_HTTP,'Optional HTTP dependencies required')
class SQLiteEnhancedHTTP(unittest.TestCase):
    def test_real_signed_http_mcp_runtime(self):self.assertTrue(run_http('sqlite')['passed'])

@unittest.skipUnless(HAS_HTTP and os.environ.get('KNOWLEDGE_SDK_TEST_PG_DSN'),'Optional HTTP + disposable PG required')
class PostgresEnhancedHTTP(unittest.TestCase):
    def test_real_signed_http_mcp_runtime(self):self.assertTrue(run_http('postgres')['passed'])
