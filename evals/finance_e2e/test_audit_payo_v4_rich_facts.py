import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import audit_payo_v4_rich_facts as auditor  # noqa: E402


class PAYORichSourceAuditTests(unittest.TestCase):
    def packet(self):
        return json.loads(auditor.PACKET.read_text())

    def test_locked_sources_rows_guidance_and_bridges(self):
        result = auditor.audit()
        self.assertEqual(result["selected_facts"], 30)
        self.assertEqual(result["gaap_net_income_delta_usd_thousand"], "-5357")
        self.assertEqual(result["model_observations"], 0)

    def test_tampered_fact_rejected(self):
        packet = self.packet()
        packet["event"]["facts"][6]["value"] = 14124
        with self.assertRaisesRegex(ValueError, "selected source value differs"):
            auditor.audit(packet)

    def test_tampered_guidance_rejected(self):
        packet = self.packet()
        packet["event"]["guidance"]["revenue_usd_million_range"][0] = 1040
        with self.assertRaisesRegex(ValueError, "guidance differs"):
            auditor.audit(packet)

    def test_tampered_source_hash_rejected(self):
        packet = self.packet()
        packet["event"]["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source identity differs"):
            auditor.audit(packet)


if __name__ == "__main__":
    unittest.main()
