import json
import unittest

from build_cross_workflow_packet_allocation_v1 import build
from preflight_reference_source_confirmation_v1 import SELECTION


class CrossWorkflowPacketAllocationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = build()

    def test_ready_packets_are_source_disjoint_and_stratified(self):
        slots = self.result["ready_source_disjoint_packets"]
        members = [item["symbol"] for slot in slots for item in slot["issuers"]]
        selected = {item["symbol"] for item in json.loads(SELECTION.read_text())["pairs"]}
        self.assertEqual(len(slots), 10)
        self.assertEqual(set(members), selected)
        self.assertEqual(len(members), len(set(members)))
        for slot in slots:
            self.assertEqual(len(slot["issuers"]), 3)
            self.assertEqual(len({item["stratum"] for item in slot["issuers"]}), 3)
            self.assertNotIn(slot["omitted_stratum"],
                             {item["stratum"] for item in slot["issuers"]})

    def test_full_twenty_packet_target_is_not_silently_claimed(self):
        self.assertEqual(self.result["unfilled_packet_slots_per_workflow"], 10)
        self.assertEqual(self.result["additional_source_qualified_issuers_needed"], 30)
        self.assertFalse(self.result["prompts_or_holdings_frozen"])
        self.assertEqual(self.result["model_observations"], 0)


if __name__ == "__main__":
    unittest.main()
