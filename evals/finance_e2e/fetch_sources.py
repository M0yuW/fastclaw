#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_MANIFEST = ROOT / "sources.json"
DEFAULT_OUTPUT = ROOT / ".cache" / "sources"
DEFAULT_LOCK = ROOT / "source-lock.json"
ACCESSION_PATTERN = re.compile(r"^\d{10}-\d{2}-\d{6}$")
CIK_PATTERN = re.compile(r"^\d{10}$")
ALLOWED_HOSTS = {"www.sec.gov", "data.sec.gov"}


@dataclass(frozen=True)
class Source:
    id: str
    company: str
    symbol: str
    cik: str
    url: str
    filed_at: str = ""
    accession: str = ""
    artifact: str = ""
    form: str = ""
    document_type: str = ""
    episode: int = 0
    kind: str = "filing_artifact"

    @property
    def suffix(self) -> str:
        suffix = Path(urllib.parse.urlparse(self.url).path).suffix.lower()
        return suffix if suffix in {".htm", ".html", ".json", ".xml", ".xlsx", ".pdf"} else ".bin"


def load_manifest(path: Path) -> tuple[dict[str, Any], list[Source]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("version") != 1:
        raise ValueError("sources manifest version must be 1")
    sources: list[Source] = []
    seen: set[str] = set()
    for kind, records in (("filing_artifact", payload.get("sources", [])), ("companyfacts", payload.get("cross_checks", []))):
        for record in records:
            source = Source(kind=kind, **record)
            validate_source(source)
            if source.id in seen:
                raise ValueError(f"duplicate source id: {source.id}")
            seen.add(source.id)
            sources.append(source)
    return payload, sources


def validate_source(source: Source) -> None:
    if not source.id or not source.company or not source.symbol:
        raise ValueError("source id, company, and symbol are required")
    if not CIK_PATTERN.fullmatch(source.cik):
        raise ValueError(f"{source.id}: cik must contain exactly 10 digits")
    parsed = urllib.parse.urlparse(source.url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError(f"{source.id}: only official SEC HTTPS sources are allowed")
    if source.kind == "filing_artifact":
        if not ACCESSION_PATTERN.fullmatch(source.accession):
            raise ValueError(f"{source.id}: invalid accession")
        if source.episode < 1:
            raise ValueError(f"{source.id}: episode must be positive")
        datetime.strptime(source.filed_at, "%Y-%m-%d")
        if source.form != "8-K" or source.document_type != "EX-99.1":
            raise ValueError(f"{source.id}: finance filing artifacts must be 8-K EX-99.1 documents")
        accession_compact = source.accession.replace("-", "")
        cik_compact = str(int(source.cik))
        expected_fragment = f"/Archives/edgar/data/{cik_compact}/{accession_compact}/{source.artifact}"
        if parsed.path != expected_fragment:
            raise ValueError(f"{source.id}: URL does not match CIK/accession/artifact")
    elif parsed.hostname != "data.sec.gov" or not parsed.path.endswith(f"/CIK{source.cik}.json"):
        raise ValueError(f"{source.id}: companyfacts URL does not match CIK")


def fetch(source: Source, output_dir: Path, user_agent: str) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"{source.id}{source.suffix}"
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    curl = shutil.which("curl")
    if curl is None:
        raise RuntimeError("curl is required for bounded, retryable SEC downloads")
    command = [
        curl,
        "--fail",
        "--silent",
        "--show-error",
        "--location",
        "--proto",
        "=https",
        "--proto-redir",
        "=https",
        "--connect-timeout",
        "15",
        "--max-time",
        "90",
        "--retry",
        "3",
        "--retry-delay",
        "2",
        "--retry-all-errors",
        "--user-agent",
        user_agent,
        "--header",
        "Accept-Encoding: identity",
        "--output",
        str(temporary),
        "--write-out",
        "%{url_effective}\n%{content_type}",
        source.url,
    ]
    try:
        completed = subprocess.run(command, check=True, capture_output=True, text=True, timeout=380)
        metadata = completed.stdout.splitlines()
        final_url = metadata[0] if metadata else source.url
        content_type = metadata[1] if len(metadata) > 1 else "application/octet-stream"
        if not temporary.exists() or temporary.stat().st_size == 0:
            raise RuntimeError(f"{source.id}: empty response")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    content_hash = hashlib.sha256()
    with destination.open("rb") as downloaded:
        for chunk in iter(lambda: downloaded.read(1024 * 1024), b""):
            content_hash.update(chunk)
    return {
        "id": source.id,
        "kind": source.kind,
        "company": source.company,
        "symbol": source.symbol,
        "url": source.url,
        "final_url": final_url,
        "local_path": str(destination.relative_to(ROOT)),
        "sha256": content_hash.hexdigest(),
        "bytes": destination.stat().st_size,
        "content_type": content_type,
    }


def manifest_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_hash(path: Path) -> str:
    content_hash = hashlib.sha256()
    with path.open("rb") as locked_file:
        for chunk in iter(lambda: locked_file.read(1024 * 1024), b""):
            content_hash.update(chunk)
    return content_hash.hexdigest()


def verify_local_lock(manifest_path: Path, lock_path: Path, root: Path = ROOT) -> None:
    _, sources = load_manifest(manifest_path)
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if lock.get("version") != 1 or lock.get("dataset") != "fastclaw-finance-e2e-v1":
        raise RuntimeError("unexpected source lock version or dataset")
    if lock.get("manifest_sha256") != manifest_hash(manifest_path):
        raise RuntimeError("source lock manifest hash does not match sources.json")

    expected = {source.id: source for source in sources}
    entries = {entry.get("id"): entry for entry in lock.get("entries", [])}
    if set(entries) != set(expected):
        raise RuntimeError("source lock entries do not match the source manifest")

    locked_root = (root / ".cache" / "sources").resolve()
    for source_id, source in expected.items():
        entry = entries[source_id]
        if entry.get("url") != source.url or entry.get("kind") != source.kind:
            raise RuntimeError(f"{source_id}: locked metadata does not match the source manifest")
        local_path = (root / str(entry.get("local_path", ""))).resolve()
        if local_path != locked_root and locked_root not in local_path.parents:
            raise RuntimeError(f"{source_id}: locked path escapes the source cache")
        if not local_path.is_file():
            raise RuntimeError(f"{source_id}: locked source file is missing")
        if local_path.stat().st_size != entry.get("bytes"):
            raise RuntimeError(f"{source_id}: locked source byte count changed")
        if file_hash(local_path) != entry.get("sha256"):
            raise RuntimeError(f"{source_id}: locked source SHA-256 changed")


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze official SEC evidence for the FastClaw finance study.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    parser.add_argument("--user-agent", default=os.environ.get("SEC_USER_AGENT", ""))
    parser.add_argument("--write-lock", action="store_true")
    parser.add_argument("--check-local", action="store_true", help="verify cached files against the existing lock")
    parser.add_argument("--delay", type=float, default=0.5)
    args = parser.parse_args()

    if args.check_local:
        if args.write_lock:
            parser.error("--check-local and --write-lock are mutually exclusive")
        verify_local_lock(args.manifest, args.lock)
        print("all local source hashes match the existing lock")
        return 0
    if "@" not in args.user_agent or len(args.user_agent.strip()) < 12:
        parser.error("--user-agent or SEC_USER_AGENT must identify the researcher and include a contact email")
    if args.delay < 0.12:
        parser.error("--delay must be at least 0.12 seconds to respect SEC request limits")

    _, sources = load_manifest(args.manifest)
    entries: list[dict[str, Any]] = []
    for index, source in enumerate(sources):
        if index:
            time.sleep(args.delay)
        print(f"fetching {source.id}", file=sys.stderr)
        entries.append(fetch(source, args.output_dir, args.user_agent))

    lock = {
        "version": 1,
        "dataset": "fastclaw-finance-e2e-v1",
        "manifest": str(args.manifest.relative_to(ROOT)),
        "manifest_sha256": manifest_hash(args.manifest),
        "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "entries": entries,
    }
    encoded = json.dumps(lock, indent=2, sort_keys=True) + "\n"
    if args.lock.exists() and not args.write_lock:
        existing = json.loads(args.lock.read_text(encoding="utf-8"))
        expected = {entry["id"]: entry["sha256"] for entry in existing.get("entries", [])}
        actual = {entry["id"]: entry["sha256"] for entry in entries}
        if expected != actual:
            missing = sorted(set(expected) ^ set(actual))
            changed = sorted(source_id for source_id in set(expected) & set(actual) if expected[source_id] != actual[source_id])
            raise RuntimeError(f"source lock mismatch; missing={missing}, changed={changed}")
        print("all source hashes match the existing lock")
        return 0
    if not args.write_lock:
        raise RuntimeError("source lock does not exist; pass --write-lock after reviewing the downloaded evidence")
    args.lock.write_text(encoded, encoding="utf-8")
    print(f"wrote {args.lock}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
