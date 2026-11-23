"""Free fail-closed tests; synthetic HTML here is never experiment evidence."""

import copy
import json
import tempfile
import unittest
import sys
from pathlib import Path
from unittest.mock import patch

import preflight_fintech_inference_new_issuer_v1 as preflight
import run_fintech_inference_new_issuer_flash_v1 as runner
import validate_fintech_inference_packet_v1 as packet


class SourcePreflightTests(unittest.TestCase):
    def test_unfrozen_panel_cannot_start(self):
        original = json.loads(packet.CORPUS.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory(prefix=".fintech-preflight-test-", dir=packet.HERE) as directory:
            path = Path(directory) / "draft-corpus.json"
            original["status"] = "draft_no_model_observations"
            path.write_text(json.dumps(original), encoding="utf-8")
            with patch.object(preflight, "CORPUS", path):
                with self.assertRaisesRegex(RuntimeError, "not source-frozen"):
                    preflight.verify()

    def test_six_source_hashes_are_required(self):
        original = json.loads(packet.CORPUS.read_text(encoding="utf-8"))
        result = preflight.verify()
        self.assertEqual(len(result["sources"]), 6)
        self.assertEqual(result["facts"], 38)
        with tempfile.TemporaryDirectory(prefix=".fintech-preflight-test-", dir=packet.HERE) as directory:
            corpus_path = Path(directory) / "test-corpus.json"
            corpus = copy.deepcopy(original)
            corpus["cases"][0]["event"]["source_sha256"] = "0" * 64
            corpus_path.write_text(json.dumps(corpus), encoding="utf-8")
            with patch.object(preflight, "CORPUS", corpus_path):
                with self.assertRaisesRegex(RuntimeError, "hash mismatch"):
                    preflight.verify()

    def test_runner_rejects_unfrozen_protocol_even_if_source_check_passes(self):
        with tempfile.TemporaryDirectory(prefix=".fintech-preflight-test-", dir=packet.HERE) as directory:
            protocol = Path(directory) / "protocol.md"
            protocol.write_text("Source audit pending\n", encoding="utf-8")
            with patch.object(runner, "PROTOCOL", protocol), \
                    patch.object(runner.source_preflight, "verify", return_value={"preflight": "ok"}), \
                    patch.object(sys, "argv", ["runner", "--preflight-only"]):
                with self.assertRaisesRegex(RuntimeError, "freeze markers"):
                    runner.main()


if __name__ == "__main__":
    unittest.main()
