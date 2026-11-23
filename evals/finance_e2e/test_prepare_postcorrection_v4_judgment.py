import json
import tempfile
import unittest
from pathlib import Path

import prepare_postcorrection_v4_judgment as subject
from run_thesis_event_panel import sha256


class V4JudgmentPreparationTests(unittest.TestCase):
    def frozen_one_result(self, root: Path) -> Path:
        results = root / "raw"
        results.mkdir()
        (results / "manifest.json").write_text("{}\n")
        case = "LPLA-2025-Q3-ACQUISITION-GAAP-ADJUSTED-DIVERGENCE"
        item_dir = results / f"{case}-r1"
        item_dir.mkdir()
        result = {
            "observation_id": item_dir.name, "case_id": case,
            "workflow": "sec_event_to_thesis_review", "status": "mechanical_pass",
            "error": None, "estimated_cost_usd": 0.01,
            "state": {"theses": [], "alerts": []},
            "turns": [{"prompt": "frozen prompt", "response": {
                "choices": [{"message": {"content": "research conclusion"}}],
                "fastclaw": {"trace": []}}}],
        }
        (item_dir / "result.json").write_text(json.dumps(result) + "\n")
        files = [results / "manifest.json", item_dir / "result.json"]
        (results / "RESULT-SHA256.txt").write_text("".join(
            f"{sha256(path)}  {path.relative_to(results)}\n" for path in files))
        return results

    def test_blinds_outcome_but_preserves_answer_and_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            results = self.frozen_one_result(root)
            output = root / "judgment"
            summary = subject.prepare(results, output)
            self.assertEqual(summary["packets"], 1)
            packet = json.loads(next((output / "masked_packets").glob("*.json")).read_text())
            self.assertEqual(packet["final_answer"], "research conclusion")
            self.assertEqual(packet["source_packet"]["case_id"],
                             "LPLA-2025-Q3-ACQUISITION-GAAP-ADJUSTED-DIVERGENCE")
            self.assertNotIn("mechanical_pass", json.dumps(packet))
            blank = json.loads(next((output / "scores").glob("*.json")).read_text())
            self.assertEqual(blank["scores"], {name: None for name in subject.DIMENSIONS})

    def test_tampered_raw_result_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            results = self.frozen_one_result(root)
            raw = next(results.glob("*/result.json"))
            raw.write_text(raw.read_text() + " ")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                subject.prepare(results, root / "judgment")


if __name__ == "__main__":
    unittest.main()
