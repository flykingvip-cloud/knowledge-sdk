"""Signed v1 compatibility plus actual v2 probe; only isolated loopback fixtures."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from urllib.parse import urlsplit
from seed_openbot_sandbox import actor,TENANTS
from probe_openbot_sandbox import probe as probe_v1
from knowledge_sdk.server.v2_auth import signed_v2_headers


def probe(base,key_file):
    target=urlsplit(base)
    if target.scheme!='http' or target.hostname not in ('127.0.0.1','localhost') or target.username or target.port in (3000,3001,8000,8002,8090,8091):raise ValueError('Owned loopback fixture required')
    legacy=probe_v1(base,key_file)
    secret=Path(key_file).read_text().strip();a=actor(TENANTS[0]);org=a.org_id
    context=dict(request_id='wave2-sandbox-probe',tenant_id=org,actor=dict(issuer='https://sandbox.example.invalid',subject_id=a.user_id,actor_type='human',roles=list(a.roles),department_ids=list(a.department_ids),ancestor_department_ids=[],org_roles=list(a.org_roles),clearance_level=a.clearance_level,clearance_tags=[],policy_generation=1,session_id=a.session_id),agent=dict(agent_id='fixture-agent-private',profile_generation=1,task_id=''),purpose='read')
    checks=0
    def wire(method,path,payload=None,key=None,expected=200):
        nonlocal checks
        body=json.dumps(payload,separators=(',',':')).encode() if payload is not None else b''
        headers=signed_v2_headers(context,secret,method,path,body);headers['Content-Type']='application/json'
        if key is not None:headers['Idempotency-Key']=key
        try:r=urlopen(Request(base+path,data=body if method=='POST' else None,method=method,headers=headers),timeout=15)
        except HTTPError as exc:r=exc
        with r:
            result=json.loads(r.read());assert r.status==expected,(path,r.status);assert r.headers.get('Cache-Control')=='no-store'
        checks+=1;return result
    spaces=wire('GET','/v2/spaces');assert spaces and all(k['tenant_id']==org for k in spaces)
    wire('GET','/v2/spaces/'+org+'-private')
    wire('GET','/v2/assets/'+org+'-private-doc')
    payload=dict(kb_id=org+'-private',content='wave2 isolated fixture content',filename='wave2.txt',asset_type='document',idempotency_key='wave2-probe')
    first=wire('POST','/v2/assets',payload,'wave2-probe');again=wire('POST','/v2/assets',payload,'wave2-probe');assert first==again
    assert len(first['raw_hash'])==64 and first['hash_algorithm']=='sha256'
    conflict=wire('POST','/v2/assets',dict(payload,content='different'),'wave2-probe',409);assert conflict['error']['code']=='IDEMPOTENCY_CONFLICT'
    rollback=wire('POST','/v2/assets/'+org+'-private-doc:rollback',{'target_version':1});assert rollback['activated'] and rollback['rollback_scope']=='content_and_filename_only'
    return {'status':'REAL_SIGNED_WAVE2_SANDBOX_PASSED','v2_http_checks':checks,'v1_compatibility':legacy,'runtime_v2_implemented':True,'nonproduction_only':True}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--key-file',default='/run/secrets/knowledge_auth_secret');a=p.parse_args()
    print(json.dumps(probe(a.url,a.key_file)))
