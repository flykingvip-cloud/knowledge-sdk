"""Read-only physical schema digest of the retained owned before/after snapshots."""
from __future__ import annotations
import argparse,hashlib,json,sqlite3
from contextlib import closing
from pathlib import Path

def physical(engine,state):
    if engine=='sqlite':
        with closing(sqlite3.connect(state['sqlite_file'])) as c:
            rows=c.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name").fetchall()
    else:
        import psycopg
        with psycopg.connect(state['dsn'],autocommit=True) as c:
            rows=[['columns',*r] for r in c.execute('SELECT table_name,column_name,data_type,is_nullable,column_default FROM information_schema.columns WHERE table_schema=current_schema() ORDER BY table_name,ordinal_position')]
            rows += [['indexes',*r] for r in c.execute('SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname=current_schema() ORDER BY tablename,indexname')]
            rows += [['rls',*r] for r in c.execute("SELECT relname,relrowsecurity,relforcerowsecurity FROM pg_class WHERE relnamespace=current_schema()::regnamespace AND relkind='r' ORDER BY relname")]
            rows += [['policies',*r] for r in c.execute('SELECT tablename,policyname,permissive,roles,cmd,qual,with_check FROM pg_policies WHERE schemaname=current_schema() ORDER BY tablename,policyname')]
    return {'engine':engine,'schema_version':5,'structural_rows':len(rows),'physical_schema_sha256':hashlib.sha256(json.dumps(rows,sort_keys=True,default=list,separators=(',',':')).encode()).hexdigest(),'read_only_catalog_query':True,'includes_columns_indexes_rls_policies':engine=='postgres'}

def compare(root):
    result={}
    for engine in ('sqlite','postgres'):
        before=json.loads((root/('perf-before-'+engine+'.json')).read_text());after=json.loads((root/('perf-after-final-'+engine+'.json')).read_text())
        for key in ('dataset_sha256','corpus_sha256','index_sha256','protected_pool_sha256','protected_pool_calls','configuration'):
            assert before[key]==after[key],(engine,key)
        entry={'identical_dataset_corpus_index_config_and_protected_pools':True,'arms':{}}
        for arm in ('baseline','candidate'):
            a=before['arms'][arm];b=after['arms'][arm];assert a['quality']==b['quality']
            entry['arms'][arm]={'quality_unchanged':True,'before':{k:v for k,v in a.items() if k not in ('quality','latencies_ms')},'after':{k:v for k,v in b.items() if k not in ('quality','latencies_ms')},'p50_delta_ms':b['p50_ms']-a['p50_ms'],'p50_percent_change':100*(b['p50_ms']/a['p50_ms']-1)}
        first=json.loads((root/('schema-before-'+engine+'.json')).read_text());last=json.loads((root/('schema-after-'+engine+'.json')).read_text());assert first==last
        entry['same_physical_schema_sha256']=first['physical_schema_sha256'];entry['schema_version']=5;result[engine]=entry
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=('before','after','compare'));p.add_argument('directory',type=Path);a=p.parse_args()
    if a.phase=='compare':print(json.dumps(compare(a.directory),indent=2))
    else:
        for engine in ('sqlite','postgres'):
            output=a.directory/('schema-'+a.phase+'-'+engine+'.json');assert not output.exists()
            result=physical(engine,json.loads((a.directory/('perf-snapshot-'+engine+'.json')).read_text()));output.write_text(json.dumps(result,indent=2)+'\n')
