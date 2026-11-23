import unittest

import build_reference_source_distinct_frame_v1 as frame_builder
from run_thesis_event_panel import sha256


FRAME = frame_builder.HERE / (
    "results/2026-10-25-reference-source-distinct-frame-v2/FRAME.json")


class SourceDistinctFrameTests(unittest.TestCase):
    def test_frozen_provisional_pool_excludes_prior_observed_issuers(self):
        result = frame_builder.frame()
        self.assertEqual(result["planned_issuers"], 30)
        self.assertEqual(result["ticker_snapshot_sha256"],
                         "6c29e2e3db973d4479875164603c2434f81ad22e14c9f1694999aca9cca246cb")
        symbols = [item["ticker"] for group in result["strata"].values()
                   for item in [*group["planned"], *group["reserves_in_order"]]]
        self.assertEqual(len(symbols), len(set(symbols)))
        self.assertNotIn("PYPL", symbols)
        self.assertIn("JKHY", symbols)
        for group in result["strata"].values():
            self.assertEqual(len(group["planned"]), group["quota"])
            self.assertTrue(group["reserves_in_order"])
        self.assertEqual(sha256(FRAME),
                         "cdd00faa9391e78d266300ec0562521a85c6f839d4f31a72b68f783b600d2658")


if __name__ == "__main__":
    unittest.main()
