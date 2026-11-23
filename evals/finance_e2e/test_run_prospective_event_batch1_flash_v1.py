import unittest

import run_prospective_event_batch1_flash_v1 as subject


class ProspectiveEventRunnerTests(unittest.TestCase):
    def test_startup_requires_gateway_and_finance_plugin(self):
        self.assertEqual(subject.startup_diagnostics('msg="gateway started" finance-tools'),
                         {"gateway_started": True, "finance_plugin_seen": True})
        self.assertFalse(all(subject.startup_diagnostics('msg="gateway started"').values()))
        self.assertFalse(all(subject.startup_diagnostics('finance-tools').values()))

    def test_review_prompt_does_not_specify_a_case_decision(self):
        prompt = subject.review_prompt("TEST", "thesis-1", "alert-1")
        self.assertIn("Choose your own thesis-review decision", prompt)
        self.assertNotIn("conviction 3", prompt)
        self.assertNotIn("maintain", prompt.lower())


if __name__ == "__main__":
    unittest.main()
