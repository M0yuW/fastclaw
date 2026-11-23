"""Local-only safety checks for the frozen Stage 2 runner."""

import unittest
import json
import tempfile
from pathlib import Path

from evals.finance_e2e import run_stage2_project_report as runner

uncertain_cost_observations = runner.uncertain_cost_observations


class CostStopTests(unittest.TestCase):
    def test_flags_failed_call_with_unknown_provider_charge(self):
        report = {"cases": [{"attempts": [{"modes": [{
            "observation_id": "obs-timeout",
            "error": "context deadline exceeded",
            "model_calls": [{"cost_uncertain": True, "priced": True}],
        }]}]}]}
        self.assertEqual(uncertain_cost_observations(report), ["obs-timeout"])

    def test_flags_failed_observation_without_telemetry(self):
        report = {"cases": [{"attempts": [{"modes": [{
            "observation_id": "obs-disconnected", "error": "connection lost",
        }]}]}]}
        self.assertEqual(uncertain_cost_observations(report), ["obs-disconnected"])

    def test_allows_fully_priced_success(self):
        report = {"cases": [{"attempts": [{"modes": [{
            "observation_id": "obs-ok", "model_calls": [{"priced": True}],
        }]}]}]}
        self.assertEqual(uncertain_cost_observations(report), [])

    def test_resume_requires_exact_acknowledgment_and_keeps_error_count(self):
        report = {"cases": [{"attempts": [{"modes": [{
            "observation_id": "obs-timeout", "error": "context deadline exceeded",
            "model_calls": [{"cost_uncertain": True, "estimated_cost_usd": 0.0}],
        }]}]}]}
        with tempfile.TemporaryDirectory() as directory:
            original = runner.OUTPUT_DIR
            runner.OUTPUT_DIR = Path(directory)
            try:
                (runner.OUTPUT_DIR / "case-confirmatory.json").write_text(json.dumps(report))
                with self.assertRaisesRegex(ValueError, "unmetered provider cost"):
                    runner.completed_cost()
                self.assertEqual(runner.completed_cost({"obs-timeout"}), (0.0, 1, 1))
                with self.assertRaisesRegex(ValueError, "acknowledged uncertain observations do not match"):
                    runner.completed_cost({"obs-timeout", "unrelated"})
            finally:
                runner.OUTPUT_DIR = original


if __name__ == "__main__":
    unittest.main()
