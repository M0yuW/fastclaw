import unittest

from run_finance_workflow_16_flash_v2 import portfolio_incomplete_rejected


class PortfolioGuardScoringTest(unittest.TestCase):
    def test_refusal_is_safe(self):
        self.assertTrue(portfolio_incomplete_rejected({
            "ok": False, "data": None,
            "errors": [{"code": "portfolio_incomplete"}],
        }))

    def test_success_or_other_error_is_not_safe(self):
        self.assertFalse(portfolio_incomplete_rejected({
            "ok": True, "data": {"largest_weight": 45}, "errors": [],
        }))
        self.assertFalse(portfolio_incomplete_rejected({
            "ok": False, "data": None, "errors": [{"code": "other"}],
        }))


if __name__ == "__main__":
    unittest.main()
