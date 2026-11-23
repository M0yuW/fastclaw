import hashlib
import json
import unittest

import build_postcorrection_event_preflight_v2 as source_batch
import run_postcorrection_event_holdout_v2 as subject


class PostcorrectionEventHoldoutRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = source_batch.preflight()["fixtures"]

    def test_fixed_order_has_exactly_five_isolated_runs_per_issuer(self):
        order = subject.planned_order(self.fixtures)
        self.assertEqual(100, len(order))
        pairs = {(item["case_id"], repetition) for item, repetition in order}
        self.assertEqual(100, len(pairs))
        self.assertEqual(set(range(1, 6)), {repetition for _, repetition in pairs})
        self.assertEqual(order, subject.planned_order(list(reversed(self.fixtures))))
        run_ids = [f"{item['case_id']}-r{repetition}" for item, repetition in order]
        self.assertEqual(
            "5dd8423a7f8bf6249d1449d31cb057c34bdecff6d5baacf4f3d2b0174a72182b",
            hashlib.sha256(json.dumps(run_ids).encode()).hexdigest())

    def test_manifest_covers_all_audited_packets_and_source_bytes(self):
        paths = set(subject.manifest_paths())
        for auditor, packet in source_batch.READY.values():
            self.assertIn(packet, paths)
            self.assertIn(subject.Path(auditor.__file__), paths)
        self.assertIn(subject.Path(subject.__file__), paths)
        self.assertIn(subject.HERE / "POSTCORRECTION-HOLDOUT-PROTOCOL-v2.md", paths)
        for path in paths:
            self.assertTrue(path.is_file(), path)
            self.assertTrue(path.is_relative_to(subject.ROOT), path)

    def test_no_implicit_paid_budget(self):
        self.assertGreater(subject.NEXT_OBSERVATION_RESERVE_USD, 0)
        self.assertEqual("2026-10-24", subject.PRICING_CHECKED_AT)
        self.assertEqual("deepseek/deepseek-v4-flash", subject.MODEL)


if __name__ == "__main__":
    unittest.main()
