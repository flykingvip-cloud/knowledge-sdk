import {toKu,toKb,encodeOpaque,normalizeTextPythonCompat,isPolicyGeneration,isSha256Hex,validateWriteActivationResult} from './uri-mapping';
import type {DualUriMapping,CanonicalKbUri,LegacyKuUri} from './openbot-adapter-dto';
let assertions=0;
function assert(value:unknown):asserts value {assertions++;if(!value)throw new Error('URI mapping assertion failed');}
function rejects(f:()=>unknown){let failed=false;try{f();}catch{failed=true;}assert(failed);}
const record=(tenant='fixture-tenant',space='fixture-space',doc='fixture-doc',versionId='ver-fixture'):DualUriMapping=>({coordinates:{tenant_id:tenant,kb_id:space,doc_id:doc,version:3,version_id:versionId},canonical_uri:`kb://org/${encodeOpaque(tenant)}/doc/${encodeOpaque(doc)}@3#anchor=anchor-fixture`,legacy_ku_uri:`ku://kb/${encodeOpaque(space)}/doc/${encodeOpaque(doc)}@${encodeOpaque(versionId)}#Section/${encodeOpaque('中文 / metadata #?%')}`,section_path:['Section','中文 / metadata #?%']});
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

const other: DualUriMapping={...r,canonical_uri:r.canonical_uri.replace('anchor-fixture','another-anchor') as CanonicalKbUri};
rejects(()=>toKu(r.canonical_uri,[r,other]));
rejects(()=>toKb(r.legacy_ku_uri,[r,other]));
rejects(()=>toKu(r.canonical_uri,[{...r,section_path:['mismatched-fragment']} ]));
rejects(()=>toKu(r.canonical_uri,[{...r,unknown:'rejected'} as DualUriMapping]));
rejects(()=>toKu(r.canonical_uri,[{...r,coordinates:{...r.coordinates,unknown:'rejected'}} as DualUriMapping]));
console.log(JSON.stringify({status:'EXECUTED_TS_URI_MAPPING_PASSED',assertions,authority_granted:false}));

// Additional boundary tests; the exact original08/09 vectors are executed below.
const legacyUriAssertions=assertions;
assert(legacyUriAssertions===44);
const pythonWhitespace=[9,10,11,12,13,28,29,30,31,32,133,160,5760,
  8192,8193,8194,8195,8196,8197,8198,8199,8200,8201,8202,8232,8233,8239,8287,12288];
assert(pythonWhitespace.length===29);
for(const cp of pythonWhitespace){
 const ch=String.fromCodePoint(cp);
 assert(normalizeTextPythonCompat(ch+'alpha'+ch+ch+'beta'+ch)==='alpha beta');
 assert(normalizeTextPythonCompat(ch)==='');
}
for(const cp of [0,8,14,27,33,132,134,0x180e,0x200b,0x2060,0xfeff,0x1f600]){
 const ch=String.fromCodePoint(cp);assert(normalizeTextPythonCompat(ch+'A'+ch)===ch+'A'+ch);
}
assert(normalizeTextPythonCompat('\ufeff A \ufeff')==='\ufeff A \ufeff');
assert(normalizeTextPythonCompat('e\u0301')==='é'); // NFC explicitly resolved by source08/t61.
assert(normalizeTextPythonCompat('   ')==='');assert(normalizeTextPythonCompat('')==='');
rejects(()=>normalizeTextPythonCompat(null as unknown as string));
for(const good of [1,9007199254740991])assert(isPolicyGeneration(good));
for(const bad of [0,-1,undefined,null,'1','abc',true,false,1.5,9007199254740992,NaN,Infinity,{},[]])assert(!isPolicyGeneration(bad));
assert(isSha256Hex('a'.repeat(64)));
for(const bad of ['A'.repeat(64),'sha256:'+'a'.repeat(64),'a'.repeat(63),'a'.repeat(65),'a'.repeat(64)+'\n',true,null])assert(!isSha256Hex(bad));
// Formula properties independently exercise the states; these are not the 09 eight agreed cases.
for(const state of ['published','draft','in_review','approved','rejected','superseded','revoked']){
 for(const current of [2,3]){
  const v={created_version:3,current_version:current,lifecycle_state:state,activated:current===3&&state==='published',rollback_scope:'content_and_filename_only'};
  assert(validateWriteActivationResult(v).activated===v.activated);
  rejects(()=>validateWriteActivationResult({...v,activated:!v.activated}));
 }
}
const valid={created_version:1,current_version:1,lifecycle_state:'published',activated:true,rollback_scope:'content_and_filename_only'};
for(const change of [{created_version:true},{created_version:'1'},{current_version:null},{current_version:9007199254740992},{lifecycle_state:'not_draft'},{activated:'true'},{rollback_scope:'all_metadata'},{extra:'forbidden'}])rejects(()=>validateWriteActivationResult({...valid,...change}));
for(const key of Object.keys(valid)){const bad:Record<string,unknown>={...valid};delete bad[key];rejects(()=>validateWriteActivationResult(bad));}
console.log(JSON.stringify({status:'EXECUTED_DECOUPLED_DELTA_BOUNDARIES_PASSED',legacy_uri_assertions:legacyUriAssertions,total_assertions:assertions,python_whitespace_codepoints:pythonWhitespace,agreed_hash_vectors_executed:0,agreed_signed_vectors_executed:0,source_status:'INDEPENDENT_BOUNDARIES_ONLY_VECTOR_STAGE_FOLLOWS',runtime_v2_implemented:false}));

// Built-in Node crypto is a TEST tool only, not an external runtime dependency.
declare function require(name:string):any;
declare const process:{cwd():string};
import type {HashVectorFixture,SignedCanonicalizationFixture,RollbackActivationFixture,PolicyGenerationFixture} from './openbot-adapter-dto';
const fs=require('node:fs'),crypto=require('node:crypto');
const fixture=(name:string):unknown=>JSON.parse(fs.readFileSync(process.cwd()+'/contract-fixtures/'+name,'utf8'));
const sha=(text:string):string=>crypto.createHash('sha256').update(text,'utf8').digest('hex');
const hashes=fixture('hash-vectors-utf8.json') as HashVectorFixture;
assert(hashes.cases.length===7&&hashes.runtime_captured===false);
for(const c of hashes.cases){
 assert(c.hash_algorithm==='sha256');assert(isSha256Hex(c.raw_hash)&&isSha256Hex(c.semantic_hash));
 assert(normalizeTextPythonCompat(c.raw)===c.normalized);
 assert(sha(c.raw)===c.raw_hash);assert(sha(normalizeTextPythonCompat(c.raw))===c.semantic_hash);
 assert(sha(c.raw+'tampered')!==c.raw_hash);
}
const signed=fixture('signed-request-canonicalization.json') as SignedCanonicalizationFixture;
assert(signed.cases.length===4&&signed.evidence_kind==='offline_algorithm_vector_only'&&!signed.runtime_captured);
assert(signed.test_only_secret.startsWith('TEST_ONLY_DO_NOT_USE_IN_PROD_'));
function canonicalCase(c:SignedCanonicalizationFixture['cases'][number]):string {
 const lines=[c.method.toUpperCase(),c.signed_target,signed.actor_header,signed.timestamp,c.nonce,sha(c.body_utf8)];
 if(c.agent_header_present||c.purpose_header_present)lines.push(c.agent_header_present?signed.agent_header:'',c.purpose_header_present?c.purpose??'':'');
 return lines.join('\n');
}
const hmac=(text:string):string=>crypto.createHmac('sha256',signed.test_only_secret).update(text,'utf8').digest('hex');
for(const c of signed.cases){
 assert(typeof c.agent_header_present==='boolean'&&typeof c.purpose_header_present==='boolean');
 const canonical=canonicalCase(c);
 assert(canonical.split('\n').length===c.canonical_lines_count);assert(sha(c.body_utf8)===c.body_sha256);
 assert(hmac(canonical)===c.signature);
 assert(hmac(canonicalCase({...c,signed_target:c.signed_target+'&tampered=1'}))!==c.signature);
 if(c.signed_target.includes('%2F'))assert(hmac(canonicalCase({...c,signed_target:c.signed_target.replace('%2F','/')}))!==c.signature);
 if(c.body_utf8.includes('临床'))assert(hmac(canonicalCase({...c,body_utf8:JSON.stringify(JSON.parse(c.body_utf8))+' '}))!==c.signature);
}
const rollback=fixture('rollback-activation-cases.json') as RollbackActivationFixture;
assert(rollback.cases.length===8);
for(const c of rollback.cases){const {id,...value}=c;assert(id.length>0);assert(validateWriteActivationResult(value).activated===c.activated);rejects(()=>validateWriteActivationResult({...value,activated:!value.activated}));}
const generations=fixture('policy-generation-cases.json') as PolicyGenerationFixture;
assert(generations.cases.length===12);
for(const c of generations.cases){
 const value=c.submitted.policy_generation;
 const actual=!isPolicyGeneration(value)?'VALIDATION_ERROR':value<c.stored_generation?'POLICY_GENERATION_STALE':null;
 assert(actual===c.expected.code);assert((actual===null)===c.expected.allowed);
}
console.log(JSON.stringify({status:'ALL_SOURCE_VECTORS_AND_BOUNDARIES_PASSED',legacy_uri_assertions:legacyUriAssertions,total_assertions:assertions,agreed_hash_vectors_executed:7,agreed_signed_vectors_executed:4,agreed_rollback_cases_executed:8,policy_cases:12,normalization:'NFC_then_Python29_whitespace_FEFF_preserved',runtime_v2_implemented:false}));
