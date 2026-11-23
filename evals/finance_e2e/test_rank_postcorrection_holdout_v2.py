import copy
import json
import unittest

import rank_postcorrection_holdout_v2 as subject


class PostcorrectionHoldoutFrameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frame = json.loads(subject.FRAME.read_text())
        cls.parent = json.loads(
            (subject.HERE / cls.frame["parent_v1_frame_path"]).read_text())
        cls.snapshot = json.loads(
            (subject.ROOT / cls.frame["issuer_identity_snapshot_path"]).read_text())
        cls.observed = subject.observed_v1_symbols()

    def test_current_frame_is_twenty_source_distinct_unseen_issuers(self):
        result = subject.preflight()
        self.assertEqual(20, result["selected_issuer_count"])
        self.assertEqual(100, result["planned_observations"])
        self.assertEqual("WFC", result["selected_by_stratum"]["banking_capital_markets"][-1])
        self.assertFalse(set(result["selected_cik"]) & self.observed)

    def test_adding_an_observed_issuer_is_rejected(self):
        changed = copy.deepcopy(self.frame)
        changed["retained_unobserved_v1_primaries"]["banking_capital_markets"][0] = "GS"
        with self.assertRaisesRegex(ValueError, "retained primaries differ"):
            subject.select(changed, self.parent, self.snapshot, self.observed)

    def test_bank_cannot_be_chosen_after_results(self):
        changed = copy.deepcopy(self.frame)
        changed["selected_extension_bank"] = "USB"
        with self.assertRaisesRegex(ValueError, "hash rank"):
            subject.select(changed, self.parent, self.snapshot, self.observed)

    def test_unknown_or_duplicate_extension_is_rejected(self):
        changed = copy.deepcopy(self.frame)
        changed["extension_candidate_pools"]["banking_capital_markets"].append("WFC")
        with self.assertRaisesRegex(ValueError, "pool invalid"):
            subject.select(changed, self.parent, self.snapshot, self.observed)
        changed = copy.deepcopy(self.frame)
        changed["extension_candidate_pools"]["credit_wealth"].append("NOT-A-TICKER")
        with self.assertRaisesRegex(ValueError, "pool invalid"):
            subject.select(changed, self.parent, self.snapshot, self.observed)


if __name__ == "__main__":
    unittest.main()
