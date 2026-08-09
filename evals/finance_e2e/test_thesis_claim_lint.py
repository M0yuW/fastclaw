from __future__ import annotations

import unittest

from evals.finance_e2e.thesis_claim_lint import DEFAULT_PAPER, check


class ThesisClaimLintTest(unittest.TestCase):
    def test_current_paper_passes(self) -> None:
        self.assertEqual([], check(DEFAULT_PAPER.read_text(encoding="utf-8")))

    def test_unqualified_language_fails(self) -> None:
        self.assertTrue(check("This is a negative result and is compute-matched."))


if __name__ == "__main__":
    unittest.main()
