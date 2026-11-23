#!/usr/bin/env python3
"""Build source-audited v4 event fixtures without contacting a model.

The material is an intentionally selected extract, not a complete filing.
It provides types and checked arithmetic but no prewritten investment view.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

import audit_postcorrection_v4_source_identity as source_audit


HERE = Path(__file__).resolve().parent
FIRST_FOUR = ("WEX", "HBAN", "VRSK", "NTRS")
FIRST_PACKETS = {symbol: HERE / f"{symbol.lower()}_v4_source_fact_packet.json"
                 for symbol in FIRST_FOUR}
DECLARED_PACKETS = {
    symbol: HERE / f"{symbol.lower()}_v4_declared_source_packet.json"
    for symbol in ("SEIC", "MKTX", "FDS", "RELY", "CPAY", "TFC", "FITB",
                   "USB", "C", "FLYW", "EVTC", "SPGI", "TRU", "NAVI",
                   "RKT", "LPLA")
}
MANIFEST_DIRS = (source_audit.FIRST, source_audit.WEX,
                 source_audit.REMAINING, source_audit.NAVI_DETAIL)


def watchlist_keyword(symbol: str) -> str:
    # Finance-tools ignores one-character keywords; C is Citigroup in this frame.
    return "Citigroup" if symbol == "C" else symbol


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _number(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _first_unit(symbol: str, metric: str) -> str:
    if metric.endswith("_usd_billion") or metric == "reported_total_volume_usd_billion":
        return "USD_billion"
    if metric.endswith("_percent"):
        return "percent"
    if "eps" in metric:
        return "USD_per_share"
    if symbol == "HBAN" and metric in ("average_earning_assets", "average_loans_and_leases",
                                        "average_total_deposits"):
        return "USD_million"
    return "USD_million"


def _first_basis(metric: str) -> str:
    if metric.startswith("non_gaap_") or metric.startswith("fte_"):
        return "non_GAAP"
    if metric.startswith("reported_") or metric.startswith("average_"):
        return "reported_operating"
    return "GAAP"


def _normalize(symbol: str, packet: dict) -> dict:
    if symbol in FIRST_FOUR:
        facts = {}
        for role in ("baseline", "event"):
            facts[role] = {
                name: {"value": str(value), "unit": _first_unit(symbol, name),
                       "basis": _first_basis(name)}
                for name, value in packet[role]["facts"].items()
            }
        return {"facts": facts, "identities": [], "extra": {
            role: packet[role].get("guidance", {}) for role in ("baseline", "event")}}
    facts = {}
    for role in ("baseline", "event"):
        facts[role] = {
            item["metric"]: {"value": str(item["value"]), "unit": item["unit"],
                             "basis": item["basis"]}
            for item in packet[role]["facts"]
        }
    return {"facts": facts, "identities": packet["identities"], "extra": {}}


def _source_index() -> dict[str, dict]:
    entries = {}
    for directory in MANIFEST_DIRS:
        manifest = json.loads((directory / "manifest.json").read_text())
        for entry in manifest["entries"]:
            if entry["id"] in entries:
                raise ValueError(f"duplicate source ID: {entry['id']}")
            entries[entry["id"]] = entry
    return entries


def _source_ref(section: dict, entries: dict[str, dict]) -> tuple[dict, str]:
    entry = entries[section["source_id"]]
    if section["source_sha256"] != entry["sha256"]:
        raise ValueError("source packet hash differs from frozen exhibit")
    filed = entry.get("filing_date") or entry.get("filed_at")
    if not filed and entry["id"].endswith("-DETAIL"):
        primary = entries[entry["id"].removesuffix("-DETAIL")]
        if primary["accession"] != entry["accession"]:
            raise ValueError("detailed exhibit filing accession differs")
        filed = primary.get("filing_date") or primary.get("filed_at")
    if not filed:
        raise ValueError("source filing date missing")
    return {"id": entry["id"], "url": entry["url"],
            "sha256": entry["sha256"]}, filed


def _fact_line(name: str, fact: dict) -> str:
    return f"{name}={fact['value']} {fact['unit']} [{fact['basis']}]"


def _matched_identities(normalized: dict) -> list[str]:
    """Render only signed identities checked in both quarters by the auditor."""
    by_role = {role: {} for role in ("baseline", "event")}
    for item in normalized["identities"]:
        components = tuple((part["metric"], part["sign"])
                           for part in item["components"])
        by_role[item["role"]][(item["total"], components)] = item
    common = by_role["baseline"].keys() & by_role["event"].keys()
    rendered = []
    facts = normalized["facts"]
    for total, components in sorted(common):
        names = [total, *(name for name, _ in components)]
        if any(name not in facts[role] for role in ("baseline", "event") for name in names):
            raise ValueError("audited identity references omitted prompt fact")
        unit = facts["baseline"][total]["unit"]
        if (facts["event"][total]["unit"] != unit or any(
                facts[role][name]["unit"] != unit
                for role in ("baseline", "event") for name in names)):
            raise ValueError("audited identity mixes units")
        delta_total = (Decimal(facts["event"][total]["value"])
                       - Decimal(facts["baseline"][total]["value"]))
        contributions = []
        for name, sign in components:
            delta = (Decimal(facts["event"][name]["value"])
                     - Decimal(facts["baseline"][name]["value"])) * sign
            contributions.append(("+" if delta >= 0 else "−") + _number(abs(delta))
                                 + f" ({name})")
        baseline_tolerance = Decimal(str(by_role["baseline"][(total, components)].get(
            "tolerance", "0")))
        event_tolerance = Decimal(str(by_role["event"][(total, components)].get(
            "tolerance", "0")))
        residual = delta_total - sum((Decimal(facts["event"][name]["value"])
                                      - Decimal(facts["baseline"][name]["value"])) * sign
                                     for name, sign in components)
        if abs(residual) > baseline_tolerance + event_tolerance:
            raise ValueError("signed change exceeds source rounding tolerance")
        qualifier = ("exact" if residual == 0 and baseline_tolerance == event_tolerance == 0
                     else f"displayed-value residual {_number(residual)}; rounding tolerance "
                          f"at most {_number(baseline_tolerance + event_tolerance)}")
        rendered.append(f"{total} change {_number(delta_total)} {unit}: "
                        + " ".join(contributions) + f"; {qualifier}.")
    return rendered


def fixture(symbol: str, packet: dict, entries: dict[str, dict]) -> dict:
    normalized = _normalize(symbol, packet)
    before, after = normalized["facts"]["baseline"], normalized["facts"]["event"]
    common = before.keys() & after.keys()
    for name in common:
        if (before[name]["unit"], before[name]["basis"]) != (
                after[name]["unit"], after[name]["basis"]):
            raise ValueError(f"quarterly fact basis/unit changed: {symbol} {name}")
    before_ref, _ = _source_ref(packet["baseline"], entries)
    after_ref, filed = _source_ref(packet["event"], entries)
    before_lines = [_fact_line(name, before[name]) for name in sorted(before)]
    after_lines = [_fact_line(name, after[name]) for name in sorted(after)]
    delta_lines = []
    for name in sorted(common):
        value = Decimal(after[name]["value"]) - Decimal(before[name]["value"])
        delta_lines.append(f"{name}: {_number(value)} {before[name]['unit']} "
                           f"[{before[name]['basis']}] event-minus-baseline change")
    identity_lines = _matched_identities(normalized)
    guidance = normalized["extra"]
    context = (f"Source-bounded {symbol} comparison; {packet['baseline']['period']} "
               f"versus {packet['event']['period']}. These are selected SEC rows, "
               "not complete filings. All changes are sequential, not year over year. "
               "Signed accounting identities are not economic causal explanations.\n"
               + "Baseline selected facts:\n" + "\n".join(before_lines)
               + "\nEvent selected facts:\n" + "\n".join(after_lines)
               + "\nDisplayed-value comparisons (host-computed, same basis):\n"
               + "\n".join(delta_lines))
    if identity_lines:
        context += "\nSource-audited signed accounting bridges:\n" + "\n".join(identity_lines)
    if guidance:
        for role in ("baseline", "event"):
            for name, bounds in sorted(guidance.get(role, {}).items()):
                context += (f"\n{role} filing forward guidance, not realized actual: "
                            f"{name}={bounds}")
    observed = {
        name: {"value": item["value"], "unit": item["unit"],
               "fact_id": f"V4-{symbol}-Q3-{name}"}
        for name, item in after.items() if item["basis"] != "forward_guidance"
    }
    seed = {
        "market": "US", "symbol": symbol,
        "title": f"{symbol} source-bounded earnings thesis",
        "thesis": (f"Baseline {packet['baseline']['period']}: "
                   + "; ".join(before_lines)
                   + ". Review the next filing for changes, counterevidence and missing "
                     "context. No valuation or trading conclusion is established."),
        "status": "active", "conviction": 3,
        "required_event_metrics": sorted(observed), "evidence": [before_ref],
    }
    event = {
        "external_id": f"HOLDOUT-V4-{symbol}-EVENT", "type": "earnings",
        "as_of": filed,
        "summary": (f"{symbol} Citigroup" if symbol == "C" else symbol)
                   + f" {packet['event']['period']} selected SEC facts: "
                   + "; ".join(after_lines),
        "sources": [after_ref], "observed_metrics": observed,
    }
    return {"case_id": packet["case_id"], "runtime_symbol": symbol,
            "seed_thesis": seed, "event": event, "numeric_context": context,
            "packet_sha256": _digest(FIRST_PACKETS.get(symbol)
                                     or DECLARED_PACKETS[symbol]),
            "bridge_count": len(identity_lines)}


def preflight() -> dict:
    audit = source_audit.audit()
    if audit["issuer_pairs"] != 20 or audit["numeric_row_audits_complete"] != 20:
        raise ValueError("all 20 source pairs must pass numeric audits")
    entries = _source_index()
    fixtures = []
    for symbol, path in {**FIRST_PACKETS, **DECLARED_PACKETS}.items():
        packet = json.loads(path.read_text())
        if packet.get("model_observations") != 0 or packet.get("paid_calls_authorized") is not False:
            raise ValueError("v4 source packet is not pre-observation material")
        fixtures.append(fixture(symbol, packet, entries))
    if len(fixtures) != 20 or len({item["case_id"] for item in fixtures}) != 20:
        raise ValueError("v4 fixture count/identity differs")
    return {"status": "source_audited_v4_fixtures_no_model_observations",
            "ready_cases": len(fixtures), "selected_source_cases": 20,
            "rendered_signed_bridges": sum(item["bridge_count"] for item in fixtures),
            "model_observations": 0, "paid_calls_authorized": False,
            "fixtures": fixtures}


def review_prompt(fixture: dict, thesis_id: str, alert_id: str) -> str:
    return (
        "Historical source-bounded SEC research-state evaluation, not a trade request. "
        "Read the stored thesis and earnings alert using finance tools. The numeric "
        "context is host-checked selected-source arithmetic, not a complete filing or "
        "economic explanation. Distinguish sequential from year-over-year, GAAP from "
        "non-GAAP, guidance from realized results, percentage points from percent, "
        "and accounting identities from causal drivers. Form your own conclusion with "
        "a supported implication, material counterevidence, missing evidence and "
        "research-state decision. Do not claim that an item is absent from the full "
        "filing solely because it is absent from this extract. Persist one source-linked "
        "version-protected review, acknowledge the alert, and verify that any "
        "needs_review decision leaves the thesis blocked. Do not trade.\n\n"
        + fixture["numeric_context"] + "\n\n"
        + f"Case {fixture['case_id']}; thesis ID {thesis_id}; alert ID {alert_id}."
    )


if __name__ == "__main__":
    prepared = preflight()
    print(json.dumps({key: value for key, value in prepared.items()
                      if key != "fixtures"}, ensure_ascii=False, indent=2))
