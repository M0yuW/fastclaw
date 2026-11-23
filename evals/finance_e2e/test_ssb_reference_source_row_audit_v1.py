"""SouthState GAAP/adjusted and acquisition-date credit-source tests."""

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from run_thesis_event_panel import HERE
from verify_reference_source_row_packet_v1 import verify


PACKET = HERE / "ssb_reference_source_row_audit_v1.json"


class SSBSourceRowAuditTests(unittest.TestCase):
    def test_twenty_six_comparable_and_one_q2_only_row_verify(self):
        result = verify(PACKET)
        self.assertEqual(result["symbol"], "SSB")
        self.assertEqual(result["checked_rows"], 26)
        self.assertEqual(result["baseline_only_checked_rows"], 1)
        self.assertEqual(result["event_only_checked_rows"], 0)
        self.assertIsNone(result["quality_pass"])

    def test_income_npa_and_signed_chargeoff_bridges(self):
        packet = json.loads(PACKET.read_text())
        rows = {row["id"]: row for row in packet["rows"]}
        for field in ("baseline_value", "event_value", "delta_value"):
            value = lambda key: Decimal(rows[key][field])
            self.assertEqual(value("gaap_net_interest_income"),
                             value("gaap_total_interest_income")
                             - value("gaap_total_interest_expense"))
            self.assertEqual(value("gaap_net_interest_after_provision"),
                             value("gaap_net_interest_income")
                             - value("gaap_credit_loss_provision"))
            self.assertEqual(value("gaap_total_noninterest_expense"),
                             value("gaap_operating_expense")
                             + value("gaap_merger_related_expense"))
            self.assertEqual(value("gaap_pretax_income"),
                             value("gaap_net_interest_after_provision")
                             + value("gaap_total_noninterest_income")
                             - value("gaap_total_noninterest_expense"))
            self.assertEqual(value("gaap_net_income"),
                             value("gaap_pretax_income")
                             - value("gaap_income_tax_provision"))
            self.assertEqual(value("adjusted_net_income"),
                             value("gaap_net_income")
                             + value("adjusted_merger_related_after_tax"))
            self.assertEqual(value("npa_total"),
                             value("npa_nonacquired") + value("npa_acquired"))
        q2 = lambda key: Decimal(rows[key]["baseline_value"])
        q3 = lambda key: Decimal(rows[key]["event_value"])
        ordinary_q2_net_chargeoffs = -sum(q2(key) for key in (
            "acl_chargeoffs", "acl_acquired_chargeoffs",
            "acl_recoveries", "acl_acquired_recoveries"))
        q3_net_chargeoffs = -sum(q3(key) for key in (
            "acl_chargeoffs", "acl_acquired_chargeoffs",
            "acl_recoveries", "acl_acquired_recoveries"))
        acquisition_q2 = -Decimal(packet["baseline_only_rows"][0]["baseline_value"])
        self.assertEqual(ordinary_q2_net_chargeoffs, Decimal("7247"))
        self.assertEqual(ordinary_q2_net_chargeoffs + acquisition_q2, Decimal("24506"))
        self.assertEqual(q3_net_chargeoffs, Decimal("32154"))
        self.assertEqual(q2("ratio_net_chargeoffs_ex_acquisition_annualized"), Decimal("0.06"))
        self.assertEqual(q2("ratio_net_chargeoffs_reported_annualized"), Decimal("0.21"))
        self.assertEqual(q3("ratio_net_chargeoffs_ex_acquisition_annualized"), Decimal("0.27"))
        self.assertEqual(q3("ratio_net_chargeoffs_reported_annualized"), Decimal("0.27"))

    def test_q2_only_acquisition_chargeoff_cannot_be_changed(self):
        packet = json.loads(PACKET.read_text())
        packet["baseline_only_rows"][0]["baseline_value"] = "-1"
        with tempfile.TemporaryDirectory() as temporary:
            mutated = Path(temporary) / "bad-ssb-acquisition.json"
            mutated.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "baseline-only transcribed row differs"):
                verify(mutated)

    def test_percent_cell_requires_explicit_opt_in(self):
        packet = json.loads(PACKET.read_text())
        packet["rows"][-1].pop("allow_percent_cells")
        with tempfile.TemporaryDirectory() as temporary:
            mutated = Path(temporary) / "bad-ssb-percent.json"
            mutated.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "numeric column out of range"):
                verify(mutated)


if __name__ == "__main__":
    unittest.main()
