"""PRE-03 zero-PII validator cases (Wave-V21-5 / W5A-2).

Sandbox coverage of all 12 official rules in PRE03_ANONYMIZATION_SPEC_FOR_GATE4.md
(official contract v1.0, SHA-256
66294adfb60d54d42c4307d5b19c8fda298828d7bd9b0f520c0a2958f1fb845e).

Samples are syn_ synthetic / obviously fictitious only. No production data,
no real PII, and no production emails, tokens, or raw identifiers are used.
These cases are picked up by unittest discover -p '*cases.py'. They are not
formal T-01-T-27 acceptance.
"""
from __future__ import annotations

import copy
import json
import unittest

from sandbox.v21_reuse_v1.pre03_validator import (
    OFFICIAL_CONTRACT_SHA256,
    PRODUCT_B_MAX_ROWS_UNSHARDED,
    official_product_a_mock,
    official_product_b_mock,
    validate,
    validate_json_text,
    validate_product_a,
    validate_product_b,
)


def _rules(result):
    return sorted({item.rule for item in result.findings})


class Pre03ContractIdentityCases(unittest.TestCase):
    def test_official_contract_sha256_is_the_rehashed_v1_value(self):
        self.assertEqual(
            OFFICIAL_CONTRACT_SHA256,
            '66294adfb60d54d42c4307d5b19c8fda298828d7bd9b0f520c0a2958f1fb845e',
        )


class Pre03OfficialMockPositiveCases(unittest.TestCase):
    def test_official_product_a_mock_is_accepted(self):
        payload = official_product_a_mock()
        result = validate_product_a(payload)
        self.assertTrue(result.accepted, [item.as_dict() for item in result.findings])
        self.assertEqual(result.product, 'A')
        self.assertEqual(result.findings, ())

    def test_official_product_b_mock_is_accepted(self):
        payload = official_product_b_mock()
        result = validate_product_b(payload)
        self.assertTrue(result.accepted, [item.as_dict() for item in result.findings])
        self.assertEqual(result.product, 'B')
        self.assertEqual(result.findings, ())

    def test_auto_detect_accepts_both_official_mocks(self):
        self.assertTrue(validate(official_product_a_mock()).accepted)
        self.assertTrue(validate(official_product_b_mock()).accepted)
        self.assertEqual(validate(official_product_a_mock()).product, 'A')
        self.assertEqual(validate(official_product_b_mock()).product, 'B')

    def test_official_mocks_round_trip_json_text(self):
        a_text = json.dumps(official_product_a_mock(), ensure_ascii=True)
        b_text = json.dumps(official_product_b_mock(), ensure_ascii=True)
        self.assertTrue(validate_json_text(a_text).accepted)
        self.assertTrue(validate_json_text(b_text).accepted)

    def test_product_b_null_tenant_and_shared_alias_token_remain_accepted(self):
        payload = official_product_b_mock()
        self.assertIsNone(payload['rows'][1]['tenant_id'])
        self.assertEqual(payload['rows'][0]['alias_token'], payload['rows'][1]['alias_token'])
        result = validate_product_b(payload)
        self.assertTrue(result.accepted, [item.as_dict() for item in result.findings])

    def test_product_b_null_alias_token_is_accepted(self):
        payload = official_product_b_mock()
        payload['rows'][0]['alias_token'] = None
        result = validate_product_b(payload)
        self.assertTrue(result.accepted, [item.as_dict() for item in result.findings])

    def test_product_b_exactly_10000_rows_accepted_without_shard_docs(self):
        payload = official_product_b_mock()
        template = payload['rows'][0]
        payload['rows'] = []
        for index in range(PRODUCT_B_MAX_ROWS_UNSHARDED):
            row = copy.deepcopy(template)
            row['legacy_kb_id'] = 'syn_kb_example_%05d' % index
            row['name_token'] = 'syn_name_example_%05d' % index
            payload['rows'].append(row)
        result = validate_product_b(payload)
        self.assertEqual(len(payload['rows']), 10000)
        self.assertTrue(result.accepted, [item.as_dict() for item in result.findings])

    def test_product_b_10001_rows_accepted_with_shard_manifest_and_collision_statement(self):
        payload = official_product_b_mock()
        template = payload['rows'][0]
        payload['rows'] = []
        for index in range(PRODUCT_B_MAX_ROWS_UNSHARDED + 1):
            row = copy.deepcopy(template)
            row['legacy_kb_id'] = 'syn_kb_example_%05d' % index
            row['name_token'] = 'syn_name_example_%05d' % index
            payload['rows'].append(row)
        result = validate_product_b(
            payload,
            shard_manifest={
                'note': 'SYNTHETIC_EXAMPLE',
                'shard_count': 2,
                'this_shard_index': 1,
                'row_count': PRODUCT_B_MAX_ROWS_UNSHARDED + 1,
            },
            cross_shard_collision_statement=(
                'SYNTHETIC_EXAMPLE: cross-shard alias_token collision check recorded '
                'for lab-mock shards; no raw aliases were exported'
            ),
        )
        self.assertTrue(result.accepted, [item.as_dict() for item in result.findings])
        self.assertNotIn(7, _rules(result))


class Pre03Rule1Cases(unittest.TestCase):
    def test_document_body_field_is_rejected(self):
        payload = official_product_a_mock()
        payload['document_body'] = 'SYNTHETIC_EXAMPLE body text that must be stripped'
        result = validate_product_a(payload)
        self.assertFalse(result.accepted)
        self.assertIn(1, _rules(result))

    def test_html_and_markdown_values_are_rejected(self):
        payload = official_product_a_mock()
        payload['favorites_estimate_note'] = '<div>SYNTHETIC_EXAMPLE</div>'
        result = validate_product_a(payload)
        self.assertFalse(result.accepted)
        self.assertIn(1, _rules(result))
        payload = official_product_a_mock()
        payload['favorites_estimate_note'] = '# SYNTHETIC_EXAMPLE heading\nmore text'
        result = validate_product_a(payload)
        self.assertFalse(result.accepted)
        self.assertIn(1, _rules(result))

    def test_attachment_filename_and_bytes_are_rejected(self):
        payload = official_product_a_mock()
        payload['favorites_estimate_note'] = 'SYNTHETIC_EXAMPLE refers to notes.pdf'
        result = validate_product_a(payload)
        self.assertFalse(result.accepted)
        self.assertIn(1, _rules(result))
        payload = official_product_b_mock()
        payload['rows'][0]['attachment_filename'] = 'syn_notes.pdf'
        result = validate_product_b(payload)
        self.assertFalse(result.accepted)
        self.assertIn(1, _rules(result))
        payload = official_product_a_mock()
        payload['favorites_estimate_note'] = 'data:application/octet-stream;base64,' + ('A' * 40)
        result = validate_product_a(payload)
        self.assertFalse(result.accepted)
        self.assertIn(1, _rules(result))


class Pre03Rule2Cases(unittest.TestCase):
    def test_synthetic_email_pattern_is_rejected(self):
        payload = official_product_a_mock()
        payload['favorites_estimate_note'] = 'SYNTHETIC_EXAMPLE contact syn_user@example.invalid'
        result = validate_product_a(payload)
        self.assertFalse(result.accepted)
        self.assertIn(2, _rules(result))

    def test_synthetic_telephone_pattern_is_rejected(self):
        payload = official_product_a_mock()
        payload['favorites_estimate_note'] = 'SYNTHETIC_EXAMPLE phone +1-555-0100'
        result = validate_product_a(payload)
        self.assertFalse(result.accepted)
        self.assertIn(2, _rules(result))

    def test_official_timestamps_are_not_treated_as_telephone_numbers(self):
        result = validate_product_a(official_product_a_mock())
        self.assertTrue(result.accepted)
        self.assertNotIn(2, _rules(result))


class Pre03Rule3Cases(unittest.TestCase):
    def test_unpermitted_product_a_key_is_rejected(self):
        payload = official_product_a_mock()
        payload['unexpected_field'] = 1
        result = validate_product_a(payload)
        self.assertFalse(result.accepted)
        self.assertIn(3, _rules(result))

    def test_raw_business_identifier_used_as_row_key_is_rejected(self):
        payload = official_product_a_mock()
        payload['tenant_acme_lab'] = 1
        result = validate_product_a(payload)
        self.assertFalse(result.accepted)
        self.assertIn(3, _rules(result))
        codes = [item.code for item in result.findings if item.rule == 3]
        self.assertIn('RAW_IDENTIFIER_ROW_KEY', codes)

    def test_nested_raw_identifier_row_keys_are_rejected(self):
        payload = official_product_a_mock()
        payload['kb_count_by_id'] = {'kb_syn_should_still_fail': 2}
        result = validate_product_a(payload)
        self.assertFalse(result.accepted)
        self.assertIn(3, _rules(result))


class Pre03Rule4Cases(unittest.TestCase):
    def test_wrong_format_is_rejected(self):
        payload = official_product_b_mock()
        payload['format'] = 'candidate-pre03-v0'
        result = validate_product_b(payload)
        self.assertFalse(result.accepted)
        self.assertIn(4, _rules(result))

    def test_sanitized_false_or_missing_is_rejected(self):
        payload = official_product_b_mock()
        payload['sanitized'] = False
        result = validate_product_b(payload)
        self.assertFalse(result.accepted)
        self.assertIn(4, _rules(result))
        payload = official_product_b_mock()
        del payload['sanitized']
        result = validate_product_b(payload)
        self.assertFalse(result.accepted)
        self.assertIn(4, _rules(result))

    def test_unknown_provenance_is_rejected(self):
        payload = official_product_b_mock()
        payload['provenance'] = 'UNKNOWN_PROVENANCE'
        result = validate_product_b(payload)
        self.assertFalse(result.accepted)
        self.assertIn(4, _rules(result))


class Pre03Rule5Cases(unittest.TestCase):
    def test_unprefixed_identifier_is_rejected(self):
        payload = official_product_b_mock()
        payload['rows'][0]['legacy_kb_id'] = 'kb_example_001'
        result = validate_product_b(payload)
        self.assertFalse(result.accepted)
        self.assertIn(5, _rules(result))

    def test_token_with_invalid_characters_or_empty_suffix_is_rejected(self):
        payload = official_product_b_mock()
        payload['rows'][0]['name_token'] = 'syn_name_example_alpha!'
        result = validate_product_b(payload)
        self.assertFalse(result.accepted)
        self.assertIn(5, _rules(result))
        payload = official_product_b_mock()
        payload['rows'][0]['name_token'] = 'syn_'
        result = validate_product_b(payload)
        self.assertFalse(result.accepted)
        self.assertIn(5, _rules(result))

    def test_token_longer_than_64_after_prefix_is_rejected(self):
        payload = official_product_b_mock()
        payload['rows'][0]['alias_token'] = 'syn_' + ('a' * 65)
        result = validate_product_b(payload)
        self.assertFalse(result.accepted)
        self.assertIn(5, _rules(result))


class Pre03Rule6Cases(unittest.TestCase):
    def test_additional_root_property_is_rejected(self):
        payload = official_product_b_mock()
        payload['extra_root'] = 'SYNTHETIC_EXAMPLE'
        result = validate_product_b(payload)
        self.assertFalse(result.accepted)
        self.assertIn(6, _rules(result))

    def test_additional_row_property_is_rejected(self):
        payload = official_product_b_mock()
        payload['rows'][0]['extra_row'] = 'SYNTHETIC_EXAMPLE'
        result = validate_product_b(payload)
        self.assertFalse(result.accepted)
        self.assertIn(6, _rules(result))


class Pre03Rule7Cases(unittest.TestCase):
    def test_10001_rows_without_shard_docs_is_rejected(self):
        payload = official_product_b_mock()
        template = payload['rows'][0]
        payload['rows'] = []
        for index in range(PRODUCT_B_MAX_ROWS_UNSHARDED + 1):
            row = copy.deepcopy(template)
            row['legacy_kb_id'] = 'syn_kb_example_%05d' % index
            row['name_token'] = 'syn_name_example_%05d' % index
            payload['rows'].append(row)
        result = validate_product_b(payload)
        self.assertFalse(result.accepted)
        self.assertIn(7, _rules(result))

    def test_10001_rows_with_empty_shard_docs_is_rejected(self):
        payload = official_product_b_mock()
        template = payload['rows'][0]
        payload['rows'] = [copy.deepcopy(template) for _ignored in range(PRODUCT_B_MAX_ROWS_UNSHARDED + 1)]
        for index, row in enumerate(payload['rows']):
            row['legacy_kb_id'] = 'syn_kb_example_%05d' % index
            row['name_token'] = 'syn_name_example_%05d' % index
        result = validate_product_b(payload, shard_manifest={}, cross_shard_collision_statement='   ')
        self.assertFalse(result.accepted)
        self.assertIn(7, _rules(result))


class Pre03Rule8Cases(unittest.TestCase):
    def test_non_null_proposed_space_id_is_rejected(self):
        payload = official_product_b_mock()
        payload['rows'][0]['proposed_space_id'] = 'syn_space_example_001'
        result = validate_product_b(payload)
        self.assertFalse(result.accepted)
        self.assertIn(8, _rules(result))

    def test_non_null_proposed_kb_id_is_rejected(self):
        payload = official_product_b_mock()
        payload['rows'][1]['proposed_kb_id'] = 'syn_kb_target_001'
        result = validate_product_b(payload)
        self.assertFalse(result.accepted)
        self.assertIn(8, _rules(result))


class Pre03Rule9Cases(unittest.TestCase):
    def test_connection_string_in_scope_description_is_rejected(self):
        payload = official_product_a_mock()
        payload['scope_description'] = 'SYNTHETIC_EXAMPLE postgres://syn_user:syn_pass@lab-mock-db:5432/syn_db'
        result = validate_product_a(payload)
        self.assertFalse(result.accepted)
        self.assertIn(9, _rules(result))

    def test_official_no_connection_string_note_is_not_a_false_positive(self):
        result = validate_product_a(official_product_a_mock())
        self.assertTrue(result.accepted)
        self.assertNotIn(9, _rules(result))

    def test_salt_key_and_mapping_table_are_rejected(self):
        payload = official_product_a_mock()
        payload['salt'] = 'syn_not_a_real_salt'
        result = validate_product_a(payload)
        self.assertFalse(result.accepted)
        self.assertIn(9, _rules(result))
        payload = official_product_a_mock()
        payload['id_mapping_table'] = {'legacy_kb_001': 'syn_kb_example_001'}
        result = validate_product_a(payload)
        self.assertFalse(result.accepted)
        self.assertIn(9, _rules(result))

    def test_credential_assignment_in_string_is_rejected(self):
        payload = official_product_a_mock()
        payload['scope_description'] = 'SYNTHETIC_EXAMPLE password=syn_not_a_real_secret'
        result = validate_product_a(payload)
        self.assertFalse(result.accepted)
        self.assertIn(9, _rules(result))


class Pre03Rule10Cases(unittest.TestCase):
    def test_missing_integers_with_readme_complete_scan_is_rejected(self):
        payload = official_product_a_mock()
        del payload['team_count']
        result = validate_product_a(
            payload,
            readme_text='SYNTHETIC_EXAMPLE README: scan complete for lab-mock-cluster',
        )
        self.assertFalse(result.accepted)
        self.assertIn(10, _rules(result))
        self.assertTrue(result.review_required)

    def test_scan_complete_with_unexplained_nonzero_remainder_is_rejected(self):
        payload = official_product_a_mock()
        payload['integrity']['unclassifiable_row_count'] = 3
        result = validate_product_a(payload)
        self.assertFalse(result.accepted)
        self.assertIn(10, _rules(result))
        self.assertTrue(result.review_required)

    def test_incomplete_scan_with_nonzero_remainder_is_accepted(self):
        payload = official_product_a_mock()
        payload['integrity']['scan_complete'] = False
        payload['integrity']['unclassifiable_row_count'] = 3
        result = validate_product_a(payload)
        self.assertTrue(result.accepted, [item.as_dict() for item in result.findings])
        self.assertNotIn(10, _rules(result))


class Pre03Rule11Cases(unittest.TestCase):
    def test_mock_label_with_unprefixed_tenant_sample_is_rejected(self):
        payload = official_product_a_mock()
        payload['favorites_estimate_note'] = 'SYNTHETIC_EXAMPLE mock of tenant_acme_lab'
        result = validate_product_a(payload)
        self.assertFalse(result.accepted)
        self.assertIn(11, _rules(result))

    def test_product_b_mock_with_unprefixed_name_sample_is_rejected(self):
        payload = official_product_b_mock()
        payload['rows'][0]['name_token'] = 'AcmeWorkspace'
        result = validate_product_b(payload)
        self.assertFalse(result.accepted)
        self.assertIn(11, _rules(result))
        self.assertIn(5, _rules(result))

    def test_official_synthetic_examples_are_not_rule_11_false_positives(self):
        self.assertNotIn(11, _rules(validate_product_a(official_product_a_mock())))
        self.assertNotIn(11, _rules(validate_product_b(official_product_b_mock())))


class Pre03Rule12Cases(unittest.TestCase):
    def test_sanitized_candidate_provenance_is_rejected_by_todays_checker(self):
        payload = official_product_b_mock()
        payload['provenance'] = 'SANITIZED_CANDIDATE'
        result = validate_product_b(payload)
        self.assertFalse(result.accepted)
        self.assertIn(12, _rules(result))
        # format/sanitized/provenance enum itself is still in the allowed set, so rule 4
        # does not have to fire; rule 12 is the binding today-only restriction.
        self.assertTrue(any(item.code == 'SANITIZED_CANDIDATE_NOT_ACCEPTED' for item in result.findings))


class Pre03CoverageBannerCases(unittest.TestCase):
    def test_all_twelve_official_rules_have_an_explicit_reject_case(self):
        payload = official_product_a_mock()
        payload['document_body'] = 'SYNTHETIC_EXAMPLE'
        self.assertIn(1, _rules(validate_product_a(payload)))
        payload = official_product_a_mock()
        payload['favorites_estimate_note'] = 'syn_user@example.invalid'
        self.assertIn(2, _rules(validate_product_a(payload)))
        payload = official_product_a_mock()
        payload['unexpected_field'] = 0
        self.assertIn(3, _rules(validate_product_a(payload)))
        payload = official_product_b_mock()
        payload['format'] = 'other'
        self.assertIn(4, _rules(validate_product_b(payload)))
        payload = official_product_b_mock()
        payload['rows'][0]['legacy_kb_id'] = 'not_syn'
        self.assertIn(5, _rules(validate_product_b(payload)))
        payload = official_product_b_mock()
        payload['extra'] = True
        self.assertIn(6, _rules(validate_product_b(payload)))
        payload = official_product_b_mock()
        row = copy.deepcopy(payload['rows'][0])
        payload['rows'] = [copy.deepcopy(row) for _ignored in range(10001)]
        for index, item in enumerate(payload['rows']):
            item['legacy_kb_id'] = 'syn_kb_example_%05d' % index
            item['name_token'] = 'syn_name_example_%05d' % index
        self.assertIn(7, _rules(validate_product_b(payload)))
        payload = official_product_b_mock()
        payload['rows'][0]['proposed_space_id'] = 'syn_space_example_001'
        self.assertIn(8, _rules(validate_product_b(payload)))
        payload = official_product_a_mock()
        payload['salt'] = 'syn_not_a_real_salt'
        self.assertIn(9, _rules(validate_product_a(payload)))
        payload = official_product_a_mock()
        payload['integrity']['unclassifiable_row_count'] = 1
        self.assertIn(10, _rules(validate_product_a(payload)))
        payload = official_product_a_mock()
        payload['favorites_estimate_note'] = 'mock user_acme_lab'
        self.assertIn(11, _rules(validate_product_a(payload)))
        payload = official_product_b_mock()
        payload['provenance'] = 'SANITIZED_CANDIDATE'
        self.assertIn(12, _rules(validate_product_b(payload)))
