#!/usr/bin/env python3
"""Freeze NAVI EX-99.2 financial exhibits supplementing pointer EX-99.1."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

from fetch_sources import Source, fetch
from select_postcorrection_v4_remaining_pairs import select
from verify_postcorrection_v4_remaining_discovery import ROOT as DISCOVERY


HERE = Path(__file__).parent
PAIRS = HERE / "postcorrection_v4_remaining16_provisional_pairs.json"


def detailed_url(index_path: Path, accession: str, cik: str) -> str:
    source = index_path.read_text(errors="replace")
    prefix = f"/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/"
    found = []
    for row in re.findall(r"<tr\b[^>]*>.*?</tr>", source,
                          flags=re.IGNORECASE | re.DOTALL):
        if not re.search(r">\s*EX-99\.2\s*<", row, flags=re.IGNORECASE):
            continue
        for link in re.findall(r"href\s*=\s*['\"]([^'\"]+)['\"]", row,
                               flags=re.IGNORECASE):
            url = urljoin("https://www.sec.gov", html.unescape(link))
            parsed = urlparse(url)
            if (parsed.scheme == "https" and parsed.hostname == "www.sec.gov"
                    and parsed.path.startswith(prefix) and parsed.path.endswith(".htm")):
                found.append(url)
    found = sorted(set(found))
    if len(found) != 1:
        raise ValueError("NAVI filing has no unique detailed EX-99.2")
    return found[0]


def freeze(output_dir: Path, user_agent: str, delay: float = 0.75) -> dict:
    output_dir = output_dir.resolve()
    if not user_agent or "@" not in user_agent or delay < 0.25:
        raise ValueError("SEC contact User-Agent and conservative delay required")
    if output_dir.exists():
        raise ValueError("output directory exists; refusing overwrite")
    pairset = json.loads(PAIRS.read_text())
    if pairset != select():
        raise ValueError("provisional pair selection changed")
    pair = next(x for x in pairset["pairs"] if x["symbol"] == "NAVI")
    output_dir.mkdir(parents=True)
    entries = []
    for role in ("baseline", "event"):
        item = pair[role]
        index_path = (DISCOVERY / "raw" / "NAVI"
                      / f"{item['accession']}-index.html")
        if hashlib.sha256(index_path.read_bytes()).hexdigest() != item["index_sha256"]:
            raise ValueError("NAVI filing index hash changed")
        url = detailed_url(index_path, item["accession"], pair["cik"])
        source = Source(
            id=f"HOLDOUT-V4-NAVI-{role.upper()}-DETAIL",
            company="NAVI", symbol="NAVI", cik=pair["cik"],
            url=url, filed_at=item["filing_date"], accession=item["accession"],
            artifact=Path(urlparse(url).path).name, form="8-K",
            document_type="EX-99.2", episode=1 if role == "baseline" else 2,
        )
        time.sleep(delay)
        downloaded = fetch(source, output_dir, user_agent)
        if not 100_000 <= downloaded["bytes"] <= 10_000_000:
            raise ValueError("NAVI detailed financial exhibit size unexpected")
        downloaded.update({
            "role": role, "accession": item["accession"],
            "document_type": "EX-99.2", "index_sha256": item["index_sha256"],
            "source_relationship": "same 8-K as EX-99.1 pointer announcement",
            "status": "bytes_frozen_period_basis_and_rows_pending",
        })
        entries.append(downloaded)
        print(f"{source.id}: {downloaded['bytes']} bytes", flush=True)
    manifest = {
        "version": 4,
        "status": "navi_detailed_ex99_2_bytes_frozen_no_model_observations",
        "selection_sha256": hashlib.sha256(PAIRS.read_bytes()).hexdigest(),
        "model_observations": 0, "entries": entries,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n")
    hashes = [(path, hashlib.sha256(path.read_bytes()).hexdigest())
              for path in sorted(output_dir.iterdir()) if path.is_file()]
    (output_dir / "RESULT-SHA256.txt").write_text("".join(
        f"{digest}  {path.name}\n" for path, digest in hashes))
    return {"status": manifest["status"], "frozen_exhibits": len(entries),
            "model_observations": 0}


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output-dir", type=Path, required=True)
    cli.add_argument("--delay", type=float, default=0.75)
    args = cli.parse_args()
    print(json.dumps(freeze(args.output_dir,
                            os.environ.get("SEC_USER_AGENT", ""),
                            args.delay), indent=2))
