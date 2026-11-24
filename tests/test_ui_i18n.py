"""Offline locale coverage and deterministic JS DOM contracts; no browser is claimed."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import unittest
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / 'src/knowledge_sdk/ui/static'


class CopyParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.keys = []
        self.option_without_value = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        for k, v in attrs.items():
            if k.startswith('data-i18n'):
                self.keys.append(v)
        if tag == 'option' and 'value' not in attrs:
            self.option_without_value.append(attrs)


class LocaleCatalogTests(unittest.TestCase):
    def setUp(self):
        source = (STATIC / 'i18n.js').read_text()
        self.catalog = json.loads(source[source.index('{'):source.index(';\nexport const LANGUAGE_KEY')])

    def test_all_static_and_dynamic_keys_have_both_locales(self):
        parser = CopyParser(); parser.feed((STATIC / 'index.html').read_text())
        keys = parser.keys + re.findall(r'''\bt\(['"]([^'"]+)['"]''', (STATIC / 'workbench.js').read_text())
        self.assertGreater(len(keys), 170)
        for key in keys:
            self.assertIn(key, self.catalog)
            self.assertTrue(self.catalog[key]['zh-CN'])
            self.assertTrue(self.catalog[key]['en'])
        self.assertFalse(parser.option_without_value, 'Translated captions must not change API enum values')

    def test_english_interface_copy_has_no_chinese(self):
        for key, value in self.catalog.items():
            self.assertNotRegex(value['en'], '[\u4e00-\u9fff]', key)

    def test_chinese_copy_has_no_bilingual_enum_labels(self):
        for key, value in self.catalog.items():
            self.assertNotRegex(value['zh-CN'], r'enterprise_public|personal_only|org_public|all_authorized|role_clearance|WORKBENCH|LOCAL DEMO|SPACES|HITS', key)

    def test_only_locale_preference_is_persisted(self):
        script = (STATIC / 'i18n.js').read_text()
        self.assertEqual(script.count('localStorage.setItem('), 1)
        self.assertIn('localStorage.setItem(LANGUAGE_KEY, language)', script)
        self.assertNotRegex((STATIC / 'workbench.js').read_text(), r'localStorage|sessionStorage')

    def test_js_syntax(self):
        if not shutil.which('node'): self.skipTest('Node required for JavaScript syntax validation')
        for file in ('i18n.js', 'workbench.js'):
            subprocess.run(['node', '--check', str(STATIC / file)], check=True, capture_output=True)


@unittest.skipUnless(shutil.which('node'), 'Node required for deterministic DOM contracts')
class LocaleDOMTests(unittest.TestCase):
    def check_case(self, case, **env):
        result = subprocess.run(['node', str(ROOT / 'tests/ui/locale_harness.cjs'), case], env={**os.environ, **env}, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_default_chinese(self): self.check_case('default')
    def test_english_and_interpolation(self): self.check_case('english')
    def test_preference_persistence(self): self.check_case('persistence')
    def test_preference_reload(self): self.check_case('reload', TEST_LANGUAGE='en')
    def test_invalid_locale_and_key_fallback(self): self.check_case('fallback')
    def test_blocked_storage_fallback(self): self.check_case('storageBlocked', BLOCK_STORAGE='1')
    def test_static_dom_and_attributes(self): self.check_case('staticDOM')
    def test_dynamic_spaces_empty_states_and_original_content(self): self.check_case('dynamic')
    def test_dynamic_evidence_and_server_notices(self): self.check_case('evidence')
    def test_refusal_is_localized(self): self.check_case('refusal')
    def test_server_errors_do_not_leak_english(self): self.check_case('errors')
    def test_enum_labels(self): self.check_case('enums')
    def test_cached_switch_has_no_network_requests(self): self.check_case('switchCached')
    def test_identity_switch_retains_locale(self): self.check_case('identity')

    def test_document_policy_labels_and_original_body(self): self.check_case('documents')
    def test_receipt_status_and_no_duplicate_on_rerender(self): self.check_case('receipts')

    def test_compact_identity_retains_claims_and_both_languages(self): self.check_case('chromeIdentity')
    def test_navigation_labels_remain_complete_in_both_languages(self): self.check_case('chromeNavigation')
