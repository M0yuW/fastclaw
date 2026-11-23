#!/usr/bin/env python3
"""Read-only structural and arithmetic checks for the new-issuer packet.

This does not establish agreement with SEC source bytes. The run preflight must
separately verify cached official exhibits and their hashes before model calls.
"""

import json
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse


HERE = Path(__file__).resolve().parent
CORPUS = HERE / "fintech_inference_new_issuer_v1.json"
EXPECTED_CASES = {"AFRM-FISCAL-COST", "SOFI-REVENUE-BRIDGE", "UPST-MIXED-BASIS"}
PLUGIN_STATEMENT_LINES = {
    "balance_sheet", "contra_revenue", "cost_of_sales", "income_tax",
    "nonoperating", "operating_expense", "revenue", "revenue_mix", "unknown",
}


def metrics(case, period):
    return {fact["metric"]: Decimal(str(fact["value"]))
            for fact in case[period]["facts"]}


def validate():
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    cases = corpus["cases"]
    assert {case["case_id"] for case in cases} == EXPECTED_CASES
    seen_ids = set()
    for case in cases:
        assert case["workflow"] == "sec_event_to_thesis_review"
        assert len(case["precommitted_checks"]) >= 3
        for period in ("baseline", "event"):
            item = case[period]
            parsed = urlparse(item["source_url"])
            assert parsed.scheme == "https" and parsed.netloc == "www.sec.gov"
            assert parsed.path.startswith("/Archives/edgar/data/")
            assert item["as_of"] and item["period"]
            assert len(item["facts"]) == len({f["metric"] for f in item["facts"]})
            for fact in item["facts"]:
                assert fact["id"] not in seen_ids, fact["id"]
                seen_ids.add(fact["id"])
                assert fact["metric"] and fact["unit"] and fact["locator"]
                assert fact["statement_line"] in PLUGIN_STATEMENT_LINES
                if (fact["metric"].startswith("gaap_operating_income_loss")
                        or fact["metric"] == "gaap_net_income_loss"):
                    assert fact["statement_line"] == "unknown"
            if corpus["status"] == "sec_web_checked_raw_cache_pending_no_model_observations":
                assert item["source_sha256"] is None and item["local_path"] is None
            else:
                assert isinstance(item["source_sha256"], str)
                assert len(item["source_sha256"]) == 64
                assert isinstance(item["local_path"], str)
                path = HERE / item["local_path"]
                assert path.is_file(), path

    by_id = {case["case_id"]: case for case in cases}
    a0, a1 = (metrics(by_id["AFRM-FISCAL-COST"], p) for p in ("baseline", "event"))
    assert a0["gaap_total_revenue_net"] - a0["transaction_costs_non_gaap"] == a0["revenue_less_transaction_costs_non_gaap"]
    assert a1["gaap_total_revenue_net"] - a1["transaction_costs_non_gaap"] == a1["revenue_less_transaction_costs_non_gaap"]
    assert a1["gaap_total_revenue_net"] - a0["gaap_total_revenue_net"] == 39294
    assert a1["revenue_less_transaction_costs_non_gaap"] - a0["revenue_less_transaction_costs_non_gaap"] == -24271
    assert a1["transaction_costs_non_gaap"] - a0["transaction_costs_non_gaap"] == 63565
    assert a1["gaap_operating_income_loss"] - a0["gaap_operating_income_loss"] == -59163
    assert a1["adjusted_operating_income_non_gaap"] - a0["adjusted_operating_income_non_gaap"] == -20218
    assert a1["provision_for_credit_losses"] - a0["provision_for_credit_losses"] == 42215
    assert a1["funding_costs"] - a0["funding_costs"] == 8889

    s0, s1 = (metrics(by_id["SOFI-REVENUE-BRIDGE"], p) for p in ("baseline", "event"))
    assert s1["gaap_total_net_revenue"] - s0["gaap_total_net_revenue"] == 98503
    assert s1["adjusted_net_revenue_non_gaap"] - s0["adjusted_net_revenue_non_gaap"] == 92480
    assert s1["gaap_net_income_loss"] - s0["gaap_net_income_loss"] == 43341
    assert (s1["gaap_total_net_revenue"] + s1["servicing_rights_valuation_adjustment"]
            + s1["residual_interests_valuation_adjustment"]
            + s1["gain_on_extinguishment_adjustment"]) == s1["adjusted_net_revenue_non_gaap"]
    assert s1["gaap_total_net_revenue"] - s1["adjusted_net_revenue_non_gaap"] == 7676

    u0, u1 = (metrics(by_id["UPST-MIXED-BASIS"], p) for p in ("baseline", "event"))
    assert u1["gaap_total_revenue"] - u0["gaap_total_revenue"] == 34510
    assert u1["gaap_net_income_loss"] - u0["gaap_net_income_loss"] == 47712
    assert u1["gaap_net_income_loss"] < 0
    assert u1["gain_on_debt_extinguishment"] == 33361
    assert next(fact for fact in by_id["UPST-MIXED-BASIS"]["event"]["facts"]
                if fact["metric"] == "gain_on_debt_extinguishment")["statement_line"] == "nonoperating"
    assert u1["gaap_net_income_loss"] - u1["gain_on_debt_extinguishment"] == -40119
    assert u1["gaap_operating_income_loss"] > u0["gaap_operating_income_loss"]
    assert u1["gaap_operating_income_loss"] < u1["gaap_operating_income_loss_prior_year_same_quarter"]
    assert u1["adjusted_net_income_loss_non_gaap"] > u0["adjusted_net_income_loss_non_gaap"] / 1000
    assert u1["adjusted_net_income_loss_non_gaap"] < u1["adjusted_net_income_loss_prior_year_same_quarter_non_gaap"]
    return {"status": "packet_structure_and_arithmetic_ok", "cases": len(cases),
            "facts": len(seen_ids), "raw_sec_byte_preflight": "pending"}


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2))
