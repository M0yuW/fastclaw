import json
import unittest

import audit_hban_v4_source_facts as subject


class HbanSourceAuditTests(unittest.TestCase):
    def packet(self):
        return json.loads(subject.PACKET.read_text())

    def test_frozen_source_rows_and_comparators(self):
        result = subject.audit()
        self.assertEqual(result["selected_facts"], 32)
        self.assertEqual(result["q2_cross_filing_comparators"], 16)
        self.assertEqual(result["q3_adjusted_noninterest_income_delta_usd_million"], "133")

    def test_changed_event_value_rejected(self):
        packet = self.packet()
        packet["event"]["facts"]["gaap_noninterest_income"] = "629"
        with self.assertRaisesRegex(ValueError, "source value/comparator"):
            subject.audit(packet)

    def test_changed_q2_value_rejected_by_cross_filing(self):
        packet = self.packet()
        packet["baseline"]["facts"]["gaap_net_interest_income"] = "1468"
        with self.assertRaisesRegex(ValueError, "source value/comparator"):
            subject.audit(packet)

    def test_changed_notable_gain_rejected(self):
        packet = self.packet()
        packet["event"]["notable_item"][
            "gaap_noninterest_income_gain_on_sale_usd_million"] = "25"
        with self.assertRaisesRegex(ValueError, "notable-item"):
            subject.audit(packet)


if __name__ == "__main__":
    unittest.main()
