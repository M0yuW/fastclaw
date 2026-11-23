#!/usr/bin/env python3
"""Check explicit fact-ID=value echoes in immutable masked SEC answer packets.

This narrow diagnostic does not assess unlabelled values, arithmetic, causal
claims, risk treatment, or research quality. It never changes source packets.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path


NUMBER = r"([+-]?(?:\d+(?:,\d{3})*(?:\.\d+)?|\.\d+))"


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_packet_hashes(judgment_dir: Path) -> list[Path]:
    listed: dict[Path, str] = {}
    for line in (judgment_dir / "MASKED-PACKET-SHA256.txt").read_text().splitlines():
        parts = line.split("  ", 1)
        if len(parts) != 2 or not re.fullmatch(r"[0-9a-f]{64}", parts[0]):
            raise ValueError("malformed packet hash list")
        relative = Path(parts[1])
        if (relative.is_absolute() or ".." in relative.parts
                or relative.parts[0] != "masked_packets" or relative in listed):
            raise ValueError("unsafe or duplicate packet path")
        listed[relative] = parts[0]
    actual = {p.relative_to(judgment_dir)
              for p in (judgment_dir / "masked_packets").glob("*.json")}
    if not listed or set(listed) != actual:
        raise ValueError("packet hash list incomplete or has extras")
    for relative, digest in listed.items():
        if file_hash(judgment_dir / relative) != digest:
            raise ValueError(f"packet hash mismatch: {relative}")
    return [judgment_dir / relative for relative in sorted(listed)]


def passages(packet: dict) -> list[tuple[str, str]]:
    texts = [("final_answer", packet.get("final_answer") or "")]
    for thesis in packet.get("persisted_theses_and_reviews") or []:
        for review in thesis.get("reviews") or []:
            texts.append(("persisted_review", review.get("rationale") or ""))
    return texts


def check_packet(packet: dict) -> tuple[dict, list[dict]]:
    facts = {f["id"]: Decimal(str(f["value"]))
             for period in ("baseline", "event")
             for f in packet["source_packet"][period]["facts"]}
    counts = {"final_answer": 0, "persisted_review": 0}
    flags = []
    for location, text in passages(packet):
        for fact_id, expected in facts.items():
            pattern = re.escape(fact_id) + r"`?\s*(?:=|:)\s*`?\s*" + NUMBER
            for match in re.finditer(pattern, text):
                counts[location] += 1
                actual = Decimal(match.group(1).replace(",", ""))
                if actual != expected:
                    flags.append({
                        "masked_id": packet["masked_id"],
                        "case_id": packet["source_packet"]["case_id"],
                        "location": location,
                        "fact_id": fact_id,
                        "source_value": str(expected),
                        "echoed_value": str(actual),
                        "span": match.group(0),
                    })
    return counts, flags


def audit(judgment_dir: Path) -> dict:
    paths = verify_packet_hashes(judgment_dir)
    totals = {"final_answer": 0, "persisted_review": 0}
    flags = []
    for path in paths:
        counts, found = check_packet(json.loads(path.read_text()))
        for key in totals:
            totals[key] += counts[key]
        flags.extend(found)
    return {
        "status": "explicit_fact_echo_diagnostic_not_quality_rating",
        "masked_packets": len(paths),
        "checked_echoes": totals,
        "mismatch_flags": len(flags),
        "flags": flags,
        "coverage_limit": "Only literal fact-ID=value or fact-ID:value echoes in final answers and persisted review rationales; every flag requires context review.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--judgment-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.judgment_dir)
    if args.output:
        if args.output.exists():
            raise ValueError("output exists; refusing overwrite")
        args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
