import copy
import json
import unittest

import verify_postcorrection_pair_selection_v2 as subject


class PostcorrectionPairSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.discovery = json.loads(subject.DISCOVERY.read_text())
        cls.manifest = json.loads(subject.MANIFEST.read_text())

    def test_five_pairs_match_archived_indexes(self):
        result = subject.verify(self.discovery, self.manifest)
        self.assertEqual(5, len(result["pairs"]))
        self.assertTrue(all(pair["filing_gap_days"] == 91 for pair in result["pairs"]))

    def test_source_swap_is_rejected(self):
        changed = copy.deepcopy(self.manifest)
        changed["sources"][0]["url"] = changed["sources"][1]["url"]
        with self.assertRaisesRegex(ValueError, "URL does not match"):
            subject.verify(self.discovery, changed)

    def test_pnc_conference_skip_must_remain_documented(self):
        changed = copy.deepcopy(self.manifest)
        changed["excluded_nonquarterly_candidate"]["reason"] = ""
        with self.assertRaisesRegex(ValueError, "not documented"):
            subject.verify(self.discovery, changed)


if __name__ == "__main__":
    unittest.main()
