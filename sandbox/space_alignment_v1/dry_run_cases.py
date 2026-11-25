import ast,copy,json,tempfile,unittest
from pathlib import Path
if __package__:
    from .dry_run import analyze,run_file,parse,Invalid
else:
    from dry_run import analyze,run_file,parse,Invalid
SAMPLE=Path(__file__).with_name('synthetic-pre03.json')
class ReadOnlyDryRun(unittest.TestCase):
    def setUp(self):self.data=json.loads(SAMPLE.read_text())
    def test_P_DRY_counts_null_collision_no_inference(self):
        r=analyze(self.data);self.assertEqual(r['counts']['tenants'],1);self.assertEqual(r['counts']['null_legacy_rows'],1);self.assertEqual(r['counts']['mappings'],2)
        self.assertEqual({a['code']for a in r['alerts']},{'NULL_TENANT_MANUAL_REVIEW_NO_ASSIGNMENT','UNMAPPED_NO_INFERENCE','NULL_ALIAS_MANUAL_REVIEW','MAPPING_COLLISION','ALIAS_COLLISION','NAME_COLLISION'})
        self.assertFalse(r['migration_authorized']);self.assertFalse(any(m['tenant_id']is None for m in r['mappings']))
    def test_P_DRY_canonical_order_is_input_independent(self):
        reverse=copy.deepcopy(self.data);reverse['rows'].reverse();self.assertEqual(analyze(self.data),analyze(reverse))
    def test_P_DRY_cross_tenant_alias_not_collision(self):
        self.data['rows']=self.data['rows'][:2];self.data['rows'][1]['tenant_id']='syn_other';self.assertEqual(analyze(self.data)['alerts'],[])
    def test_P_DRY_readonly_hashes_output_and_exit_codes(self):
        with tempfile.TemporaryDirectory(prefix='sdk25-dry-')as tmp:
            source=Path(tmp)/'input.json';output=Path(tmp)/'output.json';source.write_text(json.dumps(self.data));before=source.read_bytes();r,code=run_file(source,output)
            self.assertEqual(code,2);self.assertEqual(before,source.read_bytes());self.assertEqual(r['input_sha256_before'],r['input_sha256_after'])
            with self.assertRaises(FileExistsError):run_file(source,output)
            with self.assertRaises(Invalid):run_file(source,source)
            self.data['rows']=self.data['rows'][:1];source.write_text(json.dumps(self.data));self.assertEqual(run_file(source)[1],0)
    def test_P_DRY_pii_content_secret_unknown_fields_refused(self):
        for field in ['body','content','password','credentials','email','phone','owner_name']:
            d=copy.deepcopy(self.data);d['rows'][0][field]='PRIVATE-SENTINEL test@example.invalid'
            with self.assertRaises(Invalid):analyze(d)
        for field in self.data['rows'][0]:
            d=copy.deepcopy(self.data);d['rows'][0][field]='private-person@example.invalid'
            with self.assertRaises(Invalid):analyze(d)
    def test_P_DRY_bad_format_unsigned_adapter_refused(self):
        for key,value in [('sanitized',False),('format','official-pre03'),('provenance','TEAM_B_SIGNED'),('rows',{})]:
            with self.assertRaises(Invalid):analyze(dict(self.data,**{key:value}))
    def test_P_DRY_duplicate_nan_json_refused(self):
        for text in ['{"rows":[],"rows":[]}','{"x":NaN}']:
            with self.assertRaises(Invalid):parse(text)
    def test_P_DRY_no_database_or_network_imports(self):
        tree=ast.parse(Path(__file__).with_name('dry_run.py').read_text());modules=[]
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):modules.extend(a.name for a in node.names)
            if isinstance(node,ast.ImportFrom):modules.append(node.module)
        self.assertFalse(set(modules)&{'sqlite3','psycopg','socket','subprocess','urllib','requests','knowledge_sdk'})
    def test_P_DRY_actual_cli_exit_codes_and_non_echoing_errors(self):
        import subprocess,sys
        script=Path(__file__).with_name('dry_run.py')
        with tempfile.TemporaryDirectory(prefix='sdk25-cli-')as directory:
            source=Path(directory)/'input.json'
            cases=[(self.data,2),(dict(self.data,rows=self.data['rows'][:1]),0),(dict(self.data,body='PII-SENTINEL user@example.invalid'),3)]
            for data,expected in cases:
                source.write_text(json.dumps(data));before=source.read_bytes()
                result=subprocess.run([sys.executable,'-W','error::ResourceWarning',str(script),str(source)],capture_output=True,text=True)
                self.assertEqual(result.returncode,expected);self.assertEqual(before,source.read_bytes());self.assertNotIn('PII-SENTINEL',result.stdout+result.stderr);self.assertNotIn('user@example.invalid',result.stdout+result.stderr)
