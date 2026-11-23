"""Strict first-column extraction from a named section of SEC exhibit text.

This is only a mechanical aid. The fact packet must still declare the metric,
unit, reporting period, accounting basis and source locator before model output.
"""

from __future__ import annotations

import re


CELL = re.compile(r"(?<![A-Za-z])\(?-?\d[\d,]*(?:\.\d+)?\)?")


def numeric_cell(text: str) -> int:
    cleaned = text.replace(",", "").strip()
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = "-" + cleaned[1:-1]
    if not re.fullmatch(r"-?\d+", cleaned):
        raise ValueError(f"expected an integer-valued SEC table cell: {text!r}")
    return int(cleaned)


def first_column_value(lines: list[str], *, start_anchor: str, end_anchor: str,
                       row_label: str, header_fragments: tuple[str, ...],
                       min_columns: int = 3) -> int:
    starts = [i for i, line in enumerate(lines) if start_anchor in line]
    if len(starts) != 1:
        raise ValueError(f"source table start missing or ambiguous: {start_anchor}")
    start = starts[0]
    stop = next((i for i in range(start + 1, len(lines)) if end_anchor in lines[i]), None)
    if stop is None:
        raise ValueError(f"source table end missing: {end_anchor}")
    header = " ".join(lines[max(0, start - 3):min(stop, start + 7)]).lower()
    if any(fragment.lower() not in header for fragment in header_fragments):
        raise ValueError(f"source table column header mismatch: {row_label}")
    rows = [line for line in lines[start:stop]
            if line.startswith(row_label + " ")
            and line[len(row_label):].lstrip().startswith(("$", "(", "-", *"0123456789"))]
    if len(rows) != 1:
        raise ValueError(f"source row missing or ambiguous: {row_label}")
    tail = rows[0][len(row_label):]
    cells = CELL.findall(tail)
    if len(cells) < min_columns:
        raise ValueError(f"source row has too few numeric columns: {row_label}")
    return numeric_cell(cells[0])
