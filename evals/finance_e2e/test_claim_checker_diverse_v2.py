"""Read-only checker preflight and masking tests; no model calls."""

import json
import tempfile
import unittest
from pathlib import Path

import preflight_claim_checker_diverse_v2 as preflight
import run_claim_checker_diverse_flash_v2 as runner


class DiverseCheckerTests(unittest.TestCase):
    def test_retained_hashes_and_first_pass_labels(self):
        result = preflight.verify()
        self.assertEqual(result["cases"], 10)
        self.assertEqual(result["material_issue_oracle"], 5)
        self.assertEqual(result["no_material_issue_oracle"], 5)
        self.assertEqual(result["external_calls"], 0)

    def test_prompt_masks_experiment_identifiers_and_not_oracle(self):
        items = json.loads(preflight.CORPUS.read_text(encoding="utf-8"))["cases"]
        for item in items:
            with self.subTest(item=item["blind_id"]):
                archived = json.loads((preflight.RESULTS / item["result_dir"] / "result.json")
                                      .read_text(encoding="utf-8"))
                text = runner.scrub_identifiers(preflight.final_text(archived), archived, item)
                message = runner.prompt(item["blind_id"], item["context"], text)
                self.assertNotIn(item["result_dir"], message)
                self.assertNotIn(Path(item["result_dir"]).name, message)
                if archived.get("case_id"):
                    self.assertNotIn(archived["case_id"], message)
                self.assertIn(item["context"], message)
                self.assertNotIn('"oracle":', message)

    def test_relative_output_hashes_after_gateway_log_directory_exists(self):
        with tempfile.TemporaryDirectory(dir=runner.ROOT) as temporary:
            output_dir = Path(temporary)
            (output_dir / "manifest.json").write_text("{}\n")
            observation = output_dir / "S"
            observation.mkdir()
            (observation / "gateway.log").write_text("gateway started\n")
            observation.mkdir(exist_ok=True)
            (observation / "result.json").write_text("{}\n")
            pilot = type("FakePilot", (), {
                "turns": [{"response": {"choices": [{"message": {"content": "test"}}]}}],
                "cost": 0.001,
            })()
            runner.save_turn_checkpoint(observation, pilot)
            runner.write_hashes(Path(output_dir.relative_to(runner.ROOT)))
            lines = (output_dir / "RESULT-SHA256.txt").read_text().splitlines()
            self.assertEqual(len(lines), 4)
            self.assertTrue(lines[1].endswith("/S/result.json"))
            self.assertTrue(lines[2].endswith("/S/turn_checkpoint.json"))
            checkpoint = json.loads((observation / "turn_checkpoint.json").read_text())
            self.assertEqual(checkpoint["estimated_cost_usd"], 0.001)
            self.assertEqual(checkpoint["turns"][0]["response"]["choices"][0]["message"]["content"], "test")


if __name__ == "__main__":
    unittest.main()
