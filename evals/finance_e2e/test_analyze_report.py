import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from evals.finance_e2e.analyze_report import analyze, numbers, unauthorized_numbers


class FinanceReportAnalysisTest(unittest.TestCase):
    def test_finds_missing_ids_and_unauthorized_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            suite = root / "suite.json"
            suite.write_text("{}\n", encoding="utf-8")
            report = root / "report.json"
            report.write_text(
                json.dumps(
                    {
                        "source_sha256": hashlib.sha256(suite.read_bytes()).hexdigest(),
                        "metrics": {},
                        "cases": [
                            {
                                "id": "FSEC-TEST-01",
                                "attempts": [
                                    {
                                        "passed": False,
                                        "output": "SEC-TEST-01 reports 10; derived ratio is 12.5.",
                                        "trace": [
                                            {
                                                "type": "tool_result",
                                                "name": "spawn_subagent",
                                                "result": "SEC-TEST-01: FACT-TEST-01 is 10.",
                                            }
                                        ],
                                        "baselines": [],
                                        "graders": [],
                                    }
                                ],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            result = analyze(report, suite)
        case = result["cases"][0]
        self.assertEqual(["FACT-TEST-01"], case["missing_evidence_ids"])
        self.assertEqual(["12.5"], case["unauthorized_numeric_values"])

    def test_uses_only_the_delegated_evidence_field(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            suite = root / "suite.json"
            suite.write_text("{}\n", encoding="utf-8")
            report = root / "report.json"
            report.write_text(
                json.dumps(
                    {
                        "source_sha256": hashlib.sha256(suite.read_bytes()).hexdigest(),
                        "metrics": {},
                        "cases": [
                            {
                                "id": "FSEC-TEST-01",
                                "attempts": [
                                    {
                                        "passed": True,
                                        "output": "SEC-TEST-01 reports 10.",
                                        "trace": [
                                            {
                                                "type": "tool_result",
                                                "name": "spawn_subagent",
                                                "result": json.dumps(
                                                    {
                                                        "case_id": "FSEC-TEST-01",
                                                        "role": "finance-source",
                                                        "evidence": "SEC-TEST-01 reports 10.",
                                                    }
                                                ),
                                            }
                                        ],
                                        "baselines": [],
                                        "graders": [],
                                    }
                                ],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            result = analyze(report, suite)
        self.assertEqual(["SEC-TEST-01"], result["cases"][0]["expected_evidence_ids"])

    def test_numbers_ignore_identifier_suffixes_and_preserve_loss_semantics(self) -> None:
        self.assertEqual({"-6955"}, numbers("FY2023 operating loss of USD 6,955."))
        self.assertEqual({"-6955"}, numbers("FY2023 operating income was –6,955."))
        self.assertEqual({"5835"}, numbers("Q2 revenue was USD 5,835M."))
        self.assertEqual({"44.7"}, numbers("Q4FY24 gross margin was 44.7 percent."))
        self.assertEqual({"-10"}, numbers("NIKE Brand Digital reported a 10 percent decline."))
        self.assertEqual(
            {"-20.4"},
            numbers("A revenue increase did not offset the 20.4-point gross-margin decline."),
        )

    def test_unauthorized_numbers_use_suite_values_and_accounting_context(self) -> None:
        authorized = {"-6955", "2023", "18910", "22600", "26044"}
        output = (
            "Foundry revenue (2023) was 18,910 and operating income was (6,955). "
            "NVDA-Q1-DC (22,600) divided by NVDA-Q1-REV (26,044)."
        )
        self.assertEqual(set(), unauthorized_numbers(output, authorized))

    def test_numbers_ignore_unicode_hyphenated_structural_identifiers(self) -> None:
        output = (
            "SEC‑INTC‑01 SEC 8‑K EX‑99.1 accession 0000050863‑24‑000068 reports "
            "INTC‑2023‑FOUNDRY‑REV USD 18,910 million."
        )
        self.assertEqual({"18910"}, numbers(output))

    def test_numbers_ignore_lowercase_evidence_labels(self) -> None:
        self.assertEqual({"26044"}, numbers("evidence-2 reports USD 26,044 million."))

    def test_numbers_parse_financial_unit_suffixes(self) -> None:
        self.assertEqual({"-3.3", "110"}, numbers("Gross margin changed -3.3pp after increasing 110bps."))

    def test_numbers_parse_coordinated_declines(self) -> None:
        self.assertEqual(
            {"-1.1", "-3.3"},
            numbers("Gross margin declined first by 1.1 pp then by 3.3 pp."),
        )

    def test_numbers_ignore_ordered_list_markers(self) -> None:
        self.assertEqual({"10", "20"}, numbers("1. Revenue was 10.\n2) Gross margin was 20 percent."))


if __name__ == "__main__":
    unittest.main()
