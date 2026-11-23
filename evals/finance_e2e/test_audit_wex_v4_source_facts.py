import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import audit_wex_v4_source_facts as auditor  # noqa: E402


class WEXSourceAuditTests(unittest.TestCase):
    def packet(self):
        return json.loads(auditor.PACKET.read_text())

    def test_frozen_sources_facts_guidance_and_rounding(self):
        result = auditor.audit()
        self.assertEqual(result["selected_facts"], 40)
        self.assertEqual(result["displayed_gaap_residuals_usd_million"][
            "event"]["operating_to_pretax"], "-0.1")
        self.assertEqual(result["model_observations"], 0)

    def test_wrong_current_quarter_fact_rejected(self):
        packet = self.packet()
        packet["event"]["facts"]["total_revenues"] = "665.5"
        with self.assertRaisesRegex(ValueError, "selected source value differs"):
            auditor.audit(packet)

    def test_wrong_guidance_rejected(self):
        packet = self.packet()
        packet["event"]["guidance"][
            "full_year_revenue_usd_billion_range"][0] = "2.61"
        with self.assertRaisesRegex(ValueError, "forward-looking guidance differs"):
            auditor.audit(packet)

    def test_wrong_source_hash_rejected(self):
        packet = self.packet()
        packet["baseline"]["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source identity differs"):
            auditor.audit(packet)


if __name__ == "__main__":
    unittest.main()
