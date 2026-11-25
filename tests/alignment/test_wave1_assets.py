import importlib.util,json,unittest,subprocess,sys,tempfile,shutil,hashlib
from pathlib import Path
ROOT=Path(__file__).parents[2]
ASSETS=ROOT/'docs/architecture/knowledge-sdk-alignment/contracts'

class DraftAssets(unittest.TestCase):
    def test_full_used_schema_security_and_negative_probes(self):
        spec=importlib.util.spec_from_file_location('wave_validator',ASSETS/'validate_assets.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        result=m.run();self.assertEqual(result['fixtures'],6);self.assertGreaterEqual(result['negative_probes'],30);self.assertFalse(result['runtime_v2_implemented'])
    def test_dto_schema_fixture_generation_exact(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);assets=base/'contracts';(assets/'contract-fixtures').mkdir(parents=True)
            shutil.copyfile(ASSETS/'generate_assets.py',assets/'generate_assets.py');shutil.copyfile(ASSETS.parent/'03_DOMAIN_CONTRACTS.md',base/'03_DOMAIN_CONTRACTS.md')
            subprocess.run([sys.executable,'-S',str(assets/'generate_assets.py')],check=True,capture_output=True)
            for file in ('openapi-v2-draft.yaml','openbot-adapter-dto.d.ts','fixture-schemas.json'):
                self.assertEqual((assets/file).read_bytes(),(ASSETS/file).read_bytes())
            for fixture in (ASSETS/'contract-fixtures').glob('*.json'):self.assertEqual(fixture.read_bytes(),(assets/'contract-fixtures'/fixture.name).read_bytes())
    def test_six_governance_original_hashes_unchanged(self):
        manifest=json.loads((ASSETS.parent/'PROVENANCE.json').read_text())
        for file,digest in manifest['archive_originals_sha256'].items():self.assertEqual(hashlib.sha256((ASSETS.parent/file).read_bytes()).hexdigest(),digest)
        self.assertEqual(hashlib.sha256((ASSETS.parent/'OWNER_SUPPLEMENT_WAVE1_T56U_ORIGINAL.md').read_bytes()).hexdigest(),manifest['owner_supplement_sha256'])
    def test_docker_bounded_source_structure_not_engine_pass(self):
        text=(ROOT/'Dockerfile').read_text();self.assertEqual(sum(x.startswith('FROM ') for x in text.splitlines()),2)
        self.assertIn('USER 65532:65532',text);self.assertIn('--no-index',text);self.assertNotIn('dev-insecure',text);self.assertIn('8088',text)
        self.assertNotIn('dependencies = ["', (ROOT/'pyproject.toml').read_text().split('[project.optional-dependencies]')[0])
    def test_legacy_operations_unchanged_additive_only(self):
        from knowledge_sdk.client.http_client import OPERATIONS
        expected={'create_kb':('POST','/v1/kbs'),'list_kbs':('GET','/v1/kbs'),'get_document':('POST','/v1/documents/get'),'search':('POST','/v1/search')}
        for name,value in expected.items():self.assertEqual(OPERATIONS[name],value)
        self.assertEqual(len(OPERATIONS),70)
