"""Only validates a pending review package. Cannot authorize/sign/freeze anything."""
from __future__ import annotations
import json,hashlib
from pathlib import Path
ROOT=Path(__file__).parent
REFS={'main': 'b953c9922cc1096e0e88455dab6746c01a9d27f9', 'v2.0.0_object': '4afc1d71f9f5583d93c28f3f4380544a4e5fcc46', 'v2.0.0_peeled': 'b953c9922cc1096e0e88455dab6746c01a9d27f9', 'q3_m1': '69b6c986251161ca02b1e77b0806e2c8861a30b6', 'q3_m2': 'd1532951b08c8ef950dc604aa3427ceb9eab5d75', 'wave1': '60b6436ed9fccb4b49ae32e30f1664412e505888'}

def check(data):
    required={'schema','work_item','status','scope_authorization','refs','source_hashes','required_signoff_roles','approvals','decisions'}
    if set(data)!=required or data['schema']!='m1-readiness-1' or data['work_item']!='SDK-22':raise ValueError('Invalid manifest contract')
    if data['status']!='pending_joint_signoff' or data['approvals']!=[]:raise ValueError('This checker cannot validate or authorize signoffs')
    if data['scope_authorization']!='owner-t58u-engineering-only-not-joint-signoff':raise ValueError('Scope is not joint approval')
    if data['refs']!=REFS:raise ValueError('Protected refs mismatch')
    expected={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.glob('0[0-5]_*.md')}
    if data['source_hashes']!=expected or len(expected)!=6:raise ValueError('Original governance source mismatch')
    if data['required_signoff_roles']!=['owner','architecture','team_a','team_b']:raise ValueError('Incomplete signoff roles')
    decisions=data['decisions']
    if not isinstance(decisions,list) or [x.get('id') for x in decisions]!=['D'+str(i) for i in range(1,8)]:raise ValueError('Exactly D1-D7 required')
    fields={'id','title','status','owner_role','owner_identity','options','recommendation','selected_option','dissent','open_questions','evidence','approvals'}
    for d in decisions:
        if set(d)!=fields or d['status']!='pending_joint_signoff' or d['owner_identity'] is not None or d['selected_option'] is not None or d['approvals']!=[]:raise ValueError('Unverified decision/signature state')
        if not d['title'] or not d['owner_role'] or d['dissent']!=[]:raise ValueError('No invented owner or dissent')
        options=d['options']
        if not isinstance(options,list) or len(options)<2 or len({o['id'] for o in options})!=len(options) or d['recommendation'] not in {o['id'] for o in options}:raise ValueError('Compare at least two options')
        for o in options:
            if set(o)!={'id','description','pros','cons','risks','migration'} or any(not isinstance(o[k],str) or not o[k] for k in ('id','description','migration')):raise ValueError('Invalid option')
            for k in ('pros','cons','risks'):
                if not isinstance(o[k],list) or not o[k] or any(not isinstance(v,str) or not v for v in o[k]):raise ValueError('Incomplete option analysis')
        for k in ('open_questions','evidence'):
            if not isinstance(d[k],list) or not d[k] or any(not isinstance(v,str) or not v for v in d[k]):raise ValueError('Incomplete review evidence')
        for e in d['evidence']:
            if not (ROOT.parents[2]/e).is_file():raise ValueError('Missing evidence')
    return {'status':'WELL_FORMED_PENDING','freeze_authorized':False,'decisions':7,'signoffs_verified':0}

if __name__=='__main__':print(json.dumps(check(json.loads((ROOT/'m1-freeze-manifest.json').read_text())),sort_keys=True))
