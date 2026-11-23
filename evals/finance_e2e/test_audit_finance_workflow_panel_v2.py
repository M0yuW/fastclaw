import json
import unittest

from audit_finance_workflow_panel_v2 import (
    EXPECTED_NUMBERS, financial_tool_data_exact, number_present, reasoning_flags,
)


class TargetedClaimAuditTest(unittest.TestCase):
    def test_numeric_match_has_boundaries(self):
        self.assertTrue(number_present("revenue 30,040 USD million", "30040"))
        self.assertFalse(number_present("revenue 130040 USD million", "30040"))

    def test_missing_current_margin_does_not_require_baseline_repetition(self):
        self.assertNotIn("78.4", EXPECTED_NUMBERS["E4"])

    def test_p4_rejects_false_breach_uncertainty(self):
        text = "The unreported position could exceed 50%, so compliance is unknown."
        self.assertIn("unsupported_50_percent_breach_uncertainty",
                      reasoning_flags("P4", text))

    def test_p4_accepts_correct_bound_and_missing_hhi(self):
        text = ("The omitted holdings total at most 25% of the portfolio, so none "
                "can exceed 50%. Full HHI cannot be computed without identities.")
        self.assertEqual([], reasoning_flags("P4", text))

    def test_conflicting_points_are_not_a_guidance_range(self):
        self.assertIn("conflicting_points_recast_as_range", reasoning_flags(
            "C2", "Management issued guidance in the USD 5,000-8,000 million range."))

    def test_zero_tool_trace_not_a_content_quality_proxy(self):
        self.assertEqual([], reasoning_flags("P4", "No full-portfolio HHI can be computed."))

    def test_screening_metric_mismatch_is_caught(self):
        payload = {"ok": True, "data": {"synthetic": True, "results": [{
            "symbol": "FICC", "period": "FY2025",
            "valuation": {"pe_trailing": 16.5},
            "growth": {"revenue_growth_yoy": 0.12, "earnings_growth_yoy": 0.14},
            "leverage": {"debt_to_equity": 0.22},
            "cash_flow": {"free_cash_flow": 999, "unit": "USD_million"},
            "profitability": {"roic": 0.13},
            "analyst_consensus": {"upside_pct": 0.31},
        }], "rejected": [{"symbol": "FICD", "missing_metrics": ["earnings_growth_yoy"]}],
            "passed": 1, "failed": 1}}
        result = {"case_id": "S1", "turns": [{"response": {"fastclaw": {
            "trace": [{"type": "tool_result", "name": "finance-tools__screen_stocks",
                       "result": json.dumps(payload)}]}}}]}
        self.assertFalse(financial_tool_data_exact(result))

    def test_portfolio_hhi_mismatch_is_caught(self):
        payload = {"ok": True, "data": {
            "holdings": {"FICA": 0.45, "FICB": 0.30, "FICC": 0.25},
            "largest_weight_pct": 45, "limit_breached": False,
            "herfindahl_index": 0.5}}
        result = {"case_id": "P1", "turns": [{"response": {"fastclaw": {
            "trace": [{"type": "tool_result", "name": "finance-tools__portfolio_risk",
                       "result": json.dumps(payload)}]}}}]}
        self.assertFalse(financial_tool_data_exact(result))


if __name__ == "__main__":
    unittest.main()
