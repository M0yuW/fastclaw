#!/usr/bin/env python3
"""Competition-scoped TheSportsDB client for the Go football team.

The model supplies only reviewed competition names and football-facing inputs. Provider
URLs and league identifiers are selected inside this script.
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common.football_competitions import normalize, resolve_competition
from common.http_fetch import FetchError, fetch_json
from common.utils import output_json

BASE = "https://www.thesportsdb.com/api/v1/json/123"
MAX_BYTES = 2_000_000
TRUSTED_LEAGUE_IDS = {"FIFA World Cup": "4429"}

# Total budget per HTTP call, retries included. A schedule lookup makes two
# calls (league resolution, then the query), so the script's worst case is
# ~2x this — sized to stay well inside the agent's tool timeout.
REQUEST_TIMEOUT = 20.0

# FetchError.kind -> (error_code, safe_reason). The kinds that mean "we never
# got an answer" map to codes containing "request", which fetch() below turns
# into status "unavailable" rather than "rejected": the competition is fine,
# the provider just didn't answer.
_FETCH_ERRORS = {
    "timeout": ("thesportsdb_request_timeout", "TheSportsDB did not respond in time"),
    "connect": ("thesportsdb_request_failed", "TheSportsDB was unreachable"),
    "http": ("thesportsdb_request_failed", "TheSportsDB returned an error status"),
    "too_large": (
        "thesportsdb_response_too_large",
        "TheSportsDB response exceeded the limit",
    ),
    "malformed": ("thesportsdb_malformed_json", "TheSportsDB returned malformed JSON"),
}


class SourceError(RuntimeError):
    """Sanitized upstream failure."""

    def __init__(self, code: str, reason: str) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason


def _status(
    state: str,
    *,
    mapping: dict[str, str] | None = None,
    data: Any = None,
    error_code: str = "",
    safe_reason: str = "",
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "source": "thesportsdb",
        "status": state,
        "as_of": datetime.now(timezone.utc).isoformat(),
    }
    if mapping:
        result["mapping"] = {
            "competition": mapping["competition"],
            "country": mapping["country"],
        }
    if data is not None:
        result["data"] = data
    if error_code:
        result["error_code"] = error_code
    if safe_reason:
        result["safe_reason"] = safe_reason
    return result


def _request(endpoint: str, params: dict[str, str]) -> dict[str, Any]:
    query = urllib.parse.urlencode(params)
    try:
        payload = fetch_json(
            f"{BASE}/{endpoint}?{query}",
            timeout=REQUEST_TIMEOUT,
            max_bytes=MAX_BYTES,
        )
    except FetchError as exc:
        code, reason = _FETCH_ERRORS.get(
            exc.kind, ("thesportsdb_request_failed", "TheSportsDB request failed")
        )
        raise SourceError(code, reason) from exc
    if not isinstance(payload, dict):
        raise SourceError(
            "thesportsdb_unexpected_payload",
            "TheSportsDB response shape was not recognized",
        )
    return payload


def _resolve_league(mapping: dict[str, str]) -> str:
    trusted = TRUSTED_LEAGUE_IDS.get(mapping["competition"])
    if trusted:
        return trusted
    payload = _request(
        "search_all_leagues.php", {"s": "Soccer", "c": mapping["country"]}
    )
    rows = payload.get("countries") or payload.get("leagues") or []
    expected = normalize(mapping["competition"])
    matches: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        names = {
            normalize(str(row.get("strLeague") or "")),
            *{
                normalize(label)
                for label in str(row.get("strLeagueAlternate") or "").split(",")
                if label.strip()
            },
        }
        country = normalize(str(row.get("strCountry") or ""))
        league_id = str(row.get("idLeague") or "")
        if (
            expected in names
            and country == normalize(mapping["country"])
            and re.fullmatch(r"\d+", league_id)
        ):
            matches.add(league_id)
    if len(matches) != 1:
        raise SourceError(
            "primary_competition_not_confirmed",
            "TheSportsDB did not resolve exactly one reviewed competition",
        )
    return next(iter(matches))


def _event(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": row.get("idEvent"),
        "competition": row.get("strLeague"),
        "season": row.get("strSeason"),
        "stage": row.get("strRound"),
        "date": row.get("dateEvent"),
        "time": row.get("strTime"),
        "home": row.get("strHomeTeam"),
        "away": row.get("strAwayTeam"),
        "home_score": row.get("intHomeScore"),
        "away_score": row.get("intAwayScore"),
        "venue": row.get("strVenue"),
        "status": row.get("strStatus"),
    }


def _standing(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "rank": row.get("intRank"),
        "team": row.get("strTeam"),
        "played": row.get("intPlayed"),
        "win": row.get("intWin"),
        "draw": row.get("intDraw"),
        "loss": row.get("intLoss"),
        "goals_for": row.get("intGoalsFor"),
        "goals_against": row.get("intGoalsAgainst"),
        "goal_difference": row.get("intGoalDifference"),
        "points": row.get("intPoints"),
    }


def _rows(payload: dict[str, Any], key: str, transform: Any) -> list[dict[str, Any]]:
    raw = payload.get(key) or []
    if not isinstance(raw, list):
        raise SourceError(
            "thesportsdb_unexpected_payload",
            "TheSportsDB response shape was not recognized",
        )
    return [transform(row) for row in raw if isinstance(row, dict)]


def fetch(args: argparse.Namespace) -> dict[str, Any]:
    mapping = resolve_competition(args.competition)
    if mapping is None:
        return _status(
            "rejected",
            error_code="competition_not_reviewed",
            safe_reason="Competition is not in the reviewed provider catalog",
        )
    try:
        league_id = _resolve_league(mapping)
        if args.schedule:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.date or ""):
                raise SourceError(
                    "date_required", "Schedule requires date in YYYY-MM-DD format"
                )
            payload = _request("eventsday.php", {"d": args.date, "l": league_id})
            data = {"date": args.date, "matches": _rows(payload, "events", _event)}
        elif args.results:
            if not args.season:
                raise SourceError(
                    "season_required", "Results require an explicit season"
                )
            payload = _request("eventsseason.php", {"id": league_id, "s": args.season})
            data = {"season": args.season, "matches": _rows(payload, "events", _event)}
        elif args.standings:
            if not args.season:
                raise SourceError(
                    "season_required", "Standings require an explicit season"
                )
            payload = _request("lookuptable.php", {"l": league_id, "s": args.season})
            data = {
                "season": args.season,
                "standings": _rows(payload, "table", _standing),
            }
        else:
            raise SourceError(
                "action_required", "Choose schedule, results, or standings"
            )
    except SourceError as exc:
        return _status(
            "unavailable" if "request" in exc.code else "rejected",
            mapping=mapping,
            error_code=exc.code,
            safe_reason=exc.reason,
        )
    return _status("success", mapping=mapping, data=data)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Competition-scoped TheSportsDB client"
    )
    parser.add_argument("--competition", required=True)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--schedule", action="store_true")
    action.add_argument("--results", action="store_true")
    action.add_argument("--standings", action="store_true")
    parser.add_argument("--date", default="")
    parser.add_argument("--season", default="")
    output_json(fetch(parser.parse_args()))


if __name__ == "__main__":
    main()
