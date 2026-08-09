from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

import yaml

from evals.finance_e2e.human_grader_validation import analyze, prepare_r5


class HumanGraderValidationTest(unittest.TestCase):
    def fixtures(self, root: Path) -> tuple[Path, Path]:
        suite = {
            "cases": [
                {
                    "id": "case-a",
                    "agents": [{"id": "source", "role": "source", "response": "E-1 fact"}],
                    "milestones": [{"id": "m-1", "values": ["E-1", "fact"]}],
                    "forbidden_output_values": ["unsupported claim"],
                }
            ]
        }
        report = {
            "cases": [
                {
                    "id": "case-a",
                    "attempts": [
                        {
                            "output": "E-1 fact; no unsupported claim is made.",
                            "graders": [{"type": "ma_milestone", "passed": True}],
                            "multi_agent": {"grounding_assertions": 1, "grounding_violations": 0},
                        }
                    ],
                }
            ]
        }
        suite_path = root / "suite.yaml"
        report_path = root / "report.json"
        suite_path.write_text(yaml.safe_dump(suite), encoding="utf-8")
        report_path.write_text(json.dumps(report), encoding="utf-8")
        return report_path, suite_path

    def fill(self, path: Path, labels: dict[str, str]) -> None:
        with path.open(encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["item_id", "item_type", "label", "notes"])
            writer.writeheader()
            for row in rows:
                row["label"] = labels[row["item_type"]]
                writer.writerow(row)

    def test_prepare_and_analyze(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report, suite = self.fixtures(root)
            output = root / "validation"
            counts = prepare_r5(report, suite, output)
            self.assertEqual({"milestone": 1, "grounding": 1}, counts)
            tasks = [json.loads(line) for line in (output / "tasks.jsonl").read_text().splitlines()]
            self.assertEqual(2, len(tasks))
            self.assertNotIn("machine_label", tasks[0])
            labels = {"milestone": "satisfied", "grounding": "no_violation"}
            self.fill(output / "reviewer-a.csv", labels)
            self.fill(output / "reviewer-b.csv", labels)
            result, disagreements = analyze(
                output / "tasks.jsonl",
                output / "machine-labels.json",
                output / "reviewer-a.csv",
                output / "reviewer-b.csv",
            )
            self.assertEqual(1.0, result["by_type"]["milestone"]["raw_agreement"])
            self.assertEqual([], disagreements)


if __name__ == "__main__":
    unittest.main()
