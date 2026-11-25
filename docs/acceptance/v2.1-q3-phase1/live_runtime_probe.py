"""Actual disposable loopback runtime HTTP + HMAC/OIDC + MCP; no browser.

Requires optional http dependencies; PG only with explicitly supplied disposable
KNOWLEDGE_SDK_TEST_PG_DSN. Never prints tokens, HMAC secrets or connection strings.
"""
from __future__ import annotations
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
import json,os,secrets,socket,threading,time,uuid,urllib.request,urllib.error
import uvicorn
from knowledge_sdk import (Actor,LocalKnowledgeClient,HttpKnowledgeClient,ResourceRights,
                           DocumentACL,Purpose,PermissionDeniedError,ContextBudget)
from knowledge_sdk.server.app import create_app
from knowledge_sdk.server.auth import signed_headers
from knowledge_sdk.contracts.identity import IdentityPrincipal
from tests.benchmark.g7_g8 import token,authenticator
from tests.pg_helpers import PgSandbox

@contextmanager
def live(app):
    sock=socket.socket();sock.bind(('127.0.0.1',0))
    assert sock.getsockname()[1] not in (3000,3001,8000,8002,8090,8091)
    server=uvicorn.Server(uvicorn.Config(app,log_level='critical',access_log=False));thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
    try:
        deadline=time.monotonic()+15
        while not server.started:
            if not thread.is_alive() or time.monotonic()>deadline:raise RuntimeError('Runtime fixture startup failed')
            threading.Event().wait(.01)
        yield 'http://127.0.0.1:'+str(sock.getsockname()[1])
    finally:
        server.should_exit=True;thread.join(15);sock.close();assert not thread.is_alive()

def run(engine):
    sandbox=PgSandbox() if engine=='postgres' else None
    if sandbox:
        from knowledge_sdk.storage.postgres_store import PostgresStore
        c=LocalKnowledgeClient(PostgresStore(sandbox.dsn))
    else:c=LocalKnowledgeClient()
    secret=secrets.token_hex(32);a=Actor('admin','org',org_roles=('admin',));u=Actor('reader','org',policy_generation='1')
    c.store.upsert_principal(IdentityPrincipal('org','reader'));c.create_kb(a,'Runtime','enterprise',kb_id='kb')
    auth=authenticator();app=create_app(c,auth_secret=secret,enable_ui=False,enable_mcp=True,auth_mode='dual',oidc_authenticator=auth)
    checks=0;families=[]
    try:
        with live(app) as base:
            h=HttpKnowledgeClient(base,secret)
            def wire(path,data,actor=u,bearer=False,expected=200):
                nonlocal checks
                raw=json.dumps(data,separators=(',',':')).encode()
                headers={'Authorization':'Bearer '+token(jti=str(uuid.uuid4()))} if bearer else signed_headers(actor,secret,'POST',path,raw,purpose=Purpose.GROUND_INTERNAL_LLM.value)
                headers.update({'Content-Type':'application/json','X-KB-Task-Id':'forged','X-KB-Budget':'99999999','X-KB-Policy-Generation':'999'})
                try:r=urllib.request.urlopen(urllib.request.Request(base+path,data=raw,headers=headers),timeout=15)
                except urllib.error.HTTPError as exc:r=exc
                with r:
                    body=r.read();assert r.status==expected,(path,r.status);assert r.headers.get('Cache-Control')=='no-store'
                checks+=1;return json.loads(body)
            for variant in ('doc_revoked','archive','acl','anchor_drift','anchor_orphan','profile_generation','profile_disabled','principal_generation','principal_disabled'):
                # Independent actor for each directory variant; bearer test is for reader only.
                actor=u
                if variant.startswith('principal_'):
                    actor=replace(u,user_id=variant);c.store.upsert_principal(IdentityPrincipal('org',actor.user_id))
                doc='doc-'+variant;agent='agent-'+variant
                h.ingest(a,'kb','# H\n\nalpha evidence '+variant,filename='fixture.md',doc_id=doc)
                profile=h.register_agent_profile(a,agent,default_budget=ContextBudget(2,3,80,120,60))
                t=h.create_task_context(actor,agent,purpose=Purpose.GROUND_INTERNAL_LLM)
                entry={'doc_id':doc}
                if variant.startswith('anchor_'):entry['anchor_id']=c.list_anchors(actor,doc)[0].anchor_id
                s=h.create_context_snapshot(actor,t.task_id,[entry]);assert s.items and s.items[0].version==1
                assert h.read_task_snapshot(actor,t.task_id,s.snapshot_id)==s;checks+=4
                if actor==u:
                    got=wire('/v1/runtime/snapshots/read',{'params':{'task_id':t.task_id,'snapshot_id':s.snapshot_id}},bearer=True)
                    assert got['snapshot_sha256']==s.snapshot_sha256
                args={'query':'alpha','task_id':t.task_id,'snapshot_id':s.snapshot_id}
                request={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'search_evidence','arguments':args}}
                good=wire('/v1/mcp',request,actor=actor);assert not good['result']['isError'] and good['result']['structuredContent']['hits']
                if variant=='doc_revoked':h.set_document_rights(a,doc,ResourceRights(revoked=True))
                elif variant=='archive':h.archive(a,doc)
                elif variant=='acl':h.set_document_acl(a,doc,DocumentACL(deny_users=[actor.user_id]))
                elif variant.startswith('anchor_'):
                    text='# H\n\nalpha evidence '+variant+'\n\nalpha evidence '+variant if variant=='anchor_drift' else '# H\n\nreplacement'
                    h.ingest(a,'kb',text,filename='fixture.md',doc_id=doc)
                elif variant=='profile_generation':h.update_agent_profile(a,agent,allowed_purposes=[Purpose.READ])
                elif variant=='profile_disabled':h.update_agent_profile(a,agent,active=False)
                else:
                    # SCIM HTTP uses POST-only helper by direct PATCH request below.
                    raw=json.dumps({'Operations':[{'op':'replace','path':'active' if variant=='principal_disabled' else 'department_ids','value':False if variant=='principal_disabled' else ['changed']}]}).encode()
                    path='/scim/v2/Users/'+actor.user_id;headers=signed_headers(a,secret,'PATCH',path,raw);headers['Content-Type']='application/json'
                    with urllib.request.urlopen(urllib.request.Request(base+path,data=raw,headers=headers,method='PATCH'),timeout=10) as r:assert r.status==200
                checks+=1
                # No dispatcher flush: write-path proactive invalidation is already committed.
                assert c.store.get_task_context('org',t.task_id).status=='revoked'
                assert c.store.get_context_snapshot('org',s.snapshot_id).status=='revoked'
                assert c.store.list_task_revocations('org',t.task_id)[0].trigger_event_id
                for call in (lambda:h.read_task_snapshot(actor,t.task_id,s.snapshot_id),lambda:h.create_context_snapshot(actor,t.task_id,[entry])):
                    try:call()
                    except PermissionDeniedError:checks+=1
                    else:raise AssertionError('Revoked runtime exposed content')
                for name,params in [('search_evidence',{'query':'alpha'}),('verify_citation',{'source_uri':s.items[0].source_uri}),('get_evidence_pack',{'source_uris':[s.items[0].source_uri]})]:
                    request={'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':name,'arguments':dict(params,task_id=t.task_id,snapshot_id=s.snapshot_id)}}
                    result=wire('/v1/mcp',request,actor=actor,expected=401 if variant.startswith('principal_') else 200)
                    assert 'alpha evidence' not in json.dumps(result)
                    if not variant.startswith('principal_'):assert 'error' in result
                alerts=c.store.list_impact_alerts('org',target_id=t.task_id)
                assert any(x.target_type=='task_context' and 'alpha evidence' not in x.summary for x in alerts)
                families.append(variant)
            # Complete and expiry behavior over real HTTP; no field ownership overrides.
            h.register_agent_profile(a,'terminal');t=h.create_task_context(u,'terminal');h.complete_task_context(u,t.task_id)
            try:h.create_context_snapshot(u,t.task_id,[])
            except PermissionDeniedError:checks+=1
            else:raise AssertionError('Completed task revived')
            wire('/v1/runtime/tasks',{'params':{'agent_id':'terminal','actor_id':'admin'}},expected=400)
            wire('/v1/runtime/profiles/update',{'params':{'agent_id':'terminal','profile_generation':100}},actor=a,expected=400)
            assert c.verify_audit_chain(a).valid
            rls={}
            if sandbox:
                with c.store.transaction():
                    assert c.store._execute('SELECT rolsuper FROM pg_roles WHERE rolname=current_user')[0][0] is False
                    with c.store.tenant_scope('foreign'):
                        for table in ('agent_profiles','task_contexts','context_snapshots','task_revocations'):
                            rows=c.store._execute('SELECT COUNT(*) FROM '+table)[0][0];assert rows==0
                            flags=c.store._execute('SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=%s::regclass',(table,))[0]
                            assert all(flags);rls[table]={'foreign_rows':rows,'force_rls':True}
        return {'engine':engine,'passed':True,'http_assertion_groups':checks,'revocation_variants':families,'six_families':True,'hmac_oidc':True,'before_dispatch_flush':True,'rls':rls,'browser':'NOT_RUN_NO_UI_CHANGES'}
    finally:
        c.store.close()
        if sandbox:sandbox.close()

if __name__=='__main__':
    results=[run(e) for e in (('sqlite','postgres') if os.environ.get('KNOWLEDGE_SDK_TEST_PG_DSN') else ('sqlite',))]
    print(json.dumps(results,indent=2,sort_keys=True))
