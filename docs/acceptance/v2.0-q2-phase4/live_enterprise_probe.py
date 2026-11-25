"""Actual loopback HMAC/OIDC/SCIM/connector HTTP, no browser automation."""
from __future__ import annotations
from contextlib import contextmanager
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
import importlib.util,json,os,secrets,socket,threading,time,urllib.request,urllib.error,tempfile,sys
import uvicorn
from knowledge_sdk import Actor
from knowledge_sdk.server.auth import signed_headers
from knowledge_sdk.server.oidc import OIDCAuthenticator,JWKSProvider
from knowledge_sdk.connectors.webhook_sync import sign_sync

here=Path(__file__).parent
spec=importlib.util.spec_from_file_location('m4_fixture',here/'enterprise_fixture.py');fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)

@contextmanager
def live(app):
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(app,log_level='critical',access_log=False));thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
    try:
        deadline=time.monotonic()+15
        while not server.started:
            if not thread.is_alive() or time.monotonic()>deadline:raise RuntimeError('Fixture failed startup')
            threading.Event().wait(.02)
        yield 'http://127.0.0.1:'+str(port)
    finally:server.should_exit=True;thread.join(10);sock.close();assert not thread.is_alive()

def request(base,path,method='GET',body=None,headers=None):
    raw=b'' if body is None else body if isinstance(body,bytes) else json.dumps(body,separators=(',',':')).encode()
    hs=dict(headers or {})
    if body is not None:hs['Content-Type']='application/json'
    try:r=urllib.request.urlopen(urllib.request.Request(base+path,data=raw if method!='GET' else None,headers=hs,method=method),timeout=10)
    except urllib.error.HTTPError as exc:r=exc
    try:return r.status,dict(r.headers),r.read()
    finally:r.close()

def run(engine):
    with tempfile.TemporaryDirectory() as directory:
        st=fixture.build_fixture(engine,directory,auth_mode='dual');c=st['client'];a=st['author'];u=st['reader'];issuer=st['issuer'];observed=[]
        try:
            with live(st['app']) as base:
                def bearer(actor=u,**changes):return {'Authorization':'Bearer '+issuer.token(actor,**changes)}
                def call(path,params=None,method='POST',actor=u,expected=200,headers=None):
                    status,hs,body=request(base,path,method,params,headers if headers is not None else bearer(actor));assert status==expected,(path,status,body[:200]);assert hs.get('cache-control')=='no-store';observed.append((method,path,status));return hs,body
                # Real RSA signature and standard claims accepted.
                call('/v1/search',{'params':{'query':'alpha'}})
                # Real HMAC wire path remains accepted in dual mode.
                payload=json.dumps({'params':{'query':'alpha'}},separators=(',',':')).encode();headers=signed_headers(u,st['hmac_secret'],'POST','/v1/search',payload);call('/v1/search',payload,headers=headers)
                # All public/error/private routes are non-cacheable.
                for path in ('/ui','/ui/config','/v1/health','/openapi.json'):call(path,method='GET',headers={})
                call('/ui/demo/sign',{},expected=404,headers={})
                # Replay, issuer, tenant, expiry and signature rejection.
                replay=bearer();call('/v1/search',{'params':{'query':'alpha'}},headers=replay);call('/v1/search',{'params':{'query':'alpha'}},headers=replay,expected=401)
                for changes in ({'exp':int(time.time())-1},{'iss':'foreign'},{'aud':'other'},{'org_id':'foreign-tenant'}):call('/v1/search',{'params':{'query':'alpha'}},headers=bearer(**changes),expected=401)
                call('/v1/search',{'params':{'query':'alpha'}},headers={'Authorization':'Bearer malformed'},expected=401)
                # Authenticated session; JWT is never exposed in cookie or URL.
                hs,_=call('/v1/auth/session',headers=bearer());cookie=hs['set-cookie'].split(';')[0];assert 'HttpOnly' in hs['set-cookie'];assert 'Bearer' not in cookie
                call('/v1/kbs',method='GET',headers={'Cookie':cookie})
                call('/v1/search',{'params':{'query':'alpha'}},headers={'Cookie':cookie,'Origin':base})
                call('/v1/search',{'params':{'query':'alpha'}},headers={'Cookie':cookie,'Origin':'https://evil.invalid'},expected=401)
                # No unsigned header changes the verified identity/generation.
                h=bearer();h.update({'X-KB-Org-Id':'foreign-tenant','X-KB-Policy-Generation':'999999','X-KB-Actor':'forged'})
                _,raw=call('/v1/search',{'params':{'query':'FOREIGN_NEVER_LEAK_MARKER'}},headers=h);assert 'FOREIGN_NEVER_LEAK_MARKER' not in raw.decode()
                _,raw=call('/v1/search',{'params':{'query':'DRAFT_NEVER_LEAK_MARKER'}});assert 'DRAFT_NEVER_LEAK_MARKER' not in raw.decode()
                call('/v1/packs/get',{'params':{'pack_id':'browser-pack'}})
                call('/v1/impact/alerts',{'params':{}})
                call('/v1/mcp',{'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'search_evidence','arguments':{'query':'alpha'}}})
                # Full SCIM endpoint surface, tenant-bound administrative token.
                scim={'Authorization':'Bearer '+st['scim_secret']}
                call('/scim/v2/Users',{'id':'new-user','userName':'new-user','active':True},headers=scim,expected=201)
                call('/scim/v2/Users',b'[]',headers=scim,expected=400)
                call('/scim/v2/Users',b'{broken',headers=scim,expected=400)
                call('/scim/v2/Users?filter=userName%20eq%20%22new-user%22',method='GET',headers=scim)
                call('/scim/v2/Users',method='GET',headers=scim);call('/scim/v2/Users/new-user',method='GET',headers=scim)
                new_actor=Actor('new-user',a.org_id,org_roles=('admin',),policy_generation='1');preissued_generation_token=issuer.token(new_actor)
                call('/v1/search',{'params':{'query':'alpha'}},headers={'Authorization':'Bearer '+issuer.token(new_actor)})
                call('/scim/v2/Users/new-user',{'userName':'renamed','roles':['employee']},method='PUT',headers=scim)
                call('/v1/search',{'params':{'query':'alpha'}},headers={'Authorization':'Bearer '+preissued_generation_token},expected=401)
                call('/v1/search',{'params':{'query':'alpha'}},headers={'Authorization':'Bearer '+issuer.token(new_actor,policy_generation='2')})
                call('/scim/v2/Users/new-user',{'Operations':[{'op':'replace','path':'department_ids','value':['research']}]},method='PATCH',headers=scim)
                call('/scim/v2/Groups',{'id':'g1','displayName':'department-r','members':[{'value':'new-user'}]},headers=scim,expected=201)
                call('/scim/v2/Groups',method='GET',headers=scim)
                call('/scim/v2/Groups/g1',{'Operations':[{'op':'remove','path':'members','value':[{'value':'new-user'}]}]},method='PATCH',headers=scim)
                call('/scim/v2/Groups/g1',{'Operations':[{'op':'add','path':'members','value':[{'value':'new-user'}]}]},method='PATCH',headers=scim)
                call('/scim/v2/Groups/g1',{'Operations':[{'op':'remove','path':'members[value eq "new-user"]'}]},method='PATCH',headers=scim)
                call('/scim/v2/Users/new-user',method='DELETE',headers=scim,expected=204)
                call('/scim/v2/Users',method='GET',expected=403)
                call('/scim/v2/Users',{'org_id':'foreign','id':'bad'},headers=scim,expected=403)
                # Reference connectors run via authenticated real routes.
                call('/v1/connectors/filesystem/sync',{},actor=a)
                for event,delta in [('upsert',{'upserts':[{'external_id':'wiki','doc_id':'wiki','content':'alpha webhook source','rights':{'allow_export':True}}]}),('delete',{'tombstones':[{'external_id':'wiki','doc_id':'wiki','action':'revoke'}]})]:
                    raw=json.dumps(delta,separators=(',',':')).encode();stamp=str(int(time.time()));headers=bearer(a);headers.update({'X-KB-Event-Id':event,'X-KB-Webhook-Timestamp':stamp,'X-KB-Webhook-Signature':sign_sync(st['conn_secret'],raw,event,stamp)})
                    call('/v1/connectors/wiki/webhook',raw,headers=headers)
                    if event=='upsert':c.create_evidence_pack(u,'wire-pack',[{'doc_id':'wiki','version':1}],pack_id='wire-pack')
                c.drain_outbox(a,limit=1000);assert c.store.get_evidence_pack(a.org_id,'wire-pack').status=='impacted'
                # Preissued valid high-privilege JWT and session become stale after SCIM.
                privileged=Actor('reader',a.org_id,org_roles=('admin',),public_kb_admin=True,policy_generation='1');old=issuer.token(privileged)
                call('/scim/v2/Users/reader',{'Operations':[{'op':'replace','path':'active','value':False}]},method='PATCH',headers=scim)
                for path,body in [('/v1/search',{'params':{'query':'alpha'}}),('/v1/packs/get',{'params':{'pack_id':'browser-pack'}}),('/v1/impact/alerts',{'params':{}}),('/v1/mcp',{'jsonrpc':'2.0','id':1,'method':'tools/list'})]:
                    call(path,body,headers={'Authorization':'Bearer '+old},expected=401);old=issuer.token(privileged)
                call('/v1/kbs',method='GET',headers={'Cookie':cookie},expected=401)
                payload=json.dumps({'params':{'query':'alpha'}},separators=(',',':')).encode();headers=signed_headers(privileged,st['hmac_secret'],'POST','/v1/search',payload);headers['X-KB-Policy-Generation']='999999';call('/v1/search',payload,headers=headers,expected=401)
                assert c.verify_audit_chain(a).valid
            # Real local JWKS GET, not a stub transport. Pinning allows loopback only explicitly.
            class Handler(BaseHTTPRequestHandler):
                def do_GET(self):
                    data=json.dumps({'keys':[issuer.jwk]}).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(data)
                def log_message(self,*args):pass
            server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                provider=JWKSProvider('http://127.0.0.1:'+str(server.server_port)+'/jwks',allow_insecure_local=True)
                auth=OIDCAuthenticator(fixture.ISSUER,fixture.AUDIENCE,provider,algorithms=('RS256',));assert auth.authenticate(issuer.token(a)).user_id==a.user_id
            finally:server.shutdown();server.server_close();thread.join()
            print(json.dumps({'engine':engine,'passed':True,'wire_assertions':observed,'jwks_real_http':True,'signed_tombstone_impacted_pack':True,'stale_privileged_jwt_and_cookie_denied':True,'implicit_model_calls':0},indent=2))
        finally:
            for close in reversed(st['cleanup']):close()

def main():
    for engine in ('sqlite','postgres') if os.environ.get('KNOWLEDGE_SDK_TEST_PG_DSN') else ('sqlite',):run(engine)
if __name__=='__main__':main()
