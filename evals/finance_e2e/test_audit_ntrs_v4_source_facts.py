import json
import unittest

import audit_ntrs_v4_source_facts as subject


class NtrsSourceAuditTests(unittest.TestCase):
    def packet(self):
        return json.loads(subject.PACKET.read_text())

    def test_source_values_comparators_and_signed_bridge(self):
        result = subject.audit()
        self.assertEqual(result["selected_facts"], 34)
        self.assertEqual(result["q2_cross_filing_comparators"], 17)
        self.assertEqual(result["signed_provision_delta_usd_million"], "-33.5")

    def test_changed_event_provision_rejected(self):
        packet = self.packet()
        packet["event"]["facts"]["gaap_provision_for_credit_losses_signed"] = "17.0"
        with self.assertRaisesRegex(ValueError, "source value/comparator"):
            subject.audit(packet)

    def test_changed_fte_value_rejected(self):
        packet = self.packet()
        packet["baseline"]["facts"]["non_gaap_fte_total_revenue"] = "2002.5"
        with self.assertRaisesRegex(ValueError, "source value/comparator"):
            subject.audit(packet)

    def test_changed_client_asset_unit_value_rejected(self):
        packet = self.packet()
        packet["event"]["facts"][
            "reported_assets_under_management_usd_billion"] = "1772.8"
        with self.assertRaisesRegex(ValueError, "source value/comparator"):
            subject.audit(packet)


if __name__ == "__main__":
    unittest.main()
