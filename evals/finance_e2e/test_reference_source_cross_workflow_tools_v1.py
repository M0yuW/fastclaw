"""Selected-source screen and policy-bound preflight regressions."""

from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path

from preflight_cross_workflow_source_tools_v1 import run
from run_thesis_event_panel import HERE


SCRIPT = HERE / "workflow_fixtures_reference_source_v1/US-market/findata-toolkit/scripts/stock_data.py"
SPEC = importlib.util.spec_from_file_location("reference_source_screen_adapter", SCRIPT)
ADAPTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ADAPTER)


class ReferenceSourceCrossWorkflowToolsTests(unittest.TestCase):
    def test_bokf_is_incomplete_not_negative(self):
        result = ADAPTER.screen(["BOKF", "PGR", "JKHY"])
        bokf = next(item for item in result["rejected"] if item["symbol"] == "BOKF")
        self.assertEqual(bokf["reason"], "insufficient_data")
        self.assertEqual(bokf["missing_metrics"], ["comparable_reported_profit_row"])
        self.assertTrue(result["not_live_market_data"])

    def test_official_source_hash_tamper_fails_closed(self):
        selection, freeze, _, mapping = ADAPTER.checked_inputs()
        pair = copy.deepcopy(next(item for item in selection["pairs"]
                                  if item["symbol"] == "ACIW"))
        pair["periods"]["CY2025_Q3"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "official SEC exhibit hash mismatch"):
            ADAPTER.candidate(pair, freeze, mapping["ACIW"])

    def test_ten_packet_tools_and_bounds(self):
        result = run()
        self.assertEqual(result["packets"], 10)
        self.assertEqual(result["passed_packets"], 10)
        self.assertEqual(result["external_provider_requests"], 0)
        self.assertIsNone(result["quality_pass"])


if __name__ == "__main__":
    unittest.main()
