from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from pypdf import PdfReader


REPORT_DIR = Path(__file__).resolve().parent
SOURCE_PATH = REPORT_DIR / "fastclaw_project_report.md"


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def source_headings() -> list[str]:
    return [
        line[2:].strip()
        for line in SOURCE_PATH.read_text(encoding="utf-8").splitlines()
        if line.startswith("# ")
    ]


def source_table_count() -> int:
    return sum(
        1
        for line in SOURCE_PATH.read_text(encoding="utf-8").splitlines()
        if line.startswith("TABLE_CAPTION:")
    )


def extract_page_map(pdf_path: Path) -> dict[str, int]:
    reader = PdfReader(pdf_path)
    pages = [normalized(page.extract_text() or "") for page in reader.pages]
    body_pages = pages[4:]
    result: dict[str, int] = {}

    for heading in source_headings():
        for offset, text in enumerate(body_pages, start=5):
            if heading in text:
                result[f"heading::{heading}"] = offset
                break

    for figure_number in range(1, 5):
        marker = f"Fig. {figure_number}."
        for offset, text in enumerate(body_pages, start=5):
            if marker in text:
                result[f"figure::FIGURE_{figure_number}"] = offset
                break

    for table_number in range(1, source_table_count() + 1):
        marker = f"Table {roman(table_number)}."
        for offset, text in enumerate(body_pages, start=5):
            if marker in text:
                result[f"table::{table_number}"] = offset
                break

    result["pages"] = len(pages)
    return result


def roman(number: int) -> str:
    values = (
        (10, "X"),
        (9, "IX"),
        (5, "V"),
        (4, "IV"),
        (1, "I"),
    )
    output = ""
    remaining = number
    for value, numeral in values:
        while remaining >= value:
            output += numeral
            remaining -= value
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract stable body page numbers for report front matter.")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    page_map = extract_page_map(args.pdf)
    args.output.write_text(json.dumps(page_map, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
