"""Extract readable block text from frozen SEC HTML exhibits without network access."""

from __future__ import annotations

import argparse
import re
from html.parser import HTMLParser
from pathlib import Path


class _Blocks(HTMLParser):
    BREAKS = {"div", "p", "li", "tr", "h1", "h2", "h3", "br"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.suppressed = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style"}:
            self.suppressed += 1
        elif tag in self.BREAKS and not self.suppressed:
            self.parts.append("\n")
        elif tag in {"td", "th"} and not self.suppressed:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self.suppressed = max(0, self.suppressed - 1)
        elif tag in self.BREAKS and not self.suppressed:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.suppressed:
            self.parts.append(data)


def extract_blocks(path: Path) -> list[str]:
    parser = _Blocks()
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    return [line for raw in "".join(parser.parts).splitlines()
            if (line := re.sub(r"\s+", " ", raw).strip())]


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("path", type=Path)
    cli.add_argument("--match", default="")
    cli.add_argument("--max-hits", type=int, default=20)
    args = cli.parse_args()
    hits = 0
    for index, block in enumerate(extract_blocks(args.path)):
        if args.match.lower() in block.lower():
            print(f"{index}: {block}")
            hits += 1
            if hits >= args.max_hits:
                break
