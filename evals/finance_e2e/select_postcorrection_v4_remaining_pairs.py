#!/usr/bin/env python3
"""Select provisional adjacent SEC earnings exhibits before any model output.

EX-99.1 is standard. A single EX-99 whose linked filename identifies an
earnings release is allowed under the same public-source rule; this handles
SPGI's Q3 2025 filing without reclassifying it as a model failure.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from verify_postcorrection_v4_remaining_discovery import MANIFEST, ROOT, verify_discovery


def fallback_ex99(index_html: str, accession: str, cik: str) -> list[str]:
    prefix = f"/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/"
    found = []
    for row in re.findall(r"<tr\b[^>]*>.*?</tr>", index_html,
                          flags=re.IGNORECASE | re.DOTALL):
        if not re.search(r">\s*EX-99\s*<", row, flags=re.IGNORECASE):
            continue
        for link in re.findall(r"href\s*=\s*['\"]([^'\"]+)['\"]", row,
                               flags=re.IGNORECASE):
            url = urljoin("https://www.sec.gov", html.unescape(link))
            parsed = urlparse(url)
            if (parsed.scheme == "https" and parsed.hostname == "www.sec.gov"
                    and parsed.path.startswith(prefix)
                    and "earningsrelease" in Path(parsed.path).name.lower()):
                found.append(url)
    return sorted(set(found))


def select() -> dict:
    verify_discovery()
    discovery = json.loads(MANIFEST.read_text())
    pairs = []
    for issuer in discovery["issuers"]:
        chosen = []
        for filing in issuer["candidate_filings"][:2]:
            urls = filing["ex99_1_urls"]
            kind = "EX-99.1"
            if not urls:
                source = (ROOT / filing["index_path"]).read_text(errors="replace")
                urls = fallback_ex99(source, filing["accession"], issuer["cik"])
                kind = "EX-99"
            if len(urls) != 1:
                raise ValueError(f"{issuer['symbol']}: no unique quarterly earnings exhibit")
            chosen.append({"filing_date": filing["filing_date"],
                           "accession": filing["accession"],
                           "index_url": filing["index_url"],
                           "index_sha256": filing["index_sha256"],
                           "document_type": kind, "url": urls[0]})
        if chosen[0]["filing_date"] <= chosen[1]["filing_date"]:
            raise ValueError("discovery order is not newest first")
        pairs.append({"symbol": issuer["symbol"], "cik": issuer["cik"],
                      "baseline": chosen[1], "event": chosen[0],
                      "status": "provisional_period_basis_and_rows_unverified"})
    return {"version": 4,
            "status": "remaining16_provisional_source_pairs_before_model_output",
            "selection_rule": "Latest two archived 2025 Item 2.02 filings with exactly one EX-99.1 earnings exhibit, or exactly one EX-99 earningsrelease filename when no EX-99.1 is listed; period, basis and rows require independent source audit.",
            "discovery_manifest_sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
            "model_observations": 0, "paid_calls_authorized": False,
            "pairs": pairs}


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    if args.output.exists():
        raise ValueError("selection output exists; refusing overwrite")
    result = select()
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"],
                      "pairs": len(result["pairs"]),
                      "ex99_exception": [p["symbol"] for p in result["pairs"]
                                         if p["event"]["document_type"] == "EX-99"],
                      "model_observations": 0}, indent=2))


if __name__ == "__main__":
    main()
