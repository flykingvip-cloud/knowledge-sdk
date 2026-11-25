"""Full used-schema validation, negative probes and cross-field security invariants.

No network or third-party runtime dependency. CI additionally runs the official
OpenAPI 3.1/JSON Schema validators when available as development-only packages.
"""
from pathlib import Path
import json,re,math,copy,sys
ROOT=Path(__file__).parent

def validate(value,schema,document,path='$',depth=0):
    if depth>100:raise ValueError('Schema depth exceeded')
    def check(ok):
        if not ok:raise ValueError('Schema violation at '+path)
    if '$ref' in schema:
        ref=schema['$ref'];check(ref.startswith('#/'));target=document
        for key in ref[2:].split('/'):target=target[key.replace('~1','/').replace('~0','~')]
        return validate(value,target,document,path,depth+1)
    if 'anyOf' in schema:
        for branch in schema['anyOf']:
            try:validate(value,branch,document,path,depth+1);return
            except ValueError:pass
        raise ValueError('No schema alternative at '+path)
    if 'const' in schema:check(type(value) is type(schema['const']) and value==schema['const'])
    if 'enum' in schema:check(any(type(value) is type(x) and value==x for x in schema['enum']))
    typ=schema.get('type')
    check({'object':lambda:isinstance(value,dict),'array':lambda:isinstance(value,list),'string':lambda:isinstance(value,str),'integer':lambda:type(value) is int,'number':lambda:type(value) in (float,int) and math.isfinite(value),'boolean':lambda:type(value) is bool,'null':lambda:value is None}.get(typ,lambda:True)())
    if typ in ('number','integer'):
        if 'minimum' in schema:check(value>=schema['minimum'])
        if 'maximum' in schema:check(value<=schema['maximum'])
    if typ=='string':
        check(len(value)>=schema.get('minLength',0) and len(value)<=schema.get('maxLength',10**8))
        if 'pattern' in schema:check(re.search(schema['pattern'],value) is not None)
        if schema.get('format')=='date-time':
            from datetime import datetime
            try:check(datetime.fromisoformat(value.replace('Z','+00:00')).tzinfo is not None)
            except (ValueError,TypeError):raise ValueError('Invalid date time at '+path) from None
    if typ=='array':
        check(len(value)<=schema.get('maxItems',10**8))
        for i,v in enumerate(value):validate(v,schema['items'],document,path+'['+str(i)+']',depth+1)
    if typ=='object':
        check(not set(schema.get('required',[]))-set(value))
        for k,v in value.items():
            if k in schema.get('properties',{}):validate(v,schema['properties'][k],document,path+'.'+k,depth+1)
            else:
                extra=schema.get('additionalProperties',True);check(extra is not False)
                if isinstance(extra,dict):validate(v,extra,document,path+'.'+k,depth+1)

def run():
    spec=json.loads((ROOT/'openapi-v2-draft.yaml').read_text());schemas=spec['components']['schemas'];mapping=json.loads((ROOT/'fixture-schemas.json').read_text())
    assert spec['openapi']=='3.1.0' and spec['x-contract-status']=='draft-pending-m1-freeze' and spec['x-runtime-implemented'] is False
    def references(node):
        if isinstance(node,dict):
            if '$ref' in node:
                target=spec;assert node['$ref'].startswith('#/')
                for key in node['$ref'][2:].split('/'):target=target[key]
            for x in node.values():references(x)
        elif isinstance(node,list):
            for x in node:references(x)
    references(spec)
    for path,methods in spec['paths'].items():
        assert path.startswith('/v2/')
        for op in methods.values():
            assert op['security']==[{'TrustedGateway':[]}]
            assert 'user-intersect-agent' in op['x-security-invariants'] and 'explicit-deny-wins' in op['x-security-invariants']
            assert len(op['parameters'])>=2 and op['x-contract-status']=='draft-pending-m1-freeze'
    assert 'never' in spec['components']['parameters']['TenantId']['description'].lower()
    fixtures={}
    negative=0
    for file,name in mapping.items():
        value=json.loads((ROOT/'contract-fixtures'/file).read_text());validate(value,schemas[name],spec);fixtures[file]=value
        for key in schemas[name].get('required',[]):
            broken=copy.deepcopy(value);broken.pop(key)
            try:validate(broken,schemas[name],spec)
            except ValueError:negative+=1
            else:raise AssertionError('Missing-required-field accepted')
        broken=copy.deepcopy(value);broken['__unknown__']='forbidden'
        try:validate(broken,schemas[name],spec)
        except ValueError:negative+=1
        else:raise AssertionError('Unknown field accepted')
    deny=fixtures['agent-intersection-deny.json'];assert deny['kb_id'] in deny['agent_allowed_kb_ids'] and not deny['user_is_member'] and deny['expected_allowed'] is False
    assert deny['error']['error']['code']=='PERMISSION_DENIED'
    # Execute the real pure SDK policy engine, not a fixture's declared outcome.
    from knowledge_sdk import Actor,KnowledgeBase,Document,DocumentACL,AgentIdentity,Purpose
    from knowledge_sdk.permissions.engine import DefaultPolicyEngine
    identity=deny['identity'];actor=Actor(identity['actor']['subject_id'],identity['tenant_id'])
    kb=KnowledgeBase(deny['kb_id'],identity['tenant_id'],'private fixture','different-owner','private')
    document=Document('fixture',identity['tenant_id'],kb.kb_id,'different-owner','fixture','team')
    agent=AgentIdentity(identity['agent']['agent_id'],identity['tenant_id'],allowed_kb_ids=deny['agent_allowed_kb_ids'])
    assert DefaultPolicyEngine().evaluate(actor,agent,kb,document,DocumentACL(),None,purpose=Purpose.READ).allowed is False
    negative+=1
    life=fixtures['kb-lifecycle.json'];assert life['archived_asset']['archived'] and not life['restored_asset']['archived']
    assert life['archived_asset']['tenant_id']==life['space']['tenant_id']==life['restored_asset']['tenant_id']
    dual=fixtures['dual-uri-evidence.json'];m=dual['mapping'];e=dual['evidence'];assert m['canonical_uri']==e['canonical_uri']
    from knowledge_sdk.contracts.uri import parse_uri_v2
    parsed=parse_uri_v2(m['canonical_uri']);coord=m['coordinates']
    assert (parsed.org_id,parsed.doc_id,parsed.version)==(coord['tenant_id'],coord['doc_id'],coord['version'])
    assert all(e[k]==v for k,v in coord.items()) and m['legacy_ku_uri'].startswith('ku://kb/'+coord['kb_id']+'/doc/'+coord['doc_id']+'@'+coord['version_id'])
    for name,bad in [('ErrorCode','INVENTED'),('CanonicalKbUri','ku://wrong')]:
        try:validate(bad,schemas[name],spec)
        except ValueError:negative+=1
        else:raise AssertionError('Bad enum/URI accepted')
    search=fixtures['calibrated-search-response.json']
    for score in (True,float('nan'),float('inf'),1.01,-.01):
        broken=copy.deepcopy(search);broken['hits'][0]['calibrated_score']=score
        try:validate(broken,schemas['SearchResponse'],spec)
        except ValueError:negative+=1
        else:raise AssertionError('Invalid calibrated score accepted')
    optional='NOT_INSTALLED'
    try:
        import jsonschema
        from openapi_spec_validator import validate as validate_spec
    except ImportError:pass
    else:
        validate_spec(spec)
        for file,name in mapping.items():jsonschema.Draft202012Validator({'$ref':'#/components/schemas/'+name,**{k:v for k,v in spec.items() if k!='openapi'}},format_checker=jsonschema.FormatChecker()).validate(fixtures[file])
        optional='PASSED'
    result=dict(status='DRAFT_ASSET_SELFCHECK_PASSED',fixtures=len(fixtures),schemas=len(schemas),paths=len(spec['paths']),negative_probes=negative,official_optional_validator=optional,m1_joint_freeze='PENDING',runtime_v2_implemented=False)
    print(json.dumps(result,sort_keys=True));return result
if __name__=='__main__':run()
