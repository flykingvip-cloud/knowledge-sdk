"""Stdlib candidate validator. No runtime imports, database, network or approvals."""
import json,math,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent
class Invalid(ValueError):pass
def load(text):
    def pairs(items):
        out={}
        for k,v in items:
            if k in out:raise Invalid('INVALID_CANDIDATE')
            out[k]=v
        return out
    return json.loads(text,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(Invalid('INVALID_CANDIDATE')))
def validate(schema,value,schemas):
    if '$ref' in schema:return validate(schemas[schema['$ref'].split('/')[-1]],value,schemas)
    if 'oneOf' in schema:
        count=0
        for option in schema['oneOf']:
            try:validate(option,value,schemas);count+=1
            except Invalid:pass
        if count!=1:raise Invalid('INVALID_CANDIDATE')
        return
    if 'const' in schema and (type(value)!=type(schema['const']) or value!=schema['const']):raise Invalid('INVALID_CANDIDATE')
    if 'enum' in schema and not any(type(value)==type(x) and value==x for x in schema['enum']):raise Invalid('INVALID_CANDIDATE')
    types=schema.get('type',[]);types=[types] if isinstance(types,str) else types
    kind='null' if value is None else 'boolean' if type(value)is bool else 'integer' if type(value)is int else 'number' if type(value)is float and math.isfinite(value) else 'string' if type(value)is str else 'array' if type(value)is list else 'object' if type(value)is dict else 'INVALID'
    if types and kind not in types:raise Invalid('INVALID_CANDIDATE')
    if kind=='object':
        props=schema.get('properties',{})
        if not set(schema.get('required',[]))<=set(value) or (schema.get('additionalProperties')is False and set(value)-set(props)):raise Invalid('INVALID_CANDIDATE')
        for key,item in value.items():
            if key in props:validate(props[key],item,schemas)
    if kind=='array':
        if len(value)>schema.get('maxItems',100000):raise Invalid('INVALID_CANDIDATE')
        for item in value:validate(schema['items'],item,schemas)
    if kind=='string':
        try:value.encode('utf-8')
        except UnicodeError:raise Invalid('INVALID_CANDIDATE') from None
        if 'pattern' in schema and not re.fullmatch(schema['pattern'],value):raise Invalid('INVALID_CANDIDATE')
    if kind in ('integer','number') and not schema.get('minimum',-float('inf'))<=value<=schema.get('maximum',float('inf')):raise Invalid('INVALID_CANDIDATE')
def check(name,value,schemas,now=100):
    validate(schemas[name],value,schemas)
    if name=='AssetEnvelope' and value['kind']=='enterprise_materialized_ref':
        p=value['payload'];f=p['freshness']
        if p['tombstone']is None and not f['asserted_at']<=now<f['valid_until']:raise Invalid('STALE_EXTERNAL')
        if p['tombstone']is not None and p['cursor']is not None:raise Invalid('STALE_CURSOR')
    if name=='PolicyCheck':
        if len({value[k] for k in ('tenant_id','space_tenant_id','kb_tenant_id')})!=1 or value['explicit_deny'] or not all(value[k] for k in ('user_allowed','agent_allowed','fine_scope_allowed')) or value['policy_generation']!=value['current_generation']:raise Invalid('DENIED')
    if name=='HydrateRequest' and any(t['tenant_id']!=value['tenant_id'] for t in value['targets']):raise Invalid('TENANT_DENIED')
def run():
    api=load((ROOT/'openapi.json').read_text());data=load((ROOT/'fixtures.json').read_text());count=0
    for vector in data['vectors']:
        try:check(vector['schema'],vector['data'],api['components']['schemas'],data['reference_now']);actual=True
        except Invalid:actual=False
        assert actual==vector['valid'],vector['id'];count+=1
    status=load((ROOT/'status.json').read_text())
    for flag in ('schema_v7_ddl_authorized','migration_authorized','prod_shadow_or_cutover_authorized','final_alignment_frozen'):assert status[flag]is False
    assert all(v=='NOT_RUN_NOT_ACCEPTED' for v in status['formal_tests'].values())
    result=dict(status='DRAFT_PROTOTYPE_VALIDATED_NOT_FORMAL_ACCEPTANCE',vectors=count,positive=sum(x['valid'] for x in data['vectors']),negative=sum(not x['valid'] for x in data['vectors']),formal_acceptance=False);print(json.dumps(result));return result
if __name__=='__main__':run()
