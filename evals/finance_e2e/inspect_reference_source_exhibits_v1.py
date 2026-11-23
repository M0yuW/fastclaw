#!/usr/bin/env python3
"""Read-only period-cue inspection of frozen SEC EX-99-family artifacts.

This does not qualify a source or extract/audit facts. It exposes human-readable
text so the selected period can be checked before any case is constructed.
"""

from __future__ import annotations

import argparse
import json
import re
from html.parser import HTMLParser
from pathlib import Path

from build_reference_source_distinct_frame_v1 import sha256


PERIOD_CUE = re.compile(
    r"(?:quarter|three months ended|six months ended|nine months ended|"
    r"june\s+30|september\s+30|jun\.?\s+30|sep\.?\s+30)",
    re.IGNORECASE,
)


class PlainText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self.skip += 1
        elif tag in {"p", "div", "tr", "br", "h1", "h2", "h3"}:
            self.parts.append("\n")
        elif tag in {"td", "th"}:
            self.parts.append(" | ")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self.skip = max(0, self.skip - 1)
        elif tag in {"p", "div", "tr", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.parts.append(data)

    def text(self) -> str:
        return re.sub(r"[ \t]+", " ", "".join(self.parts))


def inspect(manifest_path: Path) -> list[dict]:
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("status") != "sec_exhibits_frozen_period_and_rows_unverified":
        raise ValueError("frozen artifact manifest status differs")
    output = []
    for item in manifest["artifacts"]:
        path = manifest_path.parent / item["path"]
        if sha256(path) != item["sha256"]:
            raise ValueError(f"source hash differs: {path}")
        parser = PlainText()
        parser.feed(path.read_text(errors="replace"))
        body = re.sub(r"\s+", " ", parser.text())
        cues = []
        for match in PERIOD_CUE.finditer(body[:25000]):
            snippet = body[max(0, match.start() - 45):match.end() + 90]
            if snippet not in cues:
                cues.append(snippet)
            if len(cues) >= 6:
                break
        output.append({"symbol": item["symbol"],
                       "period_window": item["period_window"],
                       "filing_date": item["filing_date"],
                       "source_url": item["url"],
                       "body_opening": body[:350],
                       "period_cues": cues,
                       "status": "text_cues_only_not_fact_audit"})
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(inspect(args.manifest), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
