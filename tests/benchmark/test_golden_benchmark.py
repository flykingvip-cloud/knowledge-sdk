from __future__ import annotations
import unittest
from .runner import run_suite

class GoldenGate(unittest.TestCase):
    def test_exact60_offline_cases_no_skips_hard_gate(self):
        result=run_suite()
        self.assertEqual(result['case_count'],60)
        self.assertEqual(result['skipped'],0)
        self.assertTrue(result['gate_passed'],[r for r in result['results'] if r['status']!='passed'])
        self.assertEqual(result['acl_violation_rate']['numerator'],0)
        self.assertEqual(result['implicit_model_calls'],0)
        self.assertEqual(result['mcp_injection_blocked']['denominator'],36)
        self.assertEqual(result['mcp_injection_blocked']['numerator'],36)
