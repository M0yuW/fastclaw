#!/usr/bin/env python3
"""Check selected facts against the six pinned SEC EX-99.1 HTML files.

The anchors below were selected from the source documents before model runs.
They verify the nearby row/column context, not just a number somewhere in a
filing. This is still a selected-fact audit, not a complete filing review.
"""

import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path

from validate_fintech_inference_packet_v1 import CORPUS, HERE


class _VisibleText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def _text(path):
    parser = _VisibleText()
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    return re.sub(r"\s+", " ", " ".join(parser.parts))


# Exact source-row fragments. Upstart's 2023 column precedes 2024; the paired
# numbers in these anchors make that distinction checkable.
ANCHORS = {
    "AFRM-FQ4-REV": "Total revenue, net 659,185 445,825",
    "AFRM-FQ4-TC": "Transaction costs (Non-GAAP) $ 349,787 $ 263,747",
    "AFRM-FQ4-RLTC": "Revenue less transaction costs (Non-GAAP) $ 309,398 $ 182,078",
    "AFRM-FQ4-OPLOSS": "Operating loss $ (73,460) $ (243,828)",
    "AFRM-FQ4-ADJOP": "Adjusted operating income (loss) (Non-GAAP) $ 149,807 $ 14,709",
    "AFRM-FQ4-PROVISION": "Provision for credit losses 117,609 94,483",
    "AFRM-FQ4-FUNDING": "Funding costs 95,256 63,008",
    "AFRM-FQ1-REV": "Total revenue, net 698,479 496,547",
    "AFRM-FQ1-TC": "Transaction costs (Non-GAAP) $ 413,352 $ 284,164",
    "AFRM-FQ1-RLTC": "Revenue less transaction costs (Non-GAAP) $ 285,127 $ 212,383",
    "AFRM-FQ1-OPLOSS": "Operating loss $ (132,623) $ (209,447)",
    "AFRM-FQ1-ADJOP": "Adjusted operating income (Non-GAAP) $ 129,589 $ 59,944",
    "AFRM-FQ1-PROVISION": "Provision for credit losses 159,824 99,696",
    "AFRM-FQ1-FUNDING": "Funding costs 104,145 73,931",
    "SOFI-Q2-GAAP-REV": "Consolidated – GAAP Total net revenue $ 598,618 $ 498,018",
    "SOFI-Q2-ADJ-REV": "Adjusted net revenue (1) $ 596,965 $ 488,815",
    "SOFI-Q2-NETINC": "Net income (loss) 17,404 (47,549)",
    "SOFI-Q3-GAAP-REV": "Consolidated – GAAP Total net revenue $ 697,121 $ 537,209",
    "SOFI-Q3-ADJ-REV": "Adjusted net revenue (1) $ 689,445 $ 530,717",
    "SOFI-Q3-NETINC": "Net income (loss) 60,745 (266,684)",
    "SOFI-Q3-SERVICING": "Servicing rights – change in valuation inputs or assumptions (1) (4,362) (7,420)",
    "SOFI-Q3-RESIDUAL": "Residual interests classified as debt – change in valuation inputs or assumptions (2) 9 928 83 415",
    "SOFI-Q3-DEBTGAIN": "Gain on extinguishment of debt (3) (3,323) — (62,517)",
    "UPST-Q2-REV": "Total revenue 135,766 127,630",
    "UPST-Q2-OPLOSS": "Loss from operations (33,344) (55,486)",
    "UPST-Q2-NETLOSS": "Net loss $ (28,165) $ (54,470)",
    "UPST-Q2-ADJ-NETLOSS": "Adjusted Net Income (Loss) $ 5,354 $ (15,282)",
    "UPST-Q2-CONTRIB": "Contribution profit was $76.1 million in the second quarter of 2024",
    "UPST-Q2-ADJ-EBITDA": "Adjusted EBITDA was $(9.3) million",
    "UPST-Q3-REV": "Total revenue 134,557 162,140",
    "UPST-Q3-OPLOSS": "Loss from operations (43,845) (45,152)",
    "UPST-Q3-NETLOSS": "Net loss $ (40,315) $ (6,758)",
    "UPST-Q3-DEBTGAIN": "Gain on debt extinguishment — 33,361",
    "UPST-Q3-ADJ-NETLOSS": "Adjusted net income (loss) was ($5.3) million",
    "UPST-Q3-CONTRIB": "Contribution profit was $102.4 million in the third quarter of 2024",
    "UPST-Q3-ADJ-EBITDA": "Adjusted EBITDA was $1.4 million",
    "UPST-Q3-PRIOR-OPLOSS": "Loss from operations (43,845) (45,152)",
    "UPST-Q3-PRIOR-ADJ-NETLOSS": "down from ($3.9) million in the same quarter of the prior year",
}

# Independently transcribed selected values; a corpus value change cannot
# silently pass merely because another comparative value appears in the row.
EXPECTED_VALUES = {
    "AFRM-FQ4-REV": "659185", "AFRM-FQ4-TC": "349787",
    "AFRM-FQ4-RLTC": "309398", "AFRM-FQ4-OPLOSS": "-73460",
    "AFRM-FQ4-ADJOP": "149807", "AFRM-FQ4-PROVISION": "117609",
    "AFRM-FQ4-FUNDING": "95256", "AFRM-FQ1-REV": "698479",
    "AFRM-FQ1-TC": "413352", "AFRM-FQ1-RLTC": "285127",
    "AFRM-FQ1-OPLOSS": "-132623", "AFRM-FQ1-ADJOP": "129589",
    "AFRM-FQ1-PROVISION": "159824", "AFRM-FQ1-FUNDING": "104145",
    "SOFI-Q2-GAAP-REV": "598618", "SOFI-Q2-ADJ-REV": "596965",
    "SOFI-Q2-NETINC": "17404", "SOFI-Q3-GAAP-REV": "697121",
    "SOFI-Q3-ADJ-REV": "689445", "SOFI-Q3-NETINC": "60745",
    "SOFI-Q3-SERVICING": "-4362", "SOFI-Q3-RESIDUAL": "9",
    "SOFI-Q3-DEBTGAIN": "-3323", "UPST-Q2-REV": "127630",
    "UPST-Q2-OPLOSS": "-55486", "UPST-Q2-NETLOSS": "-54470",
    "UPST-Q2-ADJ-NETLOSS": "-15282", "UPST-Q2-CONTRIB": "76.1",
    "UPST-Q2-ADJ-EBITDA": "-9.3", "UPST-Q3-REV": "162140",
    "UPST-Q3-OPLOSS": "-45152", "UPST-Q3-NETLOSS": "-6758",
    "UPST-Q3-DEBTGAIN": "33361", "UPST-Q3-ADJ-NETLOSS": "-5.3",
    "UPST-Q3-CONTRIB": "102.4", "UPST-Q3-ADJ-EBITDA": "1.4",
    "UPST-Q3-PRIOR-OPLOSS": "-43845",
    "UPST-Q3-PRIOR-ADJ-NETLOSS": "-3.9",
}


def verify():
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    checked = []
    all_ids = {fact["id"] for case in corpus["cases"]
               for period in ("baseline", "event")
               for fact in case[period]["facts"]}
    if all_ids != set(ANCHORS) or all_ids != set(EXPECTED_VALUES):
        raise ValueError("source audit anchor IDs differ from packet fact IDs")
    for case in corpus["cases"]:
        for period in ("baseline", "event"):
            item = case[period]
            path = (HERE / item["local_path"]).resolve()
            if not path.is_relative_to(HERE.resolve()) or not path.is_file():
                raise ValueError(f"missing or escaped SEC source: {case['case_id']} {period}")
            if hashlib.sha256(path.read_bytes()).hexdigest() != item["source_sha256"]:
                raise ValueError(f"SEC source hash mismatch: {case['case_id']} {period}")
            body = _text(path)
            if case["symbol"] == "UPST":
                expected_header = "2023 2024 2023 2024"
                if expected_header not in body:
                    raise ValueError(f"Upstart comparative column order missing: {period}")
            for fact in item["facts"]:
                anchor = ANCHORS[fact["id"]]
                if str(fact["value"]) != EXPECTED_VALUES[fact["id"]]:
                    raise ValueError(f"source-audited value changed: {fact['id']}")
                if anchor not in body:
                    raise ValueError(f"source-row anchor missing: {fact['id']}")
                checked.append(fact["id"])
    return {"status": "selected_fact_rows_and_source_hashes_match",
            "sources": 6, "facts": len(checked)}


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
