import json
import tempfile
import unittest
from pathlib import Path

import prepare_postcorrection_judgment_v2 as subject


class MaskedJudgmentPreparationTests(unittest.TestCase):
    def test_packet_keeps_answer_and_state_but_hides_runner_outcome(self):
        result = {
            "observation_id": "test-case-r3", "workflow": "sec_event_to_thesis_review",
            "status": "needs_review", "error": "test-only failure",
            "estimated_cost_usd": 0.01,
            "turns": [{"prompt": "Review the alert", "response": {
                "choices": [{"message": {"content": "A bounded conclusion"}}],
                "fastclaw": {"trace": [{"type": "tool_call", "id": "x", "name": "thesis_get"}]}}}],
            "state": {"theses": [{"reviews": [{"decision": "needs_review",
                                               "created_at": "2099-01-01T00:00:00Z"}]}],
                      "alerts": [{"status": "acknowledged",
                                  "created_in_session_id": "reveals-run-order"}]},
        }
        packet = subject.packet_for_judge(result, {
            "symbol": "TEST", "precommitted_interpretation_checks": ["private oracle"]})
        self.assertEqual("A bounded conclusion", packet["final_answer"])
        self.assertEqual("Review the alert", packet["model_prompt"])
        self.assertEqual("needs_review", packet["persisted_theses_and_reviews"][0]
                         ["reviews"][0]["decision"])
        self.assertEqual(1, len(packet["tool_evidence"]))
        text = json.dumps(packet)
        self.assertNotIn("private oracle", text)
        self.assertNotIn("test-only failure", text)
        self.assertNotIn("estimated_cost_usd", text)
        self.assertNotIn("test-case-r3", text)
        self.assertNotIn("2099-01-01T00:00:00Z", text)
        self.assertNotIn("reveals-run-order", text)

    def test_transform_is_non_destructive_and_refuses_overwrite(self):
        symbol = "BAC"
        packet = json.loads(subject.source_batch.READY[symbol][1].read_text())
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result_dir = root / "results" / "test-r1"
            result_dir.mkdir(parents=True)
            raw = result_dir / "result.json"
            raw.write_text(json.dumps({
                "observation_id": "BAC-test-r1", "case_id": packet["case_id"],
                "workflow": "sec_event_to_thesis_review", "status": "mechanical_pass",
                "turns": [], "state": {},
            }))
            results_root = root / "results"
            (results_root / "manifest.json").write_text("{}\n")
            (results_root / "RESULT-SHA256.txt").write_text(
                f"{subject.sha256(results_root / 'manifest.json')}  manifest.json\n"
                f"{subject.sha256(raw)}  test-r1/result.json\n")
            original = raw.read_bytes()
            output = root / "masked"
            summary = subject.prepare(results_root, output)
            self.assertEqual(1, summary["packets"])
            self.assertEqual(original, raw.read_bytes())
            self.assertEqual(1, len(list((output / "masked_packets").glob("*.json"))))
            self.assertEqual(1, len(list((output / "scores").glob("*.json"))))
            with self.assertRaises(ValueError):
                subject.prepare(results_root, output)


if __name__ == "__main__":
    unittest.main()
