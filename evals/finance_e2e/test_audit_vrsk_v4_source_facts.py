import json
import unittest

import audit_vrsk_v4_source_facts as subject


class VrskSourceAuditTests(unittest.TestCase):
    def packet(self):
        return json.loads(subject.PACKET.read_text())

    def test_current_quarter_rows_bridges_and_guidance(self):
        result = subject.audit()
        self.assertEqual(result["selected_facts"], 22)
        self.assertEqual(result["guidance_ranges_checked"], 6)
        self.assertEqual(result["gaap_net_income_sequential_delta_usd_million"], "-27.8")

    def test_changed_gaap_cell_rejected(self):
        packet = self.packet()
        packet["event"]["facts"]["gaap_revenues"] = "768.4"
        with self.assertRaisesRegex(ValueError, "selected source value"):
            subject.audit(packet)

    def test_changed_non_gaap_cell_rejected(self):
        packet = self.packet()
        packet["baseline"]["facts"]["non_gaap_adjusted_ebitda"] = "444.7"
        with self.assertRaisesRegex(ValueError, "selected source value"):
            subject.audit(packet)

    def test_changed_guidance_chronology_rejected(self):
        packet = self.packet()
        packet["event"]["guidance"][
            "updated_full_year_revenue_usd_million_range"] = ["3090", "3130"]
        with self.assertRaisesRegex(ValueError, "guidance chronology"):
            subject.audit(packet)


if __name__ == "__main__":
    unittest.main()
