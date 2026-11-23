"""Free, deterministic tests for the optional workflow publication gate."""

import json
import unittest

import fintech_inference_publication_gate_v2 as gate
from verify_fintech_inference_answer_v1 import CORPUS


CASES = {case["case_id"]: case for case in json.loads(CORPUS.read_text())["cases"]}


def turn(answer, tools=None):
    return {"response": {"choices": [{"message": {"content": answer}}]},
            "tool_calls": tools or []}


class FakePilot:
    def __init__(self, answers, cost=0.001, tools=None):
        self.answers = answers
        self.tools = tools or [[] for _ in answers]
        self.turns = []
        self.cost = cost
        self.spent_before = 0.0

    def turn(self, prompt):
        result = turn(self.answers[len(self.turns)], self.tools[len(self.turns)])
        self.turns.append({"prompt": prompt, **result})
        return result


class PublicationGateTests(unittest.TestCase):
    def test_required_checks_and_source_derived_values(self):
        afrm = CASES["AFRM-FISCAL-COST"]
        wrong = gate.predeclared_check(afrm, "Revenue **+39,304**.\n[CHECK] AFRM_QOQ_REVENUE_DELTA=39304")
        self.assertFalse(wrong["accepted_for_claim_review"])
        self.assertIn("AFRM_REVENUE_DELTA", {item["code"] for item in wrong["failures"]})
        correct = gate.predeclared_check(afrm, "Revenue **+39,294**.\n[CHECK] AFRM_QOQ_REVENUE_DELTA=39294")
        self.assertTrue(correct["accepted_for_claim_review"])
        self.assertIsNone(correct["quality_pass"])
        self.assertFalse(gate.predeclared_check(afrm, "Revenue grew.")["accepted_for_claim_review"])

        sofi = CASES["SOFI-REVENUE-BRIDGE"]
        bridge = gate.predeclared_check(sofi,
            "GAAP and adjusted differ.\n[CHECK] SOFI_Q3_GAAP_TO_ADJUSTED_REVENUE=697121-4362+9-3323=689445")
        self.assertTrue(bridge["accepted_for_claim_review"])
        self.assertFalse(gate.predeclared_check(sofi,
            "[CHECK] SOFI_Q3_GAAP_TO_ADJUSTED_REVENUE=697121-3323+9-4362=689445")
            ["accepted_for_claim_review"])

        upst = CASES["UPST-MIXED-BASIS"]
        self.assertTrue(gate.predeclared_check(upst,
            "YoY adjusted net loss widened.\n[CHECK] UPST_ADJUSTED_NET_LOSS_YOY=WIDER")
            ["accepted_for_claim_review"])
        self.assertFalse(gate.predeclared_check(upst,
            "YoY adjusted net loss narrowed.\n[CHECK] UPST_ADJUSTED_NET_LOSS_YOY=WIDER")
            ["accepted_for_claim_review"])

    def test_one_repair_is_bounded_and_retains_both_candidates(self):
        pilot = FakePilot(["Revenue **+39,304**.\n[CHECK] AFRM_QOQ_REVENUE_DELTA=39304",
                           "Revenue **+39,294**.\n[CHECK] AFRM_QOQ_REVENUE_DELTA=39294"])
        result = gate.run_with_one_repair(pilot, CASES["AFRM-FISCAL-COST"],
                                          "review", 0.1, 0.01)
        self.assertEqual(len(pilot.turns), 2)
        self.assertEqual(result["publication_status"], "candidate_for_manual_claim_review")
        self.assertEqual(result["final_turn_index"], 1)
        self.assertEqual(result["attempts"][0]["check"]["failures"][0]["code"],
                         "AFRM_REVENUE_DELTA")
        self.assertFalse(gate.run_with_one_repair(
            FakePilot(["[CHECK] AFRM_QOQ_REVENUE_DELTA=1"]),
            CASES["AFRM-FISCAL-COST"], "review", 0.005, 0.01)["publication_status"]
            == "candidate_for_manual_claim_review")
        used_tool = FakePilot(["[CHECK] AFRM_QOQ_REVENUE_DELTA=1",
                               "[CHECK] AFRM_QOQ_REVENUE_DELTA=39294"],
                              tools=[[], ["finance-tools__thesis_record_review"]])
        held = gate.run_with_one_repair(used_tool, CASES["AFRM-FISCAL-COST"],
                                        "review", 0.1, 0.01)
        self.assertEqual(held["publication_status"], "held_checker")


if __name__ == "__main__":
    unittest.main()
