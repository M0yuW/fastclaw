"""Read-only SEC-text and arithmetic checks for one source-row audit example."""

import json
import re
import unittest
from decimal import Decimal

from build_reference_source_distinct_frame_v1 import sha256
from inspect_reference_source_exhibits_v1 import PlainText
from run_thesis_event_panel import HERE


PACKET = HERE / "bokf_reference_source_row_audit_v1.json"
FREEZE = HERE / "results/2026-10-25-reference-source-distinct-sec-exhibits-pilot-v1"
NUMBERS = re.compile(r"(?<![A-Za-z0-9])\(?\d[\d,]*\)?")


def first_two_table_values(source: str, label: str) -> tuple[str, str]:
    matches = re.finditer(r"\|\s*" + re.escape(label) + r"\s*\|", source,
                          flags=re.IGNORECASE)
    for match in matches:
        following = source[match.end():match.end() + 180].split("\n", 1)[0]
        values = [item.strip("()").replace(",", "")
                  for item in NUMBERS.findall(following)]
        if len(values) >= 2:
            return values[0], values[1]
    raise AssertionError(f"table row with two values not found: {label}")


class BokfSourceRowAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = json.loads(PACKET.read_text())
        manifest = json.loads((FREEZE / "manifest.json").read_text())
        cls.texts = {}
        for artifact in manifest["artifacts"]:
            if artifact["symbol"] != "BOKF":
                continue
            role = "baseline" if artifact["period_window"] == "CY2025_Q2" else "event"
            path = FREEZE / artifact["path"]
            assert sha256(path) == artifact["sha256"]
            assert artifact["sha256"] == cls.packet["sources"][role]["sha256"]
            parser = PlainText()
            parser.feed(path.read_text(errors="replace"))
            cls.texts[role] = parser.text()

    def test_exact_rows_and_event_prior_column(self):
        self.assertEqual(len(self.texts), 2)
        for row in self.packet["rows"]:
            with self.subTest(metric=row["id"]):
                before, _ = first_two_table_values(
                    self.texts["baseline"], row["source_label"])
                after, event_prior = first_two_table_values(
                    self.texts["event"], row["source_label"])
                self.assertEqual(before, row["baseline_value"])
                self.assertEqual(after, row["event_value"])
                self.assertEqual(event_prior, row["baseline_value"])
                self.assertEqual(Decimal(row["delta_value"]),
                                 Decimal(after) - Decimal(before))

    def test_signed_tax_equivalent_bridge(self):
        rows = {item["id"]: item for item in self.packet["rows"]}
        for field in ("baseline_value", "event_value", "delta_value"):
            revenue = Decimal(rows["reported_total_interest_revenue"][field])
            expense = Decimal(rows["reported_total_interest_expense"][field])
            adjustment = Decimal(rows["reported_tax_equivalent_adjustment"][field])
            net = Decimal(rows["reported_net_interest_income"][field])
            self.assertEqual(revenue - expense - adjustment, net)
        self.assertIsNone(self.packet["quality_pass"])
        self.assertEqual(self.packet["model_observations"], 0)


if __name__ == "__main__":
    unittest.main()
