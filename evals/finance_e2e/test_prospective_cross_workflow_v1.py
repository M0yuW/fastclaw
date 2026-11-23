import copy
import json
import unittest

import rank_prospective_cross_workflow_v1 as frame_rank
import verify_prospective_source_discovery_v1 as source_verify


class ProspectiveCrossWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frame = json.loads(frame_rank.FRAME.read_text(encoding="utf-8"))
        cls.discovery = json.loads(source_verify.DISCOVERY.read_text(encoding="utf-8"))

    def test_frozen_frame_and_sec_identity_snapshot(self):
        raw = (frame_rank.ROOT / self.frame["issuer_identity_snapshot_path"]).read_bytes()
        frame_rank.verify_identity_snapshot(self.frame, raw)
        ranked = frame_rank.rank(self.frame, frame_rank.SEED_SOURCE.read_bytes())
        self.assertEqual((ranked["primary_count"], ranked["reserve_count"]), (20, 4))

    def test_gs_source_identity_is_not_fact_audit(self):
        result = source_verify.verify(self.frame, self.discovery)
        self.assertEqual(result["source_files"], 2)
        self.assertFalse(result["fact_semantics_audited"])

    def test_development_issuer_cannot_enter_frame(self):
        changed = copy.deepcopy(self.frame)
        changed["strata"]["credit_wealth"][0] = "SOFI"
        with self.assertRaisesRegex(ValueError, "development ticker"):
            frame_rank.rank(changed, frame_rank.SEED_SOURCE.read_bytes())

    def test_hash_mismatch_is_rejected(self):
        changed = copy.deepcopy(self.discovery)
        changed["issuers"][0]["sources"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source hash changed"):
            source_verify.verify(self.frame, changed)

    def test_nonadjacent_pair_is_rejected(self):
        changed = copy.deepcopy(self.discovery)
        changed["issuers"][0]["sources"][1]["fiscal_period"] = "2025 Q4"
        with self.assertRaisesRegex(ValueError, "nonadjacent fiscal pair"):
            source_verify.verify(self.frame, changed)


if __name__ == "__main__":
    unittest.main()
