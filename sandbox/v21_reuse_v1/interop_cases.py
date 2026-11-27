"""Interop cases for Wave-V21-2 W2A-1 golden fixture. Named to stay outside default pytest discovery."""
from __future__ import annotations

import ast
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from sandbox.v21_reuse_v1.interop_harness import (
    GOLDEN_PATH,
    InteropHarness,
    SemanticObjectCatalogReadAdapter,
    explain_purge_receipt,
    load_golden,
    verify_golden,
)
from sandbox.v21_reuse_v1.revocation import (
    FourChannelRevocation,
    canonical_json_bytes,
    canonical_sha256_hex,
)
from sandbox.v21_reuse_v1.semantic_reference import SemanticReferenceWriteForbidden

ROOT = Path(__file__).resolve().parents[2]
BANNED_MODULES = {
    'socket', 'ssl', 'http', 'http.client', 'http.server', 'urllib',
    'urllib.request', 'urllib.client', 'requests', 'aiohttp', 'httpx',
}


class GoldenInteropCases(unittest.TestCase):
    def setUp(self):
        self.golden = load_golden()
        self.harness = InteropHarness(catalog_records=self.golden['catalog_seed'])

    def test_fixture_has_five_official_groups(self):
        self.assertTrue(GOLDEN_PATH.is_file())
        self.assertEqual(self.golden['fixture_id'], 'W2_INTEROP_GOLDEN_V1')
        self.assertIs(self.golden['formal_acceptance'], False)
        self.assertEqual(self.golden['formal_t01_t27'], 'NOT_RUN_NOT_ACCEPTED')
        self.assertIs(self.golden['experimental_v3_enabled_default'], False)
        ids = [group['id'] for group in self.golden['groups']]
        self.assertEqual(ids, [
            'G1_MODELS_EMBED',
            'G2_AI_EXECUTION_TRACE',
            'G3_SEMANTIC_OBJECT_CATALOG',
            'G4_COGNIWEAVE_REVOCATION',
            'G5_CONTROLLED_DATA_BRIDGE',
        ])

    def test_verify_golden_passes_offline(self):
        report = verify_golden(harness=self.harness)
        self.assertTrue(report['passed'], report)
        self.assertEqual(report['group_count'], 5)
        self.assertGreaterEqual(report['case_count'], 5)
        self.assertIs(report['formal_acceptance'], False)

    def test_canonicalization_reuses_revocation_algorithm(self):
        from sandbox.v21_reuse_v1 import interop_harness
        from sandbox.v21_reuse_v1 import revocation
        self.assertIs(interop_harness.canonical_json_bytes, revocation.canonical_json_bytes)
        self.assertIs(interop_harness.canonical_sha256_hex, revocation.canonical_sha256_hex)
        payload = dict(b=2, a=1)
        raw = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
        self.assertEqual(canonical_json_bytes(payload), raw)
        self.assertEqual(canonical_sha256_hex(payload), hashlib.sha256(raw).hexdigest())
        self.assertEqual(len(canonical_sha256_hex(payload)), 64)
        self.assertEqual(canonical_sha256_hex(payload), canonical_sha256_hex(payload).lower())

    def test_canonicalization_probes(self):
        for probe in self.golden['canonicalization']['probes']:
            actual_json = canonical_json_bytes(probe['input']).decode('utf-8')
            actual_hash = canonical_sha256_hex(probe['input'])
            self.assertEqual(actual_json, probe['canonical_json'], probe['id'])
            self.assertEqual(actual_hash, probe['sha256'], probe['id'])
            # No decorative whitespace, no trailing newline in the hashed text.
            self.assertFalse(actual_json.startswith(' ') or actual_json.endswith('\n') or ': ' in actual_json or ', ' in actual_json)

    def test_unicode_probe_is_raw_utf8_not_backslash_u(self):
        probes = {item['id']: item for item in self.golden['canonicalization']['probes']}
        probe = probes['P2-UNICODE-ENSURE-ASCII-FALSE']
        raw = canonical_json_bytes(probe['input'])
        self.assertIn('撤权回执'.encode('utf-8'), raw)
        self.assertNotIn(b'\\u', raw)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), probe['sha256'])

    def test_revocation_receipt_hashes_match_golden_and_verifier(self):
        groups = {group['id']: group for group in self.golden['groups']}
        for case in groups['G4_COGNIWEAVE_REVOCATION']['cases']:
            explained = explain_purge_receipt(
                case['input']['tenant_id'],
                case['input']['subject_id'],
                case['input']['policy_generation'],
                case['input']['task_id'],
                failures=case['input'].get('failures') or {},
            )
            self.assertEqual(explained['receipt_hash'], case['expected']['receipt_hash'])
            self.assertEqual(explained['parent_canonical_json'], case['expected']['parent_canonical_json'])
            self.assertEqual(len(explained['receipt_hash']), 64)
            self.assertTrue(FourChannelRevocation().verify(explained['receipt']))
            for index, channel in enumerate(explained['channels']):
                expected = case['expected']['channels'][index]
                self.assertEqual(channel.get('receipt_hash'), expected.get('receipt_hash'))
                self.assertEqual(channel.get('canonical_json'), expected.get('canonical_json'))

    def test_catalog_read_is_memory_only_and_redacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            disk = Path(tmp)
            adapter = SemanticObjectCatalogReadAdapter(self.golden['catalog_seed'], disk_path=str(disk))
            result = adapter.read('syn_org', 'semobj:openbot:finance.invoice')
            self.assertEqual(result['disk_writes'], 0)
            self.assertFalse(result['writable'])
            self.assertEqual(sorted(result['redacted_fields']), ['dsn', 'password'])
            self.assertNotIn('dsn', result)
            self.assertNotIn('password', result)
            dumped = json.dumps(result)
            self.assertNotIn('postgresql://example.invalid/db', dumped)
            self.assertNotIn('REDACTED-NOT-A-REAL-SECRET', dumped)
            self.assertEqual(list(disk.iterdir()), [])
            with self.assertRaises(SemanticReferenceWriteForbidden) as ctx:
                adapter.write(dict(tenant_id='syn_org', semantic_object_key='semobj:openbot:finance.invoice'))
            self.assertEqual(ctx.exception.code, 'SEMANTIC_WRITE_FORBIDDEN')
            self.assertEqual(adapter.disk_writes, 0)
            self.assertEqual(list(disk.iterdir()), [])

    def test_harness_and_revocation_have_no_network_imports(self):
        root = ROOT / 'sandbox' / 'v21_reuse_v1'
        found = set()
        for path in (root / 'interop_harness.py', root / 'revocation.py', root / 'adapters.py'):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        found.add(alias.name)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    found.add(node.module)
        self.assertFalse(found & BANNED_MODULES)

    def test_sandbox_python39_ast_includes_new_modules(self):
        root = ROOT / 'sandbox' / 'v21_reuse_v1'
        names = {path.name for path in root.glob('*.py')}
        self.assertIn('interop_harness.py', names)
        self.assertIn('interop_cases.py', names)
        for path in root.glob('*.py'):
            ast.parse(path.read_text())


if __name__ == '__main__':
    unittest.main()
