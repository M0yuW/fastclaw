"""Fail-closed frame qualification checks before paid confirmation."""

import unittest

from preflight_reference_source_confirmation_v1 import inspect


class ConfirmationSourcePreflightTests(unittest.TestCase):
    def test_current_frame_is_not_falsely_marked_ready(self):
        result = inspect()
        self.assertEqual(result["selected_issuers"], 30)
        self.assertEqual(result["legacy_audit_pending_unified_locator"], [])
        self.assertEqual(result["invalid_packets"], [])
        self.assertEqual(result["generic_verified_count"]
                         + len(result["missing_packet_symbols"]), 30)
        self.assertIn("ALL", {item["symbol"] for item in result["generic_verified"]})
        self.assertEqual(result["ready"], result["generic_verified_count"] == 30)
        self.assertIsNone(result["quality_pass"])


if __name__ == "__main__":
    unittest.main()
