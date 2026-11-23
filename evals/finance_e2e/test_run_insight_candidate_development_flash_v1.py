import unittest

import run_insight_candidate_development_flash_v1 as runner


class DevelopmentRunnerTests(unittest.TestCase):
    def test_frozen_seen_case_order_and_source_audit(self):
        frozen = runner.preflight()
        self.assertEqual(len(frozen["order"]), 8)
        self.assertEqual(len(set(frozen["run_ids"])), 8)
        self.assertEqual({item["runtime_symbol"] for item, _ in frozen["order"]},
                         set(runner.SYMBOLS))
        self.assertEqual(frozen["order_hash"],
                         "9da12b469a19365e7940a692cc6a5ad0654e15f6f00f771fa307ccceba3244cb")


if __name__ == "__main__":
    unittest.main()
