import hashlib
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import run_postcorrection_event_holdout_v4 as subject


class PostcorrectionV4RunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frozen = subject.preflight()

    def test_source_distinct_100_order_is_precommitted(self):
        order = self.frozen["order"]
        self.assertEqual(len(order), 100)
        self.assertEqual(len(set(self.frozen["run_ids"])), 100)
        self.assertEqual({repeat for _, repeat in order}, set(range(1, 6)))
        self.assertEqual(self.frozen["order_hash"],
                         "c421216d9332475c37af20b01fce83deae4714da3c397e4422a9ba1f4b85b20c")
        self.assertEqual(subject.planned_order(
            list(reversed(self.frozen["prepared"]["fixtures"]))), order)
        self.assertEqual(hashlib.sha256(json.dumps(
            self.frozen["run_ids"]).encode()).hexdigest(), self.frozen["order_hash"])

    def test_manifest_includes_every_packet_and_frozen_exhibit(self):
        paths = set(subject.manifest_paths())
        self.assertIn(subject.HERE / "POSTCORRECTION-V4-INSIGHT-QUALITY-PROTOCOL.md", paths)
        for packet in (*subject.source_batch.FIRST_PACKETS.values(),
                       *subject.source_batch.DECLARED_PACKETS.values()):
            self.assertIn(packet, paths)
        for directory in subject.source_batch.MANIFEST_DIRS:
            for item in directory.iterdir():
                if item.is_file():
                    self.assertIn(item, paths)
        self.assertTrue(all(path.is_file() and path.is_relative_to(subject.ROOT)
                            for path in paths))

    def test_no_implicit_authorization_or_spend_cap(self):
        self.assertGreater(subject.NEXT_OBSERVATION_RESERVE_USD, 0)
        self.assertGreater(subject.MAX_TOKENS, 5000)
        self.assertIsNone(subject.main.__defaults__)
        with patch.object(subject, "preflight", return_value=self.frozen), patch.object(
                sys, "argv", ["run_postcorrection_event_holdout_v4.py"]):
            with self.assertRaises(SystemExit) as caught:
                subject.main()
        self.assertEqual(caught.exception.code, 2)

    def test_output_and_tool_limits_are_set_only_in_copied_db(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            with sqlite3.connect(home / "fastclaw.db") as database:
                database.execute("CREATE TABLE agents (id TEXT PRIMARY KEY, config TEXT)")
                database.execute("INSERT INTO agents VALUES (?, ?)", (
                    subject.AGENT_ID, json.dumps({"model": subject.MODEL,
                                                  "maxTokens": 2500,
                                                  "maxToolIterations": 8})))

            def fake_parent(instance, *args):
                instance.home = home

            with patch.object(subject.panel.PanelPilot, "__init__", fake_parent):
                subject.V4Pilot("case", None, None, temp, False, 0.0)
            with sqlite3.connect(home / "fastclaw.db") as database:
                actual = json.loads(database.execute(
                    "SELECT config FROM agents WHERE id=?", (subject.AGENT_ID,)
                ).fetchone()[0])
            self.assertEqual(actual["maxTokens"], 8192)
            self.assertEqual(actual["maxToolIterations"], 16)
            self.assertEqual(actual["model"], subject.MODEL)


if __name__ == "__main__":
    unittest.main()
