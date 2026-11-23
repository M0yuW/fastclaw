"""Free checks for source-complete reference-only insight candidates."""

import copy
import json
import unittest
from decimal import Decimal

import build_postcorrection_v4_event_preflight as source_batch
from build_reference_insight_prompt_v1 import reference_prompt
from reference_insight_catalog_v1 import build_catalog, render_catalog
from verify_insight_candidate_v1 import canonical_state
from verify_reference_insight_candidate_v1 import (render_reference_card,
                                                   verify_reference_candidate)


class ReferenceCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepared = source_batch.preflight()
        packet = json.loads(source_batch.DECLARED_PACKETS["FITB"].read_text())
        cls.catalog = build_catalog("FITB", packet)
        path = source_batch.HERE / "results/2026-10-25-insight-candidate-development-flash-v2" / (
            "FITB-2025-Q3-GAAP-INTEREST-CREDIT-INCOME-BRIDGE-r1/result.json")
        cls.state = json.loads(path.read_text())["state"]

    def candidate(self):
        return {
            "selected_comparisons": {
                "support": ["SEQ:gaap_net_interest_income"],
                "counterevidence": ["SEQ:gaap_credit_loss_provision"],
            },
            "interpretation": {
                "implication": "The selected earnings rows improved, but the gain is not broad-based.",
                "counterevidence": "Higher credit costs limit the underlying improvement.",
                "uncertainty": "The extract does not identify durability or the drivers of credit costs.",
            },
            "asserted_state": canonical_state(self.state),
        }

    def test_catalog_covers_every_common_metric_for_all_audited_cases(self):
        self.assertEqual(self.prepared["ready_cases"], 20)
        for symbol, path in {**source_batch.FIRST_PACKETS,
                             **source_batch.DECLARED_PACKETS}.items():
            with self.subTest(symbol=symbol):
                packet = json.loads(path.read_text())
                catalog = build_catalog(symbol, packet)
                facts = source_batch._normalize(symbol, packet)["facts"]
                common = facts["baseline"].keys() & facts["event"].keys()
                self.assertEqual(set(catalog["rows"]),
                                 {f"SEQ:{metric}" for metric in common})
                self.assertEqual(catalog["baseline"]["source_sha256"],
                                 packet["baseline"]["source_sha256"])
                self.assertEqual(catalog["event"]["source_sha256"],
                                 packet["event"]["source_sha256"])
                for role in ("baseline", "event"):
                    self.assertTrue(catalog[role]["source_url"].startswith(
                        "https://www.sec.gov/Archives/"))
                    self.assertTrue(catalog[role]["filing_date"])
                for metric in common:
                    row = catalog["rows"][f"SEQ:{metric}"]
                    self.assertEqual(Decimal(row["delta_value"]),
                                     Decimal(row["event_value"])
                                     - Decimal(row["baseline_value"]))
                self.assertEqual(render_catalog(catalog).count("SEQ:"), len(common))

    def test_clean_candidate_only_reaches_qualitative_review(self):
        candidate = self.candidate()
        card = render_reference_card(self.catalog, candidate, self.state)
        self.assertEqual(card["status"], "candidate_for_qualitative_review")
        self.assertIsNone(card["quality_pass"])
        self.assertEqual(set(card["complete_host_comparison_table"]),
                         set(self.catalog["rows"]))

    def test_invented_reference_or_ledger_state_is_held(self):
        candidate = self.candidate()
        candidate["selected_comparisons"]["support"] = ["SEQ:invented"]
        candidate["asserted_state"]["next_review_at"] = "2026-01-01"
        result = verify_reference_candidate(self.catalog, candidate, self.state)
        self.assertIn("support_comparison_refs_invalid", result["issues"])
        self.assertIn("state_claim_contradicted_by_ledger", result["issues"])

    def test_numeric_prose_and_saved_rationale_are_held(self):
        candidate = self.candidate()
        candidate["interpretation"]["implication"] = "Income rose by 29 million."
        state = copy.deepcopy(self.state)
        state["theses"][0]["reviews"][0]["rationale"] = "Income rose by 29 million."
        result = verify_reference_candidate(self.catalog, candidate, state)
        self.assertIn("unstructured_numeric_prose", result["issues"])
        self.assertIn("unstructured_numeric_saved_rationale", result["issues"])

    def test_duplicate_or_overlapping_refs_are_held(self):
        candidate = self.candidate()
        candidate["selected_comparisons"]["support"] *= 2
        candidate["selected_comparisons"]["counterevidence"] = [
            "SEQ:gaap_net_interest_income"]
        result = verify_reference_candidate(self.catalog, candidate, self.state)
        self.assertIn("support_comparison_refs_invalid", result["issues"])
        self.assertIn("support_counterevidence_refs_overlap", result["issues"])

    def test_prompt_delivers_catalog_without_preselecting_decision(self):
        fixture = next(item for item in self.prepared["fixtures"]
                       if item["runtime_symbol"] == "FITB")
        prompt = reference_prompt(fixture, self.catalog, "thesis-id", "alert-id")
        self.assertIn("SEQ:gaap_net_interest_income", prompt)
        self.assertIn("selected_comparisons", prompt)
        self.assertIn("Choose the research-state decision yourself", prompt)
        self.assertNotIn("you must maintain conviction", prompt)

    def test_false_qualitative_direction_is_not_automatically_certified(self):
        candidate = self.candidate()
        candidate["interpretation"]["implication"] = (
            "Net interest income fell and therefore core earnings deteriorated."
        )
        result = verify_reference_candidate(self.catalog, candidate, self.state)
        self.assertEqual(result["status"], "candidate_for_qualitative_review")
        self.assertIsNone(result["quality_pass"])


if __name__ == "__main__":
    unittest.main()
