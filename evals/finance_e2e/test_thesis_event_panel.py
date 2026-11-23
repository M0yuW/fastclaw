"""Offline checks for the frozen SEC event-to-thesis case inputs."""

import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from run_thesis_event_panel import prompt_for, validate_suite
from test_thesis_event_integration import locked_episode


class ThesisEventPanelTest(unittest.TestCase):
    def test_original_suite_is_source_locked_and_does_not_leak_decisions(self):
        suite = json.loads((HERE / "thesis_event_panel_v1.json").read_text())
        validate_suite(suite)
        self.assertEqual(4, len(suite["cases"]))
        for case in suite["cases"]:
            prompt = prompt_for(case, "th_test", "fa_test").lower()
            self.assertNotIn("conviction 3", prompt)
            self.assertNotIn("choose maintain", prompt)
            self.assertNotIn("oracle", prompt)

    def test_expected_arithmetic_uses_frozen_fact_values(self):
        cases = json.loads((HERE / "thesis_event_panel_v1.json").read_text())["cases"]
        cases += json.loads((HERE / "thesis_event_same_quarter_addendum_v1.json").read_text())["cases"]
        for case in cases:
            baseline, _ = locked_episode(case["baseline_episode"])
            event, _ = locked_episode(case["event_episode"])
            b = {fact["metric"]: float(fact["value"]) for fact in baseline["facts"]
                 if fact["id"] in case["baseline_metrics"]}
            e = {fact["metric"]: float(fact["value"]) for fact in event["facts"]
                 if fact["id"] in case["event_metrics"]}
            calculations = case["oracle"]["calculations"]
            if "revenue_change_percent" in calculations:
                expected = calculations["revenue_change_percent"]
            elif "selected_observation_revenue_change_percent" in calculations:
                expected = calculations["selected_observation_revenue_change_percent"]
            else:
                expected = calculations["year_over_year_revenue_change_percent"]
            self.assertAlmostEqual((e["quarterly_revenue"] / b["quarterly_revenue"] - 1) * 100,
                                   expected, delta=0.02, msg=case["id"])
            if "gross_margin_change_pp" in calculations:
                self.assertAlmostEqual(e["gross_margin"] - b["gross_margin"],
                                       calculations["gross_margin_change_pp"], delta=0.01, msg=case["id"])
            else:
                self.assertEqual("controlled_evidence_omission", case["scenario"])
                self.assertNotIn("gross_margin", e)

    def test_missing_packet_field_is_present_in_source_locked_evidence(self):
        case = next(item for item in json.loads((HERE / "thesis_event_panel_v1.json").read_text())["cases"]
                    if item["id"] == "NVDA-packet-missing-margin")
        episode, _ = locked_episode(case["event_episode"])
        self.assertIn("NVDA-Q2-GM", {fact["id"] for fact in episode["facts"]})
        self.assertNotIn("NVDA-Q2-GM", case["event_metrics"])


if __name__ == "__main__":
    unittest.main()
