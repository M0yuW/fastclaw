"""Free pre-run checks for the new-issuer panel; never calls a model."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import audit_fintech_inference_sources_v1 as source_audit
import preflight_fintech_inference_new_issuer_v1 as preflight
import prepare_fintech_inference_claim_review_v1 as review
import run_fintech_inference_new_issuer_flash_v1 as runner
import validate_fintech_inference_packet_v1 as packet
import verify_fintech_inference_answer_v1 as answer_verify
from run_thesis_event_gateway import load_plugin


class NewIssuerPreRunTests(unittest.TestCase):
    def test_packet_has_nonoperating_gain_and_derived_checks(self):
        result = packet.validate()
        self.assertEqual(result["cases"], 3)
        self.assertEqual(result["facts"], 38)
        self.assertIn("gain_on_debt_extinguishment",
                      runner.REVIEW_METRICS["UPST-MIXED-BASIS"])

    def test_frozen_sec_sources_and_selected_facts_pass(self):
        result = preflight.verify()
        self.assertEqual(result["facts"], 38)
        self.assertEqual(len(result["sources"]), 6)
        self.assertEqual(result["selected_fact_audit"]["facts"], 38)

    def test_selected_sec_fact_audit_fails_on_value_or_hash_change(self):
        self.assertEqual(source_audit.verify()["facts"], 38)
        original = json.loads(source_audit.CORPUS.read_text())
        with tempfile.TemporaryDirectory(dir=source_audit.HERE) as temporary:
            changed = Path(temporary) / "changed.json"
            wrong_value = json.loads(json.dumps(original))
            wrong_value["cases"][0]["baseline"]["facts"][0]["value"] += 1
            changed.write_text(json.dumps(wrong_value))
            with patch.object(source_audit, "CORPUS", changed):
                with self.assertRaisesRegex(ValueError, "source-audited value changed"):
                    source_audit.verify()
            wrong_hash = json.loads(json.dumps(original))
            wrong_hash["cases"][0]["baseline"]["source_sha256"] = "0" * 64
            changed.write_text(json.dumps(wrong_hash))
            with patch.object(source_audit, "CORPUS", changed):
                with self.assertRaisesRegex(ValueError, "SEC source hash mismatch"):
                    source_audit.verify()

    def test_debt_gain_is_not_an_operating_margin_driver(self):
        plugin = load_plugin()
        cases = json.loads(runner.CORPUS.read_text())["cases"]
        event = next(case["event"] for case in cases
                     if case["case_id"] == "UPST-MIXED-BASIS")
        gain = next(fact for fact in event["facts"]
                    if fact["id"] == "UPST-Q3-DEBTGAIN")
        facts = {gain["id"]: gain}
        claim = {"target_metric": "net_income", "strength": "consistent_with",
                 "driver_fact_ids": [gain["id"]]}
        self.assertEqual(plugin._lineage.validate_causal_claims(facts, [claim]), [claim])
        with self.assertRaisesRegex(plugin._lineage.ClaimValidationError, "not a operating_margin driver"):
            plugin._lineage.validate_causal_claims(
                facts, [{**claim, "target_metric": "operating_margin"}])
        with self.assertRaisesRegex(plugin._lineage.ClaimValidationError, "lacks reconciliation"):
            plugin._lineage.validate_causal_claims(
                facts, [{**claim, "attributed_change_percentage_points": 1}])

    def test_checkpoint_and_relative_result_hashes(self):
        with tempfile.TemporaryDirectory(dir=runner.ROOT) as temporary:
            output = Path(temporary)
            (output / "manifest.json").write_text("{}\n")
            observation = output / "AFRM-FISCAL-COST-r1"
            observation.mkdir()
            (observation / "gateway.log").write_text("gateway started\n")
            pilot = type("FakePilot", (), {
                "turns": [{"response": {"choices": [{"message": {"content": "test"}}]}}],
                "cost": 0.001,
            })()
            runner.save_turn_checkpoint(observation, pilot)
            (observation / "result.json").write_text("{}\n")
            runner.write_result_hashes(output.relative_to(runner.ROOT))
            lines = (output / "RESULT-SHA256.txt").read_text().splitlines()
            self.assertEqual(len(lines), 4)
            self.assertTrue(lines[1].endswith("/AFRM-FISCAL-COST-r1/result.json"))
            self.assertTrue(lines[2].endswith("/AFRM-FISCAL-COST-r1/turn_checkpoint.json"))
            checkpoint = json.loads((observation / "turn_checkpoint.json").read_text())
            self.assertEqual(checkpoint["estimated_cost_usd"], 0.001)

    def test_claim_review_requires_retained_hashes_and_frozen_criteria(self):
        with tempfile.TemporaryDirectory(dir=runner.ROOT) as temporary:
            output = Path(temporary)
            manifest_path = output / "manifest.json"
            order = [(case, repeat) for case in runner.REVIEW_METRICS
                     for repeat in range(1, 6)]
            manifest_path.write_text(json.dumps({"run_order": order}))
            observation = output / "UPST-MIXED-BASIS-r1"
            observation.mkdir()
            result_path = observation / "result.json"
            result_path.write_text(json.dumps({"observation_id": observation.name,
                                               "case_id": "UPST-MIXED-BASIS"}))
            runner.write_result_hashes(output.relative_to(runner.ROOT))
            rows = review.worksheet_rows(output)
            self.assertEqual(len(rows), 8)
            self.assertIn("NONOPERATING_GAIN", {row["criterion_id"] for row in rows})
            self.assertTrue(all(row["verdict"] == "" for row in rows))
            result_path.write_text(result_path.read_text() + " ")
            with self.assertRaisesRegex(ValueError, "result hash mismatch"):
                review.worksheet_rows(output)

    def test_answer_screen_catches_arithmetic_and_direction_but_never_awards_quality(self):
        cases = {case["case_id"]: case for case in json.loads(runner.CORPUS.read_text())["cases"]}
        afrm = answer_verify.check_answer(cases["AFRM-FISCAL-COST"],
                                          "Sequential GAAP revenue **+39,304**.")
        self.assertEqual(afrm["failures"][0]["code"], "AFRM_REVENUE_DELTA")
        self.assertIsNone(afrm["quality_pass"])
        self.assertEqual(answer_verify.check_answer(
            cases["AFRM-FISCAL-COST"], "Sequential revenue **+39,294**.")["failures"], [])
        sofi = answer_verify.check_answer(cases["SOFI-REVENUE-BRIDGE"],
                                          "The GAAP/non-GAAP gap narrowed in relative terms.")
        self.assertEqual(sofi["failures"][0]["code"], "SOFI_RELATIVE_GAP")
        upst = answer_verify.check_answer(cases["UPST-MIXED-BASIS"],
                                          "Adjusted net loss: -5.3 vs -3.9, narrower by 1.4 YoY.")
        self.assertEqual(upst["failures"][0]["code"], "UPST_ADJUSTED_LOSS_YOY")
        equation = answer_verify.check_answer(cases["AFRM-FISCAL-COST"],
                                              "Revenue 698,479 - 659,185 = 39,304.")
        self.assertEqual(equation["failures"][0]["code"], "EQUATION")
        multi_term = answer_verify.check_answer(cases["SOFI-REVENUE-BRIDGE"],
                                                "697,121 - 4,362 + 9 - 3,323 = 689,445")
        self.assertEqual(multi_term["failures"], [])
        unparsed = answer_verify.check_answer(cases["UPST-MIXED-BASIS"],
                                              "The outlook warrants caution.")
        self.assertEqual(unparsed["screen"], "unassessed")
        self.assertIsNone(unparsed["quality_pass"])


if __name__ == "__main__":
    unittest.main()
