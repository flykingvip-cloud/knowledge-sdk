"""Independent t59/t60 boundary tests; NOT missing agreed Team B source vectors."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO=Path(__file__).resolve().parents[2]
BASE=REPO/'docs/architecture/knowledge-sdk-alignment'
ASSETS=BASE/'contracts'
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
validator=load('p5b_assets',ASSETS/'validate_assets.py')
manifest=load('p5b_manifest',BASE/'validate_m1_manifest.py')

class DraftDeltaBoundaries(unittest.TestCase):
    def setUp(self):
        self.doc=json.loads((ASSETS/'openapi-v2-draft.yaml').read_text())
        self.schemas=self.doc['components']['schemas']
    def test_policy_generation_strict_no_coercion_and_missing(self):
        for value in (1,9007199254740991):validator.validate(value,self.schemas['PolicyGeneration'],self.doc)
        for value in (0,-1,None,'1','abc',True,False,1.5,9007199254740992,float('nan'),float('inf')):
            with self.subTest(value=repr(value)),self.assertRaises(ValueError):validator.validate(value,self.schemas['PolicyGeneration'],self.doc)
        identity=json.loads((ASSETS/'contract-fixtures/identity-context.json').read_text())
        del identity['actor']['policy_generation']
        with self.assertRaises(ValueError):validator.validate(identity,self.schemas['IdentityContext'],self.doc)
    def test_all_digest_fields_reference_raw_hex_and_algorithm(self):
        def inspect(node):
            if isinstance(node,dict):
                props=node.get('properties',{})
                for key,schema in props.items():
                    if key.endswith('_hash'):
                        self.assertEqual(schema,{'$ref':'#/components/schemas/Sha256Hex'})
                        self.assertEqual(props['hash_algorithm'],{'type':'string','const':'sha256'})
                        self.assertIn('hash_algorithm',node['required'])
                for child in node.values():inspect(child)
            elif isinstance(node,list):
                for child in node:inspect(child)
        inspect(self.schemas)
        for value in ('A'*64,'sha256:'+'a'*64,'a'*63,'a'*65,'a'*64+'\n',True,None):
            with self.subTest(value=repr(value)),self.assertRaises(ValueError):validator.validate(value,self.schemas['Sha256Hex'],self.doc)
    def test_activation_formula_strict_states_pointers_and_types(self):
        schema=self.schemas['WriteActivationResult']
        for state in ('published','draft','in_review','approved','rejected','superseded','revoked'):
            for current in (2,3):
                value=dict(created_version=3,current_version=current,lifecycle_state=state,activated=current==3 and state=='published',rollback_scope='content_and_filename_only')
                validator.validate(value,schema,self.doc)
                with self.assertRaises(ValueError):validator.validate({**value,'activated':not value['activated']},schema,self.doc)
        value=dict(created_version=1,current_version=1,lifecycle_state='published',activated=True,rollback_scope='content_and_filename_only')
        for patch in ({'created_version':True},{'created_version':'1'},{'current_version':None},{'current_version':9007199254740992},{'lifecycle_state':'notdraft'},{'activated':'true'},{'rollback_scope':'all_metadata'},{'extra':1}):
            with self.subTest(patch=patch),self.assertRaises(ValueError):validator.validate({**value,**patch},schema,self.doc)
        for key in value:
            bad=copy.deepcopy(value);del bad[key]
            with self.assertRaises(ValueError):validator.validate(bad,schema,self.doc)
    def test_draft_idempotency_routes_no_runtime_authority(self):
        self.assertFalse(self.doc['x-implementation-status']['runtime_v2_implemented'])
        response=self.schemas['DocumentWriteResponse']
        self.assertTrue(set(self.schemas['DocumentVersion']['required']).issubset(response['required']))
        self.assertTrue(set(self.schemas['WriteActivationResult']['required']).issubset(response['required']))
        self.assertEqual(self.doc['paths']['/v2/assets']['post']['responses']['200']['content']['application/json']['schema'],{'$ref':'#/components/schemas/DocumentWriteResponse'})
        for path in ('/v2/spaces','/v2/assets'):
            op=self.doc['paths'][path]['post']
            self.assertEqual(op['x-contract-status'],'draft-pending-m1-freeze')
            self.assertIn({'$ref':'#/components/parameters/IdempotencyKey'},op['parameters'])
            self.assertEqual(op['security'],[{'TrustedGateway':[]}])
            conflict=op['responses']['409']['content']['application/json']['schema']
            error=json.loads((ASSETS/'contract-fixtures/error-envelope.json').read_text())
            with self.assertRaises(ValueError):validator.validate(error,conflict,self.doc)
            error['error']['code']='IDEMPOTENCY_CONFLICT';validator.validate(error,conflict,self.doc)
        self.assertIs(self.doc['components']['parameters']['IdempotencyKey']['required'],False)
    def test_bare_scripts_unset_pythonpath_foreign_cwd_verified_pending(self):
        env={k:v for k,v in os.environ.items() if k!='PYTHONPATH'}
        for site in ([],['-S']):
            for script in (ASSETS/'validate_assets.py',BASE/'validate_m1_manifest.py'):
                with self.subTest(site=site,script=script.name),tempfile.TemporaryDirectory() as cwd:
                    result=subprocess.run([sys.executable]+site+[str(script)],cwd=cwd,env=env,text=True,capture_output=True,timeout=30)
                    self.assertEqual(result.returncode,0,result.stderr)
                    data=json.loads(result.stdout)
                    if script.name=='validate_assets.py':self.assertTrue(data['delta']['complete']);self.assertEqual(data['delta']['agreed_hash_vectors_verified'],7)
                    else:self.assertFalse(data['freeze_authorized']);self.assertTrue(data['contract_delta_complete'])
                    self.assertNotIn('ModuleNotFoundError',result.stderr)
    def test_pending_manifest_verifies_assets_never_promotes_to_approval(self):
        data=json.loads((BASE/'m1-freeze-manifest.json').read_text())
        result=manifest.check(data)
        self.assertEqual(result['status'],'WELL_FORMED_PENDING');self.assertTrue(result['contract_delta_complete']);self.assertFalse(result['freeze_authorized'])
        for patch in ({'freeze_authorized':True},{'freeze_authorized':0},{'contract_delta_status':'APPROVED'},{'status':'FROZEN'},{'approvals':[{'role':'owner','by':'executor'}]}):
            with self.subTest(patch=patch),self.assertRaises(ValueError):manifest.check({**data,**patch})
    def test_python_whitespace_set_and_source_confirmed_nfc(self):
        expected=set(range(9,14))|set(range(28,33))|{133,160,5760}|set(range(8192,8203))|{8232,8233,8239,8287,12288}
        self.assertEqual(len(expected),29)
        self.assertEqual({i for i in range(0x110000) if chr(i).isspace()},expected)
        self.assertFalse('\ufeff'.isspace())
        from knowledge_sdk.ingestion.fingerprint import normalize_text
        self.assertEqual(normalize_text('e\u0301'),'é')
        self.assertIn('NFC explicitly resolved',(ASSETS/'uri-mapping.test.ts').read_text())
        self.assertIn('NFC then exactly29',(BASE/'M1_DECISION_PACKAGE.md').read_text())
    def test_original_ten_archive_is_known_exact_bytes(self):
        self.assertEqual(hashlib.sha256((BASE/'10_WAVE1P5_ACCEPTANCE_AND_DELTA_DIRECTIVE.md').read_bytes()).hexdigest(),'d7c3330c0c2c7ae9756fe23a2cab0de8b3c14bc192ea7eb2d4105d32e82a401d')
        self.assertEqual(hashlib.sha256((BASE/'SOURCE10_STANDALONE_T59_ORIGINAL.md').read_bytes()).hexdigest(),'3c01cfb0e8fb43f675116ffb0963273a6edcc58596b01685172d854ccf0afc2c')

class ClosedAssetCoverage(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.repo=Path(self.temp.name)/'repo';self.root=self.repo/'docs/architecture/knowledge-sdk-alignment'
        for relative in tuple('contracts/'+name for name in manifest.CONTRACT_ROOT_FILES)+('M1_DECISION_PACKAGE.md','validate_m1_manifest.py','WAVE1P5B_SOURCE_PROVENANCE.json')+tuple('contracts/contract-fixtures/'+name for name in validator.delta.FILES+('identity-context.json','agent-intersection-deny.json','kb-lifecycle.json','dual-uri-evidence.json','calibrated-search-response.json','error-envelope.json')):
            p=self.root/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('{}')
        self.hashes={p.relative_to(self.repo).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*') if p.is_file()}
    def test_exact_closed_coverage_and_missing_extra_malformed_hashes(self):
        self.assertEqual(manifest.validate_asset_hashes(self.hashes,self.root),len(self.hashes))
        for key in self.hashes:
            with self.subTest(deleted_required_asset=key),self.assertRaises(ValueError):manifest.validate_asset_hashes({k:v for k,v in self.hashes.items() if k!=key},self.root)
        first=next(iter(self.hashes))
        candidates=[{k:v for k,v in self.hashes.items() if k!=first},{**self.hashes,'extra.json':'0'*64}]
        for bad in ('G'*64,'a'*63,'sha256:'+'a'*64,True,None):candidates.append({**self.hashes,first:bad})
        for bad in candidates:
            with self.subTest(bad=bad),self.assertRaises(ValueError):manifest.validate_asset_hashes(bad,self.root)
    def test_actual_mismatch_and_unpinned_new_fixture_rejected(self):
        p=self.root/'contracts/contract-fixtures/hash-vectors-utf8.json';p.write_text('{"changed":true}')
        with self.assertRaises(ValueError):manifest.validate_asset_hashes(self.hashes,self.root)
        p.write_text('{}');(p.parent/'extra.json').write_text('{}')
        with self.assertRaises(ValueError):manifest.validate_asset_hashes(self.hashes,self.root)
    def test_absolute_traversal_and_windows_alias_paths_rejected(self):
        first=next(key for key in self.hashes if '/contracts/' in key)
        for name in ('../outside','/tmp/outside',first.replace('/','\\'),first.replace('/contracts/','/contracts/../contracts/')):
            bad=dict(self.hashes);digest=bad.pop(first);bad[name]=digest
            with self.subTest(name=name),self.assertRaises(ValueError):manifest.validate_asset_hashes(bad,self.root)
    def test_symlink_asset_outside_governance_root_rejected(self):
        outside=Path(self.temp.name)/'outside.json';outside.write_text('{}')
        p=self.root/'contracts/contract-fixtures/hash-vectors-utf8.json';p.unlink();p.symlink_to(outside)
        with self.assertRaises(ValueError):manifest.validate_asset_hashes(self.hashes,self.root)
    def test_symlink_fixture_directory_outside_root_rejected(self):
        outside=Path(self.temp.name)/'outside';outside.mkdir()
        directory=self.root/'contracts/contract-fixtures';[p.unlink() for p in directory.iterdir()];directory.rmdir();directory.symlink_to(outside,target_is_directory=True)
        with self.assertRaises(ValueError):manifest.validate_asset_hashes(self.hashes,self.root)

class SourceVectors(unittest.TestCase):
    def setUp(self):
        self.fixtures={name:json.loads((ASSETS/'contract-fixtures'/name).read_text()) for name in validator.delta.FILES}
    def test_all_source_vectors_recomputed_not_declared_only(self):
        result=validator.delta.verify(BASE,self.fixtures)
        self.assertEqual((result['hash_vectors'],result['hmac_vectors'],result['rollback_cases'],result['minimum_slice_assertions']),(7,4,8,10))
    def test_hmac_exact_actual_sdk_canonicalization_and_tamper(self):
        import hmac
        from knowledge_sdk.server.auth import _message
        fixture=self.fixtures['signed-request-canonicalization.json']
        for case in fixture['cases']:
            actual=_message(case['method'],case['signed_target'],fixture['actor_header'],fixture['timestamp'],case['nonce'],case['body_utf8'].encode('utf-8'),fixture['agent_header'] if case['agent_header_present'] else None,case.get('purpose') if case['purpose_header_present'] else None)
            self.assertEqual(actual,validator.delta.canonical(case,fixture))
            signature=hmac.new(fixture['test_only_secret'].encode(),actual,hashlib.sha256).hexdigest()
            self.assertEqual(signature,case['signature'])
            self.assertNotEqual(hmac.new(fixture['test_only_secret'].encode(),actual+b'changed',hashlib.sha256).hexdigest(),signature)
            if not case['agent_header_present'] and case['purpose_header_present']:self.assertEqual(actual.split(b'\n')[6],b'')
    def test_sdk_nfc_python29_and_all_seven_literal_pairs(self):
        from knowledge_sdk.ingestion.fingerprint import normalize_text,sha256
        for case in self.fixtures['hash-vectors-utf8.json']['cases']:
            self.assertEqual(sha256(case['raw']),case['raw_hash']);self.assertEqual(normalize_text(case['raw']),case['normalized']);self.assertEqual(sha256(normalize_text(case['raw'])),case['semantic_hash'])
    def test_every_source_fixture_deleted_case_or_changed_literal_rejected(self):
        for filename in validator.delta.FILES:
            broken=copy.deepcopy(self.fixtures);broken[filename]['cases'].pop()
            with self.subTest(filename=filename),self.assertRaises(ValueError):validator.delta.verify(BASE,broken)
        for filename,key,value in [('hash-vectors-utf8.json','raw','changed'),('signed-request-canonicalization.json','signed_target','/v1/search?raw=/'),('rollback-activation-cases.json','activated',False),('policy-generation-cases.json','stored_generation',True),('identity-lifecycle-fixtures.json','presented_generation',True)]:
            broken=copy.deepcopy(self.fixtures);broken[filename]['cases'][0][key]=value
            with self.subTest(filename=filename),self.assertRaises(ValueError):validator.delta.verify(BASE,broken)
    def test_generation_and_identity_reference_not_email_oracle(self):
        policy=self.fixtures['policy-generation-cases.json']['cases']
        self.assertEqual(len(policy),12)
        self.assertNotIn('policy_generation',next(c for c in policy if c['id']=='missing')['submitted'])
        self.assertIsNone(next(c for c in policy if c['id']=='null')['submitted']['policy_generation'])
        cases={c['id']:c for c in self.fixtures['identity-lifecycle-fixtures.json']['cases']}
        self.assertEqual(validator.delta.identity_result(cases['cross_idp_same_email_new_user_not_merged'])['user_id'],'stable-user-002')
        self.assertFalse(validator.delta.identity_result(cases['cross_idp_same_user_without_rebound_denied'])['allowed'])
        rebound=copy.deepcopy(cases['explicit_identity_rebound']);rebound['migration']['administrator_authorized']=False
        self.assertFalse(validator.delta.identity_result(rebound)['allowed'])
        rebound=copy.deepcopy(cases['explicit_identity_rebound']);rebound['incoming']['policy_generation']=1
        self.assertFalse(validator.delta.identity_result(rebound)['allowed'])
    def test_all_draft_examples_uncaptured_no_v2_documents_alias(self):
        examples=self.fixtures['signed-request-canonicalization.json']['draft_v2_examples']
        self.assertEqual([e['status'] for e in examples],[200,403,409,422])
        self.assertTrue(all(e['runtime_captured'] is False and e['reason']=='v2_runtime_prohibited_before_m1_freeze' for e in examples))
        spec=json.loads((ASSETS/'openapi-v2-draft.yaml').read_text());self.assertNotIn('/v2/documents',spec['paths'])
        checklist=json.loads((ASSETS/'minimum-slice-checklist.json').read_text())
        self.assertEqual(checklist['synchronous_writes'],['POST /v2/spaces','POST /v2/assets']);self.assertFalse(checklist['freeze_authorized'])
    def test_changed_source_bytes_and_missing_sources_failclosed(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name in validator.delta.SOURCE_SHA256:(root/name).write_bytes((BASE/name).read_bytes())
            self.assertEqual(validator.delta.verify_sources(root),6)
            file=root/validator.delta.SOURCE08;file.write_bytes(file.read_bytes()+b'\n')
            with self.assertRaises(ValueError):validator.delta.verify_sources(root)
            file.unlink()
            with self.assertRaises(ValueError):validator.delta.verify_sources(root)
