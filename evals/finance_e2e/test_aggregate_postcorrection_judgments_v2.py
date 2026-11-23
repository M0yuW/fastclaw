import json
import tempfile
import unittest
from pathlib import Path

import aggregate_postcorrection_judgments_v2 as subject
import prepare_postcorrection_judgment_v2 as prepare


def review(scores=None, critical=None, coverage=None):
    return {
        "masked_id": "J-test", "reviewer": "Codex diagnostic",
        "coverage": coverage or {"final_answer": True, "persisted_review": True},
        "scores": scores or {name: 2 for name in subject.DIMENSIONS},
        "claim_adjudications": [{
            "location": "final_answer", "span": "revenue rose",
            "verdict": "supported", "evidence_refs": ["SEC:REV"],
        }],
        "critical_errors": critical or [], "assessable_implication": True,
    }


class PostcorrectionJudgmentAggregationTests(unittest.TestCase):
    def test_score_labels_and_critical_priority(self):
        self.assertEqual("high", subject.validate_review(review(), "J-test"))
        adequate = review(scores={"F": 2, "I": 1, "R": 2, "S": 2, "U": 2})
        self.assertEqual("adequate", subject.validate_review(adequate, "J-test"))
        problematic = review(scores={"F": 0, "I": 2, "R": 2, "S": 2, "U": 2})
        self.assertEqual("problematic", subject.validate_review(problematic, "J-test"))
        incomplete = review(scores={"F": None, "I": 2, "R": 2, "S": 2, "U": 2})
        incomplete["notes"] = "Final answer evidence is missing."
        self.assertEqual("not_assessable", subject.validate_review(incomplete, "J-test"))
        incomplete["critical_errors"] = [{"claim_index": 0, "code": "wrong_fact",
                                          "evidence_refs": ["SEC:REV"]}]
        self.assertEqual("problematic", subject.validate_review(incomplete, "J-test"))

    def test_invalid_review_cannot_be_silently_counted(self):
        item = review()
        item["claim_adjudications"] = []
        with self.assertRaises(ValueError):
            subject.validate_review(item, "J-test")
        item = review()
        item["claim_adjudications"][0]["evidence_refs"] = []
        with self.assertRaises(ValueError):
            subject.validate_review(item, "J-test")

    def test_five_session_gate_is_conjunctive(self):
        observations = [{"qualitative_label": "high", "mechanical_pass": True,
                         "critical_error_count": 0} for _ in range(4)]
        observations.append({"qualitative_label": "adequate", "mechanical_pass": True,
                             "critical_error_count": 0})
        self.assertTrue(subject.case_gate(observations)["gate_pass"])
        for changed in ({"mechanical_pass": False}, {"critical_error_count": 1},
                        {"qualitative_label": "problematic"}):
            altered = [dict(item) for item in observations]
            altered[-1].update(changed)
            self.assertFalse(subject.case_gate(altered)["gate_pass"])
        self.assertFalse(subject.case_gate(observations[:4])["gate_pass"])

    def test_predeclared_exact_lower_bound(self):
        self.assertAlmostEqual(subject.BONFERRONI_ALPHA ** (1 / 20),
                               subject.one_sided_exact_lower(20, 20), places=12)
        self.assertGreater(subject.one_sided_exact_lower(20, 20), 0.8)
        self.assertLess(subject.one_sided_exact_lower(19, 20), 0.8)

    def test_preparation_and_aggregation_join_without_rewriting_raw(self):
        packet = json.loads(prepare.source_batch.READY["BAC"][1].read_text())
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw_dir = root / "results" / "one"
            raw_dir.mkdir(parents=True)
            raw = raw_dir / "result.json"
            raw.write_text(json.dumps({
                "observation_id": "BAC-test-r1", "case_id": packet["case_id"],
                "workflow": "sec_event_to_thesis_review", "status": "mechanical_pass",
                "turns": [{"prompt": "Review", "response": {
                    "choices": [{"message": {"content": "revenue rose"}}]}}],
                "state": {"theses": [{"reviews": [{"rationale": "revenue rose"}]}],
                          "alerts": []},
            }))
            results_root = root / "results"
            (results_root / "manifest.json").write_text("{}\n")
            (results_root / "RESULT-SHA256.txt").write_text(
                f"{subject.sha256(results_root / 'manifest.json')}  manifest.json\n"
                f"{subject.sha256(raw)}  one/result.json\n")
            original = raw.read_bytes()
            judgment_dir = root / "judgment"
            prepare.prepare(results_root, judgment_dir)
            score_path = next((judgment_dir / "scores").glob("*.json"))
            item = review()
            item["masked_id"] = score_path.stem
            score_path.write_text(json.dumps(item))
            summary = subject.aggregate(results_root, judgment_dir)
            self.assertEqual("incomplete_observation_panel", summary["status"])
            self.assertEqual(1, summary["observations"])
            self.assertEqual(0, summary["case_gate_passes"])
            self.assertIsNone(summary["bonferroni_one_sided_95_lower_bound"])
            self.assertEqual(original, raw.read_bytes())
            score_path.unlink()
            missing = subject.aggregate(results_root, judgment_dir)
            self.assertEqual(0, missing["adjudicated_observations"])
            self.assertEqual(1, len(missing["unreviewed_masked_ids"]))
            self.assertFalse(missing["predeclared_all_20_gate_met"])


if __name__ == "__main__":
    unittest.main()
