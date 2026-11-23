import json
import unittest

import build_postcorrection_v5_hban_development_fixture as subject


class HBANDevelopmentCorrectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = subject.corrected_hban_fixture()

    def test_disclosed_notable_item_reaches_prompt_and_alert(self):
        fixture = self.fixture
        self.assertIn("gain on sale", fixture["numeric_context"])
        self.assertIn("adjusted sequential increase 133 USD_million",
                      fixture["numeric_context"])
        self.assertIn("gain on sale", fixture["event"]["summary"])
        self.assertEqual("24", fixture["event"]["observed_metrics"][
            "gaap_noninterest_income_gain_on_sale"]["value"])
        self.assertEqual("604", fixture["event"]["observed_metrics"][
            "non_gaap_adjusted_noninterest_income"]["value"])
        self.assertIn("non_gaap_adjusted_noninterest_income",
                      fixture["seed_thesis"]["required_event_metrics"])
        self.assertNotIn("decision", fixture["event"])
        self.assertIn("not_confirmatory", fixture["status"])

    def test_tampered_notable_bridge_is_rejected(self):
        packet = json.loads(subject.v4.FIRST_PACKETS["HBAN"].read_text())
        packet["event"]["notable_item"][
            "non_gaap_adjusted_noninterest_income_usd_million"] = "605"
        with self.assertRaisesRegex(ValueError, "does not reconcile"):
            subject.corrected_hban_fixture(packet)


if __name__ == "__main__":
    unittest.main()
