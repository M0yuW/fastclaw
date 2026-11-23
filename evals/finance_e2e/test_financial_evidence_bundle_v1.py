"""Free assembly tests; these are not model-output quality judgments."""

import copy
import json
import unittest

from financial_evidence_bundle_v1 import build_bundle, render_research_note, validate_interpretation
from verify_fintech_inference_answer_v1 import CORPUS


CASES = {case["case_id"]: case for case in json.loads(CORPUS.read_text())["cases"]}
SOFI_RECONCILIATION = [{
    "id": "REC:SOFI_Q3_ADJUSTED_REVENUE",
    "base_fact_id": "SOFI-Q3-GAAP-REV",
    "signed_adjustment_fact_ids": ["SOFI-Q3-SERVICING", "SOFI-Q3-RESIDUAL",
                                   "SOFI-Q3-DEBTGAIN"],
    "reported_fact_id": "SOFI-Q3-ADJ-REV",
}]


def interpretation(comparison_id):
    return {
        "implication": "The selected comparison warrants a focused review of earnings quality before a stronger conclusion.",
        "counterpoint": "The favorable operating signal may reflect timing or mix rather than a durable change in economics.",
        "next_evidence": "A complete reconciliation and a comparable subsequent period would distinguish those explanations.",
        "comparison_ids": [comparison_id],
        "causal_status": "bounded_hypothesis",
        "decision": "needs_review",
    }


class EvidenceBundleTests(unittest.TestCase):
    def test_three_development_cases_have_expected_calculations(self):
        afrm = build_bundle(CASES["AFRM-FISCAL-COST"])
        revenue = next(row for row in afrm["comparisons"]
                       if row["id"] == "SEQ:gaap_total_revenue_net")
        self.assertEqual((revenue["delta_usd_thousand"], revenue["percent_change_of_baseline"]),
                         ("39294", "5.96"))
        self.assertEqual(len(afrm["comparisons"]), 7)

        sofi = build_bundle(CASES["SOFI-REVENUE-BRIDGE"], SOFI_RECONCILIATION)
        self.assertEqual(len(sofi["comparisons"]), 3)
        self.assertTrue(sofi["reconciliations"][0]["reconciled"])
        self.assertEqual(sofi["reconciliations"][0]["computed_usd_thousand"], "689445")

        upst = build_bundle(CASES["UPST-MIXED-BASIS"])
        adjusted_seq = next(row for row in upst["comparisons"]
                            if row["id"] == "SEQ:adjusted_net_income_loss_non_gaap")
        adjusted_yoy = next(row for row in upst["comparisons"]
                            if row["id"] == "YOY:adjusted_net_income_loss_non_gaap")
        self.assertEqual(adjusted_seq["direction"], "loss_narrowed")
        self.assertEqual(adjusted_yoy["direction"], "loss_widened")
        self.assertEqual(len(upst["comparisons"]), 8)

    def test_period_and_source_reference_fail_closed(self):
        bad = copy.deepcopy(CASES["AFRM-FISCAL-COST"])
        bad["event"]["period"] = "FY2025 Q2 ended 2024-09-30"
        with self.assertRaisesRegex(ValueError, "not adjacent"):
            build_bundle(bad)
        bad = copy.deepcopy(CASES["SOFI-REVENUE-BRIDGE"])
        with self.assertRaisesRegex(ValueError, "missing or non-event"):
            build_bundle(bad, [{**SOFI_RECONCILIATION[0],
                                "signed_adjustment_fact_ids": ["SOFI-Q2-GAAP-REV"]}])

    def test_numeric_prose_unknown_reference_and_false_causal_status_are_rejected(self):
        bundle = build_bundle(CASES["UPST-MIXED-BASIS"])
        item = interpretation("SEQ:gaap_total_revenue")
        self.assertIsNone(validate_interpretation(item, bundle)["quality_pass"])
        rendered = render_research_note(bundle, item)
        self.assertIn("loss_widened", rendered)
        self.assertIn("Source scope: selected", rendered)
        with self.assertRaisesRegex(ValueError, "numerical claim"):
            validate_interpretation({**item, "implication": "Revenue rose by 27 percent in the selected comparison."}, bundle)
        with self.assertRaisesRegex(ValueError, "unknown or duplicate"):
            validate_interpretation({**item, "comparison_ids": ["YOY:invented"]}, bundle)
        with self.assertRaisesRegex(ValueError, "causal bridge"):
            validate_interpretation({**item, "causal_status": "source_explicit_bridge"}, bundle)


if __name__ == "__main__":
    unittest.main()
