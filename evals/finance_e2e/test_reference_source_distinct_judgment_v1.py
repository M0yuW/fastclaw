"""Guard the new 30-case review mapping and cluster denominator."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from aggregate_postcorrection_judgments_v2 import one_sided_exact_lower
from aggregate_reference_source_distinct_judgments_v1 import aggregate, cluster_gate
from prepare_reference_source_distinct_judgment_v1 import prepare
from run_thesis_event_panel import sha256


class SourceDistinctJudgmentTests(unittest.TestCase):
    def test_cluster_requires_all_five_and_candidate_contract(self):
        high = {"qualitative_label": "high", "mechanical_pass": True,
                "contract_pass": True, "critical_error_count": 0}
        adequate = {**high, "qualitative_label": "adequate"}
        self.assertTrue(cluster_gate([high] * 4 + [adequate])["gate_pass"])
        self.assertFalse(cluster_gate([high] * 4)["gate_pass"])
        self.assertFalse(cluster_gate([high] * 4 + [{**adequate, "contract_pass": False}])
                         ["gate_pass"])
        self.assertFalse(cluster_gate([high] * 4 + [{**adequate, "critical_error_count": 1}])
                         ["gate_pass"])

    def test_declared_thirty_cluster_thresholds(self):
        self.assertLess(one_sided_exact_lower(27, 30, 0.05), 0.8)
        self.assertGreater(one_sided_exact_lower(28, 30, 0.05), 0.8)
        self.assertLess(one_sided_exact_lower(28, 30, 0.05 / 3), 0.8)
        self.assertGreater(one_sided_exact_lower(29, 30, 0.05 / 3), 0.8)

    def test_prepare_masks_status_and_keeps_original_result(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            results = root / "results"
            observation = results / "RS-ACIW-CY2025Q2Q3-r1"
            observation.mkdir(parents=True)
            result = {
                "observation_id": observation.name,
                "case_id": "RS-ACIW-CY2025Q2Q3", "repetition": 1,
                "workflow": "source_distinct_sec_event_to_research_view",
                "status": "held", "mechanical_pass": False, "error": "synthetic",
                "estimated_cost_usd": 0, "turns": [], "state": None,
            }
            raw = observation / "result.json"
            raw.write_text(json.dumps(result) + "\n")
            (results / "manifest.json").write_text("{}\n")
            (results / "RESULT-SHA256.txt").write_text("".join(
                f"{sha256(path)}  {path.relative_to(results)}\n"
                for path in (results / "manifest.json", raw)))
            original_hash = sha256(raw)
            output = root / "judgment"
            status = prepare(results, output)
            self.assertEqual(status["packets"], 1)
            self.assertEqual(sha256(raw), original_hash)
            packet = json.loads(next((output / "masked_packets").glob("*.json")).read_text())
            self.assertNotIn("mechanical_status", packet)
            self.assertNotIn("estimated_cost_usd", packet)
            self.assertEqual(packet["source_packet"]["symbol"], "ACIW")
            summary = aggregate(results, output)
            self.assertEqual(summary["status"], "incomplete_observation_panel")
            self.assertEqual(summary["observations"], 1)
            self.assertEqual(summary["case_gate_passes"], 0)
            self.assertIsNone(summary["event_only_one_sided_95_lower_bound"])


if __name__ == "__main__":
    unittest.main()
