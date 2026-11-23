"""Source hash, table locator, quarterly value and arithmetic checks for ACIW."""

import json
import unittest

from run_thesis_event_panel import HERE
from verify_reference_source_row_packet_v1 import verify


PACKET = HERE / "aciw_reference_source_row_audit_v1.json"


class ACIWSourceRowAuditTests(unittest.TestCase):
    def test_ten_selected_gaap_quarter_rows_verify(self):
        result = verify(PACKET)
        self.assertEqual(result["symbol"], "ACIW")
        self.assertEqual(result["checked_rows"], 10)
        self.assertIsNone(result["quality_pass"])

    def test_mixed_signal_is_preserved_not_simplified(self):
        packet = json.loads(PACKET.read_text())
        rows = {row["id"]: row for row in packet["rows"]}
        self.assertLess(int(rows["gaap_saas_paas_revenue"]["delta_value"]), 0)
        self.assertGreater(int(rows["gaap_license_revenue"]["delta_value"]), 0)
        self.assertGreater(int(rows["gaap_net_income"]["delta_value"]), 0)
        components = (
            "gaap_saas_paas_revenue", "gaap_license_revenue",
            "gaap_maintenance_revenue", "gaap_services_revenue",
        )
        for field in ("baseline_value", "event_value", "delta_value"):
            self.assertEqual(
                int(rows["gaap_total_revenue"][field]),
                sum(int(rows[metric][field]) for metric in components),
            )


if __name__ == "__main__":
    unittest.main()
