import {AssetEnvelope, FavoriteHydrated, ProposedDeliverableState, ToolBoundary} from './dto';
declare function require(name:string):any;
declare const process:{argv:string[]};
const fs=require('fs');
type Schema=Record<string,any>;
const api=JSON.parse(fs.readFileSync(process.argv[2]||'openapi.json','utf8'));
const fixtures=JSON.parse(fs.readFileSync(process.argv[3]||'fixtures.json','utf8'));
function validate(s:Schema,v:any):void {
 const fail=():never=>{throw Error('INVALID_CANDIDATE');};
 if(s.$ref)return validate(api.components.schemas[s.$ref.split('/').pop()],v);
 if(s.oneOf){let n=0;for(const option of s.oneOf){try{validate(option,v);n++;}catch{}}if(n!==1)fail();return;}
 if('const'in s&&v!==s.const)fail();if(s.enum&&!s.enum.includes(v))fail();
 const t=v===null?'null':Array.isArray(v)?'array':typeof v==='number'?(Number.isSafeInteger(v)?'integer':'number'):typeof v;
 const types=typeof s.type==='string'?[s.type]:s.type;
 if(types&&!types.includes(t))fail();
 if(t==='object'){const p=s.properties||{};if((s.required||[]).some((k:string)=>!(k in v)))fail();if(s.additionalProperties===false&&Object.keys(v).some(k=>!(k in p)))fail();for(const k of Object.keys(v))if(k in p)validate(p[k],v[k]);}
 if(t==='array'){if(v.length>(s.maxItems||100000))fail();for(const x of v)validate(s.items,x);}
 if(t==='string'&&s.pattern&&!new RegExp(s.pattern).test(v))fail();
 if(t==='integer'||t==='number'){if(!Number.isFinite(v)||v<(s.minimum??-Infinity)||v>(s.maximum??Infinity))fail();}
}
function check(name:string,v:any):void {
 validate(api.components.schemas[name],v);
 if(name==='AssetEnvelope'&&v.kind==='enterprise_materialized_ref'){const p=v.payload,f=p.freshness;if(p.tombstone===null&&!(f.asserted_at<=fixtures.reference_now&&fixtures.reference_now<f.valid_until))throw Error('STALE');if(p.tombstone!==null&&p.cursor!==null)throw Error('CURSOR');}
 if(name==='PolicyCheck'&&(v.tenant_id!==v.space_tenant_id||v.tenant_id!==v.kb_tenant_id||v.explicit_deny||!v.user_allowed||!v.agent_allowed||!v.fine_scope_allowed||v.policy_generation!==v.current_generation))throw Error('DENIED');
 if(name==='HydrateRequest'&&v.targets.some((t:any)=>t.tenant_id!==v.tenant_id))throw Error('TENANT');
}
let count=0;for(const v of fixtures.vectors){let actual=true;try{check(v.schema,v.data);}catch{actual=false;}if(actual!==v.valid)throw Error(v.id);count++;}
// Compile-time discriminated union checks (not runtime authorization).
const denied:FavoriteHydrated={target_type:'asset',target_id:'syn_id',state:'unavailable'};
if(denied.state==='unavailable'){
 // @ts-expect-error unavailable responses cannot carry display metadata
 const leak:string=denied.display_name;
}
// @ts-expect-error credentials are never document-agent supply
const tool:ToolBoundary={kind:'data_capability',capability_id:'syn_tool',mediated:true,credentials_exposed:true};
// @ts-expect-error unknown deliverable state is not one of five proposed states
const state:ProposedDeliverableState='unknown';
function exhaust(asset:AssetEnvelope):string {switch(asset.kind){case'uploaded_document':return asset.payload.version_id;case'agent_deliverable':return asset.payload.state;case'enterprise_materialized_ref':return asset.payload.projection_id;default:const impossible:never=asset;return impossible;}}
console.log(JSON.stringify({status:'DRAFT_TS_STRICT_EXECUTED',vectors:count,formal_acceptance:false}));
