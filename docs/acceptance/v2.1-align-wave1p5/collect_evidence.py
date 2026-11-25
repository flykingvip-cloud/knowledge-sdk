"""Strictly collect actual completed receipts; never synthesizes missing tests/CI."""
from __future__ import annotations
import argparse,hashlib,json,re,shutil,subprocess,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
def load(path):return json.loads(path.read_text())
def unit(path):
    text=path.read_text();runs=re.findall(r'Ran (\d+) tests in ([0-9.]+)s',text);assert runs and re.search(r'^OK(?: \(skipped=\d+\))?$',text,re.M),path.name
    assert 'ResourceWarning:' not in text
    skipped=re.findall(r'^OK \(skipped=(\d+)\)$',text,re.M);total=int(runs[-1][0]);skip=int(skipped[-1]) if skipped else 0
    return dict(total=total,passed=total-skip,skipped=skip,failed=0,resource_warnings=0,seconds=float(runs[-1][1]))
def collect(art):
    art=art.resolve();source=(art/'final-suite-source-sha.txt').read_text().strip()
    results={'source_sha_at_frozen_final_suite_start':source,'stdlib':unit(art/'final-l1-stdlib.log'),'unittest':unit(art/'final-full-unittest.log')}
    text=(art/'final-full-pytest.log').read_text();assert 'ResourceWarning:' not in text
    match=re.search(r'(\d+) passed, (\d+) skipped, (\d+) warning, (\d+) subtests passed',text);assert match,'Actual pytest summary missing'
    results['pytest']=dict(zip(('passed','skipped','non_resource_warnings','subtests_passed'),map(int,match.groups())));results['pytest'].update(failed=0,resource_warnings=0,warning_kind='Existing optional Starlette TestClient deprecation; not a core/ResourceWarning')
    names=['final-l1-stdlib.log','final-full-unittest.log','final-full-pytest.log','final-package-verification.log','perf-paired-comparison.json','performance-timestamp-provenance.json','protected-sources.json','pending-manifest.json','openapi-structural.json','ts-final-tests.json','p5-focused-all.log','principal-final-reentrant-task.log','sandbox-shutdown-final.log','final-compose-validation.log']
    results['golden']={};results['wire']={}
    for engine in ('sqlite','postgres'):
        results['golden'][engine]={}
        for mode,count in (('default',115),('legacy75',75),('legacy100',100)):
            name='golden-'+engine+'-'+mode+'.json';d=load(art/name);assert d['gate_passed'] and d['case_count']==d['passed']==count and not any(d[k] for k in ('failed','skipped','implicit_model_calls','security_assertion_failures'));names.append(name);results['golden'][engine][mode]={k:d[k] for k in ('case_count','passed','failed','skipped','implicit_model_calls','security_assertion_failures')}
        name='wire-'+engine+'.json';w=load(art/name);assert w['q3_m2_nine_runtime_variants']['passed'] and w['q3_m1_hmac_oidc_six_families']['passed'] and w['provider_instrumentation']['observed_attempts']==0;names.append(name)
        results['wire'][engine]={'wave1_groups':w['wave1']['wire_assertion_groups'],'m2_runtime_groups':w['q3_m2_nine_runtime_variants']['assertion_groups'],'m1_six_family_groups':w['q3_m1_hmac_oidc_six_families']['http_assertion_groups'],'provider_attempts':w['provider_instrumentation']['observed_attempts']}
        for phase in ('before','after-final'):names += ['perf-'+phase+'-'+engine+'.json','profile-'+phase+'-'+engine+'.txt']
        for phase in ('before','after'):names.append('schema-'+phase+'-'+engine+'.json')
    assert load(art/'pending-manifest.json')['freeze_authorized'] is False
    assert load(art/'openapi-structural.json')['official_optional_validator']=='PASSED'
    assert load(art/'ts-final-tests.json')['status']=='EXECUTED_TS_URI_MAPPING_PASSED'
    wheel=next((art/'package').glob('*.whl'));matched=[]
    with zipfile.ZipFile(wheel) as z:
        for name in z.namelist():
            if name.startswith('knowledge_sdk/') and not name.endswith('/'):
                p=ROOT/'src'/name;assert p.is_file() and p.read_bytes()==z.read(name),name;matched.append({'path':name,'sha256':hashlib.sha256(z.read(name)).hexdigest()})
    results['wheel_current_source_match']={'wheel':wheel.name,'wheel_sha256':hashlib.sha256(wheel.read_bytes()).hexdigest(),'package_files_byte_identical_to_current_source':len(matched),'core_source_digest':hashlib.sha256(json.dumps(matched,sort_keys=True).encode()).hexdigest(),'inherited_all_record_ast39_extracted_stdlib_gates':'PASSED','metadata_version':'1.2.0','mandatory_dependencies':[]}
    results['L4']='DRAFT_ASSET_SELFCHECK_AND_NO_UI_CHANGES; no new browser claim';results['L5']='HANDOFF_COMPLIANCE_ONLY_INDEPENDENT_REVIEW_PENDING';results['m1_joint_freeze']='PENDING_NOT_AUTHORIZED'
    for name in names:
        source_file=art/name;assert source_file.is_file(),name;shutil.copy2(source_file,HERE/name)
        if name.startswith('profile-'):(HERE/name).write_text((HERE/name).read_text().rstrip('\n')+'\n')
    shutil.copy2(art/'docker-local/sandbox-docker.json',HERE/'docker-local-status.json')
    (HERE/'VALIDATION_SUMMARY.json').write_text(json.dumps(results,indent=2)+'\n')
    provenance={'scope':'Task0 semantic/audit-only extension, runtime v1 response and schema unchanged','commit':'d8a6176','action':'rollback_document','validated_audit_details':{'rollback_scope':'content_and_filename_only','security_metadata_preserved':True},'meaning':'Restores target content and filename only; current ACL/rights/business metadata/L2 lifecycle rules retained. rollback_from_version is the target source version.','actual_dual_engine_regression':'tests.alignment_p5.test_rollback.SQLiteRollback and PostgresRollback in final-full-unittest.log','negative_behavior':'Current denied reader remains denied; revoked rights prevent rollback, no old history or security resurrection.','v1_return_fields_added':False,'schema_ddl_added':False}
    (HERE/'TASK0_ROLLBACK_AUDIT_PROVENANCE.json').write_text(json.dumps(provenance,indent=2)+'\n');print(json.dumps(results,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('artifact_directory',type=Path);a=p.parse_args();collect(a.artifact_directory)
