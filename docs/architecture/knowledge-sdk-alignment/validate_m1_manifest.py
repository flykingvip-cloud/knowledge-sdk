"""Only validates a pending review package. Cannot authorize/sign/freeze anything."""
from __future__ import annotations
import json,hashlib,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'contracts'))
import delta_contracts as delta
CONTRACT_ROOT_FILES=('fixture-evidence-boundaries.json','README.md','delta_contracts.py','generate_assets.py','validate_assets.py','fixture-schemas.json','minimum-slice-checklist.json','openapi-v2-draft.yaml','openbot-adapter-dto.d.ts','uri-mapping.ts','uri-mapping.test.ts','package.json','package-lock.json')
REFS={'main': 'b953c9922cc1096e0e88455dab6746c01a9d27f9', 'v2.0.0_object': '4afc1d71f9f5583d93c28f3f4380544a4e5fcc46', 'v2.0.0_peeled': 'b953c9922cc1096e0e88455dab6746c01a9d27f9', 'q3_m1': '69b6c986251161ca02b1e77b0806e2c8861a30b6', 'q3_m2': 'd1532951b08c8ef950dc604aa3427ceb9eab5d75', 'wave1': '60b6436ed9fccb4b49ae32e30f1664412e505888'}

def validate_asset_hashes(hashes, root=ROOT):
    """Closed repo-relative coverage; no absolute/traversal/outside-root symlink."""
    if not isinstance(hashes,dict):raise ValueError('Asset hashes must be a map')
    root=Path(root).resolve()
    repo=root.parents[2]
    fixed={'contracts/'+name for name in CONTRACT_ROOT_FILES}|{'M1_DECISION_PACKAGE.md','validate_m1_manifest.py','WAVE1P5B_SOURCE_PROVENANCE.json'}
    fixture_dir=root/'contracts/contract-fixtures'
    try:fixture_dir.resolve(strict=True).relative_to(root)
    except (ValueError,OSError):raise ValueError('Unsafe fixture directory') from None
    files=set(root/name for name in fixed)|set((root/'contracts').glob('*.*'))|set(fixture_dir.glob('*.json'))
    # All known fixture names remain mandatory even if both file and hash are deleted.
    files.update(fixture_dir/name for name in delta.FILES)
    files.update(fixture_dir/name for name in ('identity-context.json','agent-intersection-deny.json','kb-lifecycle.json','dual-uri-evidence.json','calibrated-search-response.json','error-envelope.json'))
    files={p for p in files if p in {root/name for name in fixed} or p.parent==fixture_dir or p.is_file()}
    expected={p.relative_to(repo).as_posix() for p in files}
    if set(hashes)!=expected:raise ValueError('Missing or extra contract assets')
    for relative,digest in hashes.items():
        if not isinstance(relative,str) or '\\' in relative or any(part in ('','..','.') for part in relative.split('/')):raise ValueError('Unsafe asset path')
        if Path(relative).is_absolute() or not isinstance(digest,str) or not re.fullmatch('[0-9a-f]{64}',digest):raise ValueError('Malformed hash/path')
        path=repo/relative
        try:
            path.resolve(strict=True).relative_to(root)
            if not path.is_file():raise ValueError('Not an asset file')
            actual=hashlib.sha256(path.read_bytes()).hexdigest()
        except (ValueError,OSError):raise ValueError('Missing or outside-root asset') from None
        if actual!=digest:raise ValueError('Contract asset hash mismatch')
    return len(expected)

def check(data):
    required={'schema','work_item','status','scope_authorization','refs','source_hashes','required_signoff_roles','approvals','decisions','freeze_authorized','contract_asset_hashes','contract_delta_status','delta_source_hashes'}
    if set(data)!=required or data['schema']!='m1-readiness-1' or data['work_item']!='SDK-22':raise ValueError('Invalid manifest contract')
    if data['freeze_authorized'] is not False:raise ValueError('Never authorize a freeze')
    if data['contract_delta_status']!='VERIFIED_DRAFT_CONTRACTS_PENDING_JOINT_SIGNOFF':raise ValueError('Unverified delta completeness')
    if data['delta_source_hashes']!=delta.SOURCE_SHA256:raise ValueError('Delta original source inventory mismatch')
    verified=delta.verify(ROOT,{name:json.loads((ROOT/'contracts/contract-fixtures'/name).read_text()) for name in delta.FILES})
    asset_count=validate_asset_hashes(data['contract_asset_hashes'])
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
    return {'status':'WELL_FORMED_PENDING','freeze_authorized':False,'decisions':7,'signoffs_verified':0,'contract_assets_verified':asset_count,'contract_delta_complete':True,'verified_vectors':verified,'contract_delta_status':data['contract_delta_status']}

if __name__=='__main__':
    result=check(json.loads((ROOT/'m1-freeze-manifest.json').read_text()))
    print(json.dumps(result,sort_keys=True))
    raise SystemExit(0 if result['contract_delta_complete'] else 2)
