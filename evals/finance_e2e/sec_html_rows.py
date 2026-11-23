"""Extract row/cell text from frozen SEC HTML exhibits for source audits."""

from __future__ import annotations

import argparse
import re
from html.parser import HTMLParser
from pathlib import Path


class _Rows(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self.row: list[str] | None = None
        self.cell: list[str] | None = None
        self.suppressed = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style"}:
            self.suppressed += 1
        elif tag == "tr":
            self.row = []
        elif tag in {"td", "th"} and self.row is not None:
            self.cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self.suppressed = max(0, self.suppressed - 1)
        elif tag in {"td", "th"} and self.row is not None and self.cell is not None:
            value = re.sub(r"\s+", " ", "".join(self.cell).replace("\xa0", " ")).strip()
            self.row.append(value)
            self.cell = None
        elif tag == "tr" and self.row is not None:
            if any(self.row):
                self.rows.append(self.row)
            self.row = None

    def handle_data(self, data: str) -> None:
        if self.cell is not None and not self.suppressed:
            self.cell.append(data)


def extract_rows(path: Path) -> list[list[str]]:
    parser = _Rows()
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    return parser.rows


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("path", type=Path)
    cli.add_argument("--match", required=True)
    cli.add_argument("--max-hits", type=int, default=8)
    args = cli.parse_args()
    hits = 0
    for i, row in enumerate(extract_rows(args.path)):
        if args.match.lower() in " ".join(row).lower():
            print(f"{i}: {row}")
            hits += 1
            if hits >= args.max_hits:
                break
