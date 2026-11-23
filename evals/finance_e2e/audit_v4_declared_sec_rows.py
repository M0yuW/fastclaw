#!/usr/bin/env python3
"""Audit explicitly declared rows in frozen, source-distinct SEC exhibits.

Each selected financial claim has a source row, cell, raw displayed text,
numeric interpretation, period, unit and basis. The program checks source
bytes/URL identity, exact row/cell matches and declared signed identities.
It never scores or contacts a model. A successful audit covers only selected
rows, not every financial statement disclosure in the exhibit.
"""

from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path

from audit_wex_v4_source_facts import SourceHTML
import rank_postcorrection_holdout_v2 as prior


HERE = Path(__file__).parent
SOURCE_DIR = HERE / "results/2026-10-24-postcorrection-v4-remaining16-exhibits"
MANIFEST = SOURCE_DIR / "manifest.json"
NAVI_DETAIL_DIR = HERE / "results/2026-10-24-postcorrection-v4-navi-detailed-exhibits"
NAVI_DETAIL_MANIFEST = NAVI_DETAIL_DIR / "manifest.json"
SELECTION = HERE / "postcorrection_v4_remaining16_provisional_pairs.json"
NUMBER = re.compile(r"^-?(?:(?:\d+(?:,\d{3})*|\d+)(?:\.\d+)?|\.\d+)$")


def parse_displayed(raw: str) -> Decimal:
    value = raw.strip().replace("$", "").replace(" ", "")
    if value in ("—", "–", "-"):
        return Decimal(0)
    negative = value.startswith("(") and value.endswith(")")
    if negative:
        value = value[1:-1]
    if not NUMBER.fullmatch(value):
        raise ValueError(f"selected source cell is not a plain number: {raw!r}")
    result = Decimal(value.replace(",", ""))
    return -result if negative else result


def verify_identity(packet: dict) -> tuple[dict[str, SourceHTML], dict[str, dict]]:
    symbol = packet.get("symbol")
    if (packet.get("version") != 4 or not isinstance(symbol, str)
            or packet.get("model_observations") != 0
            or packet.get("paid_calls_authorized") is not False
            or symbol in (set(prior.preflight()["selected_cik"])
                          | prior.observed_v1_symbols())):
        raise ValueError("not a source-distinct, source-only v4 candidate")
    candidates = json.loads(SELECTION.read_text())["pairs"]
    selected = next((item for item in candidates if item["symbol"] == symbol), None)
    if selected is None:
        raise ValueError("issuer not in preselected v4 source frame")
    manifest = json.loads(MANIFEST.read_text())
    navi_manifest = json.loads(NAVI_DETAIL_MANIFEST.read_text()) if symbol == "NAVI" else None
    sections, parsed = {}, {}
    for role in ("baseline", "event"):
        section = packet.get(role)
        if not isinstance(section, dict):
            raise ValueError(f"{role} packet section absent")
        detailed = symbol == "NAVI" and str(section.get("source_id", "")).endswith("-DETAIL")
        active_manifest = navi_manifest if detailed else manifest
        source_dir = NAVI_DETAIL_DIR if detailed else SOURCE_DIR
        entry = next((item for item in active_manifest["entries"]
                      if item["id"] == section.get("source_id")), None)
        if entry is None or entry["symbol"] != symbol or entry["role"] != role:
            raise ValueError(f"{role} source manifest identity differs")
        path = (HERE / entry["local_path"]).resolve()
        if path.parent != source_dir.resolve() or not path.is_file():
            raise ValueError(f"{role} source path differs")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        expected_url = selected[role]["url"]
        if detailed:
            accession_compact = selected[role]["accession"].replace("-", "")
            expected_prefix = f"https://www.sec.gov/Archives/edgar/data/1593538/{accession_compact}/"
            if (entry.get("accession") != selected[role]["accession"]
                    or entry.get("index_sha256") != selected[role]["index_sha256"]
                    or entry.get("document_type") != "EX-99.2"
                    or not entry["url"].startswith(expected_prefix)):
                raise ValueError(f"{role} NAVI detailed exhibit is not the same filing")
            expected_url = entry["url"]
        if (digest != entry["sha256"] or digest != section.get("source_sha256")
                or entry["url"] != expected_url):
            raise ValueError(f"{role} source bytes or SEC URL differ")
        html = SourceHTML()
        html.feed(path.read_text(errors="replace"))
        for anchor in section.get("anchors", []):
            row, cell, snippet = anchor["row"], anchor["cell"], anchor["contains"]
            if (not isinstance(row, int) or not isinstance(cell, int)
                    or row < 0 or cell < 0 or row >= len(html.rows)
                    or cell >= len(html.rows[row])
                    or snippet not in html.rows[row][cell]):
                raise ValueError(f"{role} source period/unit anchor differs")
        if not section.get("anchors"):
            raise ValueError(f"{role} source period/unit anchors absent")
        parsed[role], sections[role] = html, section
    return parsed, sections


def audit(packet: dict) -> dict:
    parsed, sections = verify_identity(packet)
    values = {}
    fact_meta = {}
    selected_rows = 0
    for role in ("baseline", "event"):
        facts = sections[role].get("facts")
        if not isinstance(facts, list) or not facts:
            raise ValueError(f"{role} selected facts absent")
        values[role] = {}
        fact_meta[role] = {}
        for fact in facts:
            metric = fact["metric"]
            index, cell = fact["row"], fact["cell"]
            if (metric in values[role] or not isinstance(index, int)
                    or not isinstance(cell, int) or index < 0 or cell < 0
                    or index >= len(parsed[role].rows)
                    or cell >= len(parsed[role].rows[index])):
                raise ValueError(f"{role} duplicate/invalid row locator: {metric}")
            row = parsed[role].rows[index]
            if row[0] != fact["label"] or row[cell] != fact["raw"]:
                raise ValueError(f"{role} selected source row/cell differs: {metric}")
            if (fact.get("basis") not in ("GAAP", "non_GAAP", "reported_operating", "forward_guidance")
                    or not str(fact.get("unit", "")).strip()):
                raise ValueError(f"{role} selected source basis/unit absent: {metric}")
            raw = row[cell]
            if "closing_cell" in fact:
                closing = fact["closing_cell"]
                if (not isinstance(closing, int) or closing < 0
                        or closing >= len(row) or row[closing] != ")"
                        or not raw.startswith("(") or raw.endswith(")")):
                    raise ValueError(f"{role} split negative cell differs: {metric}")
                raw += ")"
            observed = parse_displayed(raw)
            declared = Decimal(str(fact["value"]))
            if observed != declared:
                raise ValueError(f"{role} source numeric interpretation differs: {metric}")
            values[role][metric] = declared
            fact_meta[role][metric] = (fact["basis"], fact["unit"])
            selected_rows += 1

    comparators = 0
    for item in packet.get("cross_source_comparators", []):
        role, other, metric = item["source_role"], item["expected_role"], item["metric"]
        if role not in parsed or other not in values or metric not in values[other]:
            raise ValueError("cross-source comparator references unknown metric")
        index, cell = item["row"], item["cell"]
        if (not isinstance(index, int) or not isinstance(cell, int)
                or index < 0 or cell < 0 or index >= len(parsed[role].rows)
                or cell >= len(parsed[role].rows[index])):
            raise ValueError("cross-source comparator locator invalid")
        row = parsed[role].rows[index]
        if (row[0] != item["label"] or row[cell] != item["raw"]
                or parse_displayed(row[cell]) != values[other][metric]):
            raise ValueError(f"cross-source comparator differs: {metric}")
        comparators += 1

    ranges = 0
    for rule in packet.get("cross_source_ranges", []):
        bounds = values.get(rule["range_role"], {})
        actual = values.get(rule["actual_role"], {})
        try:
            lower = bounds[rule["lower_metric"]]
            upper = bounds[rule["upper_metric"]]
            observed = actual[rule["actual_metric"]]
        except KeyError as exc:
            raise ValueError("cross-source range references unknown metric") from exc
        relation = "below" if observed < lower else "above" if observed > upper else "within"
        lower_basis, lower_unit = fact_meta[rule["range_role"]][rule["lower_metric"]]
        upper_basis, upper_unit = fact_meta[rule["range_role"]][rule["upper_metric"]]
        _, actual_unit = fact_meta[rule["actual_role"]][rule["actual_metric"]]
        if (lower_basis != "forward_guidance" or upper_basis != "forward_guidance"
                or lower_unit != upper_unit or lower_unit != actual_unit
                or lower > upper or relation != rule["expected_relation"]):
            raise ValueError("cross-source guidance range differs")
        ranges += 1

    conversions = 0
    for rule in packet.get("unit_conversions", []):
        role = rule["role"]
        if (role not in values or rule["source_metric"] not in values[role]
                or rule["target_metric"] not in values[role]):
            raise ValueError("unit conversion references unknown metric")
        divisor = Decimal(str(rule["source_divisor"]))
        tolerance = Decimal(str(rule.get("tolerance", "0")))
        if (divisor <= 0 or tolerance < 0 or abs(
                values[role][rule["source_metric"]] / divisor
                - values[role][rule["target_metric"]]) > tolerance):
            raise ValueError(f"{role} source unit conversion differs")
        conversions += 1

    identities = 0
    for rule in packet.get("identities", []):
        role, total = rule["role"], rule["total"]
        if role not in values or total not in values[role]:
            raise ValueError("identity references unknown role/total")
        components = rule.get("components")
        if not isinstance(components, list) or not components:
            raise ValueError("identity has no components")
        derived = Decimal(0)
        for component in components:
            metric, sign = component["metric"], component["sign"]
            if metric not in values[role] or sign not in (-1, 1):
                raise ValueError("identity component/sign invalid")
            derived += values[role][metric] * sign
        tolerance = Decimal(str(rule.get("tolerance", "0")))
        if tolerance < 0 or abs(values[role][total] - derived) > tolerance:
            raise ValueError(f"{role} source-defined arithmetic differs: {total}")
        identities += 1
    if not identities:
        raise ValueError("source-defined arithmetic checks absent")
    return {
        "status": "selected_sec_rows_and_declared_arithmetic_audited",
        "symbol": packet["symbol"],
        "selected_source_rows": selected_rows,
        "cross_source_comparators": comparators,
        "cross_source_ranges": ranges,
        "unit_conversions": conversions,
        "declared_identities": identities,
        "model_observations": 0,
        "scope_limit": "selected rows only; no model answer or finance-quality rating",
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(json.loads(args.packet.read_text())), indent=2))
