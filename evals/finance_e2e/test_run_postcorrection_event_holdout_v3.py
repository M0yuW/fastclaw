import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import run_postcorrection_event_holdout_v3 as subject


class PostcorrectionOutputLimitArmTests(unittest.TestCase):
    def test_same_100_observation_order_as_v2(self):
        order, digest = subject.preflight()
        self.assertEqual(100, len(order))
        self.assertEqual(subject.EXPECTED_ORDER_SHA256, digest)
        self.assertEqual(subject.v2.planned_order(subject.source_batch.preflight()["fixtures"]),
                         order)

    def test_only_copied_agent_output_limit_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            database_path = home / "fastclaw.db"
            with sqlite3.connect(database_path) as db:
                db.execute("CREATE TABLE agents (id TEXT PRIMARY KEY, config TEXT)")
                db.execute("INSERT INTO agents (id, config) VALUES (?, ?)",
                           (subject.AGENT_ID, json.dumps({"model": subject.v2.MODEL,
                                                          "maxToolIterations": 8,
                                                          "maxTokens": 2500})))
            subject.configure_output_limit(home)
            with sqlite3.connect(database_path) as db:
                actual = json.loads(db.execute("SELECT config FROM agents").fetchone()[0])
            self.assertEqual(5000, actual["maxTokens"])
            self.assertEqual(8, actual["maxToolIterations"])
            self.assertEqual(subject.v2.MODEL, actual["model"])

    def test_manifest_freezes_old_failure_and_new_arm_code(self):
        paths = set(subject.manifest_paths())
        self.assertIn(Path(subject.__file__), paths)
        self.assertIn(subject.V2_MANIFEST, paths)
        self.assertIn(subject.V2_HASH_LIST, paths)
        self.assertIn(subject.HERE / "POSTCORRECTION-HOLDOUT-OUTPUT-LIMIT-ARM-v3.md", paths)
        self.assertTrue(all(path.is_file() for path in paths))


if __name__ == "__main__":
    unittest.main()
