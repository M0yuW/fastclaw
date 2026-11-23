import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from audit_postcorrection_fact_echo_v2 import audit, check_packet, file_hash  # noqa: E402


class FactEchoAuditTests(unittest.TestCase):
    def packet(self, final="", rationale=""):
        return {
            "masked_id": "J-test", "final_answer": final,
            "source_packet": {
                "case_id": "case", "baseline": {"facts": [{"id": "X-Q2-REV", "value": 1000}]},
                "event": {"facts": [{"id": "X-Q3-REV", "value": 1200}]},
            },
            "persisted_theses_and_reviews": [
                {"reviews": [{"rationale": rationale}]}
            ],
        }

    def test_exact_echoes_and_unlabelled_claim_scope(self):
        counts, flags = check_packet(self.packet(
            "X-Q2-REV=1,000 and X-Q3-REV: 1200; revenue rose 300"))
        self.assertEqual(counts, {"final_answer": 2, "persisted_review": 0})
        self.assertEqual(flags, [])  # The unlabelled 300 is outside this check.

    def test_mislabeled_delta_is_flagged_in_review(self):
        counts, flags = check_packet(self.packet(rationale="X-Q3-REV=200"))
        self.assertEqual(counts["persisted_review"], 1)
        self.assertEqual((flags[0]["source_value"], flags[0]["echoed_value"]),
                         ("1200", "200"))

    def test_hash_mismatch_refuses_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            packets = root / "masked_packets"
            packets.mkdir()
            packet = packets / "J-test.json"
            packet.write_text("{}")
            (root / "MASKED-PACKET-SHA256.txt").write_text(
                f"{file_hash(packet)}  masked_packets/J-test.json\n")
            packet.write_text('{"changed":true}')
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                audit(root)


if __name__ == "__main__":
    unittest.main()
