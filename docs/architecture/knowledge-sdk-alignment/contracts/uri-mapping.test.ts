import {toKu,toKb,encodeOpaque} from './uri-mapping';
import type {DualUriMapping,CanonicalKbUri,LegacyKuUri} from './openbot-adapter-dto';
let assertions=0;
function assert(value:unknown):asserts value {assertions++;if(!value)throw new Error('URI mapping assertion failed');}
function rejects(f:()=>unknown){let failed=false;try{f();}catch{failed=true;}assert(failed);}
const record=(tenant='fixture-tenant',space='fixture-space',doc='fixture-doc',versionId='ver-fixture'):DualUriMapping=>({coordinates:{tenant_id:tenant,kb_id:space,doc_id:doc,version:3,version_id:versionId},canonical_uri:`kb://org/${encodeOpaque(tenant)}/doc/${encodeOpaque(doc)}@3#anchor=anchor-fixture`,legacy_ku_uri:`ku://kb/${encodeOpaque(space)}/doc/${encodeOpaque(doc)}@${encodeOpaque(versionId)}#Section`,section_path:['Section','中文 / metadata #?%']});
for(const r of [record(),record('租户甲','空间','文档 / ?#@%','版本 !()*'),record('t','k','literal%2F','opaque%252F')]){
 const mapped=toKu(r.canonical_uri,[r]);assert(mapped.legacy_ku_uri===r.legacy_ku_uri);assert(toKb(mapped.legacy_ku_uri,[r]).canonical_uri===r.canonical_uri);assert(JSON.stringify(mapped.section_path)===JSON.stringify(r.section_path));assert(Object.isFrozen(mapped)&&Object.isFrozen(mapped.coordinates)&&Object.isFrozen(mapped.section_path));
}
const r=record();
for(const invalid of ['http://org/t/doc/d@3','kb://org/t/doc/d@03','kb://org/t/doc/d@0','kb://org/t/doc/d@9007199254740993','kb://org/t/doc/../x@3','kb://org/t/doc/%2E%2E@3','kb://org/t/doc/%2e%2e%2Fx@3','kb://org/t/doc/%41@3','kb://org/t/doc/%ZZ@3','kb://org/t/doc/%C0%AF@3',r.canonical_uri+'?q=x',r.canonical_uri+'#chunk=x','kb://org/t/doc/d@3#anchor=a/b'])rejects(()=>toKu(invalid as CanonicalKbUri,[r]));
for(const invalid of ['ku://kb/k/doc/d@v?query=x','ku://kb/../doc/d@v','ku://kb/k/doc/%2F..%2Fx@v','ku://kb/k/doc/d@v#x#y','unknown://kb/k/doc/d@v'])rejects(()=>toKb(invalid as LegacyKuUri,[r]));
rejects(()=>toKu(r.canonical_uri,[]));rejects(()=>toKu(r.canonical_uri,[r,r]));rejects(()=>toKb(r.legacy_ku_uri,[r,r]));
rejects(()=>toKu(r.canonical_uri,[{...r,coordinates:{...r.coordinates,tenant_id:'other'}}]));rejects(()=>toKu(r.canonical_uri,[{...r,coordinates:{...r.coordinates,version:4}}]));
rejects(()=>toKu(r.canonical_uri,[{...r,coordinates:{...r.coordinates,version_id:'unknown'}}]));
const pct=record('t','k','literal%2F');assert(toKb(pct.legacy_ku_uri,[pct]).coordinates.doc_id==='literal%2F');rejects(()=>toKu(pct.canonical_uri.replace('%252F','%2F') as CanonicalKbUri,[pct]));
const lower=record('租户');const lowerUri=lower.canonical_uri.replace(/%[0-9A-F]{2}/g,x=>x.toLowerCase()) as CanonicalKbUri;
// Valid escape aliases never silently select a different record. Exact lookup is deliberate.
if(lowerUri!==lower.canonical_uri)rejects(()=>toKu(lowerUri,[lower]));
console.log(JSON.stringify({status:'EXECUTED_TS_URI_MAPPING_PASSED',assertions,authority_granted:false}));
