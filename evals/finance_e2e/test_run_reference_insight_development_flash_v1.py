import unittest

import run_reference_insight_development_flash_v1 as runner


class ReferenceDevelopmentRunnerTests(unittest.TestCase):
    def test_frozen_seen_case_order_and_audited_catalogs(self):
        frozen = runner.preflight()
        self.assertEqual(len(frozen["order"]), 8)
        self.assertEqual(len(set(frozen["run_ids"])), 8)
        self.assertEqual({item["runtime_symbol"] for item, _ in frozen["order"]},
                         set(runner.SYMBOLS))
        self.assertEqual(frozen["order_hash"],
                         "3fed4ab98fbfbecf7f9aaab5bddd0f3fb6022f78c529ebc70fb5a1febbdc550b")
        for symbol in runner.SYMBOLS:
            self.assertTrue(runner.catalog_for(symbol)["rows"])


if __name__ == "__main__":
    unittest.main()
