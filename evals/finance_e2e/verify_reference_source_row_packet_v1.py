#!/usr/bin/env python3
"""Verify locators, source hashes, quarterly headers, and typed row arithmetic.

This verifies a curated transcription against frozen SEC bytes; it does not
judge whether the selected metrics suffice for a useful financial insight.
"""

from __future__ import annotations

import argparse
import json
import re
from decimal import Decimal
from pathlib import Path

from lxml import html

from build_reference_source_distinct_frame_v1 import sha256
from run_thesis_event_panel import HERE, ROOT


NUMERIC_CORE = r"(?:\d[\d,]*(?:\.\d+)?|\.\d+)"
NUMERIC_CELL = re.compile(rf"\$?(?:-?{NUMERIC_CORE}|\({NUMERIC_CORE}\))")
OPEN_PAREN_NUMBER = re.compile(rf"\$?\({NUMERIC_CORE}")
PERCENT_CELL = re.compile(rf"-?{NUMERIC_CORE}%")
SPACE = re.compile(r"\s+")


def cells_for(path: Path, table_index: int, row_index: int,
              header_row_count: int = 9) -> tuple[list[str], list[str]]:
    tables = html.parse(str(path)).xpath("//table")
    if table_index >= len(tables):
        raise ValueError("table locator out of range")
    table = tables[table_index]
    rows = table.xpath(".//tr")
    if row_index >= len(rows):
        raise ValueError("row locator out of range")
    if (isinstance(header_row_count, bool) or not isinstance(header_row_count, int)
            or not 1 <= header_row_count <= 20):
        raise ValueError("header row count invalid")
    header = [SPACE.sub(" ", " ".join(node.itertext())).strip()
              for tr in rows[:header_row_count] for node in tr.xpath("./th|./td")]
    cells = [SPACE.sub(" ", " ".join(node.itertext())).strip()
             for node in rows[row_index].xpath("./th|./td")]
    return header, cells


def number_after_label(cells: list[str], label: str, index: int,
                       allow_percent_cells: bool = False) -> Decimal:
    matches = [i for i, cell in enumerate(cells) if cell.casefold() == label.casefold()]
    if len(matches) != 1:
        raise ValueError(f"source row label absent or repeated: {label}")
    if not isinstance(index, int) or isinstance(index, bool) or index < 0:
        raise ValueError("numeric column index invalid")
    numbers = []
    trailing = cells[matches[0] + 1:]
    for position, cell in enumerate(trailing):
        if NUMERIC_CELL.fullmatch(cell) or (allow_percent_cells and PERCENT_CELL.fullmatch(cell)):
            numbers.append(cell)
        elif (OPEN_PAREN_NUMBER.fullmatch(cell)
              and position + 1 < len(trailing)
              and trailing[position + 1] == ")"):
            numbers.append(cell + ")")
    if index >= len(numbers):
        raise ValueError(f"source row numeric column out of range: {label}")
    cell = numbers[index]
    currency_free = cell.removeprefix("$")
    value = currency_free.strip("()%").replace(",", "")
    return -Decimal(value) if currency_free.startswith("(") else Decimal(value)


def locator_for(row: dict, field: str, period: str) -> int:
    by_period = row.get(f"{field}_by_period")
    if by_period is not None:
        if not isinstance(by_period, dict) or set(by_period) != {"CY2025_Q2", "CY2025_Q3"}:
            raise ValueError(f"per-period {field} locators incomplete")
        value = by_period[period]
    else:
        value = row.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} locator invalid")
    return value


def label_for(row: dict, period: str) -> str:
    by_period = row.get("source_label_by_period")
    if by_period is not None:
        if not isinstance(by_period, dict) or set(by_period) != {"CY2025_Q2", "CY2025_Q3"}:
            raise ValueError("per-period source labels incomplete")
        label = by_period[period]
    else:
        label = row.get("source_label")
    if not isinstance(label, str) or not label.strip():
        raise ValueError("source label missing")
    return label


def period_header_tokens_for(packet: dict, row: dict, period: str) -> list[str]:
    by_period = row.get("period_headers_by_period")
    if by_period is not None:
        if not isinstance(by_period, dict) or set(by_period) != {"CY2025_Q2", "CY2025_Q3"}:
            raise ValueError("per-row period headers incomplete")
        tokens = by_period[period]
    else:
        tokens = packet["period_headers"][period]
    if not isinstance(tokens, list) or not tokens or any(
            not isinstance(token, str) or not token.strip() for token in tokens):
        raise ValueError("period header tokens invalid")
    return tokens


def verify(packet_path: Path) -> dict:
    packet = json.loads(packet_path.read_text())
    if packet.get("model_observations") != 0 or packet.get("quality_pass") is not None:
        raise ValueError("source row packet cannot assert model quality")
    selection_path = HERE / packet["source_pair_selection"]
    selection = json.loads(selection_path.read_text())
    pairs = [item for item in selection["pairs"] if item["symbol"] == packet["symbol"]]
    if len(pairs) != 1:
        raise ValueError("source pair symbol missing or duplicated")
    pair = pairs[0]
    parsed = {}
    for period, source in pair["periods"].items():
        path = ROOT / source["local_path"]
        if sha256(path) != source["sha256"]:
            raise ValueError(f"source hash differs: {path}")
        parsed[period] = path
    checked = []
    for row in packet["rows"]:
        if not isinstance(row.get("allow_percent_cells", False), bool):
            raise ValueError("allow_percent_cells invalid")
        values = {}
        for period, field in (("CY2025_Q2", "baseline_value"),
                              ("CY2025_Q3", "event_value")):
            header, cells = cells_for(
                parsed[period], locator_for(row, "table_index", period),
                locator_for(row, "row_index", period), row.get("header_row_count", 9))
            for token in period_header_tokens_for(packet, row, period):
                if not any(token.casefold() in item.casefold() for item in header):
                    raise ValueError(f"period header absent: {period} {token}")
            indexes = row.get("numeric_value_index_by_period")
            if indexes is not None and set(indexes) != {"CY2025_Q2", "CY2025_Q3"}:
                raise ValueError("per-period numeric column indexes incomplete")
            index = (indexes[period] if indexes is not None
                     else row.get("numeric_value_index", 0))
            actual = number_after_label(cells, label_for(row, period), index,
                                        row.get("allow_percent_cells", False))
            if actual != Decimal(row[field]):
                raise ValueError(f"transcribed row differs: {row['id']} {period}")
            values[period] = actual
        if values["CY2025_Q3"] - values["CY2025_Q2"] != Decimal(row["delta_value"]):
            raise ValueError(f"signed difference differs: {row['id']}")
        checked.append(row["id"])
    if len(checked) != len(set(checked)):
        raise ValueError("duplicate row ID")
    event_only_checked = []
    for row in packet.get("event_only_rows", []):
        if not isinstance(row.get("allow_percent_cells", False), bool):
            raise ValueError("allow_percent_cells invalid")
        period = "CY2025_Q3"
        header, cells = cells_for(
            parsed[period], locator_for(row, "table_index", period),
            locator_for(row, "row_index", period), row.get("header_row_count", 9))
        for token in period_header_tokens_for(packet, row, period):
            if not any(token.casefold() in item.casefold() for item in header):
                raise ValueError(f"period header absent: {period} {token}")
        actual = number_after_label(cells, label_for(row, period),
                                    row.get("numeric_value_index", 0),
                                    row.get("allow_percent_cells", False))
        if actual != Decimal(row["event_value"]):
            raise ValueError(f"event-only transcribed row differs: {row['id']}")
        event_only_checked.append(row["id"])
    baseline_only_checked = []
    for row in packet.get("baseline_only_rows", []):
        period = "CY2025_Q2"
        if not isinstance(row.get("allow_percent_cells", False), bool):
            raise ValueError("allow_percent_cells invalid")
        header, cells = cells_for(
            parsed[period], locator_for(row, "table_index", period),
            locator_for(row, "row_index", period), row.get("header_row_count", 9))
        for token in period_header_tokens_for(packet, row, period):
            if not any(token.casefold() in item.casefold() for item in header):
                raise ValueError(f"period header absent: {period} {token}")
        actual = number_after_label(cells, label_for(row, period),
                                    row.get("numeric_value_index", 0),
                                    row.get("allow_percent_cells", False))
        if actual != Decimal(row["baseline_value"]):
            raise ValueError(f"baseline-only transcribed row differs: {row['id']}")
        baseline_only_checked.append(row["id"])
    if (len(event_only_checked) != len(set(event_only_checked))
            or len(baseline_only_checked) != len(set(baseline_only_checked))
            or set(checked) & set(event_only_checked)
            or set(checked) & set(baseline_only_checked)
            or set(event_only_checked) & set(baseline_only_checked)):
        raise ValueError("duplicate row ID")
    return {"symbol": packet["symbol"], "checked_rows": len(checked),
            "row_ids": checked, "event_only_checked_rows": len(event_only_checked),
            "event_only_row_ids": event_only_checked,
            "baseline_only_checked_rows": len(baseline_only_checked),
            "baseline_only_row_ids": baseline_only_checked,
            "source_pair_selection_sha256": sha256(selection_path),
            "model_observations": 0, "quality_pass": None,
            "status": "source_row_transcription_verified_not_insight_quality"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.packet), indent=2))


if __name__ == "__main__":
    main()
