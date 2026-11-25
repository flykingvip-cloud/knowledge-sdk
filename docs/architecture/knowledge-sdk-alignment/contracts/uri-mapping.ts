/** DRAFT reference lookup only. Never grants tenant/content authority. No runtime dependencies. */
import type {DualUriMapping, VersionCoordinate, CanonicalKbUri, LegacyKuUri} from './openbot-adapter-dto';
const SEG='(?:[A-Za-z0-9._~-]|%[0-9A-Fa-f]{2})+';
const KB=new RegExp('^kb://org/('+SEG+')/doc/('+SEG+')@([1-9][0-9]*)(?:#(anchor|chunk)=('+SEG+'))?$');
const KU=new RegExp('^ku://kb/('+SEG+')/doc/('+SEG+')@('+SEG+')(?:#('+SEG+'(?:/'+SEG+')*))?$');
function fail():never {throw new Error('Invalid, missing, mismatched or ambiguous draft URI mapping');}
export function encodeOpaque(value:string):string {
  if(typeof value!=='string'||!value.trim()||/[\u0000-\u001f\u007f]/.test(value)||value.split(/[\\/]/).some(x=>x==='.'||x==='..'))return fail();
  try{return encodeURIComponent(value).replace(/[!'()*]/g,c=>'%'+c.charCodeAt(0).toString(16).toUpperCase());}catch{return fail();}
}
function decodeOnce(segment:string):string {
  let value:string;try{value=decodeURIComponent(segment);}catch{return fail();}
  const norm=(s:string)=>s.replace(/%[0-9a-f]{2}/gi,x=>x.toUpperCase());
  if(norm(encodeOpaque(value))!==norm(segment))return fail();return value;
}
function kb(uri:string):{tenant:string;doc:string;version:number} {
  if(typeof uri!=='string')return fail();const m=KB.exec(uri);if(!m)return fail();
  const version=Number(m[3]);if(!Number.isSafeInteger(version)||version<1)return fail();
  if(m[5])decodeOnce(m[5]);return {tenant:decodeOnce(m[1]),doc:decodeOnce(m[2]),version};
}
function ku(uri:string):{space:string;doc:string;versionId:string;sections:string[]} {
  if(typeof uri!=='string')return fail();const m=KU.exec(uri);if(!m)return fail();
  const sections=m[4]?m[4].split('/').map(decodeOnce):[];
  return {space:decodeOnce(m[1]),doc:decodeOnce(m[2]),versionId:decodeOnce(m[3]),sections};
}
function checked(record:DualUriMapping):DualUriMapping {
  if(!record||!record.coordinates||!Array.isArray(record.section_path)||Object.keys(record).sort().join(',')!=='canonical_uri,coordinates,legacy_ku_uri,section_path'||Object.keys(record.coordinates).sort().join(',')!=='doc_id,kb_id,tenant_id,version,version_id')return fail();
  const c:VersionCoordinate=record.coordinates,a=kb(record.canonical_uri),b=ku(record.legacy_ku_uri);
  for(const v of [c.tenant_id,c.kb_id,c.doc_id,c.version_id])encodeOpaque(v);
  if(!Number.isSafeInteger(c.version)||c.version<1||a.tenant!==c.tenant_id||a.doc!==c.doc_id||a.version!==c.version||b.space!==c.kb_id||b.doc!==c.doc_id||b.versionId!==c.version_id)return fail();
  // section_path is retained metadata, NOT an inferred anchor or authentication fact.
  const section=record.section_path.map(x=>{if(typeof x!=='string'||/[\u0000-\u001f\u007f]/.test(x))return fail();return x;});
  if(b.sections.length&&JSON.stringify(b.sections)!==JSON.stringify(section))return fail();
  return Object.freeze({coordinates:Object.freeze({...c}),canonical_uri:record.canonical_uri,legacy_ku_uri:record.legacy_ku_uri,section_path:Object.freeze(section)});
}
function select(uri:string,records:ReadonlyArray<DualUriMapping>,canonical:boolean):DualUriMapping {
  if(!Array.isArray(records)||records.length>1000)return fail();canonical?kb(uri):ku(uri);
  const all=records.map(checked);
  if(new Set(all.map(r=>r.canonical_uri)).size!==all.length||new Set(all.map(r=>r.legacy_ku_uri)).size!==all.length)return fail();
  const matches=all.filter(r=>(canonical?r.canonical_uri:r.legacy_ku_uri)===uri);
  if(matches.length!==1)return fail();return matches[0];
}
export function toKu(uri:CanonicalKbUri,records:ReadonlyArray<DualUriMapping>):DualUriMapping {return select(uri,records,true);}
export function toKb(uri:LegacyKuUri,records:ReadonlyArray<DualUriMapping>):DualUriMapping {return select(uri,records,false);}
