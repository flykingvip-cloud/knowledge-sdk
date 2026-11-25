"""DRAFT, source-derived offline reference cases. No runtime identity/auth changes."""
from pathlib import Path
import copy
import hashlib
import hmac
import json
import re
import unicodedata

FILES=('identity-lifecycle-fixtures.json','policy-generation-cases.json','hash-vectors-utf8.json','signed-request-canonicalization.json','rollback-activation-cases.json')
SOURCE08='08_TEAM_A_DELTA_SIGNOFF_AND_MIN_SLICE.md'
SOURCE09='09_WAVE1P5_CONSOLIDATED_EXECUTION_DIRECTIVE.md'
SOURCE_SHA256={'06_WAVE1_ACCEPTANCE_AND_NEXT_DIRECTIVE.md': 'aa4adb3c73ef4488f24540f73f05f2f79567b635cea1ae39936709184c28d560', '07_TEAM_A_TO_TEAM_B_CONSENSUS_RESPONSE.md': '1cfe9b4b60522ed48871ce5272cfd2bfa8c35baaf7f6dc528de59731e696a70c', '08_TEAM_A_DELTA_SIGNOFF_AND_MIN_SLICE.md': '78efad1e4bc90c179edf46226475d4f3c1acfd4ba25b30390234c75cfb230096', '09_WAVE1P5_CONSOLIDATED_EXECUTION_DIRECTIVE.md': '0ed8076cf0fffda4dd794c9438cfd581e6a2c7c430a70fe4f03a3464cd4f3cac', '10_WAVE1P5_ACCEPTANCE_AND_DELTA_DIRECTIVE.md': 'd7c3330c0c2c7ae9756fe23a2cab0de8b3c14bc192ea7eb2d4105d32e82a401d'}
SOURCE_SHA256['SOURCE10_STANDALONE_T59_ORIGINAL.md']='3c01cfb0e8fb43f675116ffb0963273a6edcc58596b01685172d854ccf0afc2c'

def verify_sources(root):
    root=Path(root)
    for name,expected in SOURCE_SHA256.items():
        path=root/name
        try:path.resolve(strict=True).relative_to(root.resolve())
        except (OSError,ValueError):raise ValueError('Unsafe/missing original source') from None
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:raise ValueError('Original source hash mismatch: '+name)
    return len(SOURCE_SHA256)

MAX_SAFE=9007199254740991
DRAFT='draft-pending-m1-freeze'

def obj(props, optional=()):
    return {'type':'object','properties':props,'required':[k for k in props if k not in optional],'additionalProperties':False}
def ref(name):return {'$ref':'#/components/schemas/'+name}
def string():return {'type':'string','minLength':1,'maxLength':32000}
def const(value):return {'type':'boolean' if type(value) is bool else 'string','const':value}
def array(schema, count=None):
    return {'type':'array','items':schema,'minItems':count if count is not None else 1,'maxItems':count if count is not None else 100}
def envelope(kind,cases,sources):
    return dict(contract_status=DRAFT,runtime_captured=False,evidence_kind=kind,source_documents=sources,cases=cases)
def schemas():
    def wrapper(kind,item,count):return obj({'contract_status':const(DRAFT),'runtime_captured':const(False),'evidence_kind':const(kind),'source_documents':array(string()),'cases':array(item,count)})
    hashes=obj({'id':string(),'raw':{'type':'string'},'normalized':{'type':'string'},'hash_algorithm':const('sha256'),'raw_hash':ref('Sha256Hex'),'semantic_hash':ref('Sha256Hex')})
    signed=obj({'id':string(),'method':{'type':'string','enum':['GET','POST']},'signed_target':{'type':'string','pattern':'^/v1/','minLength':1},'nonce':{'type':'string','minLength':16,'maxLength':128},'agent_header_present':{'type':'boolean'},'purpose_header_present':{'type':'boolean'},'purpose':{'type':'string','enum':['read','ground_internal_llm']},'body_utf8':{'type':'string'},'body_sha256':ref('Sha256Hex'),'canonical_lines_count':{'type':'integer','enum':[6,8]},'signature':ref('Sha256Hex')},('purpose',))
    out={'HashVectorFixture':wrapper('offline_algorithm_vector_only',hashes,7),'SignedCanonicalizationFixture':wrapper('offline_algorithm_vector_only',signed,4)}
    out['SignedCanonicalizationFixture']['properties'].update(test_only_secret={'type':'string','pattern':'^TEST_ONLY_DO_NOT_USE_IN_PROD_','minLength':32},timestamp={'type':'string','pattern':'^[0-9]+$'},actor_header=string(),agent_header=string(),draft_v2_examples=array(obj({'evidence_kind':const('draft_contract_example_only'),'runtime_captured':const(False),'reason':const('v2_runtime_prohibited_before_m1_freeze'),'method':const('POST'),'path':{'type':'string','enum':['/v2/spaces','/v2/assets']},'status':{'type':'integer','enum':[200,403,409,422]},'body':ref('JsonValue')}),4))
    out['SignedCanonicalizationFixture']['required']+=['test_only_secret','timestamp','actor_header','agent_header','draft_v2_examples']
    policy=obj({'id':string(),'submitted':obj({'policy_generation':ref('JsonValue')},('policy_generation',)),'stored_generation':ref('PolicyGeneration'),'expected':obj({'allowed':{'type':'boolean'},'code':{'anyOf':[ref('ErrorCode'),{'type':'null'}]},'http_status':{'type':'integer','enum':[200,400,403]}})})
    out['PolicyGenerationFixture']=wrapper('contract_scenario_fixture',policy,12)
    ident=obj({'tenant_id':string(),'issuer':string(),'raw_sub':string(),'user_id':string(),'email':string(),'status':{'type':'string','enum':['active','disabled']},'policy_generation':ref('PolicyGeneration')})
    migration=obj({'type':const('identity.rebound'),'administrator_authorized':{'type':'boolean'},'from_issuer':string(),'from_raw_sub':string(),'to_issuer':string(),'to_raw_sub':string()})
    scenario=obj({'id':string(),'existing':array(ident),'incoming':ident,'presented_generation':ref('PolicyGeneration'),'migration':{'anyOf':[migration,{'type':'null'}]},'expected':obj({'allowed':{'type':'boolean'},'code':{'anyOf':[ref('ErrorCode'),{'type':'null'}]},'user_id':{'anyOf':[string(),{'type':'null'}]}})})
    out['IdentityLifecycleFixture']=wrapper('contract_scenario_fixture',scenario,7)
    activation=copy.deepcopy(ref('WriteActivationResult'))
    # Resolve fields here for strict additionalProperties and the same cross-field check.
    activation=obj({'id':string(),'created_version':ref('PolicyGeneration'),'current_version':ref('PolicyGeneration'),'lifecycle_state':{'type':'string','enum':['published','draft','in_review','approved','rejected','superseded','revoked']},'activated':{'type':'boolean'},'rollback_scope':const('content_and_filename_only')})
    activation['x-activation-formula']='created_version === current_version && lifecycle_state === published'
    out['RollbackActivationFixture']=wrapper('contract_scenario_fixture',activation,8)
    return out

def generation_result(submitted,stored):
    v=submitted.get('policy_generation')
    if type(v) is not int or not 1<=v<=MAX_SAFE:return dict(allowed=False,code='VALIDATION_ERROR',http_status=400)
    if v<stored:return dict(allowed=False,code='POLICY_GENERATION_STALE',http_status=403)
    return dict(allowed=True,code=None,http_status=200)

def identity_result(case):
    """Pure proposed mapping rules; never authenticates or provisions a principal."""
    incoming=case['incoming'];key=lambda x:(x['tenant_id'],x['issuer'],x['raw_sub'])
    deny=lambda code:dict(allowed=False,code=code,user_id=None)
    for old in case['existing']:
        if key(old)==key(incoming) and old['user_id']!=incoming['user_id']:return deny('CONFLICT')
        if old['tenant_id']==incoming['tenant_id'] and old['user_id']==incoming['user_id'] and key(old)!=key(incoming):
            event=case['migration']
            expected=dict(type='identity.rebound',administrator_authorized=True,from_issuer=old['issuer'],from_raw_sub=old['raw_sub'],to_issuer=incoming['issuer'],to_raw_sub=incoming['raw_sub'])
            if event!=expected or incoming['policy_generation']<=old['policy_generation']:return deny('PERMISSION_DENIED')
    if incoming['status']!='active':return deny('IDENTITY_REVOKED')
    if case['presented_generation']<incoming['policy_generation']:return deny('POLICY_GENERATION_STALE')
    return dict(allowed=True,code=None,user_id=incoming['user_id'])

def minimum_slice(root):
    source=(Path(root)/SOURCE08).read_text()
    line=next(line for line in source.splitlines() if line.startswith('5. **验收条件确认**'))
    assertions=line.split('验收断言（',1)[1].split('）。',1)[0].split('、')
    if len(assertions)!=10:raise ValueError('Exactly ten original Team B assertions required')
    return dict(contract_status=DRAFT,runtime_captured=False,source=SOURCE08+'#3',
      synchronous_writes=['POST /v2/spaces','POST /v2/assets'],
      assertions=[dict(id='A%02d'%(i+1),description=text) for i,text in enumerate(assertions)],
      strengthening=['Idempotency-Key: same key+payload returns first result; changed payload gives409IDEMPOTENCY_CONFLICT; no unkeyed write retry',
        'Version-locked evidence+bare excerpt hash+current authority; five-field result never renders L2 draft as published'],
      freeze_authorized=False)

def build(root):
    root=Path(root)
    blocks08=[json.loads(x) for x in re.findall(r'```json\n(.*?)\n```',(root/SOURCE08).read_text(),re.S)]
    blocks09=[json.loads(x) for x in re.findall(r'```json\n(.*?)\n```',(root/SOURCE09).read_text(),re.S)]
    hashes=envelope('offline_algorithm_vector_only',blocks08[0]+blocks09[0],[SOURCE08+'#2.1',SOURCE09+'#2.1'])
    original=blocks08[1];headers=original['headers']
    base=dict(id='sign_8line_post_base_from_08',method=original['method'],signed_target=original['path'],nonce=headers['X-KB-Nonce'],agent_header_present=True,purpose_header_present=True,purpose=headers['X-KB-Purpose'],body_utf8=original['body_utf8'],body_sha256=original['body_sha256'],canonical_lines_count=original['canonical_lines_count'],signature=headers['X-KB-Signature'])
    cases=[base]+copy.deepcopy(blocks09[1])
    for c in cases:c.setdefault('purpose_header_present','purpose' in c)
    signed=envelope('offline_algorithm_vector_only',cases,[SOURCE08+'#2.2',SOURCE09+'#2.2'])
    signed.update(test_only_secret=original['test_only_secret'],timestamp=headers['X-KB-Timestamp'],actor_header=headers['X-KB-Actor'],agent_header=headers['X-KB-Agent'])
    signed['draft_v2_examples']=[dict(evidence_kind='draft_contract_example_only',runtime_captured=False,reason='v2_runtime_prohibited_before_m1_freeze',method='POST',path='/v2/assets',status=status,body=body) for status,body in [(200,dict(created_version=3,current_version=3,lifecycle_state='published',activated=True,rollback_scope='content_and_filename_only')),(403,{'error':{'code':'PERMISSION_DENIED','message':'Resource unavailable','retryable':False,'request_id':'req-offline','details':{}}}),(409,{'error':{'code':'IDEMPOTENCY_CONFLICT','message':'Conflict','retryable':False,'request_id':'req-offline','details':{}}}),(422,{'error':{'code':'TAMPERED_EXCERPT','message':'Evidence unavailable','retryable':False,'request_id':'req-offline','details':{}}})]]
    policy=[]
    inputs=[('one',1,1),('max_safe',MAX_SAFE,1),('stale',1,2),('zero',0,1),('negative',-1,1),('missing',None,1),('null',None,1),('string_one','1',1),('string_abc','abc',1),('boolean',True,1),('fraction',1.5,1),('overflow',MAX_SAFE+1,1)]
    for name,value,stored in inputs:
        submitted={} if name=='missing' else {'policy_generation':value}
        policy.append(dict(id=name,submitted=submitted,stored_generation=stored,expected=dict(allowed=name in ('one','max_safe'),code=None if name in ('one','max_safe') else 'POLICY_GENERATION_STALE' if name=='stale' else 'VALIDATION_ERROR',http_status=200 if name in ('one','max_safe') else 403 if name=='stale' else 400)))
    policy=envelope('contract_scenario_fixture',policy,[SOURCE08+'#2.3'])
    old=dict(tenant_id='tenant-sandbox-01',issuer='https://idp-a.example.invalid',raw_sub='raw-sub-001',user_id='stable-user-001',email='fixture@example.invalid',status='active',policy_generation=1)
    other={**old,'issuer':'https://idp-b.example.invalid','raw_sub':'raw-sub-002'}
    migrated={**other,'policy_generation':2}
    event=dict(type='identity.rebound',administrator_authorized=True,from_issuer=old['issuer'],from_raw_sub=old['raw_sub'],to_issuer=other['issuer'],to_raw_sub=other['raw_sub'])
    identity=[]
    scenarios=[('composite_key_cannot_reassign_user',{**old,'user_id':'stable-user-002'},1,None),('same_sub_other_tenant_is_distinct',{**old,'tenant_id':'tenant-sandbox-02','user_id':'stable-user-002'},1,None),('cross_idp_same_email_new_user_not_merged',{**other,'user_id':'stable-user-002'},1,None),('cross_idp_same_user_without_rebound_denied',other,1,None),('explicit_identity_rebound',migrated,2,event),('deactivated_existing_session_task',{**old,'status':'disabled','policy_generation':2},1,None),('revoked_generation_existing_session_task',{**old,'policy_generation':2},1,None)]
    verdicts=[(False,'CONFLICT',None),(True,None,'stable-user-002'),(True,None,'stable-user-002'),(False,'PERMISSION_DENIED',None),(True,None,'stable-user-001'),(False,'IDENTITY_REVOKED',None),(False,'POLICY_GENERATION_STALE',None)]
    for (name,incoming,presented,migration),(allowed,code,user_id) in zip(scenarios,verdicts):
        case=dict(id=name,existing=[copy.deepcopy(old)],incoming=incoming,presented_generation=presented,migration=migration)
        case['expected']=dict(allowed=allowed,code=code,user_id=user_id);identity.append(case)
    identity=envelope('contract_scenario_fixture',identity,[SOURCE08+'#remaining-technical-deltas-1'])
    rows=re.findall(r'\| `(act_[^`]+|neg_[^`]+)` \| `(\d+)` \| `(\d+)` \| `([^`]+)` \| `(true|false)` \|',(root/SOURCE09).read_text())
    if len(rows)!=8:raise ValueError('Original09 must contain eight literal rollback rows')
    rollback=envelope('contract_scenario_fixture',[dict(id=i,created_version=int(c),current_version=int(v),lifecycle_state=s,activated=a=='true',rollback_scope='content_and_filename_only') for i,c,v,s,a in rows],[SOURCE09+'#2.3'])
    return {FILES[0]:('IdentityLifecycleFixture',identity),FILES[1]:('PolicyGenerationFixture',policy),FILES[2]:('HashVectorFixture',hashes),FILES[3]:('SignedCanonicalizationFixture',signed),FILES[4]:('RollbackActivationFixture',rollback)}

def canonical(case,fixture):
    parts=[case['method'].upper(),case['signed_target'],fixture['actor_header'],fixture['timestamp'],case['nonce'],hashlib.sha256(case['body_utf8'].encode('utf-8')).hexdigest()]
    if case['agent_header_present'] or case['purpose_header_present']:
        parts.extend([fixture['agent_header'] if case['agent_header_present'] else '',case.get('purpose','') if case['purpose_header_present'] else ''])
    return '\n'.join(parts).encode('utf-8')

def verify(root,fixtures):
    """Cross-recompute ALL literals and identity/generation/activation decisions."""
    verify_sources(root)
    expected=build(root)
    for filename,(_,value) in expected.items():
        if json.dumps(fixtures[filename],sort_keys=True,ensure_ascii=False,allow_nan=False)!=json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False):raise ValueError('Source fixture literal/coverage mismatch: '+filename)
    checklist=json.loads((Path(root)/'contracts/minimum-slice-checklist.json').read_text())
    if checklist!=minimum_slice(root):raise ValueError('Minimum slice source mismatch')
    package=(Path(root)/'M1_DECISION_PACKAGE.md').read_text()
    if any(item['id'] not in package or item['description'] not in package for item in checklist['assertions']):raise ValueError('Minimum slice package mismatch')
    for case in fixtures[FILES[2]]['cases']:
        normalized=' '.join(unicodedata.normalize('NFC',case['raw']).split())
        if normalized!=case['normalized'] or hashlib.sha256(case['raw'].encode()).hexdigest()!=case['raw_hash'] or hashlib.sha256(normalized.encode()).hexdigest()!=case['semantic_hash']:raise ValueError('Source hash mismatch')
    signed=fixtures[FILES[3]]
    for case in signed['cases']:
        message=canonical(case,signed)
        if len(message.split(b'\n'))!=case['canonical_lines_count'] or hashlib.sha256(case['body_utf8'].encode()).hexdigest()!=case['body_sha256'] or not hmac.compare_digest(hmac.new(signed['test_only_secret'].encode(),message,hashlib.sha256).hexdigest(),case['signature']):raise ValueError('Source HMAC mismatch')
    for case in fixtures[FILES[0]]['cases']:
        if identity_result(case)!=case['expected']:raise ValueError('Identity rule mismatch')
    for case in fixtures[FILES[1]]['cases']:
        if generation_result(case['submitted'],case['stored_generation'])!=case['expected']:raise ValueError('Policy-generation rule mismatch')
    for case in fixtures[FILES[4]]['cases']:
        if type(case['activated']) is not bool or case['activated']!=((case['created_version']==case['current_version']) and case['lifecycle_state']=='published'):raise ValueError('Rollback activation mismatch')
    return dict(minimum_slice_assertions=len(checklist['assertions']),hash_vectors=7,hmac_vectors=4,rollback_cases=8,identity_cases=7,policy_cases=12,runtime_v2_implemented=False)
