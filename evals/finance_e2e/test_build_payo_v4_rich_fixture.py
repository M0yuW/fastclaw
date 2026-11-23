import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import build_payo_v4_rich_fixture as fixture_builder  # noqa: E402


class PAYORichFixtureTests(unittest.TestCase):
    def test_typed_evidence_and_private_checks(self):
        fixture = fixture_builder.fixture()
        packet = json.loads(fixture_builder.source_audit.PACKET.read_text())
        context = fixture["numeric_context"]
        self.assertEqual(len(fixture["event"]["observed_metrics"]), 15)
        for phrase in (
            "Source-defined GAAP change bridge",
            "net-income change -5357",
            "All three residuals are zero",
            "forward-looking, not realized",
            "source claims, not independently established causes",
            "not interchangeable with GAAP net income",
        ):
            self.assertIn(phrase, context)
        serialized = json.dumps(fixture, ensure_ascii=False)
        for private_check in packet["precommitted_interpretation_checks"]:
            self.assertNotIn(private_check, serialized)
        self.assertNotIn("precommitted_interpretation_checks", serialized)

    def test_prompt_does_not_prescribe_conclusion(self):
        fixture = fixture_builder.fixture()
        prompt = fixture_builder.review_prompt(fixture, "thesis-test", "alert-test")
        self.assertIn("Independently form", prompt)
        self.assertIn("thesis-test", prompt)
        self.assertIn("alert-test", prompt)
        self.assertNotIn("keep conviction 3", prompt)
        self.assertNotIn("must choose needs_review", prompt)


if __name__ == "__main__":
    unittest.main()
