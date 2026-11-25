"""Reproducible DRAFT-only assets from the supplied C01-C09 examples; no runtime routes."""
from pathlib import Path
import json,re,copy
import delta_contracts as delta
ROOT=Path(__file__).parent
source=(ROOT.parent/'03_DOMAIN_CONTRACTS.md').read_text()
examples=[json.loads(x) for x in re.findall(r'```json\n(.*?)\n```',source,re.S)]
NAMES=['IdentityContext','KnowledgeBase','KnowledgeAsset','DocumentVersion','EvidenceRecord','SearchExchange','IngestionJob','ConnectorSyncExchange','ErrorEnvelope']
ENUMS={'actor_type':['human','agent','service'],'purpose':['read','ground_internal_llm','ground_external_llm','export','eval_and_train'],'space_type':['enterprise_public','department','personal'],'visibility':['private','team','enterprise'],'governance_tier':['l1_agile','l2_controlled'],'asset_type':['document','web_snapshot','dataset','deliverable','structured_record','code_artifact'],'source_kind':['upload','connector','web_crawl','agent_generated','api_sync'],'lifecycle_state':['draft','in_review','approved','published','rejected','superseded','revoked']}
ERRORS=['VALIDATION_ERROR','UNAUTHENTICATED','SIGNATURE_INVALID','REPLAY_DETECTED','PERMISSION_DENIED','IDENTITY_REVOKED','POLICY_GENERATION_STALE','REDACTION_FAIL_CLOSED','RESOURCE_NOT_FOUND','CONFLICT','IDEMPOTENCY_CONFLICT','LIFECYCLE_CONFLICT','TAMPERED_EXCERPT','ANCHOR_UNRESOLVABLE','RATE_LIMITED','CONTEXT_BUDGET_EXCEEDED','BACKEND_UNAVAILABLE']
def ref(n):return {'$ref':'#/components/schemas/'+n}
def obj(props):return {'type':'object','properties':props,'required':list(props),'additionalProperties':False}
def infer(value,key=''):
 if key=='policy_generation':return ref('PolicyGeneration')
 if key.endswith('_hash'):return ref('Sha256Hex')
 if key in ENUMS:return {'type':'string','enum':ENUMS[key]}
 if key in ('code','error_code'):return ref('ErrorCode') if value is not None else {'anyOf':[ref('ErrorCode'),{'type':'null'}]}
 if value is None:
  base={'type':'integer','minimum':1} if key=='rollback_from_version' else {'type':'string','format':'date-time'} if key in ('archived_at','valid_from','valid_to') else {'type':'string'}
  return {'anyOf':[base,{'type':'null'}]}
 if type(value) is bool:return {'type':'boolean'}
 if type(value) is int:return {'type':'integer','minimum':0}
 if type(value) is float:return {'type':'number','minimum':0,'maximum':1} if key in ('calibrated_score','min_calibrated_score') else {'type':'number'}
 if isinstance(value,list):return {'type':'array','items':infer(value[0]) if value else ref('JsonValue'),'maxItems':1000}
 if isinstance(value,dict):return obj({k:infer(v,k) for k,v in value.items()}) if value else {'type':'object','additionalProperties':ref('JsonValue')}
 schema={'type':'string','maxLength':32000}
 if key in ('created_at','updated_at','published_at'):schema['format']='date-time'
 if key=='canonical_uri':return ref('CanonicalKbUri')
 return schema
schemas={'JsonValue':{'anyOf':[{'type':'null'},{'type':'boolean'},{'type':'number'},{'type':'string'},{'type':'array','items':ref('JsonValue')},{'type':'object','additionalProperties':ref('JsonValue')}]},'ErrorCode':{'type':'string','enum':ERRORS},'CanonicalKbUri':{'type':'string','pattern':r'^kb://org/[^/]+/doc/[^@]+@[1-9][0-9]*(#(anchor|chunk)=.+)?$'},'LegacyKuUri':{'type':'string','pattern':r'^ku://kb/[^/]+/doc/[^@]+@[^#]+(#.*)?$'}}
for name,example in zip(NAMES,examples):schemas[name]=infer(example)
schemas['Sha256Hex']={'type':'string','pattern':'^[0-9a-f]{64}$','minLength':64,'maxLength':64,'description':'Bare lowercase SHA-256 hex; algorithm is a separate hash_algorithm field.'}
schemas['PolicyGeneration']={'type':'integer','minimum':1,'maximum':9007199254740991,'description':'DRAFT v2 only: safe positive integer; no boolean/string/null coercion. Existing v1 generation-zero semantics unchanged.'}
schemas['IdentityContext']['properties']['agent']['properties']['profile_generation']['minimum']=1
schemas['IdentityContext']['required'].remove('agent')
schemas['KnowledgeBase']['properties']['status']['enum']=['active','archived']
schemas['IngestionJob']['properties']['status']['enum']=['queued','parsing','chunking','indexing','completed','failed','cancelled']
schemas['IngestionJob']['properties']['progress_pct']['maximum']=100
schemas['EvidenceRecord']['properties']['verification_status']['enum']=['verified','unverified','revoked','unresolvable']
schemas['SearchRequest']=schemas['SearchExchange']['properties']['request'];schemas['SearchResponse']=schemas['SearchExchange']['properties']['response']
schemas['SearchRequest']['properties']['mode']['enum']=['keyword','vector','hybrid'];schemas['SearchResponse']['properties']['mode']['enum']=['keyword','vector','hybrid']
schemas['SearchRequest']['properties']['limit'].update(minimum=1,maximum=100)
schemas['SearchRequest']['properties']['scope']['properties']['mode']['enum']=['all','none','spaces','documents']
# C06 shows one spaces example, while C01/SDK defines explicit documents/none.
# Additional optional selectors are a documented draft consistency choice, not a freeze.
scope=schemas['SearchRequest']['properties']['scope'];scope['properties'].update(doc_ids={'type':'array','items':{'type':'string'}},space_types={'type':'array','items':{'type':'string','enum':ENUMS['space_type']}});scope['required']=['mode']
schemas['SearchRequest']['properties']['rerank']['properties']['top_k'].update(minimum=1,maximum=500)
schemas['SearchRequest']['properties']['calibration']['properties']['min_calibrated_score'].update(minimum=0,maximum=1)
schemas['KBMember']=obj({'user_id':{'type':'string','minLength':1},'role':{'type':'string','enum':['viewer','editor','admin']},'granted_by':{'type':'string'},'granted_at':{'type':'string','format':'date-time'}})
schemas['KBMemberPage']=obj({'items':{'type':'array','items':ref('KBMember')},'next_cursor':{'anyOf':[{'type':'string'},{'type':'null'}]}})
schemas['SpaceUpdate']=copy.deepcopy(schemas['KnowledgeBase']);schemas['SpaceUpdate']['properties']={k:v for k,v in schemas['SpaceUpdate']['properties'].items() if k in ('name','description','visibility','tags','metadata','governance_tier')};schemas['SpaceUpdate']['required']=[]
schemas['WriteActivationResult']=obj({'created_version':{'type':'integer','minimum':1,'maximum':9007199254740991},'current_version':{'type':'integer','minimum':1,'maximum':9007199254740991},'lifecycle_state':{'type':'string','enum':ENUMS['lifecycle_state']},'activated':{'type':'boolean'},'rollback_scope':{'type':'string','const':'content_and_filename_only'}})
schemas['WriteActivationResult']['x-activation-formula']='created_version === current_version && lifecycle_state === published'
schemas['WriteActivationResult']['description']='DRAFT v2 only, not added v1 return fields. activated iff created_version === current_version AND lifecycle_state === published; checked by the reference validators. Content+filename only, CURRENT metadata/security retained; L2 draft is not activated.'
# Every object owning a digest states its algorithm separately, including nested search hits.
# SearchRequest/Response share nodes with SearchExchange; avoid visiting those aliases twice.
_seen=set()
def add_hash_algorithms_once(node):
 if id(node) in _seen:return
 _seen.add(id(node))
 if isinstance(node,dict):
  props=node.get('properties',{})
  if any(k.endswith('_hash') for k in props):
   props['hash_algorithm']={'type':'string','const':'sha256'}
   if 'hash_algorithm' not in node['required']:node['required'].append('hash_algorithm')
  for child in list(node.values()):add_hash_algorithms_once(child)
 elif isinstance(node,list):
  for child in node:add_hash_algorithms_once(child)
add_hash_algorithms_once(schemas)
schemas['VersionPair']=obj({'from_version':{'type':'integer','minimum':1},'to_version':{'type':'integer','minimum':1}})
schemas['RollbackRequest']=obj({'target_version':{'type':'integer','minimum':1}})
schemas['RollbackAuditDetails']=obj({'rollback_from_version':{'type':'integer','minimum':1},'previous_current_version':{'type':'integer','minimum':1},'created_version':{'type':'integer','minimum':1},'rollback_scope':{'type':'string','const':'content_and_filename_only'},'security_metadata_preserved':{'type':'boolean','const':True}})
schemas['RollbackAuditDetails']['description']='AUDIT ONLY, not v1 return fields. Content+filename rollback keeps CURRENT metadata/ACL/rights/validity and L2 draft workflow; never restores historical security grants.'
schemas['VersionDiff']=obj({'doc_id':{'type':'string'},'from_version':{'type':'integer','minimum':1},'to_version':{'type':'integer','minimum':1},'changes':{'type':'array','items':obj({'operation':{'type':'string','enum':['insert','delete','replace']},'before':{'type':'array','items':{'type':'string'}},'after':{'type':'array','items':{'type':'string'}}})}})
schemas['AssetIngestRequest']=obj({'kb_id':{'type':'string'},'content':{'type':'string'},'filename':{'type':'string'},'asset_type':{'type':'string','enum':ENUMS['asset_type']},'idempotency_key':{'type':'string'}})
schemas['SyncRequest']=obj({'kb_id':{'type':'string'},'cursor_in':{'type':'string'}})
schemas['VersionCoordinate']=obj({'tenant_id':{'type':'string'},'kb_id':{'type':'string'},'doc_id':{'type':'string'},'version':{'type':'integer','minimum':1},'version_id':{'type':'string'}})
schemas['DualUriMapping']=obj({'coordinates':ref('VersionCoordinate'),'canonical_uri':ref('CanonicalKbUri'),'legacy_ku_uri':ref('LegacyKuUri'),'section_path':{'type':'array','items':{'type':'string'}}})
schemas['AgentIntersectionDenyFixture']=obj({'identity':ref('IdentityContext'),'kb_id':{'type':'string'},'user_is_member':{'const':False,'type':'boolean'},'agent_allowed_kb_ids':{'type':'array','items':{'type':'string'}},'expected_allowed':{'const':False,'type':'boolean'},'error':ref('ErrorEnvelope')})
schemas['KBLifecycleFixture']=obj({'space':ref('KnowledgeBase'),'archived_asset':ref('KnowledgeAsset'),'restored_asset':ref('KnowledgeAsset')})
schemas['DualUriEvidenceFixture']=obj({'evidence':ref('EvidenceRecord'),'mapping':ref('DualUriMapping')})
schemas['DocumentWriteResponse']=copy.deepcopy(schemas['DocumentVersion'])
schemas['DocumentWriteResponse']['properties'].update(copy.deepcopy(schemas['WriteActivationResult']['properties']))
for field in schemas['WriteActivationResult']['required']:
 if field not in schemas['DocumentWriteResponse']['required']:schemas['DocumentWriteResponse']['required'].append(field)
schemas['DocumentWriteResponse']['x-activation-formula']=schemas['WriteActivationResult']['x-activation-formula']
schemas['DocumentWriteResponse']['description']='DRAFT additive version result: retains every prior DocumentVersion field plus the activation/scope fields. No runtime v1 response change.'
schemas.update(delta.schemas())
schemas['MinimumSliceWriteEndpoint']={'type':'string','enum':['POST /v2/spaces','POST /v2/assets']}
schemas['DraftContractMetadata']=obj({'contract_status':{'type':'string','const':'draft-pending-m1-freeze'},'runtime_v2_implemented':{'type':'boolean','const':False}})
paths={}
parameters={k:{'name':v,'in':'header','required':True,'schema':{'type':'string','minLength':1},'description':'Trusted verified gateway correlation/mapping only; never accepts arbitrary client identity or tenant authority.'} for k,v in [('RequestId','X-Request-Id'),('TenantId','X-Tenant-Id')]}
def route(path,method,response,request=None):
 op={'operationId':method+'_'+re.sub('[^a-zA-Z0-9]+','_',path).strip('_'),'x-contract-status':'draft-pending-m1-freeze','x-security-invariants':['tenant-hard-boundary','explicit-deny-wins','user-intersect-agent','current-principal-generation','redaction-before-delivery'],'parameters':[{'$ref':'#/components/parameters/RequestId'},{'$ref':'#/components/parameters/TenantId'}],'security':[{'TrustedGateway':[]}], 'responses':{'200':{'description':'Draft authorized result','content':{'application/json':{'schema':response}}},'default':{'description':'Uniform, redacted error; does not reveal resource existence','content':{'application/json':{'schema':ref('ErrorEnvelope')}}}}}
 for name in re.findall(r'\{(.*?)\}',path):op['parameters'].append({'name':name,'in':'path','required':True,'schema':{'type':'string'}})
 if request is not None:op['requestBody']={'required':True,'content':{'application/json':{'schema':request}}}
 paths.setdefault(path,{})[method]=op
route('/v2/spaces','get',{'type':'array','items':ref('KnowledgeBase')});route('/v2/spaces','post',ref('KnowledgeBase'),ref('KnowledgeBase'))
route('/v2/spaces/{kb_id}','get',ref('KnowledgeBase'));route('/v2/spaces/{kb_id}','patch',ref('KnowledgeBase'),ref('SpaceUpdate'))
for action in ('archive','restore'):route('/v2/spaces/{kb_id}/'+action,'post',ref('KnowledgeBase'))
route('/v2/spaces/{kb_id}/members','get',ref('KBMemberPage'));route('/v2/spaces/{kb_id}/members','post',ref('KBMember'),obj({'user_id':{'type':'string'},'role':schemas['KBMember']['properties']['role']}));route('/v2/spaces/{kb_id}/members/{user_id}','delete',{'type':'null'})
route('/v2/assets','get',{'type':'array','items':ref('KnowledgeAsset')});route('/v2/assets','post',ref('DocumentWriteResponse'),ref('AssetIngestRequest'));route('/v2/assets/{doc_id}','get',ref('KnowledgeAsset'))
for action in ('archive','restore','purge'):route('/v2/assets/{doc_id}/'+action,'post',{'type':'null'} if action=='purge' else ref('KnowledgeAsset'))
route('/v2/assets/{doc_id}/versions','get',{'type':'array','items':ref('DocumentVersion')});route('/v2/assets/{doc_id}/versions/{version}','get',ref('DocumentVersion'));route('/v2/assets/{doc_id}/versions/diff','post',ref('VersionDiff'),ref('VersionPair'));route('/v2/assets/{doc_id}/rollback','post',ref('DocumentWriteResponse'),ref('RollbackRequest'))
route('/v2/search','post',ref('SearchResponse'),ref('SearchRequest'));route('/v2/evidence/verify','post',ref('EvidenceRecord'),ref('EvidenceRecord'))
route('/v2/ingestion/jobs','post',ref('IngestionJob'),ref('AssetIngestRequest'));route('/v2/ingestion/jobs/{job_id}','get',ref('IngestionJob'))
for action in ('retry','cancel'):route('/v2/ingestion/jobs/{job_id}/'+action,'post',ref('IngestionJob'))
for action in ('plan','commit'):route('/v2/connectors/{connector_id}/'+action,'post',ref('ConnectorSyncExchange'),ref('SyncRequest'))
paths['/v2/assets/{doc_id}/rollback']['post']['x-v1-rollback-audit-semantics']={'audit_schema':ref('RollbackAuditDetails'),'runtime_v1_response_unchanged':True,'historical_business_metadata_restored':False,'current_security_metadata_preserved':True,'controlled_space_creates_draft':True}
parameters['IdempotencyKey']={'name':'Idempotency-Key','in':'header','required':False,'schema':{'type':'string','minLength':1,'maxLength':256},'description':'DRAFT future v2 only. Optional retry identity scoped to trusted (tenant_id, endpoint, idempotency_key), checked against the payload digest and current actor authority. A key reused for different content returns 409 IDEMPOTENCY_CONFLICT; no v1/runtime implementation.'}
for path in ('/v2/spaces','/v2/assets'):
 op=paths[path]['post'];op['parameters'].append({'$ref':'#/components/parameters/IdempotencyKey'})
 error_schema=copy.deepcopy(schemas['ErrorEnvelope']);error_schema['properties']['error']['properties']['code']={'type':'string','const':'IDEMPOTENCY_CONFLICT'}
 op['responses']['409']={'description':'Idempotency key conflicts with prior request in the same authorized scope; no resource existence disclosure.','content':{'application/json':{'schema':error_schema}}}
spec={'openapi':'3.1.0','info':{'title':'Knowledge SDK / OpenBot Adapter DRAFT','version':'0.1.0-draft','description':'SDK-side review assets only; no v2 routes implemented. M1 joint freeze and Team B review PENDING. JSON syntax is valid YAML 1.2. Never trust unsigned client tenant/actor headers; gateway cryptographically binds both contexts. All nine contracts remain proposals.'},'x-contract-status':'draft-pending-m1-freeze','x-evidence-boundaries':{'runtime_captured':False,'fixture_metadata':'fixture-evidence-boundaries.json','actual_v1_wire_is_separate':True},'x-authority':'OIDC-verified or gateway-signature-verified identity and canonical tenant mapping; client headers are not authority','x-runtime-implemented':False,'x-implementation-status':{'runtime_v2_implemented':False},'security':[{'TrustedGateway':[]}],'paths':paths,'components':{'parameters':parameters,'securitySchemes':{'TrustedGateway':{'type':'http','scheme':'bearer','bearerFormat':'Verified OIDC JWT or trusted gateway token bound to signed context'}},'schemas':schemas}}
(ROOT/'openapi-v2-draft.yaml').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n')
def ts(s):
 if '$ref' in s:return s['$ref'].split('/')[-1]
 if 'const' in s:return json.dumps(s['const'])
 if 'enum' in s:return ' | '.join(json.dumps(x) for x in s['enum'])
 if 'anyOf' in s:return ' | '.join('('+ts(x)+')' for x in s['anyOf'])
 typ=s.get('type')
 if typ=='object':
  props=s.get('properties')
  if props is None:return '{readonly [key: string]: '+ts(s['additionalProperties'])+'}'
  return '{\n'+''.join('  readonly '+json.dumps(k)+('' if k in s.get('required',[]) else '?')+': '+ts(v)+';\n' for k,v in props.items())+'}'
 if typ=='array':return 'ReadonlyArray<'+ts(s['items'])+'>'
 return {'null':'null','boolean':'boolean','integer':'number','number':'number','string':'string'}[typ]
text='// PolicyGeneration: runtime-validate integer 1..9007199254740991 with isPolicyGeneration; TS number alone is not validation.\n// Sha256Hex: runtime-validate bare lowercase64; never prefix algorithm in digest.\n// WriteActivationResult: activated iff created_version === current_version && lifecycle_state === published.\n// GENERATED DRAFT: pending M1 joint freeze; no v2 runtime implementation.\n// Tenant/actor claims are trusted gateway-verified mappings, not client authority.\n// RollbackAuditDetails is audit-only semantics, never added v1 response fields.\n'
for name,schema in schemas.items():
 value=ts(schema)
 if name=='CanonicalKbUri':value='`kb://org/${string}/doc/${string}@${number}${string}`'
 if name=='LegacyKuUri':value='`ku://kb/${string}/doc/${string}@${string}`'
 text+='export type '+name+' = '+value+';\n\n'
text+='// DualUriMapping requires authoritative VersionCoordinate lookup; strings alone\n// cannot infer kb_id or opaque version_id. No canonical runtime URI rewrite.\n'
(ROOT/'openbot-adapter-dto.d.ts').write_text(text)
# Six independent machine-checkable fixture families; generic tenant, no live data.
identity=copy.deepcopy(examples[0]);identity.update(request_id='req-fixture',tenant_id='fixture-tenant');identity['actor'].update(issuer='https://idp.example.invalid',subject_id='reader',roles=['member'],department_ids=[],ancestor_department_ids=[],org_roles=[],clearance_tags=[],session_id='fixture-session');identity['agent'].update(agent_id='fixture-agent',task_id='fixture-task')
error={'error':{'code':'PERMISSION_DENIED','message':'Resource unavailable','retryable':False,'request_id':'req-fixture','details':{}}}
space=copy.deepcopy(examples[1]);space.update(kb_id='fixture-space',tenant_id='fixture-tenant',owner_user_id='owner',owner_department_id='department',name='Fixture space',description='',tags=[])
asset=copy.deepcopy(examples[2]);asset.update(doc_id='fixture-doc',tenant_id='fixture-tenant',kb_id='fixture-space',owner_id='owner',title='Fixture',current_version_id='ver-fixture',tags=[],source_ref='upload://fixture')
archived=copy.deepcopy(asset);archived.update(archived=True,archived_at='2026-11-24T00:00:00Z')
evidence=copy.deepcopy(examples[4]);evidence.update(evidence_id='ev-fixture',tenant_id='fixture-tenant',kb_id='fixture-space',doc_id='fixture-doc',version_id='ver-fixture',chunk_id='chunk-fixture',anchor_id='anchor-fixture',title='Fixture',section_path=['Section'],excerpt='Authorized redacted excerpt',excerpt_hash='0'*64,canonical_uri='kb://org/fixture-tenant/doc/fixture-doc@3#anchor=anchor-fixture')
coordinate={k:evidence[k] for k in ('tenant_id','kb_id','doc_id','version','version_id')};mapping=dict(coordinates=coordinate,canonical_uri=evidence['canonical_uri'],legacy_ku_uri='ku://kb/fixture-space/doc/fixture-doc@ver-fixture#Section',section_path=evidence['section_path'])
search=copy.deepcopy(examples[5]['response']);hit=search['hits'][0];hit.update(doc_id='fixture-doc',kb_id='fixture-space',version_id='ver-fixture',chunk_id='chunk-fixture',title='Fixture',excerpt='Authorized redacted excerpt',excerpt_hash='0'*64,source_uri='kb://org/fixture-tenant/doc/fixture-doc@3#chunk=chunk-fixture')
fixtures={'identity-context.json':('IdentityContext',identity),'agent-intersection-deny.json':('AgentIntersectionDenyFixture',dict(identity=identity,kb_id='fixture-space',user_is_member=False,agent_allowed_kb_ids=['fixture-space'],expected_allowed=False,error=error)),'kb-lifecycle.json':('KBLifecycleFixture',dict(space=space,archived_asset=archived,restored_asset=asset)),'dual-uri-evidence.json':('DualUriEvidenceFixture',dict(evidence=evidence,mapping=mapping)),'calibrated-search-response.json':('SearchResponse',search),'error-envelope.json':('ErrorEnvelope',error)}
def fixture_algorithms(value):
 if isinstance(value,dict):
  if any(k.endswith('_hash') for k in value):value['hash_algorithm']='sha256'
  for child in list(value.values()):fixture_algorithms(child)
 elif isinstance(value,list):
  for child in value:fixture_algorithms(child)
for _,data in fixtures.values():fixture_algorithms(data)
fixtures.update(delta.build(ROOT.parent))
for file,(schema,data) in fixtures.items():(ROOT/'contract-fixtures'/file).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
(ROOT/'fixture-schemas.json').write_text(json.dumps({k:v[0] for k,v in fixtures.items()},indent=2)+'\n')

(ROOT/'minimum-slice-checklist.json').write_text(json.dumps(delta.minimum_slice(ROOT.parent),ensure_ascii=False,indent=2)+'\n')
(ROOT/'fixture-evidence-boundaries.json').write_text(json.dumps({name:{'runtime_captured':False,'evidence_kind':data.get('evidence_kind','draft_contract_example_only'),'runtime_v2_implemented':False} for name,(_,data) in fixtures.items()},indent=2)+'\n')
