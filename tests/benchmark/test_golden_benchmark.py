from __future__ import annotations
import unittest
from .runner import run_suite

class GoldenGate(unittest.TestCase):
    def test_exact75_offline_cases_no_skips_hard_gate(self):
        result=run_suite()
        self.assertEqual(result['case_count'],75)
        self.assertEqual(result['skipped'],0)
        self.assertTrue(result['gate_passed'],[r for r in result['results'] if r['status']!='passed'])
        self.assertEqual(result['acl_violation_rate']['numerator'],0)
        self.assertEqual(result['implicit_model_calls'],0)
        self.assertEqual(result['mcp_injection_blocked']['denominator'],36)
        self.assertEqual(result['mcp_injection_blocked']['numerator'],36)

    def test_old60_cases_retained_byte_for_byte(self):
        from pathlib import Path
        root=Path(__file__).parent
        original=(root/'golden_cases_v1.jsonl').read_bytes()
        self.assertTrue((root/'golden_cases_v2.jsonl').read_bytes().startswith(original))
        from .runner import load_cases
        self.assertEqual(len(load_cases(root/'golden_cases_v1.jsonl')),60)

    def test_g6_impact_completeness_is_not_a_constant(self):
        from unittest.mock import patch
        from .runner import Fixture,Observation,SCENARIOS,load_cases
        from knowledge_sdk.impact.radar import ImpactRadar
        case=next(c for c in load_cases() if c['case_id']=='G6-02')
        f=Fixture(case);self.addCleanup(f.close);o=Observation(case['expected'])
        with patch.object(ImpactRadar,'process',return_value=None),self.assertRaises(AssertionError):
            SCENARIOS[case['scenario']](f,o)
        self.assertEqual((o.impact_expected,o.impact_found),(2,0))

    def test_g6_audit_detection_is_not_a_constant(self):
        from unittest.mock import patch
        from .runner import Fixture,Observation,SCENARIOS,load_cases
        from knowledge_sdk import AuditChainReport
        case=next(c for c in load_cases() if c['case_id']=='G6-07')
        f=Fixture(case);self.addCleanup(f.close);o=Observation(case['expected'])
        with patch.object(f.c,'verify_audit_chain',return_value=AuditChainReport('org',True)),self.assertRaises(AssertionError):
            SCENARIOS[case['scenario']](f,o)
        self.assertEqual((o.audit_checks,o.audit_detected),(1,0))
