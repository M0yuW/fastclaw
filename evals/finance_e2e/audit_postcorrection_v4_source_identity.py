#!/usr/bin/env python3
"""Verify 20 SEC issuer pairs and run the separately completed row audits.

Identity/period coverage spans all 20; selected numeric audits span only the
explicitly registered subset, and neither check is an insight-quality result.
NAVI's detailed EX-99.2 files are mandatory in addition to pointer EX-99.1.
"""

from __future__ import annotations

import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

import audit_wex_v4_source_facts as wex
import audit_hban_v4_source_facts as hban
import audit_vrsk_v4_source_facts as vrsk
import audit_ntrs_v4_source_facts as ntrs
import audit_v4_declared_sec_rows as declared_rows
from select_postcorrection_v4_remaining_pairs import select
from verify_postcorrection_unseen_candidates_v4 import verify as roster_verify


HERE = Path(__file__).parent
RESULTS = HERE / "results"
FIRST = RESULTS / "2026-10-24-postcorrection-v4-first4-exhibits-complete"
REMAINING = RESULTS / "2026-10-24-postcorrection-v4-remaining16-exhibits"
WEX = RESULTS / "2026-10-24-postcorrection-v4-wex-exhibits"
NAVI_DETAIL = RESULTS / "2026-10-24-postcorrection-v4-navi-detailed-exhibits"
PAIRS = HERE / "postcorrection_v4_remaining16_provisional_pairs.json"


def audit_seic() -> dict:
    return declared_rows.audit(json.loads(
        (HERE / "seic_v4_declared_source_packet.json").read_text()))


def audit_mktx() -> dict:
    return declared_rows.audit(json.loads(
        (HERE / "mktx_v4_declared_source_packet.json").read_text()))


def audit_fds() -> dict:
    return declared_rows.audit(json.loads(
        (HERE / "fds_v4_declared_source_packet.json").read_text()))


def audit_rely() -> dict:
    return declared_rows.audit(json.loads(
        (HERE / "rely_v4_declared_source_packet.json").read_text()))


def audit_cpay() -> dict:
    return declared_rows.audit(json.loads(
        (HERE / "cpay_v4_declared_source_packet.json").read_text()))


def audit_tfc() -> dict:
    return declared_rows.audit(json.loads(
        (HERE / "tfc_v4_declared_source_packet.json").read_text()))


def audit_fitb() -> dict:
    return declared_rows.audit(json.loads(
        (HERE / "fitb_v4_declared_source_packet.json").read_text()))


def audit_usb() -> dict:
    return declared_rows.audit(json.loads(
        (HERE / "usb_v4_declared_source_packet.json").read_text()))


def audit_c() -> dict:
    return declared_rows.audit(json.loads(
        (HERE / "c_v4_declared_source_packet.json").read_text()))


def audit_flyw() -> dict:
    return declared_rows.audit(json.loads(
        (HERE / "flyw_v4_declared_source_packet.json").read_text()))


def audit_evtc() -> dict:
    return declared_rows.audit(json.loads(
        (HERE / "evtc_v4_declared_source_packet.json").read_text()))


def audit_spgi() -> dict:
    return declared_rows.audit(json.loads(
        (HERE / "spgi_v4_declared_source_packet.json").read_text()))


def audit_tru() -> dict:
    return declared_rows.audit(json.loads(
        (HERE / "tru_v4_declared_source_packet.json").read_text()))


def audit_navi() -> dict:
    return declared_rows.audit(json.loads(
        (HERE / "navi_v4_declared_source_packet.json").read_text()))


def audit_rkt() -> dict:
    return declared_rows.audit(json.loads(
        (HERE / "rkt_v4_declared_source_packet.json").read_text()))


def audit_lpla() -> dict:
    return declared_rows.audit(json.loads(
        (HERE / "lpla_v4_declared_source_packet.json").read_text()))


NUMERIC_AUDITORS = {"WEX": wex.audit, "HBAN": hban.audit,
                    "VRSK": vrsk.audit, "NTRS": ntrs.audit,
                    "SEIC": audit_seic, "MKTX": audit_mktx,
                    "FDS": audit_fds, "RELY": audit_rely,
                    "CPAY": audit_cpay, "TFC": audit_tfc,
                    "FITB": audit_fitb, "USB": audit_usb,
                    "C": audit_c, "FLYW": audit_flyw,
                    "EVTC": audit_evtc, "SPGI": audit_spgi,
                    "TRU": audit_tru, "NAVI": audit_navi,
                    "RKT": audit_rkt, "LPLA": audit_lpla}


class Plain(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    @property
    def text(self) -> str:
        return " ".join(" ".join(self.parts).split())


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_hash_list(directory: Path) -> None:
    lines = (directory / "RESULT-SHA256.txt").read_text().splitlines()
    expected = {path.name for path in directory.iterdir()
                if path.is_file() and path.name != "RESULT-SHA256.txt"}
    seen = set()
    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9._-]+)", line)
        if not match or match.group(2) in seen:
            raise ValueError(f"invalid result hash list: {directory}")
        name = match.group(2)
        seen.add(name)
        if file_hash(directory / name) != match.group(1):
            raise ValueError(f"result hash differs: {name}")
    if seen != expected:
        raise ValueError(f"result hash list coverage differs: {directory}")


def audit_source(entry: dict, expected_dir: Path, pattern: str) -> dict:
    path = (HERE / entry["local_path"]).resolve()
    if path.parent != expected_dir.resolve() or not path.is_file():
        raise ValueError(f"{entry['id']}: source path differs")
    if file_hash(path) != entry["sha256"] or entry["bytes"] != path.stat().st_size:
        raise ValueError(f"{entry['id']}: source byte identity differs")
    url = urlparse(entry["url"])
    fragment = (f"/Archives/edgar/data/{int(entry['symbol_cik'])}/"
                f"{entry['accession'].replace('-', '')}/")
    if (url.scheme != "https" or url.hostname != "www.sec.gov"
            or not url.path.startswith(fragment)):
        raise ValueError(f"{entry['id']}: SEC accession identity differs")
    parsed = Plain()
    parsed.feed(path.read_text(errors="replace"))
    if not re.search(pattern, parsed.text[:1600], re.IGNORECASE):
        raise ValueError(f"{entry['id']}: expected quarterly title absent")
    return {"symbol": entry["symbol"], "role": entry["role"],
            "document_type": entry.get("document_type", "EX-99.1"),
            "source_sha256": entry["sha256"], "text_characters": len(parsed.text)}


def audit() -> dict:
    roster = roster_verify()["selected_by_stratum"]
    expected = {symbol for group in roster.values() for symbol in group}
    expected.remove("PAYO")
    expected.add("WEX")
    if len(expected) != 20 or json.loads(PAIRS.read_text()) != select():
        raise ValueError("v4 replacement frame or provisional pairs changed")
    audited_symbols = sorted(NUMERIC_AUDITORS)
    if any(symbol not in expected for symbol in audited_symbols):
        raise ValueError("numeric auditor references a non-candidate issuer")
    for symbol in audited_symbols:
        result = NUMERIC_AUDITORS[symbol]()
        if result.get("model_observations") != 0:
            raise ValueError(f"{symbol} source auditor reports a model observation")
    source_summaries = []
    pair_coverage = {}
    first_cik = {p["symbol"]: p["cik"] for p in json.loads((HERE /
        "postcorrection_v4_first4_sec_pairs.json").read_text())["pairs"]}
    remaining_cik = {p["symbol"]: p["cik"] for p in json.loads(
        PAIRS.read_text())["pairs"]}
    cik_by_symbol = {**first_cik, **remaining_cik, "WEX": "0001309108"}
    for directory in (FIRST, REMAINING, WEX):
        verify_hash_list(directory)
        manifest = json.loads((directory / "manifest.json").read_text())
        for entry in manifest["entries"]:
            symbol = entry["symbol"]
            if symbol == "PAYO":
                continue
            if symbol not in expected:
                raise ValueError(f"unexpected issuer: {symbol}")
            role = entry["role"]
            if symbol == "FDS":
                pattern = (r"(fourth quarter|q4)" if role == "baseline"
                           else r"(first quarter fiscal 2026|q1 2026)")
            else:
                pattern = (r"(second[- ]quarter|2q25)" if role == "baseline"
                           else r"(third[- ]quarter|3q25)")
            checked = audit_source({**entry, "symbol_cik": cik_by_symbol[symbol]},
                                   directory, pattern)
            pair_coverage.setdefault(symbol, set()).add(role)
            source_summaries.append(checked)
    if set(pair_coverage) != expected or any(roles != {"baseline", "event"}
                                             for roles in pair_coverage.values()):
        raise ValueError("20 issuer-pair source coverage differs")
    if len(source_summaries) != 40:
        raise ValueError("expected 40 primary source attachments")

    verify_hash_list(NAVI_DETAIL)
    detailed = json.loads((NAVI_DETAIL / "manifest.json").read_text())
    primary_navi = {x["role"]: x for x in json.loads(
        (REMAINING / "manifest.json").read_text())["entries"]
        if x["symbol"] == "NAVI"}
    if len(detailed["entries"]) != 2:
        raise ValueError("NAVI detailed attachment count differs")
    for entry in detailed["entries"]:
        role = entry["role"]
        if (entry["accession"] != primary_navi[role]["accession"]
                or entry["document_type"] != "EX-99.2"):
            raise ValueError("NAVI detailed attachment filing differs")
        pattern = (r"navient reports second[- ]quarter 2025 financial results"
                   if role == "baseline" else
                   r"navient reports third[- ]quarter 2025 financial results")
        audit_source({**entry, "symbol_cik": cik_by_symbol["NAVI"]}, NAVI_DETAIL,
                     pattern)
    if any(x["symbol"] == "SPGI" and x["role"] == "event"
           and x["document_type"] != "EX-99" for x in source_summaries):
        raise ValueError("SPGI EX-99 source boundary differs")
    return {"status": "v4_twenty_source_pairs_identity_period_only_verified",
            "issuer_pairs": len(pair_coverage),
            "primary_exhibits": len(source_summaries),
            "navi_detailed_exhibits": len(detailed["entries"]),
            "special_source_rules": ["SPGI Q3 EX-99", "NAVI EX-99.1 pointer plus EX-99.2 detail",
                                     "FDS adjacent fiscal Q4 FY2025 to Q1 FY2026"],
            "numeric_row_audits_complete": len(audited_symbols),
            "numeric_row_audited_symbols": audited_symbols,
            "model_observations": 0,
            "quality_claim": "none"}


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
