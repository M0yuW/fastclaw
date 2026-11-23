#!/usr/bin/env python3
"""Download and hash eight preselected public SEC exhibits, no model calls.

This freezes bytes for later row/period/basis audit. It does not infer facts
from the exhibits or certify any future answer. Contact User-Agent is not saved.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from urllib.parse import urlparse

from fetch_sources import Source, fetch, validate_source


HERE = Path(__file__).parent
PAIRS = HERE / "postcorrection_v4_first4_sec_pairs.json"


def freeze(output_dir: Path, user_agent: str, delay: float = 0.75) -> dict:
    output_dir = output_dir.resolve()
    if not user_agent or "@" not in user_agent or delay < 0.25:
        raise ValueError("SEC contact User-Agent and conservative delay required")
    if output_dir.exists():
        raise ValueError("output directory exists; refusing overwrite")
    selected = json.loads(PAIRS.read_text())
    if len(selected["pairs"]) != 4 or selected.get("paid_calls_authorized") is not False:
        raise ValueError("unexpected pair selection")
    output_dir.mkdir(parents=True)
    entries = []
    for pair in selected["pairs"]:
        for role in ("baseline", "event"):
            item = pair[role]
            source = Source(
                id=f"HOLDOUT-V4-{pair['symbol']}-{role.upper()}",
                company=pair["symbol"], symbol=pair["symbol"], cik=pair["cik"],
                url=item["url"], filed_at=item["filed_at"],
                accession=item["accession"],
                artifact=Path(urlparse(item["url"]).path).name,
                form="8-K", document_type="EX-99.1",
                episode=1 if role == "baseline" else 2,
            )
            validate_source(source)
            time.sleep(delay)
            downloaded = fetch(source, output_dir, user_agent)
            if downloaded["bytes"] > 10_000_000:
                raise ValueError(f"SEC exhibit unexpectedly large: {source.id}")
            downloaded.update({"role": role, "period": item["period"],
                               "filed_at": item["filed_at"],
                               "accession": item["accession"],
                               "status": "bytes_frozen_row_period_basis_audit_pending"})
            entries.append(downloaded)
            print(f"{source.id}: {downloaded['bytes']} bytes frozen", flush=True)
    manifest = {
        "version": 4,
        "status": "eight_public_sec_exhibit_bytes_frozen_no_model_observations",
        "selection_sha256": hashlib.sha256(PAIRS.read_bytes()).hexdigest(),
        "model_observations": 0,
        "entries": entries,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
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
    print(json.dumps(freeze(args.output_dir, os.environ.get("SEC_USER_AGENT", ""),
                            args.delay), indent=2))
