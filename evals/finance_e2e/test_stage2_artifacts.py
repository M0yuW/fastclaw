from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from evals.finance_e2e.stage2_artifacts import analyze, create_manifest, write_json


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Stage2ArtifactsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.suite_path = self.root / "stage2a-suite.json"
        self.lock_path = self.root / "source-lock.json"
        self.protocol_path = self.root / "protocol.md"
        self.source_path = self.root / "finance_retrieval.go"
        self.agent_source_path = self.root / "tenant.go"
        self.executable_path = self.root / "fastclaw"
        self.report_path = self.root / "2026-08-09-stage2a-batch1-20260802-confirmatory.json"
        self.audit_summary_path = self.root / "audit-summary.json"
        for path in (self.lock_path, self.protocol_path, self.source_path, self.agent_source_path, self.executable_path):
            path.write_text(path.name, encoding="utf-8")
        lock_hash = sha256(self.lock_path)
        suite = {
            "study": "stage2-test",
            "status": "frozen",
            "randomization_seed": 20260802,
            "primary_modes": ["solo_staged", "team_shared_retrieval", "team_raw_context"],
            "cases": [{"id": "CASE"}],
            "source_lock_sha256": lock_hash,
            "prompt_version": "prompt-v1",
            "grader_version": "grader-v1",
            "pricing_date": "2026-08-01",
            "model_allocation": {
                "coordinator": "provider/pro",
                "solo_staged": "provider/pro",
                "retriever": "provider/flash",
                "specialists": "provider/flash",
                "capacity_matched_team": "provider/pro",
            },
            "execution_controls": {"thinking_mode": "off", "temperature": 0.1},
            "defaults": {"coordinator_agent_id": "coordinator", "solo_agent_id": "solo", "retriever_agent_id": "retriever", "analysts": [], "repetitions": 1},
        }
        write_json(self.suite_path, suite)
        report = {
            "study": "stage2-test",
            "status": "frozen",
            "randomization_seed": 20260802,
            "source_sha256": sha256(self.suite_path),
            "source_lock_sha256": lock_hash,
            "cases": [
                {
                    "id": "CASE",
                    "company": "CO",
                    "task_family": "point_in_time",
                    "cluster_id": "CO|point_in_time",
                    "corpus_load": "small",
                    "attempts": [
                        {
                            "attempt": 1,
                            "pair_id": "company=CO|task_family=point_in_time|corpus_load=small|repetition=1",
                            "modes": [self.mode(name, index) for index, name in enumerate(("solo_staged", "team_shared_retrieval", "team_raw_context"), 1)]
                            + [self.mode("oracle_evidence", 4)],
                        }
                    ],
                }
            ],
        }
        write_json(self.report_path, report)
        write_json(self.audit_summary_path, {"tasks": 98, "freeze_audit_passed": True})

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def mode(name: str, order: int) -> dict[str, object]:
        return {
            "mode": name,
            "observation_id": f"company=CO|task_family=point_in_time|corpus_load=small|repetition=1|mode={name}",
            "order_index": order,
            "passed": True,
            "latency_ms": 100 + order,
            "usage": {"total_tokens": 1000 + order},
            "model_calls": [{"agent_id": "coordinator", "model": "provider/pro", "estimated_cost_usd": 0.01}],
            "stages": {"final_evidence_recall": 1, "grounding_assertions": 10, "grounding_violations": 0},
        }

    def make_manifest(self, status: str = "confirmatory", name: str = "2026-08-09-stage2a-batch1-20260802-confirmatory.manifest.json") -> Path:
        manifest = create_manifest(
            self.suite_path,
            self.lock_path,
            self.protocol_path,
            self.source_path,
            self.agent_source_path,
            self.executable_path,
            self.report_path,
            status,
            self.audit_summary_path,
        )
        path = self.root / name
        write_json(path, manifest)
        return path

    def test_analyze_writes_primary_pair_and_error_denominators(self) -> None:
        manifest_path = self.make_manifest()
        output = self.root / "analysis"
        result = analyze([manifest_path], output, 100, allow_incomplete=True)
        self.assertEqual(3, result["primary_observations"])
        self.assertEqual(1, result["pair_blocks"])
        summary = (output / "mode-summary.csv").read_text(encoding="utf-8")
        self.assertIn("assigned_attempts,evaluated,errored,unavailable", summary)
        self.assertIn("assigned_attempt_system_success_rate", summary)
        self.assertIn("completed_output_conditional_task_success_rate", summary)
        self.assertNotIn("oracle_evidence", (output / "pair-table.csv").read_text(encoding="utf-8"))
        self.assertTrue((output / "cluster-bootstrap.json").is_file())

    def test_manifest_status_blocks_calibration(self) -> None:
        manifest_path = self.make_manifest(status="calibration")
        with self.assertRaisesRegex(ValueError, "not confirmatory"):
            analyze([manifest_path], self.root / "analysis", 10, allow_incomplete=True)

    def test_filename_blocks_pilot_and_superseded(self) -> None:
        for label in ("pilot", "superseded", "diagnostic", "calibration"):
            with self.subTest(label=label):
                manifest_path = self.make_manifest(name=f"stage2a-{label}.manifest.json")
                with self.assertRaisesRegex(ValueError, "filename"):
                    analyze([manifest_path], self.root / f"analysis-{label}", 10, allow_incomplete=True)

    def test_confirmatory_manifest_requires_frozen_suite(self) -> None:
        suite = json.loads(self.suite_path.read_text(encoding="utf-8"))
        suite["status"] = "draft"
        write_json(self.suite_path, suite)
        with self.assertRaisesRegex(ValueError, "frozen suite"):
            self.make_manifest()

    def test_confirmatory_manifest_rejects_freeze_blockers(self) -> None:
        suite = json.loads(self.suite_path.read_text(encoding="utf-8"))
        suite["formal_freeze_blockers"] = ["accepted_at audit incomplete"]
        write_json(self.suite_path, suite)
        with self.assertRaisesRegex(ValueError, "freeze blockers"):
            self.make_manifest()

    def test_pair_key_cannot_contain_mode(self) -> None:
        report = json.loads(self.report_path.read_text(encoding="utf-8"))
        report["cases"][0]["attempts"][0]["pair_id"] += "|mode=solo_staged"
        for mode in report["cases"][0]["attempts"][0]["modes"]:
            mode["observation_id"] = report["cases"][0]["attempts"][0]["pair_id"] + "|mode=" + str(mode["mode"])
        write_json(self.report_path, report)
        manifest_path = self.make_manifest()
        with self.assertRaisesRegex(ValueError, "exclude mode"):
            analyze([manifest_path], self.root / "analysis", 10, allow_incomplete=True)

    def test_pre_run_manifest_has_no_report_or_secret_configuration(self) -> None:
        manifest = create_manifest(
            self.suite_path,
            self.lock_path,
            self.protocol_path,
            self.source_path,
            self.agent_source_path,
            self.executable_path,
            None,
            "confirmatory",
            self.audit_summary_path,
        )
        self.assertNotIn("report", manifest["files"])
        self.assertEqual("confirmatory", manifest["artifact_status"])

    def test_confirmatory_manifest_requires_completed_human_audit(self) -> None:
        with self.assertRaisesRegex(ValueError, "freeze-audit summary"):
            create_manifest(
                self.suite_path, self.lock_path, self.protocol_path, self.source_path,
                self.agent_source_path, self.executable_path, self.report_path,
                "confirmatory", None,
            )
        write_json(self.audit_summary_path, {"tasks": 98, "freeze_audit_passed": False})
        with self.assertRaisesRegex(ValueError, "all 98"):
            self.make_manifest()


if __name__ == "__main__":
    unittest.main()
