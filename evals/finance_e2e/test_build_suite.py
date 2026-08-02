import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from evals.finance_e2e.build_suite import (
    DEFAULT_EVIDENCE,
    DEFAULT_SOURCES,
    build_outputs,
    verify_evidence,
)


class FinanceEvidenceTest(unittest.TestCase):
    def test_verified_evidence_builds_twelve_runtime_cases(self) -> None:
        evidence = verify_evidence(DEFAULT_EVIDENCE, DEFAULT_SOURCES)
        suite, agent_pack = build_outputs(evidence, DEFAULT_SOURCES)

        self.assertEqual(12, len(suite["cases"]))
        self.assertEqual(
            {"NVDA", "AMD", "INTC", "NKE"},
            {tag.upper() for case in suite["cases"] for tag in case["tags"] if tag in {"nvda", "amd", "intc", "nke"}},
        )
        self.assertTrue(all(case["execution_mode"] == "runtime" for case in suite["cases"]))
        self.assertEqual(
            {"finance-source", "finance-methodology", "finance-governance"},
            set(agent_pack["agents"]),
        )
        self.assertTrue(all(len(cases) == 12 for cases in agent_pack["agents"].values()))

    def test_rejects_a_manually_changed_derived_value(self) -> None:
        payload = json.loads(DEFAULT_EVIDENCE.read_text(encoding="utf-8"))
        changed = deepcopy(payload)
        changed["episodes"][1]["comparisons"][0]["expected"] = "99.9"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evidence.json"
            path.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "derived value mismatch"):
                verify_evidence(path, DEFAULT_SOURCES)

    def test_rejects_any_trade_action(self) -> None:
        payload = json.loads(DEFAULT_EVIDENCE.read_text(encoding="utf-8"))
        payload["episodes"][0]["research_state"]["trade_action"] = "buy"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evidence.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "cannot authorize a trade"):
                verify_evidence(path, DEFAULT_SOURCES)

    def test_rejects_a_manually_changed_within_period_ratio(self) -> None:
        payload = json.loads(DEFAULT_EVIDENCE.read_text(encoding="utf-8"))
        payload["episodes"][0]["calculations"][0]["expected"] = "99.9"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evidence.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "derived value mismatch"):
                verify_evidence(path, DEFAULT_SOURCES)

    def test_rejects_an_unknown_governance_evidence_basis(self) -> None:
        payload = json.loads(DEFAULT_EVIDENCE.read_text(encoding="utf-8"))
        payload["episodes"][0]["research_state"]["basis_evidence_ids"] = ["UNKNOWN-EVIDENCE-ID"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evidence.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unknown research-state evidence basis"):
                verify_evidence(path, DEFAULT_SOURCES)


if __name__ == "__main__":
    unittest.main()
