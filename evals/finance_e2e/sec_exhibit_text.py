#!/usr/bin/env python3
"""Readable local view of a frozen SEC HTML exhibit; source bytes remain authoritative."""

from __future__ import annotations

import argparse
import re
from html.parser import HTMLParser
from pathlib import Path


class ExhibitText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.suppressed = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style"}:
            self.suppressed += 1
        elif tag in {"p", "tr", "br", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self.suppressed = max(0, self.suppressed - 1)
        elif tag in {"td", "th"}:
            self.parts.append("\t")
        elif tag in {"p", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.suppressed:
            self.parts.append(data)

    def lines(self) -> list[str]:
        rendered = "".join(self.parts).replace("\xa0", " ")
        return [line for raw in rendered.splitlines()
                if (line := re.sub(r"[ \t]+", " ", raw).strip())]


def extract_lines(path: Path) -> list[str]:
    parser = ExhibitText()
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    return parser.lines()


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("path", type=Path)
    cli.add_argument("--match", default="")
    cli.add_argument("--context", type=int, default=1)
    cli.add_argument("--max-hits", type=int, default=5)
    args = cli.parse_args()
    lines = extract_lines(args.path)
    hits = 0
    for i, line in enumerate(lines):
        if args.match.lower() in line.lower():
            for j in range(max(0, i - args.context), min(len(lines), i + args.context + 1)):
                print(f"{j + 1}: {lines[j]}")
            print()
            hits += 1
            if hits >= args.max_hits:
                break
