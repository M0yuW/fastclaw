#!/usr/bin/env python3
"""Freeze 32 provisional public SEC earnings exhibits without model calls."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from urllib.parse import urlparse

from fetch_sources import Source, fetch
from select_postcorrection_v4_remaining_pairs import select


HERE = Path(__file__).parent
PAIRS = HERE / "postcorrection_v4_remaining16_provisional_pairs.json"


def secure_source(pair: dict, role: str) -> Source:
    item = pair[role]
    parsed = urlparse(item["url"])
    accession_compact = item["accession"].replace("-", "")
    prefix = f"/Archives/edgar/data/{int(pair['cik'])}/{accession_compact}/"
    if (parsed.scheme != "https" or parsed.hostname != "www.sec.gov"
            or not parsed.path.startswith(prefix) or not parsed.path.endswith(".htm")
            or item["document_type"] not in ("EX-99.1", "EX-99")):
        raise ValueError(f"{pair['symbol']} {role}: SEC source identity differs")
    if item["document_type"] == "EX-99" and pair["symbol"] != "SPGI":
        raise ValueError("EX-99 exception was not predeclared for this issuer")
    return Source(
        id=f"HOLDOUT-V4-{pair['symbol']}-{role.upper()}",
        company=pair["symbol"], symbol=pair["symbol"], cik=pair["cik"],
        url=item["url"], filed_at=item["filing_date"],
        accession=item["accession"], artifact=Path(parsed.path).name,
        form="8-K", document_type=item["document_type"],
        episode=1 if role == "baseline" else 2,
    )


def freeze(output_dir: Path, user_agent: str, delay: float = 0.75) -> dict:
    output_dir = output_dir.resolve()
    if not user_agent or "@" not in user_agent or delay < 0.25:
        raise ValueError("SEC contact User-Agent and conservative delay required")
    if output_dir.exists():
        raise ValueError("output directory exists; refusing overwrite")
    pairset = json.loads(PAIRS.read_text())
    expected = select()
    if (pairset != expected or pairset.get("paid_calls_authorized") is not False
            or len(pairset["pairs"]) != 16):
        raise ValueError("provisional pair selection or discovery hash differs")
    output_dir.mkdir(parents=True)
    entries = []
    for pair in pairset["pairs"]:
        for role in ("baseline", "event"):
            source = secure_source(pair, role)
            time.sleep(delay)
            downloaded = fetch(source, output_dir, user_agent)
            if downloaded["bytes"] > 10_000_000:
                raise ValueError(f"{source.id}: unexpectedly large SEC exhibit")
            downloaded.update({
                "role": role, "filing_date": pair[role]["filing_date"],
                "accession": pair[role]["accession"],
                "document_type": pair[role]["document_type"],
                "index_sha256": pair[role]["index_sha256"],
                "status": "bytes_frozen_period_basis_and_rows_pending",
            })
            entries.append(downloaded)
            print(f"{source.id}: {downloaded['bytes']} bytes", flush=True)
    manifest = {
        "version": 4,
        "status": "remaining16_sec_exhibit_bytes_frozen_no_model_observations",
        "selection_sha256": hashlib.sha256(PAIRS.read_bytes()).hexdigest(),
        "discovery_manifest_sha256": pairset["discovery_manifest_sha256"],
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
