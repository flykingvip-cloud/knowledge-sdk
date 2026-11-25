import hashlib,json,unittest
from pathlib import Path
from knowledge_sdk.contracts.v2_schemas import SCHEMAS,SOURCE_SHA256
from knowledge_sdk.contracts.v2_json import loads,validate
from knowledge_sdk import ValidationError


class FrozenSource(unittest.TestCase):
    def test_runtime_schema_subset_exact_frozen_source(self):
        source=Path(__file__).parents[2]/'docs/architecture/knowledge-sdk-alignment/contracts/openapi-v2-draft.yaml'
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),SOURCE_SHA256)
        original=json.loads(source.read_text())['components']['schemas']
        for name,schema in SCHEMAS.items():self.assertEqual(schema,original[name],name)
    def test_strict_json_rejects_duplicate_nan_unicode_and_generation_float(self):
        for raw in ('{"x":1,"x":2}','{"x":NaN}','{"x":Infinity}','"\\ud800"'):
            with self.assertRaises(ValidationError):loads(raw)
        for invalid in (True,1.0,'1',None,0,-1,9007199254740992):
            with self.assertRaises(ValidationError):validate('PolicyGeneration',invalid)
