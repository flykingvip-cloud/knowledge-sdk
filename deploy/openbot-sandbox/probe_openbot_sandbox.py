"""Real signed wire checks; reads a local mounted fixture key, never prints it."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from urllib.request import Request,urlopen
from knowledge_sdk import HttpKnowledgeClient,PermissionDeniedError,Purpose
from knowledge_sdk.server.auth import signed_headers
from seed_openbot_sandbox import actor,TENANTS

def probe(base_url,secret_file):
    secret=Path(secret_file).read_text().strip();h=HttpKnowledgeClient(base_url,secret);a=actor(TENANTS[0]);b=actor(TENANTS[0],'sandbox-reader');groups=0
    def denied(fn):
        nonlocal groups
        try:fn()
        except PermissionDeniedError:groups+=1
        else:raise AssertionError('Fixture policy did not fail closed')
    def request(path,who=a,payload=None):
        raw=b'' if payload is None else json.dumps(payload).encode();method='GET' if payload is None else 'POST';headers=signed_headers(who,secret,method,path,raw,purpose=Purpose.READ.value);headers['Content-Type']='application/json'
        with urlopen(Request(base_url+path,data=None if payload is None else raw,headers=headers),timeout=5) as res:
            assert res.headers['Cache-Control']=='no-store';return json.load(res)
    for path in ('/v1/health','/v1/ready'):
        with urlopen(base_url+path,timeout=5) as res:assert res.status==200
        groups+=1
    assert h.get_kb(a,TENANTS[0]+'-enterprise').kb_id.endswith('-enterprise');groups+=1
    assert len(h.list_document_versions(b,TENANTS[0]+'-team-doc'))==2;groups+=1
    for who,doc in ((a,TENANTS[1]+'-enterprise-doc'),(a,TENANTS[0]+'-deny'),(b,TENANTS[0]+'-deny'),(b,TENANTS[0]+'-private-doc')):denied(lambda who=who,doc=doc:h.get_document(who,doc))
    denied(lambda:h.get_kb(actor(TENANTS[0],generation='0'),TENANTS[0]+'-enterprise'))
    denied(lambda:h.get_kb(actor(TENANTS[0],'sandbox-inactive'),TENANTS[0]+'-enterprise'))
    denied(lambda:h.get_kb(actor('unknown-fixture-tenant'),TENANTS[0]+'-enterprise'))
    task=h.create_task_context(b,'fixture-agent-private',purpose=Purpose.READ)
    snapshot=h.create_context_snapshot(b,task.task_id,[{'doc_id':TENANTS[0]+'-private-doc'}]);assert snapshot.items==();groups+=1
    listed=request('/v1/mcp',who=b,payload={'jsonrpc':'2.0','id':1,'method':'tools/list','params':{}});assert len(listed['result']['tools'])==4;groups+=1
    result=request('/v1/mcp',who=b,payload={'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'search_evidence','arguments':{'query':'private','task_id':task.task_id}}})
    assert not result['result'].get('isError',False);assert json.loads(result['result']['content'][0]['text'])['hits']==[];assert 'fixture private evidence' not in json.dumps(result);groups+=1
    assert len(request('/v1/metrics')['counters'])==5;groups+=1
    return {'status':'REAL_SIGNED_SANDBOX_WIRE_PASSED','assertion_groups':groups,'tenants':2,'mcp_tools':4,'agent_binding_did_not_grant_human_access':True,'current_directory_generation_required':True,'UI':'NO_UI_CHANGES','secret_printed':False}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--secret-file',default='/run/secrets/knowledge_auth_secret');a=p.parse_args()
    try:print(json.dumps(probe(a.url,a.secret_file)))
    except Exception:raise SystemExit('Sandbox wire probe failed; no sensitive details emitted') from None
