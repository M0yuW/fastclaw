"""Extract a source-displayed one-decimal current-quarter SEC table cell."""

from __future__ import annotations

import re
from decimal import Decimal


DECIMAL = re.compile(r"(?<![A-Za-z])\(?-?\d[\d,]*\.\d\)?")


def first_decimal_column(lines: list[str], *, start_anchor: str,
                         end_anchor: str, row_label: str,
                         header_fragments: tuple[str, ...],
                         min_columns: int = 4) -> Decimal:
    starts = [i for i, line in enumerate(lines) if start_anchor in line]
    if len(starts) != 1:
        raise ValueError(f"decimal table start missing or ambiguous: {start_anchor}")
    start = starts[0]
    stop = next((i for i in range(start + 1, len(lines)) if end_anchor in lines[i]), None)
    if stop is None:
        raise ValueError(f"decimal table end missing: {end_anchor}")
    header = " ".join(lines[start:min(start + 6, stop)]).lower()
    if any(fragment.lower() not in header for fragment in header_fragments):
        raise ValueError(f"decimal table header mismatch: {row_label}")
    rows = [line for line in lines[start:stop]
            if line.startswith(row_label + " ")
            and line[len(row_label):].lstrip().startswith(("$", "(", "-", *"0123456789"))]
    if len(rows) != 1:
        raise ValueError(f"decimal table row missing or ambiguous: {row_label}")
    cells = DECIMAL.findall(rows[0][len(row_label):])
    if len(cells) < min_columns:
        raise ValueError(f"decimal table row has too few columns: {row_label}")
    raw = cells[0].replace(",", "")
    if raw.startswith("(") and raw.endswith(")"):
        raw = "-" + raw[1:-1]
    value = Decimal(raw)
    if value.as_tuple().exponent != -1:
        raise ValueError(f"source value is not displayed to one decimal: {row_label}")
    return value
