"""Candidate PRE-03 adapter: file-only, stdlib, no database/network/migration.
Exit0 clean,2 findings,3 invalid/refused. No output includes rejected input values.
"""
import argparse,hashlib,json,re,sys,unicodedata
from pathlib import Path
STATUS='CANDIDATE_PRE03_FORMAT_NOT_SIGNED'
FIELDS={'legacy_kb_id','tenant_id','proposed_space_id','proposed_kb_id','alias_token','name_token'}
class Invalid(ValueError):pass
def token(value,nullable=False):
    return(value is None and nullable)or(type(value)is str and re.fullmatch(r'syn_[A-Za-z0-9_-]{1,64}',value)is not None)
def parse(raw):
    def pairs(items):
        d={}
        for k,v in items:
            if k in d:raise Invalid('INVALID_SANITIZED_INPUT')
            d[k]=v
        return d
    try:return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(Invalid()))
    except(Exception,)as exc:raise Invalid('INVALID_SANITIZED_INPUT')from None
def analyze(data):
    if type(data)is not dict or set(data)!={'format','sanitized','provenance','rows'} or data['format']!='candidate-pre03-v1' or data['sanitized']is not True or data['provenance']not in('SYNTHETIC_EXAMPLE','SANITIZED_CANDIDATE')or type(data['rows'])is not list or len(data['rows'])>10000:raise Invalid('INVALID_SANITIZED_INPUT')
    rows=data['rows']
    for row in rows:
        if type(row)is not dict or set(row)!=FIELDS:raise Invalid('INVALID_SANITIZED_INPUT')
        for k,v in row.items():
            if not token(v,nullable=k in('tenant_id','proposed_space_id','proposed_kb_id','alias_token')):raise Invalid('INVALID_SANITIZED_INPUT')
    norm=lambda s:unicodedata.normalize('NFKC',s).casefold()if s is not None else None
    mappings=[];alerts=[];aliases={};names={};targets={};legacy={}
    for row in rows:
        org=row['tenant_id'];old=row['legacy_kb_id'];space=row['proposed_space_id'];kb=row['proposed_kb_id']
        def alert(code):alerts.append(dict(code=code,tenant_id=org,legacy_kb_id=old))
        if org is None:alert('NULL_TENANT_MANUAL_REVIEW_NO_ASSIGNMENT')
        if org is None or space is None or kb is None:alert('UNMAPPED_NO_INFERENCE')
        else:mappings.append(dict(tenant_id=org,legacy_kb_id=old,proposed_space_id=space,proposed_kb_id=kb))
        for index,key,code in [(legacy,(org,old),'DUPLICATE_LEGACY_ID'),(targets,(org,space,kb),'MAPPING_COLLISION'),(names,(org,space,norm(row['name_token'])),'NAME_COLLISION')]:
            if org is None or(code=='MAPPING_COLLISION'and(space is None or kb is None)):continue
            if key in index:alert(code)
            else:index[key]=old
        alias=row['alias_token']
        if alias is None:alert('NULL_ALIAS_MANUAL_REVIEW')
        elif org is not None:
            key=(org,norm(alias))
            if key in aliases:alert('ALIAS_COLLISION')
            else:aliases[key]=old
    # Which colliding row gets the alert must not depend on input order.
    # Re-run canonical order once; all rendering and reports are deterministic.
    canonical=sorted(rows,key=lambda r:json.dumps(r,sort_keys=True,separators=(',',':')))
    if rows!=canonical:return analyze(dict(data,rows=canonical))
    sorter=lambda x:json.dumps(x,sort_keys=True,separators=(',',':'))
    return dict(status=STATUS,migration_authorized=False,input_provenance=data['provenance'],counts=dict(rows=len(rows),tenants=len({r['tenant_id']for r in rows if r['tenant_id']is not None}),null_legacy_rows=sum(r['tenant_id']is None for r in rows),mappings=len(mappings),alerts=len(alerts)),mappings=sorted(mappings,key=sorter),alerts=sorted(alerts,key=sorter))
def run_file(input_path,output_path=None):
    source=Path(input_path)
    if source.is_symlink()or not source.is_file()or source.stat().st_size>2_000_000:raise Invalid('INPUT_REFUSED')
    if output_path is not None and Path(output_path).resolve()==source.resolve():raise Invalid('OUTPUT_MUST_DIFFER')
    raw=source.read_bytes();before=hashlib.sha256(raw).hexdigest();result=analyze(parse(raw))
    after=hashlib.sha256(source.read_bytes()).hexdigest()
    if before!=after:raise Invalid('INPUT_CHANGED')
    result.update(input_sha256_before=before,input_sha256_after=after,input_unchanged=True)
    encoded=json.dumps(result,indent=2,sort_keys=True)+'\n'
    if output_path is not None:
        with Path(output_path).open('x',encoding='utf-8')as target:target.write(encoded)
    return result,2 if result['alerts']else 0
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('input');parser.add_argument('--output');args=parser.parse_args()
    try:result,code=run_file(args.input,args.output);print(json.dumps(result,sort_keys=True));raise SystemExit(code)
    except(Invalid,OSError,UnicodeError,RecursionError):print(json.dumps({'status':'INVALID_SANITIZED_INPUT','input_echoed':False}));raise SystemExit(3)
