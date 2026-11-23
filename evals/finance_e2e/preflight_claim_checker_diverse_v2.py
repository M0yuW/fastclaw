#!/usr/bin/env python3
"""Read-only integrity preflight for the unrun diverse checker panel."""

import csv
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
CORPUS = HERE / "claim_checker_diverse_cases_v2.json"
SCREEN_PACKET = HERE / "fintech_sec_screen_holdout_v1.json"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_hash(result_dir, observation_id):
    manifest = result_dir / "RESULT-SHA256.txt"
    matches = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        recorded_hash, recorded_path = line.split(maxsplit=1)
        recorded_path = recorded_path.strip()
        if (recorded_path == f"{observation_id}/result.json"
                or recorded_path.endswith(f"/{observation_id}/result.json")):
            matches.append(recorded_hash)
    if len(matches) != 1:
        raise RuntimeError(f"missing or duplicate raw hash for {observation_id}")
    return matches[0]


def prior_label(result_dir, observation_id):
    with (result_dir / "INSIGHT-JUDGE-v1.csv").open(newline="", encoding="utf-8") as scores:
        matches = [row for row in csv.DictReader(scores)
                   if row["observation_id"] == observation_id]
    if len(matches) != 1:
        raise RuntimeError(f"missing or duplicate first-pass label for {observation_id}")
    return matches[0].get("overall") or matches[0].get("label")


def final_text(result):
    turns = result.get("turns") or []
    if not turns:
        return ""
    return turns[-1]["response"]["choices"][0]["message"].get("content") or ""


def verify():
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    items = corpus["cases"]
    if (corpus.get("panel_id") != "CLAIM-CHECKER-DIVERSE-v2"
            or corpus.get("status") != "draft_no_external_calls"
            or corpus.get("text_field") != "final_answer"
            or len(items) != 10
            or len({item["blind_id"] for item in items}) != 10
            or sum(item["oracle"] == "material_issue" for item in items) != 5):
        raise RuntimeError("invalid diverse checker corpus")
    source_records = {
        Path(candidate["local_path"]).stem: candidate
        for candidate in json.loads(SCREEN_PACKET.read_text(encoding="utf-8"))["candidates"]
    }
    checked_sources = set()
    checked_results = []
    for item in items:
        path = (RESULTS / item["result_dir"] / "result.json").resolve()
        if not path.is_relative_to(RESULTS.resolve()):
            raise RuntimeError(f"result path escapes retained results: {path}")
        if not path.is_file():
            raise RuntimeError(f"missing retained answer: {path}")
        result_dir = path.parent.parent
        observation_id = path.parent.name
        result_hash = sha256(path)
        if result_hash != manifest_hash(result_dir, observation_id):
            raise RuntimeError(f"raw result hash mismatch: {observation_id}")
        result = json.loads(path.read_text(encoding="utf-8"))
        if not final_text(result):
            raise RuntimeError(f"empty final answer: {observation_id}")
        expected_label = ("problematic" if item["oracle"] == "material_issue"
                          else "high_within_case")
        if prior_label(result_dir, observation_id) != expected_label:
            raise RuntimeError(f"first-pass label differs from oracle: {observation_id}")
        if item["source_kind"] == "synthetic_fixture":
            if result.get("synthetic_tool_fixture") is not True or result.get("case_id") not in {"C2", "C3"}:
                raise RuntimeError(f"synthetic fixture identity mismatch: {observation_id}")
        else:
            source_ids = item.get("source_ids") or [item.get("source_id")]
            for source_id in source_ids:
                record = source_records[source_id]
                source_path = HERE / record["local_path"]
                if sha256(source_path) != record["source_sha256"]:
                    raise RuntimeError(f"SEC exhibit hash mismatch: {source_id}")
                checked_sources.add(source_id)
        checked_results.append({"blind_id": item["blind_id"],
                                "result_sha256": result_hash})
    return {"preflight": "ok", "cases": len(items), "material_issue_oracle": 5,
            "no_material_issue_oracle": 5,
            "sec_source_exhibits_verified": sorted(checked_sources),
            "corpus_sha256": sha256(CORPUS), "results": checked_results,
            "external_calls": 0}


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
