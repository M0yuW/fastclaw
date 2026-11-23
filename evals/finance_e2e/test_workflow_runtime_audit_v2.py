import json
import unittest
from pathlib import Path

from evals.finance_e2e.workflow_runtime_audit_v2 import audit_turns


HERE = Path(__file__).parent
PANEL = HERE / "results" / "2026-10-18-finance-workflow-16-flash-v1"


class WorkflowRuntimeAuditV2Test(unittest.TestCase):
    def test_frozen_c3_detects_trace_error_and_uncertain_cost(self):
        attempt = json.loads((PANEL / "C3" / "result.json").read_text())
        audit = audit_turns(attempt["turns"])
        self.assertFalse(audit["clean_completion"])
        self.assertTrue(audit["tool_calls_paired"])
        self.assertEqual([3], audit["cost_uncertain_sequences"])
        self.assertIn("invalid finance-tools__thesis_record_review", audit["trace_errors"][0])

    def test_frozen_e1_is_clean(self):
        attempt = json.loads((PANEL / "E1" / "result.json").read_text())
        self.assertTrue(audit_turns(attempt["turns"])["clean_completion"])

    def test_typed_terminal_and_legacy_fallback_both_fail_closed(self):
        base = {"response": {"fastclaw": {
            "trace": [{"type": "tool_call", "id": "one"},
                      {"type": "tool_result", "id": "one"}],
            "model_calls": [{"priced": True}]},
            "choices": [{"message": {"content": "incomplete"}}]}}
        typed = json.loads(json.dumps(base))
        typed["response"]["fastclaw"]["trace"].append(
            {"type": "terminal", "code": "malformed_tool_arguments_exhausted"})
        self.assertEqual(["malformed_tool_arguments_exhausted"],
                         audit_turns([typed])["terminal_codes"])
        self.assertFalse(audit_turns([typed])["clean_completion"])

        legacy = json.loads(json.dumps(base))
        legacy["response"]["choices"][0]["message"]["content"] = (
            "I've reached the maximum number of tool iterations.")
        self.assertEqual(["legacy_tool_iteration_budget_exhausted"],
                         audit_turns([legacy])["terminal_codes"])
        self.assertFalse(audit_turns([legacy])["clean_completion"])

    def test_no_tool_abstention_can_still_be_clean(self):
        turn = {"response": {"fastclaw": {
            "trace": [], "model_calls": [{"priced": True}]},
            "choices": [{"message": {"content": "Insufficient input; no tool was called."}}]}}
        self.assertTrue(audit_turns([turn])["clean_completion"])


if __name__ == "__main__":
    unittest.main()
