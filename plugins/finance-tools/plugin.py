#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
import os
import re
import sqlite3
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable


_lineage_spec = importlib.util.spec_from_file_location(
    "finance_tools_accounting_lineage", Path(__file__).with_name("accounting_lineage.py")
)
if _lineage_spec is None or _lineage_spec.loader is None:
    raise ImportError("accounting lineage validator unavailable")
_lineage = importlib.util.module_from_spec(_lineage_spec)
_lineage_spec.loader.exec_module(_lineage)

_review_guard_spec = importlib.util.spec_from_file_location(
    "finance_tools_review_arithmetic_guard",
    Path(__file__).with_name("review_arithmetic_guard.py"),
)
if _review_guard_spec is None or _review_guard_spec.loader is None:
    raise ImportError("review arithmetic guard unavailable")
_review_guard = importlib.util.module_from_spec(_review_guard_spec)
_review_guard_spec.loader.exec_module(_review_guard)


SCHEMA_VERSION = "finance.tool.v1"
MARKET_PROVIDERS = {
    "US": "yfinance",
    "CN": "AKShare",
}
SCRIPT_PATHS = {
    ("US", "stock"): "US-market/findata-toolkit/scripts/stock_data.py",
    ("US", "macro"): "US-market/findata-toolkit/scripts/macro_data.py",
    ("US", "portfolio"): "US-market/findata-toolkit/scripts/portfolio_analytics.py",
    ("CN", "stock"): "China-market/findata-toolkit-cn/scripts/stock_data.py",
    ("CN", "macro"): "China-market/findata-toolkit-cn/scripts/macro_data.py",
    ("CN", "news"): "China-market/findata-toolkit-cn/scripts/news_data.py",
}
STOCK_VIEW_FLAGS = {
    "basic": [],
    "metrics": ["--metrics"],
    "history": ["--history"],
    "financials": ["--financials"],
}
MACRO_VIEW_FLAGS = {
    "dashboard": [],
    "rates": ["--rates"],
    "inflation": ["--inflation"],
    "cycle": ["--cycle"],
    "gdp": ["--gdp"],
    "employment": ["--employment"],
    "pmi": ["--pmi"],
    "social_financing": ["--social-financing"],
}
EVENT_FLAGS = {
    "stock_news": "--news",
    "lifting": "--lifting",
    "announcements": "--announcements",
    "market_news": "--market-news",
    "hot_rank": "--hot-rank",
    "margin": "--margin",
}
PORTFOLIO_FLAGS = {
    "health": "--health",
    "concentration": "--concentration",
    "correlation": "--correlation",
    "risk": "--risk",
    "stress": "--stress",
}
SYMBOL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.^=_-]{0,19}$")
THESIS_STATUSES = {"researching", "watch", "active", "invalidated", "archived"}
REVIEW_IMPACTS = {"positive", "negative", "neutral", "mixed"}
REVIEW_DECISIONS = {
    "maintain",
    "upgrade",
    "downgrade",
    "invalidate",
    "needs_review",
}
WATCHLIST_STATUSES = {"active", "paused", "archived"}
ALERT_STATUSES = {"new", "acknowledged", "dismissed"}


class ToolInputError(ValueError):
    pass


class ToolStateError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        retriable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retriable = retriable
        self.details = details


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def tool_definitions() -> list[dict[str, Any]]:
    market_property = {
        "type": "string",
        "enum": ["US", "CN"],
        "description": "US for US-listed securities, CN for mainland A-shares.",
    }
    symbol_array = {
        "type": "array",
        "items": {"type": "string"},
        "minItems": 1,
        "maxItems": 50,
    }
    return [
        {
            "name": "toolkit_status",
            "description": "Inspect available financial scripts and local Python dependencies without making network requests.",
            "parameters": {"type": "object", "properties": {}},
        },
        {
            "name": "stock_snapshot",
            "description": "Fetch source-aware stock basics, financial metrics, price history, or statements. Use screen_stocks for ranking.",
            "parameters": {
                "type": "object",
                "properties": {
                    "market": market_property,
                    "symbols": symbol_array,
                    "view": {
                        "type": "string",
                        "enum": ["basic", "metrics", "history", "financials"],
                        "default": "metrics",
                    },
                    "period": {
                        "type": "string",
                        "description": "History period such as 1m, 6m, 1y, 5y, or max.",
                        "default": "1y",
                    },
                },
                "required": ["market", "symbols"],
            },
        },
        {
            "name": "screen_stocks",
            "description": "Run deterministic Finskills screening and reject apparent passes with incomplete required metrics by default.",
            "parameters": {
                "type": "object",
                "properties": {
                    "market": market_property,
                    "symbols": symbol_array,
                    "min_upside": {
                        "type": "number",
                        "description": "US-only minimum analyst upside as a decimal.",
                        "default": 0.3,
                    },
                    "require_complete": {
                        "type": "boolean",
                        "description": "Reject candidates missing any metric used by the screen.",
                        "default": True,
                    },
                },
                "required": ["market", "symbols"],
            },
        },
        {
            "name": "market_events",
            "description": "Fetch A-share stock news, announcements, market wires, hot rank, margin data, or restricted-share lifting events.",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": list(EVENT_FLAGS),
                    },
                    "symbol": {"type": "string"},
                    "date": {
                        "type": "string",
                        "description": "Optional YYYYMMDD date for announcements or margin data.",
                    },
                    "notice_type": {
                        "type": "string",
                        "description": "A-share announcement category.",
                        "default": "全部",
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 200,
                    },
                },
                "required": ["operation"],
            },
        },
        {
            "name": "macro_snapshot",
            "description": "Fetch a US or China macro dashboard or one macro category through the configured toolkit.",
            "parameters": {
                "type": "object",
                "properties": {
                    "market": market_property,
                    "view": {
                        "type": "string",
                        "enum": list(MACRO_VIEW_FLAGS),
                        "default": "dashboard",
                    },
                },
                "required": ["market"],
            },
        },
        {
            "name": "portfolio_risk",
            "description": "Calculate portfolio risk only from a complete holdings set. Percentage or fractional weights must sum to the whole portfolio; explicit relative weights require holdings_complete=true. Do not submit a known partial portfolio.",
            "parameters": {
                "type": "object",
                "properties": {
                    "holdings": {
                        "type": "object",
                        "additionalProperties": {"type": "number"},
                        "description": "Complete ticker-to-weight map. Include cash as a holding when relevant; never omit an unknown position.",
                    },
                    "weight_unit": {
                        "type": "string",
                        "enum": ["auto", "percent", "fraction", "relative"],
                        "description": "auto accepts sums of 100 or 1; relative requires an explicit completeness confirmation.",
                        "default": "auto",
                    },
                    "holdings_complete": {
                        "type": "boolean",
                        "description": "Set false if any holding or weight is unknown; the tool will refuse to calculate.",
                    },
                    "view": {
                        "type": "string",
                        "enum": list(PORTFOLIO_FLAGS),
                        "default": "health",
                    },
                    "benchmark": {"type": "string", "default": "SPY"},
                },
                "required": ["holdings"],
            },
        },
        {
            "name": "portfolio_policy_bound",
            "description": "Compute only a strict single-issuer weight-limit bound from incomplete long-only percentage holdings. Requires an explicit statement of whether unknown holdings can duplicate known issuers. Does not calculate HHI, market risk, or a live-account verdict.",
            "parameters": {
                "type": "object",
                "properties": {
                    "known_holdings_percent": {
                        "type": "object",
                        "additionalProperties": {"type": "number"},
                        "description": "Known issuer line-item weights as percentages of the same whole portfolio, not normalized to the known subtotal.",
                    },
                    "unknown_remainder_percent": {
                        "type": "number",
                        "description": "Unidentified long-only remainder as a percentage of the whole portfolio; together with known weights it must sum to 100.",
                    },
                    "unknown_may_overlap_known": {
                        "type": "boolean",
                        "description": "False only when known weights are final issuer-aggregated totals and the remainder excludes those issuers; true when an unknown sleeve may contain more of a known issuer.",
                    },
                    "limit_percent": {
                        "type": "number",
                        "description": "Single-issuer limit; breach means strictly greater than this percentage.",
                        "default": 50,
                    },
                },
                "required": ["known_holdings_percent", "unknown_remainder_percent",
                             "unknown_may_overlap_known"],
            },
        },
        {
            "name": "serenity_scorecard",
            "description": "Apply the pinned Serenity bottleneck scorecard to supplied, already-sourced evidence. The score is a research priority, not a return forecast.",
            "parameters": {
                "type": "object",
                "properties": {
                    "scorecard": {
                        "type": "object",
                        "description": "Serenity scorecard containing ticker, factors, penalties, evidence, and failure conditions.",
                    }
                },
                "required": ["scorecard"],
            },
        },
        {
            "name": "thesis_save",
            "description": "Create or update a tenant-isolated investment research thesis with assumptions, catalysts, invalidation conditions, evidence, and optimistic version checks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "thesis_id": {"type": "string"},
                    "expected_version": {"type": "integer", "minimum": 1},
                    "market": market_property,
                    "symbol": {"type": "string"},
                    "title": {"type": "string"},
                    "thesis": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": sorted(THESIS_STATUSES),
                    },
                    "conviction": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 5,
                    },
                    "assumptions": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "catalysts": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "invalidations": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "required_event_metrics": {
                        "type": "array",
                        "description": "Metric names that must be present in a linked event packet before a substantive research decision is recorded.",
                        "items": {"type": "string"},
                    },
                    "evidence": {
                        "type": "array",
                        "items": {"type": "object"},
                    },
                    "next_review_at": {
                        "type": "string",
                        "description": "Future ISO date or timestamp for an operational review; historical source dates belong in evidence."
                    },
                },
            },
        },
        {
            "name": "thesis_get",
            "description": "Read one thesis and its recent review history from the current user's isolated ledger.",
            "parameters": {
                "type": "object",
                "properties": {
                    "thesis_id": {"type": "string"},
                    "review_limit": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 100,
                        "default": 20,
                    },
                },
                "required": ["thesis_id"],
            },
        },
        {
            "name": "thesis_list",
            "description": "List the current user's research theses with optional status, market, and symbol filters.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": sorted(THESIS_STATUSES),
                    },
                    "market": market_property,
                    "symbol": {"type": "string"},
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 50,
                    },
                },
            },
        },
        {
            "name": "thesis_match_event",
            "description": "Deterministically match a symbol-tagged event against active thesis assumptions, catalysts, and invalidation terms before model review.",
            "parameters": {
                "type": "object",
                "properties": {
                    "market": market_property,
                    "symbol": {"type": "string"},
                    "event_summary": {"type": "string"},
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 20,
                        "default": 10,
                    },
                },
                "required": ["market", "symbol", "event_summary"],
            },
        },
        {
            "name": "thesis_record_review",
            "description": "Persist a version-protected event review. Provide the stored alert_id for needs_review, when event metrics are required, or when decision_hold is true. Pass evidence and other fields as top-level arguments, never as JSON text inside rationale. An empty causal_claims array means no causal attribution; nonempty claims require trusted statement-line metadata. Any needs_review decision preserves status and conviction and blocks downstream decisions. A hold can be resolved only with a sourced, complete, conflict-free alert for the same event period and source continuity; a voluntary or conflict hold also needs new source evidence.",
            "parameters": {
                "type": "object",
                "properties": {
                    "thesis_id": {"type": "string"},
                    "alert_id": {"type": "string"},
                    "expected_version": {"type": "integer", "minimum": 1},
                    "event": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string"},
                            "summary": {"type": "string"},
                            "as_of": {"type": "string"},
                            "sources": {
                                "type": "array",
                                "items": {"type": "object"},
                            },
                        },
                        "required": ["summary"],
                    },
                    "impact": {
                        "type": "string",
                        "enum": sorted(REVIEW_IMPACTS),
                    },
                    "decision": {
                        "type": "string",
                        "enum": sorted(REVIEW_DECISIONS),
                    },
                    "rationale": {"type": "string"},
                    "matched_terms": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "evidence": {
                        "type": "array",
                        "items": {"type": "object"},
                    },
                    "causal_claims": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "target_metric": {
                                    "type": "string",
                                    "enum": sorted(_lineage.ALLOWED_DRIVER_LINES),
                                },
                                "strength": {
                                    "type": "string",
                                    "enum": sorted(_lineage.CLAIM_STRENGTHS),
                                    "description": (
                                        "directly_stated is valid for an unquantified "
                                        "source-explicit link when the stored driver fact "
                                        "lists the target in source_explicit_targets; "
                                        "do not invent a numerical contribution."
                                    ),
                                },
                                "driver_fact_ids": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "attributed_change_percentage_points": {
                                    "type": "number",
                                    "description": (
                                        "Only when a stored source reconciliation "
                                        "explicitly supports this contribution."
                                    ),
                                },
                            },
                            "required": [
                                "target_metric", "strength", "driver_fact_ids"
                            ],
                        },
                        "description": (
                            "Required when the stored alert has trusted statement_line metadata. "
                            "target_metric must be one of "
                            + ", ".join(sorted(_lineage.ALLOWED_DRIVER_LINES))
                            + ". strength must be one of "
                            + ", ".join(sorted(_lineage.CLAIM_STRENGTHS))
                            + ". Use only stored driver_fact_ids for a genuine causal link; "
                              "do not use an observed metric as its own cause. If no "
                              "source-backed driver exists, send [] and discuss the "
                              "unresolved attribution in the final answer. A trusted "
                              "source-explicit qualitative driver can be recorded "
                              "without a quantified bridge. The tool "
                              "replaces draft rationale with a validated summary."
                        ),
                    },
                    "new_status": {
                        "type": "string",
                        "enum": sorted(THESIS_STATUSES),
                    },
                    "new_conviction": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 5,
                    },
                    "next_review_at": {
                        "type": "string",
                        "description": "Future ISO date or timestamp for an operational review; historical source dates belong in evidence."
                    },
                },
                "required": [
                    "thesis_id",
                    "event",
                    "impact",
                    "decision",
                    "rationale",
                ],
            },
        },
        {
            "name": "watchlist_save",
            "description": "Create or update a tenant-isolated symbol watch with optional thesis linkage, event filters, keyword thresholds, and optimistic version checks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "watchlist_id": {"type": "string"},
                    "expected_version": {"type": "integer", "minimum": 1},
                    "market": market_property,
                    "symbol": {"type": "string"},
                    "thesis_id": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": sorted(WATCHLIST_STATUSES),
                    },
                    "event_types": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "min_match_score": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 100,
                    },
                    "dedupe_window_seconds": {
                        "type": "integer",
                        "minimum": 60,
                        "maximum": 604800,
                    },
                },
            },
        },
        {
            "name": "watchlist_list",
            "description": "List the current user's watchlist items with optional status, market, and symbol filters.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": sorted(WATCHLIST_STATUSES),
                    },
                    "market": market_property,
                    "symbol": {"type": "string"},
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 50,
                    },
                },
            },
        },
        {
            "name": "event_alert_ingest",
            "description": "Match one normalized market event against active watches and persist or deduplicate tenant-isolated alerts. Trusted ingestion may supply source_claims with metric, period, value, unit, fact_id and source_sha256; incompatible values for the same metric, period, and unit are marked as unresolved conflicts, including values printed in different tables of one source.",
            "parameters": {
                "type": "object",
                "properties": {
                    "market": market_property,
                    "symbol": {"type": "string"},
                    "event": {
                        "type": "object",
                        "properties": {
                            "external_id": {"type": "string"},
                            "type": {"type": "string"},
                            "summary": {"type": "string"},
                            "as_of": {"type": "string"},
                            "sources": {
                                "type": "array",
                                "items": {"type": "object"},
                            },
                            "observed_metrics": {
                                "type": "object",
                                "description": "Trusted event-packet metrics keyed by canonical metric name; each entry has value, unit, and fact_id. Optional audited statement_line metadata enables guarded causal reviews.",
                            },
                            "source_claims": {
                                "type": "array",
                                "items": {"type": "object"},
                            },
                        },
                        "required": ["summary"],
                    },
                },
                "required": ["market", "symbol", "event"],
            },
        },
        {
            "name": "alert_list",
            "description": "List persisted event alerts for the current user, including duplicate counts and review state.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": sorted(ALERT_STATUSES),
                    },
                    "market": market_property,
                    "symbol": {"type": "string"},
                    "watchlist_id": {"type": "string"},
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 50,
                    },
                },
            },
        },
        {
            "name": "alert_update",
            "description": "Acknowledge, dismiss, or reopen an owned event alert with optimistic version protection.",
            "parameters": {
                "type": "object",
                "properties": {
                    "alert_id": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": sorted(ALERT_STATUSES),
                    },
                    "expected_version": {"type": "integer", "minimum": 1},
                },
                "required": ["alert_id", "status"],
            },
        },
    ]


class FinanceStateStore:
    def __init__(self, path: Path, review_guard: Any = None) -> None:
        self.path = path
        self.review_guard = review_guard

    def migrate(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            os.chmod(self.path.parent, 0o700)
        except OSError:
            pass
        with self._connect() as database:
            database.executescript(
                """
                CREATE TABLE IF NOT EXISTS theses (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_by_agent_id TEXT NOT NULL,
                    created_in_session_id TEXT NOT NULL DEFAULT '',
                    market TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    title TEXT NOT NULL,
                    thesis TEXT NOT NULL,
                    status TEXT NOT NULL,
                    conviction INTEGER,
                    assumptions_json TEXT NOT NULL,
                    catalysts_json TEXT NOT NULL,
                    invalidations_json TEXT NOT NULL,
                    required_event_metrics_json TEXT NOT NULL DEFAULT '[]',
                    decision_hold INTEGER NOT NULL DEFAULT 0,
                    decision_hold_alert_id TEXT,
                    evidence_json TEXT NOT NULL,
                    next_review_at TEXT,
                    last_review_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    version INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_theses_tenant_symbol
                    ON theses(user_id, market, symbol);
                CREATE INDEX IF NOT EXISTS idx_theses_tenant_status
                    ON theses(user_id, status, updated_at);

                CREATE TABLE IF NOT EXISTS thesis_reviews (
                    id TEXT PRIMARY KEY,
                    thesis_id TEXT NOT NULL,
                    alert_id TEXT,
                    user_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    session_id TEXT NOT NULL DEFAULT '',
                    event_type TEXT NOT NULL,
                    event_summary TEXT NOT NULL,
                    event_as_of TEXT,
                    event_sources_json TEXT NOT NULL,
                    impact TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    rationale TEXT NOT NULL,
                    missing_metrics_json TEXT NOT NULL DEFAULT '[]',
                    unresolved_conflicts_json TEXT NOT NULL DEFAULT '[]',
                    matched_terms_json TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(thesis_id) REFERENCES theses(id)
                );
                CREATE INDEX IF NOT EXISTS idx_thesis_reviews_tenant_thesis
                    ON thesis_reviews(user_id, thesis_id, created_at);

                CREATE TABLE IF NOT EXISTS watchlist_items (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_by_agent_id TEXT NOT NULL,
                    created_in_session_id TEXT NOT NULL DEFAULT '',
                    market TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    thesis_id TEXT,
                    status TEXT NOT NULL,
                    event_types_json TEXT NOT NULL,
                    keywords_json TEXT NOT NULL,
                    min_match_score INTEGER NOT NULL,
                    dedupe_window_seconds INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    FOREIGN KEY(thesis_id) REFERENCES theses(id)
                );
                CREATE INDEX IF NOT EXISTS idx_watchlist_tenant_symbol
                    ON watchlist_items(user_id, market, symbol, status);
                CREATE INDEX IF NOT EXISTS idx_watchlist_tenant_updated
                    ON watchlist_items(user_id, updated_at);

                CREATE TABLE IF NOT EXISTS event_alerts (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    watchlist_id TEXT NOT NULL,
                    thesis_id TEXT,
                    created_by_agent_id TEXT NOT NULL,
                    created_in_session_id TEXT NOT NULL DEFAULT '',
                    market TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    event_fingerprint TEXT NOT NULL,
                    event_external_id TEXT,
                    event_type TEXT NOT NULL,
                    event_summary TEXT NOT NULL,
                    event_as_of TEXT,
                    event_sources_json TEXT NOT NULL,
                    observed_metrics_json TEXT NOT NULL DEFAULT '{}',
                    source_claims_json TEXT NOT NULL DEFAULT '[]',
                    unresolved_conflicts_json TEXT NOT NULL DEFAULT '[]',
                    matched_terms_json TEXT NOT NULL,
                    match_score INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    duplicate_count INTEGER NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    FOREIGN KEY(watchlist_id) REFERENCES watchlist_items(id),
                    FOREIGN KEY(thesis_id) REFERENCES theses(id)
                );
                CREATE INDEX IF NOT EXISTS idx_event_alerts_tenant_status
                    ON event_alerts(user_id, status, updated_at);
                CREATE INDEX IF NOT EXISTS idx_event_alerts_dedupe
                    ON event_alerts(user_id, watchlist_id, event_fingerprint, last_seen_at);
                """
            )
            # Existing ledgers created before the evidence-completeness rule
            # remain readable. Opt-in requirements default to an empty list.
            thesis_columns = {row[1] for row in database.execute("PRAGMA table_info(theses)")}
            if "required_event_metrics_json" not in thesis_columns:
                database.execute(
                    "ALTER TABLE theses ADD COLUMN required_event_metrics_json TEXT NOT NULL DEFAULT '[]'"
                )
            if "decision_hold" not in thesis_columns:
                database.execute("ALTER TABLE theses ADD COLUMN decision_hold INTEGER NOT NULL DEFAULT 0")
            if "decision_hold_alert_id" not in thesis_columns:
                database.execute("ALTER TABLE theses ADD COLUMN decision_hold_alert_id TEXT")
            alert_columns = {row[1] for row in database.execute("PRAGMA table_info(event_alerts)")}
            if "observed_metrics_json" not in alert_columns:
                database.execute(
                    "ALTER TABLE event_alerts ADD COLUMN observed_metrics_json TEXT NOT NULL DEFAULT '{}'"
                )
            if "source_claims_json" not in alert_columns:
                database.execute("ALTER TABLE event_alerts ADD COLUMN source_claims_json TEXT NOT NULL DEFAULT '[]'")
            if "unresolved_conflicts_json" not in alert_columns:
                database.execute("ALTER TABLE event_alerts ADD COLUMN unresolved_conflicts_json TEXT NOT NULL DEFAULT '[]'")
            review_columns = {row[1] for row in database.execute("PRAGMA table_info(thesis_reviews)")}
            if "alert_id" not in review_columns:
                database.execute("ALTER TABLE thesis_reviews ADD COLUMN alert_id TEXT")
            if "missing_metrics_json" not in review_columns:
                database.execute(
                    "ALTER TABLE thesis_reviews ADD COLUMN missing_metrics_json TEXT NOT NULL DEFAULT '[]'"
                )
            if "unresolved_conflicts_json" not in review_columns:
                database.execute("ALTER TABLE thesis_reviews ADD COLUMN unresolved_conflicts_json TEXT NOT NULL DEFAULT '[]'")
            database.execute("PRAGMA user_version = 4")
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    def save(
        self,
        tenant: dict[str, str],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        now = isoformat(utc_now())
        thesis_id = payload.get("thesis_id")
        with self._connect() as database:
            database.execute("BEGIN IMMEDIATE")
            if thesis_id:
                existing = self._fetch_owned(database, tenant["user_id"], thesis_id)
                expected_version = payload.get("expected_version")
                if (
                    expected_version is not None
                    and int(expected_version) != existing["version"]
                ):
                    raise ToolStateError(
                        "version_conflict",
                        "thesis changed since it was read",
                        True,
                        {
                            "expected_version": int(expected_version),
                            "actual_version": existing["version"],
                        },
                    )
                merged = dict(existing)
                for key in (
                    "market",
                    "symbol",
                    "title",
                    "thesis",
                    "status",
                    "conviction",
                    "assumptions",
                    "catalysts",
                    "invalidations",
                    "required_event_metrics",
                    "evidence",
                    "next_review_at",
                ):
                    if key in payload:
                        merged[key] = payload[key]
                if existing["decision_hold"] and (
                    merged["status"] != existing["status"]
                    or merged["conviction"] != existing["conviction"]
                    or merged["required_event_metrics"] != existing["required_event_metrics"]
                ):
                    raise ToolStateError(
                        "decision_on_hold",
                        "pending evidence blocks status, conviction, or required-metric changes",
                        False,
                        {"alert_id": existing["decision_hold_alert_id"]},
                    )
                version = existing["version"] + 1
                database.execute(
                    """
                    UPDATE theses
                    SET market = ?, symbol = ?, title = ?, thesis = ?, status = ?,
                        conviction = ?, assumptions_json = ?, catalysts_json = ?,
                        invalidations_json = ?, required_event_metrics_json = ?, evidence_json = ?,
                        next_review_at = ?, updated_at = ?, version = ?
                    WHERE id = ? AND user_id = ?
                    """,
                    (
                        merged["market"],
                        merged["symbol"],
                        merged["title"],
                        merged["thesis"],
                        merged["status"],
                        merged["conviction"],
                        self._json(merged["assumptions"]),
                        self._json(merged["catalysts"]),
                        self._json(merged["invalidations"]),
                        self._json(merged["required_event_metrics"]),
                        self._json(merged["evidence"]),
                        merged["next_review_at"],
                        now,
                        version,
                        thesis_id,
                        tenant["user_id"],
                    ),
                )
            else:
                thesis_id = "th_" + uuid.uuid4().hex[:20]
                version = 1
                database.execute(
                    """
                    INSERT INTO theses (
                        id, user_id, created_by_agent_id, created_in_session_id,
                        market, symbol, title, thesis, status, conviction,
                        assumptions_json, catalysts_json, invalidations_json,
                        required_event_metrics_json,
                        evidence_json, next_review_at, last_review_at,
                        created_at, updated_at, version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)
                    """,
                    (
                        thesis_id,
                        tenant["user_id"],
                        tenant["agent_id"],
                        tenant["session_id"],
                        payload["market"],
                        payload["symbol"],
                        payload["title"],
                        payload["thesis"],
                        payload["status"],
                        payload["conviction"],
                        self._json(payload["assumptions"]),
                        self._json(payload["catalysts"]),
                        self._json(payload["invalidations"]),
                        self._json(payload["required_event_metrics"]),
                        self._json(payload["evidence"]),
                        payload["next_review_at"],
                        now,
                        now,
                        version,
                    ),
                )
            return self._fetch_owned(database, tenant["user_id"], thesis_id)

    def get(
        self,
        user_id: str,
        thesis_id: str,
        review_limit: int,
    ) -> dict[str, Any]:
        with self._connect() as database:
            thesis = self._fetch_owned(database, user_id, thesis_id)
            reviews = database.execute(
                """
                SELECT * FROM thesis_reviews
                WHERE user_id = ? AND thesis_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (user_id, thesis_id, review_limit),
            ).fetchall()
            return {
                "thesis": thesis,
                "reviews": [self._review_from_row(row) for row in reviews],
            }

    def list(
        self,
        user_id: str,
        filters: dict[str, Any],
    ) -> list[dict[str, Any]]:
        clauses = ["user_id = ?"]
        values: list[Any] = [user_id]
        for key in ("status", "market", "symbol"):
            value = filters.get(key)
            if value:
                clauses.append(f"{key} = ?")
                values.append(value)
        values.append(filters["limit"])
        with self._connect() as database:
            rows = database.execute(
                f"""
                SELECT * FROM theses
                WHERE {' AND '.join(clauses)}
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                values,
            ).fetchall()
            return [self._thesis_from_row(row) for row in rows]

    def match_event(
        self,
        user_id: str,
        market: str,
        symbol: str,
        event_summary: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        with self._connect() as database:
            rows = database.execute(
                """
                SELECT * FROM theses
                WHERE user_id = ? AND market = ? AND symbol = ?
                  AND status IN ('researching', 'watch', 'active')
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (user_id, market, symbol, limit),
            ).fetchall()
        event_text = event_summary.casefold()
        matches = []
        for row in rows:
            thesis = self._thesis_from_row(row)
            buckets = {
                "invalidations": 3,
                "catalysts": 2,
                "assumptions": 1,
            }
            matched_terms = []
            score = 0
            for bucket, weight in buckets.items():
                for term in self._keywords(thesis[bucket]):
                    if term in event_text:
                        matched_terms.append({"bucket": bucket, "term": term})
                        score += weight
            matches.append(
                {
                    "thesis_id": thesis["id"],
                    "title": thesis["title"],
                    "status": thesis["status"],
                    "version": thesis["version"],
                    "match_score": score,
                    "matched_terms": matched_terms,
                    "match_reason": "term_match" if matched_terms else "symbol_match",
                }
            )
        matches.sort(key=lambda item: (item["match_score"], item["version"]), reverse=True)
        return matches

    def record_review(
        self,
        tenant: dict[str, str],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        now = isoformat(utc_now())
        thesis_id = payload["thesis_id"]
        with self._connect() as database:
            database.execute("BEGIN IMMEDIATE")
            existing = self._fetch_owned(database, tenant["user_id"], thesis_id)
            expected_version = payload.get("expected_version")
            if (
                expected_version is not None
                and int(expected_version) != existing["version"]
            ):
                raise ToolStateError(
                    "version_conflict",
                    "thesis changed before the event review was recorded",
                    True,
                    {
                        "expected_version": int(expected_version),
                        "actual_version": existing["version"],
                    },
                )
            alert_id = payload.get("alert_id")
            if (existing["required_event_metrics"] or existing["decision_hold"]
                    or payload["decision"] == "needs_review") and not alert_id:
                raise ToolStateError(
                    "alert_required",
                    "a linked, stored alert is required to verify event metrics or resolve a decision hold",
                    True,
                    {"required_metrics": existing["required_event_metrics"],
                     "decision_hold_alert_id": existing["decision_hold_alert_id"]},
                )
            event = payload["event"]
            missing_metrics = []
            unresolved_conflicts = []
            alert = None
            if alert_id:
                alert = self._fetch_alert_owned(database, tenant["user_id"], alert_id)
                if alert["thesis_id"] != thesis_id:
                    raise ToolStateError(
                        "alert_thesis_mismatch",
                        "alert is not linked to the reviewed thesis",
                    )
                # Never evaluate evidence completeness against the model's
                # review arguments. Use only the event saved at ingestion.
                event = alert["event"]
                missing_metrics = sorted(
                    set(existing["required_event_metrics"])
                    - set(event["observed_metrics"])
                )
                unresolved_conflicts = event["unresolved_conflicts"]
            review_guard_alerts = []
            if self.review_guard is not None:
                if not alert and payload["decision"] != "needs_review":
                    raise ToolStateError(
                        "review_guard_alert_required",
                        "source-bound arithmetic review requires a stored alert",
                        True,
                    )
                if alert:
                    try:
                        review_guard_alerts = self.review_guard.check(
                            existing, event, payload["rationale"], payload["decision"])
                    except _review_guard.GuardCatalogError as exc:
                        if payload["decision"] != "needs_review":
                            raise ToolStateError(
                                "review_guard_source_mismatch", str(exc), False,
                            ) from exc
                        # A deferred review must still be able to establish a
                        # decision hold when the catalog cannot validate it.
                        review_guard_alerts = ["source_comparison_unavailable"]
                if review_guard_alerts and payload["decision"] != "needs_review":
                    raise ToolStateError(
                        "review_arithmetic_contradiction",
                        "proposed review contradicts the trusted source comparison; "
                        "submit a corrected review or needs_review without changing "
                        "status or conviction",
                        True,
                        {"alert_id": alert_id, "alerts": review_guard_alerts},
                    )
            lineage_metadata = bool(alert and any(
                "statement_line" in metric
                for metric in event["observed_metrics"].values()
            ))
            if lineage_metadata:
                if "causal_claims" not in payload:
                    raise ToolStateError(
                        "causal_claims_required",
                        "this source-classified alert requires structured causal claims",
                        True,
                        {"alert_id": alert_id},
                    )
                facts = {}
                for metric in event["observed_metrics"].values():
                    fact_id = metric["fact_id"]
                    if fact_id in facts:
                        raise ToolStateError(
                            "duplicate_lineage_fact_id",
                            "the stored event reuses a fact_id across metrics",
                        )
                    facts[fact_id] = metric
                try:
                    validated_claims = _lineage.validate_causal_claims(
                        facts, payload["causal_claims"]
                    )
                except _lineage.ClaimValidationError as exc:
                    raise ToolStateError(
                        "unsupported_causal_claim", str(exc), True,
                        {
                            "alert_id": alert_id,
                            "allowed_target_metrics": sorted(_lineage.ALLOWED_DRIVER_LINES),
                            "allowed_strengths": sorted(_lineage.CLAIM_STRENGTHS),
                            "no_supported_attribution": {
                                "causal_claims": [],
                                "meaning": "Record the review without a causal attribution; discuss uncertainty in the final answer.",
                            },
                        },
                    ) from exc
                payload["rationale"] = _lineage.render_guarded_rationale(
                    payload["decision"], payload["impact"],
                    event["observed_metrics"], validated_claims,
                )
                payload["matched_terms"] = alert["matched_terms"]
                payload["evidence"] = [{
                    "type": "validated_accounting_lineage",
                    "claims": validated_claims,
                    "source_hashes": [source.get("sha256") for source in event["sources"]],
                }]
            elif payload.get("causal_claims"):
                raise ToolStateError(
                    "accounting_lineage_metadata_missing",
                    "structured causal claims require trusted statement-line metadata in the stored alert",
                )
            review_rationale = payload["rationale"]
            if review_guard_alerts and payload["decision"] == "needs_review":
                review_rationale = (
                    "Source-bound review check flagged "
                    + ", ".join(sorted(review_guard_alerts))
                    + ". The proposed financial interpretation is not accepted; "
                    "the research thesis remains on hold pending independent "
                    "source verification and a corrected review."
                )
            resolving_hold = False
            if existing["decision_hold"]:
                if alert_id != existing["decision_hold_alert_id"]:
                    held_alert = self._fetch_alert_owned(
                        database, tenant["user_id"], existing["decision_hold_alert_id"]
                    )
                    held_event = held_alert["event"]
                    held_missing = (
                        set(existing["required_event_metrics"])
                        - set(held_event["observed_metrics"])
                    )
                    held_hashes = {
                        source["sha256"] for source in held_event["sources"]
                    }
                    new_hashes = {
                        source["sha256"] for source in event["sources"]
                    }
                    resolving_hold = bool(
                        alert
                        and not missing_metrics
                        and not unresolved_conflicts
                        and new_hashes
                        and (not held_hashes or bool(new_hashes & held_hashes))
                        and (held_missing or bool(new_hashes - held_hashes))
                        and event["type"] == held_event["type"]
                        and event["as_of"] == held_event["as_of"]
                        and alert["market"] == held_alert["market"]
                        and alert["symbol"] == held_alert["symbol"]
                    )
                    if not resolving_hold:
                        raise ToolStateError(
                            "decision_hold_alert_mismatch",
                            "the hold requires its original alert or a complete, conflict-free alert for the same event period with source continuity and new evidence when required",
                            False,
                            {"decision_hold_alert_id": existing["decision_hold_alert_id"]},
                        )
                if (not resolving_hold or
                    payload["decision"] == "needs_review") and (
                    payload["decision"] != "needs_review"
                    or payload.get("new_status", existing["status"]) != existing["status"]
                    or payload.get("new_conviction", existing["conviction"])
                    != existing["conviction"]
                ):
                    raise ToolStateError(
                        "decision_on_hold",
                        "pending evidence blocks substantive reviews",
                        False,
                        {"alert_id": existing["decision_hold_alert_id"]},
                    )
            if payload["decision"] == "needs_review" and (
                payload.get("new_status", existing["status"]) != existing["status"]
                or payload.get("new_conviction", existing["conviction"])
                != existing["conviction"]
            ):
                raise ToolStateError(
                    "decision_on_hold",
                    "needs_review cannot change status or conviction",
                    False,
                    {"alert_id": alert_id},
                )
            if alert_id:
                if unresolved_conflicts and (
                    payload["decision"] != "needs_review"
                    or payload.get("new_status", existing["status"]) != existing["status"]
                    or payload.get("new_conviction", existing["conviction"])
                    != existing["conviction"]
                ):
                    raise ToolStateError(
                        "source_conflict_unresolved",
                        "conflicting source claims require needs_review without a state or conviction change",
                        True,
                        {"alert_id": alert_id, "unresolved_conflicts": unresolved_conflicts},
                    )
                if missing_metrics and (
                    payload["decision"] != "needs_review"
                    or payload.get("new_status", existing["status"]) != existing["status"]
                    or payload.get("new_conviction", existing["conviction"])
                    != existing["conviction"]
                ):
                    raise ToolStateError(
                        "required_evidence_missing",
                        "missing required event metrics require needs_review without a state or conviction change",
                        True,
                        {"alert_id": alert_id, "missing_metrics": missing_metrics},
                    )
            review_id = "tr_" + uuid.uuid4().hex[:20]
            database.execute(
                """
                INSERT INTO thesis_reviews (
                    id, thesis_id, alert_id, user_id, agent_id, session_id,
                    event_type, event_summary, event_as_of, event_sources_json,
                    impact, decision, rationale, missing_metrics_json, matched_terms_json,
                    unresolved_conflicts_json, evidence_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    review_id,
                    thesis_id,
                    alert_id,
                    tenant["user_id"],
                    tenant["agent_id"],
                    tenant["session_id"],
                    event["type"],
                    event["summary"],
                    event["as_of"],
                    self._json(event["sources"]),
                    payload["impact"],
                    payload["decision"],
                    review_rationale,
                    self._json(missing_metrics),
                    self._json(payload["matched_terms"]),
                    self._json(unresolved_conflicts),
                    self._json(payload["evidence"]),
                    now,
                ),
            )
            new_status = payload.get("new_status")
            if payload["decision"] == "invalidate" and not new_status:
                new_status = "invalidated"
            status = new_status or existing["status"]
            conviction = payload.get("new_conviction", existing["conviction"])
            next_review_at = payload.get(
                "next_review_at", existing["next_review_at"]
            )
            version = existing["version"] + 1
            decision_hold = bool(
                (existing["decision_hold"] and
                 not (resolving_hold and payload["decision"] != "needs_review"))
                or unresolved_conflicts or missing_metrics
                or payload["decision"] == "needs_review"
            )
            decision_hold_alert_id = (
                (alert_id if payload["decision"] == "needs_review" else
                 (existing["decision_hold_alert_id"] or alert_id))
                if decision_hold else None
            )
            database.execute(
                """
                UPDATE theses
                SET status = ?, conviction = ?, next_review_at = ?,
                    last_review_at = ?, updated_at = ?, version = ?,
                    decision_hold = ?, decision_hold_alert_id = ?
                WHERE id = ? AND user_id = ?
                """,
                (
                    status,
                    conviction,
                    next_review_at,
                    now,
                    now,
                    version,
                    int(decision_hold),
                    decision_hold_alert_id,
                    thesis_id,
                    tenant["user_id"],
                ),
            )
            thesis = self._fetch_owned(database, tenant["user_id"], thesis_id)
            review = database.execute(
                "SELECT * FROM thesis_reviews WHERE id = ?",
                (review_id,),
            ).fetchone()
            return {
                "thesis": thesis,
                "review": self._review_from_row(review),
            }

    def save_watchlist(
        self,
        tenant: dict[str, str],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        now = isoformat(utc_now())
        watchlist_id = payload.get("watchlist_id")
        with self._connect() as database:
            database.execute("BEGIN IMMEDIATE")
            if watchlist_id:
                existing = self._fetch_watchlist_owned(
                    database, tenant["user_id"], watchlist_id
                )
                expected_version = payload.get("expected_version")
                if (
                    expected_version is not None
                    and int(expected_version) != existing["version"]
                ):
                    raise ToolStateError(
                        "version_conflict",
                        "watchlist item changed since it was read",
                        True,
                        {
                            "expected_version": int(expected_version),
                            "actual_version": existing["version"],
                        },
                    )
                merged = dict(existing)
                for key in (
                    "market",
                    "symbol",
                    "thesis_id",
                    "status",
                    "event_types",
                    "keywords",
                    "min_match_score",
                    "dedupe_window_seconds",
                ):
                    if key in payload:
                        merged[key] = payload[key]
                self._validate_owned_thesis(
                    database,
                    tenant["user_id"],
                    merged["thesis_id"],
                    merged["market"],
                    merged["symbol"],
                )
                duplicate = self._find_watchlist_duplicate(
                    database,
                    tenant["user_id"],
                    merged["market"],
                    merged["symbol"],
                    merged["thesis_id"],
                    watchlist_id,
                )
                if duplicate:
                    raise ToolStateError(
                        "watchlist_exists",
                        "an equivalent watchlist item already exists",
                        False,
                        {"watchlist_id": duplicate},
                    )
                version = existing["version"] + 1
                database.execute(
                    """
                    UPDATE watchlist_items
                    SET market = ?, symbol = ?, thesis_id = ?, status = ?,
                        event_types_json = ?, keywords_json = ?,
                        min_match_score = ?, dedupe_window_seconds = ?,
                        updated_at = ?, version = ?
                    WHERE id = ? AND user_id = ?
                    """,
                    (
                        merged["market"],
                        merged["symbol"],
                        merged["thesis_id"],
                        merged["status"],
                        self._json(merged["event_types"]),
                        self._json(merged["keywords"]),
                        merged["min_match_score"],
                        merged["dedupe_window_seconds"],
                        now,
                        version,
                        watchlist_id,
                        tenant["user_id"],
                    ),
                )
            else:
                self._validate_owned_thesis(
                    database,
                    tenant["user_id"],
                    payload["thesis_id"],
                    payload["market"],
                    payload["symbol"],
                )
                duplicate = self._find_watchlist_duplicate(
                    database,
                    tenant["user_id"],
                    payload["market"],
                    payload["symbol"],
                    payload["thesis_id"],
                    "",
                )
                if duplicate:
                    raise ToolStateError(
                        "watchlist_exists",
                        "an equivalent watchlist item already exists",
                        False,
                        {"watchlist_id": duplicate},
                    )
                watchlist_id = "wl_" + uuid.uuid4().hex[:20]
                version = 1
                database.execute(
                    """
                    INSERT INTO watchlist_items (
                        id, user_id, created_by_agent_id, created_in_session_id,
                        market, symbol, thesis_id, status, event_types_json,
                        keywords_json, min_match_score, dedupe_window_seconds,
                        created_at, updated_at, version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        watchlist_id,
                        tenant["user_id"],
                        tenant["agent_id"],
                        tenant["session_id"],
                        payload["market"],
                        payload["symbol"],
                        payload["thesis_id"],
                        payload["status"],
                        self._json(payload["event_types"]),
                        self._json(payload["keywords"]),
                        payload["min_match_score"],
                        payload["dedupe_window_seconds"],
                        now,
                        now,
                        version,
                    ),
                )
            return self._fetch_watchlist_owned(
                database, tenant["user_id"], watchlist_id
            )

    def list_watchlist(
        self,
        user_id: str,
        filters: dict[str, Any],
    ) -> list[dict[str, Any]]:
        clauses = ["user_id = ?"]
        values: list[Any] = [user_id]
        for key in ("status", "market", "symbol"):
            value = filters.get(key)
            if value:
                clauses.append(f"{key} = ?")
                values.append(value)
        values.append(filters["limit"])
        with self._connect() as database:
            rows = database.execute(
                f"""
                SELECT * FROM watchlist_items
                WHERE {' AND '.join(clauses)}
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                values,
            ).fetchall()
            return [self._watchlist_from_row(row) for row in rows]

    def ingest_event(
        self,
        tenant: dict[str, str],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        now_value = utc_now()
        now = isoformat(now_value)
        event = payload["event"]
        fingerprint = self._event_fingerprint(
            payload["market"], payload["symbol"], event
        )
        results = []
        skipped = []
        with self._connect() as database:
            database.execute("BEGIN IMMEDIATE")
            rows = database.execute(
                """
                SELECT * FROM watchlist_items
                WHERE user_id = ? AND market = ? AND symbol = ?
                  AND status = 'active'
                ORDER BY updated_at DESC
                """,
                (tenant["user_id"], payload["market"], payload["symbol"]),
            ).fetchall()
            for row in rows:
                watchlist = self._watchlist_from_row(row)
                event_type = event["type"].casefold()
                if (
                    watchlist["event_types"]
                    and event_type not in watchlist["event_types"]
                ):
                    skipped.append(
                        {
                            "watchlist_id": watchlist["id"],
                            "reason": "event_type_filtered",
                        }
                    )
                    continue
                matched_terms, match_score = self._score_watchlist_event(
                    database,
                    tenant["user_id"],
                    watchlist,
                    event["summary"],
                )
                if match_score < watchlist["min_match_score"]:
                    skipped.append(
                        {
                            "watchlist_id": watchlist["id"],
                            "reason": "below_match_threshold",
                            "match_score": match_score,
                        }
                    )
                    continue
                existing_row = database.execute(
                    """
                    SELECT * FROM event_alerts
                    WHERE user_id = ? AND watchlist_id = ?
                      AND event_fingerprint = ?
                    ORDER BY last_seen_at DESC
                    LIMIT 1
                    """,
                    (
                        tenant["user_id"],
                        watchlist["id"],
                        fingerprint,
                    ),
                ).fetchone()
                if existing_row is not None and self._within_dedupe_window(
                    existing_row["last_seen_at"],
                    now_value,
                    watchlist["dedupe_window_seconds"],
                ):
                    database.execute(
                        """
                        UPDATE event_alerts
                        SET duplicate_count = duplicate_count + 1,
                            last_seen_at = ?, event_summary = ?,
                            event_as_of = ?, event_sources_json = ?,
                            observed_metrics_json = ?, source_claims_json = ?,
                            unresolved_conflicts_json = ?,
                            matched_terms_json = ?, match_score = ?,
                            updated_at = ?, version = version + 1
                        WHERE id = ? AND user_id = ?
                        """,
                        (
                            now,
                            event["summary"],
                            event["as_of"],
                            self._json(event["sources"]),
                            self._json(event["observed_metrics"]),
                            self._json(event["source_claims"]),
                            self._json(event["unresolved_conflicts"]),
                            self._json(matched_terms),
                            match_score,
                            now,
                            existing_row["id"],
                            tenant["user_id"],
                        ),
                    )
                    alert = self._fetch_alert_owned(
                        database, tenant["user_id"], existing_row["id"]
                    )
                    action = "deduplicated"
                else:
                    alert_id = "fa_" + uuid.uuid4().hex[:20]
                    database.execute(
                        """
                        INSERT INTO event_alerts (
                            id, user_id, watchlist_id, thesis_id,
                            created_by_agent_id, created_in_session_id,
                            market, symbol, event_fingerprint, event_external_id,
                            event_type, event_summary, event_as_of,
                            event_sources_json, observed_metrics_json,
                            source_claims_json, unresolved_conflicts_json,
                            matched_terms_json, match_score,
                            status, duplicate_count, first_seen_at, last_seen_at,
                            created_at, updated_at, version
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, 1)
                        """,
                        (
                            alert_id,
                            tenant["user_id"],
                            watchlist["id"],
                            watchlist["thesis_id"],
                            tenant["agent_id"],
                            tenant["session_id"],
                            payload["market"],
                            payload["symbol"],
                            fingerprint,
                            event["external_id"],
                            event["type"],
                            event["summary"],
                            event["as_of"],
                            self._json(event["sources"]),
                            self._json(event["observed_metrics"]),
                            self._json(event["source_claims"]),
                            self._json(event["unresolved_conflicts"]),
                            self._json(matched_terms),
                            match_score,
                            "new",
                            now,
                            now,
                            now,
                            now,
                        ),
                    )
                    alert = self._fetch_alert_owned(
                        database, tenant["user_id"], alert_id
                    )
                    action = "created"
                if alert["thesis_id"]:
                    thesis = self._fetch_owned(
                        database, tenant["user_id"], alert["thesis_id"]
                    )
                    missing_metrics = (
                        set(thesis["required_event_metrics"])
                        - set(alert["event"]["observed_metrics"])
                    )
                    # The hold starts at stored ingestion, before a model
                    # review can omit the alert linkage or rewrite the event.
                    if event["unresolved_conflicts"] or missing_metrics:
                        database.execute(
                            """
                            UPDATE theses SET decision_hold = 1,
                                decision_hold_alert_id = ?, updated_at = ?,
                                version = version + 1
                            WHERE id = ? AND user_id = ? AND decision_hold = 0
                            """,
                            (alert["id"], now, alert["thesis_id"], tenant["user_id"]),
                        )
                results.append(
                    {
                        "action": action,
                        "watchlist": watchlist,
                        "alert": alert,
                    }
                )
        return {
            "market": payload["market"],
            "symbol": payload["symbol"],
            "event_fingerprint": fingerprint,
            "results": results,
            "created": sum(item["action"] == "created" for item in results),
            "deduplicated": sum(
                item["action"] == "deduplicated" for item in results
            ),
            "skipped": skipped,
        }

    def list_alerts(
        self,
        user_id: str,
        filters: dict[str, Any],
    ) -> list[dict[str, Any]]:
        clauses = ["user_id = ?"]
        values: list[Any] = [user_id]
        for key in ("status", "market", "symbol", "watchlist_id"):
            value = filters.get(key)
            if value:
                clauses.append(f"{key} = ?")
                values.append(value)
        values.append(filters["limit"])
        with self._connect() as database:
            rows = database.execute(
                f"""
                SELECT * FROM event_alerts
                WHERE {' AND '.join(clauses)}
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                values,
            ).fetchall()
            return [self._alert_from_row(row) for row in rows]

    def update_alert(
        self,
        tenant: dict[str, str],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        now = isoformat(utc_now())
        with self._connect() as database:
            database.execute("BEGIN IMMEDIATE")
            existing = self._fetch_alert_owned(
                database, tenant["user_id"], payload["alert_id"]
            )
            expected_version = payload.get("expected_version")
            if (
                expected_version is not None
                and int(expected_version) != existing["version"]
            ):
                raise ToolStateError(
                    "version_conflict",
                    "alert changed since it was read",
                    True,
                    {
                        "expected_version": int(expected_version),
                        "actual_version": existing["version"],
                    },
                )
            database.execute(
                """
                UPDATE event_alerts
                SET status = ?, updated_at = ?, version = version + 1
                WHERE id = ? AND user_id = ?
                """,
                (
                    payload["status"],
                    now,
                    payload["alert_id"],
                    tenant["user_id"],
                ),
            )
            return self._fetch_alert_owned(
                database, tenant["user_id"], payload["alert_id"]
            )

    def _connect(self) -> sqlite3.Connection:
        database = sqlite3.connect(str(self.path), timeout=5)
        database.row_factory = sqlite3.Row
        database.execute("PRAGMA foreign_keys = ON")
        database.execute("PRAGMA busy_timeout = 5000")
        return database

    def _fetch_owned(
        self,
        database: sqlite3.Connection,
        user_id: str,
        thesis_id: str,
    ) -> dict[str, Any]:
        row = database.execute(
            "SELECT * FROM theses WHERE id = ? AND user_id = ?",
            (thesis_id, user_id),
        ).fetchone()
        if row is None:
            raise ToolStateError("thesis_not_found", "thesis not found")
        return self._thesis_from_row(row)

    def _validate_owned_thesis(
        self,
        database: sqlite3.Connection,
        user_id: str,
        thesis_id: str | None,
        market: str,
        symbol: str,
    ) -> None:
        if thesis_id:
            thesis = self._fetch_owned(database, user_id, thesis_id)
            if thesis["market"] != market or thesis["symbol"] != symbol:
                raise ToolStateError(
                    "thesis_watch_mismatch",
                    "linked thesis market and symbol must match the watchlist item",
                )

    def _find_watchlist_duplicate(
        self,
        database: sqlite3.Connection,
        user_id: str,
        market: str,
        symbol: str,
        thesis_id: str | None,
        exclude_id: str,
    ) -> str:
        row = database.execute(
            """
            SELECT id FROM watchlist_items
            WHERE user_id = ? AND market = ? AND symbol = ?
              AND COALESCE(thesis_id, '') = COALESCE(?, '')
              AND id != ?
            LIMIT 1
            """,
            (user_id, market, symbol, thesis_id, exclude_id),
        ).fetchone()
        return str(row["id"]) if row is not None else ""

    def _fetch_watchlist_owned(
        self,
        database: sqlite3.Connection,
        user_id: str,
        watchlist_id: str,
    ) -> dict[str, Any]:
        row = database.execute(
            "SELECT * FROM watchlist_items WHERE id = ? AND user_id = ?",
            (watchlist_id, user_id),
        ).fetchone()
        if row is None:
            raise ToolStateError(
                "watchlist_not_found", "watchlist item not found"
            )
        return self._watchlist_from_row(row)

    def _fetch_alert_owned(
        self,
        database: sqlite3.Connection,
        user_id: str,
        alert_id: str,
    ) -> dict[str, Any]:
        row = database.execute(
            "SELECT * FROM event_alerts WHERE id = ? AND user_id = ?",
            (alert_id, user_id),
        ).fetchone()
        if row is None:
            raise ToolStateError("alert_not_found", "event alert not found")
        return self._alert_from_row(row)

    def _thesis_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        if row["decision_hold"]:
            actionability = "blocked"
        elif row["status"] in ("researching", "watch"):
            actionability = "research_only"
        elif row["status"] in ("invalidated", "archived"):
            actionability = "closed"
        else:
            actionability = "available"
        return {
            "id": row["id"],
            "market": row["market"],
            "symbol": row["symbol"],
            "title": row["title"],
            "thesis": row["thesis"],
            "status": row["status"],
            "conviction": row["conviction"],
            "decision_hold": bool(row["decision_hold"]),
            "actionability": actionability,
            "decision_hold_alert_id": row["decision_hold_alert_id"],
            "assumptions": json.loads(row["assumptions_json"]),
            "catalysts": json.loads(row["catalysts_json"]),
            "invalidations": json.loads(row["invalidations_json"]),
            "required_event_metrics": json.loads(row["required_event_metrics_json"]),
            "evidence": json.loads(row["evidence_json"]),
            "next_review_at": row["next_review_at"],
            "last_review_at": row["last_review_at"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "version": row["version"],
            "created_by_agent_id": row["created_by_agent_id"],
            "created_in_session_id": row["created_in_session_id"],
        }

    def _review_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "thesis_id": row["thesis_id"],
            "alert_id": row["alert_id"],
            "agent_id": row["agent_id"],
            "session_id": row["session_id"],
            "event": {
                "type": row["event_type"],
                "summary": row["event_summary"],
                "as_of": row["event_as_of"],
                "sources": json.loads(row["event_sources_json"]),
            },
            "impact": row["impact"],
            "decision": row["decision"],
            "rationale": row["rationale"],
            "missing_metrics": json.loads(row["missing_metrics_json"]),
            "unresolved_conflicts": json.loads(row["unresolved_conflicts_json"]),
            "matched_terms": json.loads(row["matched_terms_json"]),
            "evidence": json.loads(row["evidence_json"]),
            "created_at": row["created_at"],
        }

    def _watchlist_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "market": row["market"],
            "symbol": row["symbol"],
            "thesis_id": row["thesis_id"],
            "status": row["status"],
            "event_types": json.loads(row["event_types_json"]),
            "keywords": json.loads(row["keywords_json"]),
            "min_match_score": row["min_match_score"],
            "dedupe_window_seconds": row["dedupe_window_seconds"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "version": row["version"],
            "created_by_agent_id": row["created_by_agent_id"],
            "created_in_session_id": row["created_in_session_id"],
        }

    def _alert_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "watchlist_id": row["watchlist_id"],
            "thesis_id": row["thesis_id"],
            "market": row["market"],
            "symbol": row["symbol"],
            "event_fingerprint": row["event_fingerprint"],
            "event": {
                "external_id": row["event_external_id"],
                "type": row["event_type"],
                "summary": row["event_summary"],
                "as_of": row["event_as_of"],
                "sources": json.loads(row["event_sources_json"]),
                "observed_metrics": json.loads(row["observed_metrics_json"]),
                "source_claims": json.loads(row["source_claims_json"]),
                "unresolved_conflicts": json.loads(row["unresolved_conflicts_json"]),
            },
            "matched_terms": json.loads(row["matched_terms_json"]),
            "match_score": row["match_score"],
            "status": row["status"],
            "duplicate_count": row["duplicate_count"],
            "first_seen_at": row["first_seen_at"],
            "last_seen_at": row["last_seen_at"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "version": row["version"],
            "created_by_agent_id": row["created_by_agent_id"],
            "created_in_session_id": row["created_in_session_id"],
        }

    def _score_watchlist_event(
        self,
        database: sqlite3.Connection,
        user_id: str,
        watchlist: dict[str, Any],
        event_summary: str,
    ) -> tuple[list[dict[str, Any]], int]:
        event_text = event_summary.casefold()
        weighted_terms = [
            ("watchlist", term, 1) for term in self._keywords(watchlist["keywords"])
        ]
        if watchlist["thesis_id"]:
            thesis = self._fetch_owned(
                database, user_id, watchlist["thesis_id"]
            )
            for bucket, weight in (
                ("invalidations", 3),
                ("catalysts", 2),
                ("assumptions", 1),
            ):
                weighted_terms.extend(
                    (bucket, term, weight)
                    for term in self._keywords(thesis[bucket])
                )
        matches = []
        seen = set()
        score = 0
        for bucket, term, weight in weighted_terms:
            key = (bucket, term)
            if key in seen or term not in event_text:
                continue
            seen.add(key)
            matches.append({"bucket": bucket, "term": term, "weight": weight})
            score += weight
        return matches, score

    def _event_fingerprint(
        self,
        market: str,
        symbol: str,
        event: dict[str, Any],
    ) -> str:
        external_id = str(event.get("external_id") or "").strip().casefold()
        if external_id:
            identity = {
                "market": market,
                "symbol": symbol,
                "type": event["type"].casefold(),
                "external_id": external_id,
            }
        else:
            normalized_summary = re.sub(
                r"\s+", " ", event["summary"].casefold()
            ).strip()
            identity = {
                "market": market,
                "symbol": symbol,
                "type": event["type"].casefold(),
                "summary": normalized_summary,
            }
        encoded = json.dumps(
            identity, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _within_dedupe_window(
        self,
        last_seen_at: str,
        now: datetime,
        dedupe_window_seconds: int,
    ) -> bool:
        try:
            last_seen = datetime.fromisoformat(
                last_seen_at.replace("Z", "+00:00")
            )
        except ValueError:
            return False
        return (now - last_seen).total_seconds() <= dedupe_window_seconds

    def _keywords(self, values: list[str]) -> set[str]:
        keywords = set()
        for value in values:
            normalized = str(value).casefold().strip()
            if len(normalized) >= 2:
                keywords.add(normalized)
            keywords.update(
                re.findall(r"[a-z0-9][a-z0-9._-]{1,}|[\u4e00-\u9fff]{2,}", normalized)
            )
        return keywords

    def _json(self, value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class FinanceToolsPlugin:
    def __init__(self) -> None:
        self.finskills_path = Path(
            os.environ.get("FINSKILLS_HOME", "~/finskills")
        ).expanduser()
        self.serenity_skill_path = self._default_serenity_path()
        self.state_db_path = self._default_state_db_path()
        self.state_store: FinanceStateStore | None = None
        self.python_bin = "python3"
        self.timeout_seconds = 45
        self.evaluation_fixture = False
        self.cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self.review_guard: Any = None

    def _default_serenity_path(self) -> Path:
        fastclaw_home = os.environ.get("FASTCLAW_HOME")
        if fastclaw_home:
            return Path(fastclaw_home).expanduser() / "skills" / "serenity-skill"
        return Path(__file__).resolve().parents[2] / "skills" / "serenity-skill"

    def _default_state_db_path(self) -> Path:
        fastclaw_home = Path(
            os.environ.get("FASTCLAW_HOME", "~/.fastclaw")
        ).expanduser()
        return fastclaw_home / "data" / "finance-tools.db"

    def initialize(self, config: dict[str, Any]) -> dict[str, Any]:
        fixture_flag = config.get("evaluationFixture", False)
        if not isinstance(fixture_flag, bool):
            raise ToolInputError("evaluationFixture must be a boolean")
        self.evaluation_fixture = fixture_flag
        finskills_path = str(config.get("finskillsPath") or "").strip()
        serenity_path = str(config.get("serenitySkillPath") or "").strip()
        state_db_path = str(config.get("stateDbPath") or "").strip()
        guard_catalog_path = str(config.get("reviewArithmeticGuardCatalogPath") or "").strip()
        python_bin = str(config.get("pythonBin") or "").strip()
        if finskills_path:
            self.finskills_path = Path(finskills_path).expanduser().resolve()
        if serenity_path:
            self.serenity_skill_path = Path(serenity_path).expanduser().resolve()
        if state_db_path:
            self.state_db_path = Path(state_db_path).expanduser().resolve()
        if python_bin:
            self.python_bin = python_bin
        if guard_catalog_path:
            try:
                self.review_guard = _review_guard.ReviewArithmeticGuard(
                    Path(guard_catalog_path).expanduser().resolve())
            except _review_guard.GuardCatalogError as exc:
                raise ToolInputError(str(exc)) from exc
        timeout = config.get("timeoutSeconds", self.timeout_seconds)
        try:
            self.timeout_seconds = max(1, min(300, int(timeout)))
        except (TypeError, ValueError) as exc:
            raise ToolInputError("timeoutSeconds must be an integer from 1 to 300") from exc
        self.state_store = FinanceStateStore(self.state_db_path, self.review_guard)
        self.state_store.migrate()
        return {
            "status": "ok",
            "schema_version": SCHEMA_VERSION,
            "finskills_path": str(self.finskills_path),
            "serenity_skill_path": str(self.serenity_skill_path),
            "state_db_path": str(self.state_db_path),
            "review_arithmetic_guard_enabled": self.review_guard is not None,
        }

    def execute(
        self,
        name: str,
        args: dict[str, Any],
        call_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "toolkit_status": self.toolkit_status,
            "stock_snapshot": self.stock_snapshot,
            "screen_stocks": self.screen_stocks,
            "market_events": self.market_events,
            "macro_snapshot": self.macro_snapshot,
            "portfolio_risk": self.portfolio_risk,
            "portfolio_policy_bound": self.portfolio_policy_bound,
            "serenity_scorecard": self.serenity_scorecard,
        }
        state_handlers = {
            "thesis_save": self.thesis_save,
            "thesis_get": self.thesis_get,
            "thesis_list": self.thesis_list,
            "thesis_match_event": self.thesis_match_event,
            "thesis_record_review": self.thesis_record_review,
            "watchlist_save": self.watchlist_save,
            "watchlist_list": self.watchlist_list,
            "event_alert_ingest": self.event_alert_ingest,
            "alert_list": self.alert_list,
            "alert_update": self.alert_update,
        }
        try:
            if name in state_handlers:
                tenant = self._tenant(call_context)
                return state_handlers[name](args, tenant)
            handler = handlers.get(name)
            if handler is None:
                raise ToolInputError(f"unknown finance tool: {name}")
            return handler(args)
        except ToolInputError as exc:
            return self._error_envelope("invalid_input", str(exc), False)
        except ToolStateError as exc:
            return self._error_envelope(
                exc.code,
                str(exc),
                exc.retriable,
                exc.details,
            )

    def toolkit_status(self, _: dict[str, Any]) -> dict[str, Any]:
        scripts = {}
        for (market, capability), relative_path in SCRIPT_PATHS.items():
            scripts[f"{market.lower()}_{capability}"] = {
                "available": (self.finskills_path / relative_path).is_file(),
                "artifact": relative_path,
            }
        serenity_script = self.serenity_skill_path / "scripts" / "serenity_scorecard.py"
        dependencies = {
            "yfinance": importlib.util.find_spec("yfinance") is not None,
            "akshare": importlib.util.find_spec("akshare") is not None,
            "numpy": importlib.util.find_spec("numpy") is not None,
            "scipy": importlib.util.find_spec("scipy") is not None,
            "requests": importlib.util.find_spec("requests") is not None,
        }
        data = {
            "scripts": scripts,
            "serenity_scorecard": {
                "available": serenity_script.is_file(),
                "artifact": "scripts/serenity_scorecard.py",
            },
            "dependencies": dependencies,
        }
        flags = [
            f"missing_script:{name}"
            for name, details in scripts.items()
            if not details["available"]
        ]
        if not serenity_script.is_file():
            flags.append("missing_script:serenity_scorecard")
        return self._success_envelope(
            data,
            [{"name": "local_runtime", "kind": "capability_check"}],
            60,
            flags,
        )

    def stock_snapshot(self, args: dict[str, Any]) -> dict[str, Any]:
        market = self._market(args)
        symbols = self._symbols(args.get("symbols"))
        view = str(args.get("view") or "metrics")
        if view not in STOCK_VIEW_FLAGS:
            raise ToolInputError(f"unsupported stock view: {view}")
        if view in {"history", "financials"} and len(symbols) != 1:
            raise ToolInputError(f"{view} requires exactly one symbol")
        period = self._period(args.get("period", "1y"))
        command_args = [*symbols, *STOCK_VIEW_FLAGS[view]]
        if view == "history":
            command_args.extend(["--period", period])
        ttl = 300 if view in {"basic", "history"} else 21600
        return self._run_cached_script(
            "stock_snapshot",
            {"market": market, "symbols": symbols, "view": view, "period": period},
            self._script(market, "stock"),
            command_args,
            ttl,
            self._market_sources(market, "stock_data"),
        )

    def screen_stocks(self, args: dict[str, Any]) -> dict[str, Any]:
        market = self._market(args)
        symbols = self._symbols(args.get("symbols"))
        require_complete = args.get("require_complete", True)
        if not isinstance(require_complete, bool):
            raise ToolInputError("require_complete must be a boolean")
        command_args = [*symbols, "--screen"]
        min_upside = args.get("min_upside", 0.3)
        if market == "US":
            try:
                min_upside = float(min_upside)
            except (TypeError, ValueError) as exc:
                raise ToolInputError("min_upside must be numeric") from exc
            command_args.extend(["--min-upside", str(min_upside)])
        normalized = {
            "market": market,
            "symbols": symbols,
            "min_upside": min_upside,
            "require_complete": require_complete,
        }
        return self._run_cached_script(
            "screen_stocks",
            normalized,
            self._script(market, "stock"),
            command_args,
            21600,
            self._market_sources(market, "deterministic_screen"),
            lambda data: self._enforce_screen_completeness(
                market, data, require_complete
            ),
        )

    def market_events(self, args: dict[str, Any]) -> dict[str, Any]:
        operation = str(args.get("operation") or "")
        flag = EVENT_FLAGS.get(operation)
        if flag is None:
            raise ToolInputError(f"unsupported market event operation: {operation}")
        command_args: list[str] = []
        if operation in {"stock_news", "lifting"}:
            symbol = self._symbol(args.get("symbol"))
            command_args.append(symbol)
        command_args.append(flag)
        date = str(args.get("date") or "").strip()
        if date:
            if not re.fullmatch(r"\d{8}", date):
                raise ToolInputError("date must use YYYYMMDD")
            command_args.extend(["--date", date])
        notice_type = str(args.get("notice_type") or "全部").strip()
        if operation == "announcements" and notice_type:
            command_args.extend(["--type", notice_type])
        limit = args.get("limit")
        if limit is not None:
            try:
                limit = int(limit)
            except (TypeError, ValueError) as exc:
                raise ToolInputError("limit must be an integer") from exc
            if limit < 1 or limit > 200:
                raise ToolInputError("limit must be from 1 to 200")
            command_args.extend(["--limit", str(limit)])
        return self._run_cached_script(
            "market_events",
            {
                "operation": operation,
                "symbol": args.get("symbol"),
                "date": date,
                "notice_type": notice_type,
                "limit": limit,
            },
            self._script("CN", "news"),
            command_args,
            300,
            self._market_sources("CN", operation),
        )

    def macro_snapshot(self, args: dict[str, Any]) -> dict[str, Any]:
        market = self._market(args)
        view = str(args.get("view") or "dashboard")
        allowed = {
            "US": {"dashboard", "rates", "inflation", "gdp", "employment", "cycle"},
            "CN": {"dashboard", "rates", "inflation", "pmi", "social_financing", "cycle"},
        }
        if view not in allowed[market]:
            raise ToolInputError(f"{view} is not available for market {market}")
        return self._run_cached_script(
            "macro_snapshot",
            {"market": market, "view": view},
            self._script(market, "macro"),
            MACRO_VIEW_FLAGS[view],
            86400,
            self._market_sources(market, "macro"),
        )

    def portfolio_risk(self, args: dict[str, Any]) -> dict[str, Any]:
        holdings = args.get("holdings")
        if not isinstance(holdings, dict) or not holdings:
            raise ToolInputError("holdings must be a non-empty ticker-to-weight object")
        complete = args.get("holdings_complete")
        if complete is not None and not isinstance(complete, bool):
            raise ToolInputError("holdings_complete must be a boolean")
        if complete is False:
            raise ToolStateError("portfolio_incomplete", "portfolio holdings are incomplete; risk calculation refused")
        weight_unit = args.get("weight_unit", "auto")
        if weight_unit not in ("auto", "percent", "fraction", "relative"):
            raise ToolInputError("weight_unit must be auto, percent, fraction, or relative")
        normalized_holdings: dict[str, float] = {}
        for raw_symbol, raw_weight in holdings.items():
            symbol = self._symbol(raw_symbol)
            if isinstance(raw_weight, bool):
                raise ToolInputError(f"weight for {symbol} must be numeric, not boolean")
            try:
                weight = float(raw_weight)
            except (TypeError, ValueError) as exc:
                raise ToolInputError(f"weight for {symbol} must be numeric") from exc
            if not math.isfinite(weight) or weight <= 0:
                raise ToolInputError(f"weight for {symbol} must be finite and positive")
            normalized_holdings[symbol] = weight
        total = sum(normalized_holdings.values())
        percent_total = math.isclose(total, 100.0, rel_tol=0, abs_tol=0.01)
        fraction_total = math.isclose(total, 1.0, rel_tol=0, abs_tol=0.0001)
        if weight_unit == "relative":
            if complete is not True:
                raise ToolStateError(
                    "portfolio_incomplete",
                    "relative weights require holdings_complete=true; a partial set cannot be normalized",
                )
        elif not ((weight_unit in ("auto", "percent") and percent_total) or
                  (weight_unit in ("auto", "fraction") and fraction_total)):
            raise ToolStateError(
                "portfolio_incomplete",
                "portfolio weights must cover the whole portfolio before risk calculation",
                details={"weight_unit": weight_unit, "weight_total": total},
            )
        view = str(args.get("view") or "health")
        if view not in PORTFOLIO_FLAGS:
            raise ToolInputError(f"unsupported portfolio view: {view}")
        benchmark = self._symbol(args.get("benchmark") or "SPY")
        holdings_arg = ",".join(
            f"{symbol}:{weight:g}" for symbol, weight in normalized_holdings.items()
        )
        command_args = [
            "--holdings",
            holdings_arg,
            "--benchmark",
            benchmark,
            PORTFOLIO_FLAGS[view],
        ]
        return self._run_cached_script(
            "portfolio_risk",
            {
                "holdings": normalized_holdings,
                "weight_unit": weight_unit,
                "holdings_complete": complete,
                "view": view,
                "benchmark": benchmark,
            },
            self._script("US", "portfolio"),
            command_args,
            3600,
            ([{"name": "local_evaluation_fixture", "kind": "portfolio_analytics"}]
             if self.evaluation_fixture else [
                 {"name": "yfinance", "kind": "market_data"},
                 {"name": "finskills", "kind": "portfolio_analytics"},
             ]),
        )

    def portfolio_policy_bound(self, args: dict[str, Any]) -> dict[str, Any]:
        """Return only conclusions proven by partial, same-denominator long-only weights."""
        holdings = args.get("known_holdings_percent")
        if not isinstance(holdings, dict) or not holdings:
            raise ToolInputError("known_holdings_percent must be a non-empty issuer-to-weight object")
        overlap = args.get("unknown_may_overlap_known")
        if not isinstance(overlap, bool):
            raise ToolInputError("unknown_may_overlap_known must be an explicit boolean")

        def percentage(value: Any, label: str, *, positive: bool = False) -> float:
            if isinstance(value, bool):
                raise ToolInputError(f"{label} must be numeric, not boolean")
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise ToolInputError(f"{label} must be numeric") from exc
            if not math.isfinite(number) or number < 0 or (positive and number <= 0):
                raise ToolInputError(f"{label} must be finite and {'positive' if positive else 'nonnegative'}")
            return number

        known: dict[str, float] = {}
        for raw_symbol, raw_weight in holdings.items():
            symbol = self._symbol(raw_symbol)
            if symbol in known:
                raise ToolInputError(f"duplicate issuer after normalization: {symbol}")
            known[symbol] = percentage(raw_weight, f"weight for {symbol}", positive=True)
        remainder = percentage(args.get("unknown_remainder_percent"),
                               "unknown_remainder_percent")
        limit = percentage(args.get("limit_percent", 50), "limit_percent", positive=True)
        if limit >= 100:
            raise ToolInputError("limit_percent must be below 100")
        if not math.isclose(sum(known.values()) + remainder, 100.0,
                            rel_tol=0, abs_tol=0.000001):
            raise ToolInputError("known weights and unknown remainder must sum to 100 percent")

        bounds = {symbol: {"min_percent": weight,
                           "max_percent": weight + remainder if overlap else weight}
                  for symbol, weight in known.items()}
        breach_proven = any(weight > limit for weight in known.values())
        no_breach_proven = (not breach_proven and remainder <= limit
                            and all(bound["max_percent"] <= limit
                                    for bound in bounds.values()))
        status = ("breach_proven" if breach_proven else
                  "no_breach_proven" if no_breach_proven else "indeterminate")
        data = {
            "calculation": "partial_long_only_single_issuer_bound",
            "known_holdings_percent": known,
            "unknown_remainder_percent": remainder,
            "unknown_may_overlap_known": overlap,
            "known_issuer_bounds_percent": bounds,
            "unidentified_new_issuer_max_percent": remainder,
            "policy_limit_percent": limit,
            "policy_breach_operator": ">",
            "policy_status": status,
            "exact_hhi_available": False,
            "portfolio_risk_calculated": False,
            "assumptions": ["long_only", "common_whole_portfolio_denominator",
                            "input_weights_not_independently_verified"],
        }
        result = self._success_envelope(
            data, [{"name": "supplied_portfolio_weights", "kind": "user_input"}], 0,
            ["partial_holdings", "policy_bound_only"])
        result["quality"]["completeness"] = round(sum(known.values()) / 100.0, 6)
        return result

    def serenity_scorecard(self, args: dict[str, Any]) -> dict[str, Any]:
        scorecard = args.get("scorecard")
        if not isinstance(scorecard, dict):
            raise ToolInputError("scorecard must be an object")
        script = self.serenity_skill_path / "scripts" / "serenity_scorecard.py"
        return self._run_cached_script(
            "serenity_scorecard",
            {"scorecard": scorecard},
            script,
            ["-", "--format", "json"],
            0,
            [
                {
                    "name": "serenity-skill",
                    "kind": "research_methodology",
                    "version": "c2fe93deedfd0d1bd9fe7ef0601ea1b9c20ea24a",
                }
            ],
            stdin_payload=json.dumps(scorecard, ensure_ascii=False),
            extra_flags=["subjective_score_inputs", "not_a_return_forecast"],
        )

    def thesis_save(
        self,
        args: dict[str, Any],
        tenant: dict[str, str],
    ) -> dict[str, Any]:
        thesis_id = str(args.get("thesis_id") or "").strip()
        is_update = bool(thesis_id)
        if is_update:
            self._record_id(thesis_id, "th_")
        payload: dict[str, Any] = {"thesis_id": thesis_id or None}
        if "expected_version" in args:
            payload["expected_version"] = self._bounded_int(
                args["expected_version"], "expected_version", 1, 1_000_000
            )
        if "market" in args or not is_update:
            payload["market"] = self._market(args)
        if "symbol" in args or not is_update:
            payload["symbol"] = self._symbol(args.get("symbol"))
        if "title" in args:
            payload["title"] = self._required_text(args.get("title"), "title", 300)
        elif not is_update:
            payload["title"] = f"{payload['symbol']} research thesis"
        if "thesis" in args or not is_update:
            payload["thesis"] = self._required_text(
                args.get("thesis"), "thesis", 20_000
            )
        if "status" in args:
            payload["status"] = self._choice(
                args.get("status"), "status", THESIS_STATUSES
            )
        elif not is_update:
            payload["status"] = "researching"
        if "conviction" in args:
            payload["conviction"] = self._bounded_int(
                args.get("conviction"), "conviction", 1, 5
            )
        elif not is_update:
            payload["conviction"] = None
        for field in ("assumptions", "catalysts", "invalidations"):
            if field in args:
                payload[field] = self._string_list(args.get(field), field, 100)
            elif not is_update:
                payload[field] = []
        if "required_event_metrics" in args:
            payload["required_event_metrics"] = self._metric_names(
                args.get("required_event_metrics"), "required_event_metrics"
            )
        elif not is_update:
            payload["required_event_metrics"] = []
        if "evidence" in args:
            payload["evidence"] = self._evidence_list(args.get("evidence"))
        elif not is_update:
            payload["evidence"] = []
        if "next_review_at" in args:
            payload["next_review_at"] = self._future_review_at(args.get("next_review_at"))
        elif not is_update:
            payload["next_review_at"] = None
        if is_update and not any(
            key in payload
            for key in (
                "market",
                "symbol",
                "title",
                "thesis",
                "status",
                "conviction",
                "assumptions",
                "catalysts",
                "invalidations",
                "required_event_metrics",
                "evidence",
                "next_review_at",
            )
        ):
            raise ToolInputError("thesis update contains no mutable fields")
        thesis = self._state().save(tenant, payload)
        return self._state_envelope(
            {"thesis": thesis, "operation": "updated" if is_update else "created"}
        )

    def thesis_get(
        self,
        args: dict[str, Any],
        tenant: dict[str, str],
    ) -> dict[str, Any]:
        thesis_id = self._record_id(args.get("thesis_id"), "th_")
        review_limit = self._bounded_int(
            args.get("review_limit", 20), "review_limit", 0, 100
        )
        return self._state_envelope(
            self._state().get(tenant["user_id"], thesis_id, review_limit)
        )

    def thesis_list(
        self,
        args: dict[str, Any],
        tenant: dict[str, str],
    ) -> dict[str, Any]:
        filters: dict[str, Any] = {
            "limit": self._bounded_int(args.get("limit", 50), "limit", 1, 100)
        }
        if args.get("status"):
            filters["status"] = self._choice(
                args.get("status"), "status", THESIS_STATUSES
            )
        if args.get("market"):
            filters["market"] = self._market(args)
        if args.get("symbol"):
            filters["symbol"] = self._symbol(args.get("symbol"))
        theses = self._state().list(tenant["user_id"], filters)
        return self._state_envelope(
            {"theses": theses, "count": len(theses), "filters": filters}
        )

    def thesis_match_event(
        self,
        args: dict[str, Any],
        tenant: dict[str, str],
    ) -> dict[str, Any]:
        market = self._market(args)
        symbol = self._symbol(args.get("symbol"))
        event_summary = self._required_text(
            args.get("event_summary"), "event_summary", 10_000
        )
        limit = self._bounded_int(args.get("limit", 10), "limit", 1, 20)
        matches = self._state().match_event(
            tenant["user_id"], market, symbol, event_summary, limit
        )
        return self._state_envelope(
            {
                "market": market,
                "symbol": symbol,
                "event_summary": event_summary,
                "matches": matches,
                "count": len(matches),
            },
            ["deterministic_event_match", "model_review_required"],
        )

    def thesis_record_review(
        self,
        args: dict[str, Any],
        tenant: dict[str, str],
    ) -> dict[str, Any]:
        thesis_id = self._record_id(args.get("thesis_id"), "th_")
        event = args.get("event")
        if not isinstance(event, dict):
            raise ToolInputError("event must be an object")
        rationale = self._required_text(args.get("rationale"), "rationale", 20_000)
        if re.search(
            r'"\s*,\s*"(?:evidence|matched_terms|causal_claims|next_review_at|new_status|new_conviction)"\s*:',
            rationale,
        ):
            raise ToolStateError(
                "malformed_review_payload",
                "review fields appear serialized inside rationale; keep thesis_id and pass evidence, matched_terms, causal_claims and next_review_at as separate top-level arguments",
                True,
            )
        normalized_event = {
            "type": self._optional_text(event.get("type"), "event.type", 100)
            or "unspecified",
            "summary": self._required_text(
                event.get("summary"), "event.summary", 10_000
            ),
            "as_of": self._optional_text(event.get("as_of"), "event.as_of", 100),
            "sources": self._evidence_list(event.get("sources", [])),
        }
        payload: dict[str, Any] = {
            "thesis_id": thesis_id,
            "event": normalized_event,
            "impact": self._choice(
                args.get("impact"), "impact", REVIEW_IMPACTS
            ),
            "decision": self._choice(
                args.get("decision"), "decision", REVIEW_DECISIONS
            ),
            "rationale": rationale,
            "matched_terms": self._string_list(
                args.get("matched_terms", []), "matched_terms", 100
            ),
            "evidence": self._evidence_list(args.get("evidence", [])),
        }
        if args.get("alert_id"):
            payload["alert_id"] = self._record_id(args.get("alert_id"), "fa_")
        if "expected_version" in args:
            payload["expected_version"] = self._bounded_int(
                args.get("expected_version"), "expected_version", 1, 1_000_000
            )
        if args.get("new_status"):
            payload["new_status"] = self._choice(
                args.get("new_status"), "new_status", THESIS_STATUSES
            )
        if "new_conviction" in args:
            payload["new_conviction"] = self._bounded_int(
                args.get("new_conviction"), "new_conviction", 1, 5
            )
        if "next_review_at" in args:
            payload["next_review_at"] = self._future_review_at(args.get("next_review_at"))
        if "causal_claims" in args:
            raw_claims = args["causal_claims"]
            if not isinstance(raw_claims, list) or len(raw_claims) > 20:
                raise ToolInputError("causal_claims must be an array with at most 20 claims")
            claims = []
            for index, raw in enumerate(raw_claims):
                if not isinstance(raw, dict):
                    raise ToolInputError(f"causal_claims[{index}] must be an object")
                target = self._required_text(
                    raw.get("target_metric"), f"causal_claims[{index}].target_metric", 64
                )
                strength = self._required_text(
                    raw.get("strength"), f"causal_claims[{index}].strength", 64
                )
                drivers = self._string_list(
                    raw.get("driver_fact_ids"), f"causal_claims[{index}].driver_fact_ids", 20
                )
                claim = {"target_metric": target, "strength": strength,
                         "driver_fact_ids": drivers}
                if "attributed_change_percentage_points" in raw:
                    value = raw["attributed_change_percentage_points"]
                    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                        raise ToolInputError(
                            f"causal_claims[{index}].attributed_change_percentage_points must be finite"
                        )
                    claim["attributed_change_percentage_points"] = value
                claims.append(claim)
            payload["causal_claims"] = claims
        result = self._state().record_review(tenant, payload)
        return self._state_envelope(
            result,
            ["research_state_only", "human_trading_decision_required"],
        )

    def watchlist_save(
        self,
        args: dict[str, Any],
        tenant: dict[str, str],
    ) -> dict[str, Any]:
        watchlist_id = str(args.get("watchlist_id") or "").strip()
        is_update = bool(watchlist_id)
        if is_update:
            self._record_id(watchlist_id, "wl_")
        payload: dict[str, Any] = {"watchlist_id": watchlist_id or None}
        if "expected_version" in args:
            payload["expected_version"] = self._bounded_int(
                args.get("expected_version"), "expected_version", 1, 1_000_000
            )
        if "market" in args or not is_update:
            payload["market"] = self._market(args)
        if "symbol" in args or not is_update:
            payload["symbol"] = self._symbol(args.get("symbol"))
        if "thesis_id" in args:
            thesis_id = self._optional_text(
                args.get("thesis_id"), "thesis_id", 64
            )
            if thesis_id:
                self._record_id(thesis_id, "th_")
            payload["thesis_id"] = thesis_id
        elif not is_update:
            payload["thesis_id"] = None
        if "status" in args:
            payload["status"] = self._choice(
                args.get("status"), "status", WATCHLIST_STATUSES
            )
        elif not is_update:
            payload["status"] = "active"
        if "event_types" in args:
            event_types = self._string_list(
                args.get("event_types"), "event_types", 50
            )
            payload["event_types"] = sorted(
                {value.casefold() for value in event_types}
            )
        elif not is_update:
            payload["event_types"] = []
        if "keywords" in args:
            payload["keywords"] = self._string_list(
                args.get("keywords"), "keywords", 100
            )
        elif not is_update:
            payload["keywords"] = []
        if "min_match_score" in args:
            payload["min_match_score"] = self._bounded_int(
                args.get("min_match_score"), "min_match_score", 0, 100
            )
        elif not is_update:
            payload["min_match_score"] = 0
        if "dedupe_window_seconds" in args:
            payload["dedupe_window_seconds"] = self._bounded_int(
                args.get("dedupe_window_seconds"),
                "dedupe_window_seconds",
                60,
                604_800,
            )
        elif not is_update:
            payload["dedupe_window_seconds"] = 86_400
        if is_update and not any(
            key in payload
            for key in (
                "market",
                "symbol",
                "thesis_id",
                "status",
                "event_types",
                "keywords",
                "min_match_score",
                "dedupe_window_seconds",
            )
        ):
            raise ToolInputError("watchlist update contains no mutable fields")
        watchlist = self._state().save_watchlist(tenant, payload)
        return self._state_envelope(
            {
                "watchlist": watchlist,
                "operation": "updated" if is_update else "created",
            },
            ["deterministic_alert_policy"],
        )

    def watchlist_list(
        self,
        args: dict[str, Any],
        tenant: dict[str, str],
    ) -> dict[str, Any]:
        filters: dict[str, Any] = {
            "limit": self._bounded_int(args.get("limit", 50), "limit", 1, 100)
        }
        if args.get("status"):
            filters["status"] = self._choice(
                args.get("status"), "status", WATCHLIST_STATUSES
            )
        if args.get("market"):
            filters["market"] = self._market(args)
        if args.get("symbol"):
            filters["symbol"] = self._symbol(args.get("symbol"))
        watchlist = self._state().list_watchlist(tenant["user_id"], filters)
        return self._state_envelope(
            {
                "watchlist": watchlist,
                "count": len(watchlist),
                "filters": filters,
            }
        )

    def event_alert_ingest(
        self,
        args: dict[str, Any],
        tenant: dict[str, str],
    ) -> dict[str, Any]:
        event = args.get("event")
        if not isinstance(event, dict):
            raise ToolInputError("event must be an object")
        normalized_event = {
            "external_id": self._optional_text(
                event.get("external_id"), "event.external_id", 300
            ),
            "type": (
                self._optional_text(event.get("type"), "event.type", 100)
                or "unspecified"
            ).casefold(),
            "summary": self._required_text(
                event.get("summary"), "event.summary", 10_000
            ),
            "as_of": self._optional_text(event.get("as_of"), "event.as_of", 100),
            "sources": self._evidence_list(event.get("sources", [])),
            "observed_metrics": self._observed_metrics(event.get("observed_metrics", {})),
        }
        normalized_event["source_claims"] = self._source_claims(
            event.get("source_claims", []), normalized_event["sources"]
        )
        normalized_event["unresolved_conflicts"] = self._conflicting_claims(
            normalized_event["source_claims"]
        )
        if normalized_event["observed_metrics"] and not any(
            re.fullmatch(r"[0-9a-fA-F]{64}", str(source.get("sha256", "")))
            for source in normalized_event["sources"]
        ):
            raise ToolInputError("observed_metrics require a SHA-256 source reference")
        result = self._state().ingest_event(
            tenant,
            {
                "market": self._market(args),
                "symbol": self._symbol(args.get("symbol")),
                "event": normalized_event,
            },
        )
        return self._state_envelope(
            result,
            [
                "deterministic_alert_match",
                "duplicate_alerts_suppressed",
                "model_review_required",
            ],
        )

    def alert_list(
        self,
        args: dict[str, Any],
        tenant: dict[str, str],
    ) -> dict[str, Any]:
        filters: dict[str, Any] = {
            "limit": self._bounded_int(args.get("limit", 50), "limit", 1, 100)
        }
        if args.get("status"):
            filters["status"] = self._choice(
                args.get("status"), "status", ALERT_STATUSES
            )
        if args.get("market"):
            filters["market"] = self._market(args)
        if args.get("symbol"):
            filters["symbol"] = self._symbol(args.get("symbol"))
        if args.get("watchlist_id"):
            filters["watchlist_id"] = self._record_id(
                args.get("watchlist_id"), "wl_"
            )
        alerts = self._state().list_alerts(tenant["user_id"], filters)
        return self._state_envelope(
            {"alerts": alerts, "count": len(alerts), "filters": filters}
        )

    def alert_update(
        self,
        args: dict[str, Any],
        tenant: dict[str, str],
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "alert_id": self._record_id(args.get("alert_id"), "fa_"),
            "status": self._choice(
                args.get("status"), "status", ALERT_STATUSES
            ),
        }
        if "expected_version" in args:
            payload["expected_version"] = self._bounded_int(
                args.get("expected_version"), "expected_version", 1, 1_000_000
            )
        alert = self._state().update_alert(tenant, payload)
        return self._state_envelope(
            {"alert": alert, "operation": "updated"},
            ["research_state_only"],
        )

    def _run_cached_script(
        self,
        tool_name: str,
        normalized_args: dict[str, Any],
        script: Path,
        command_args: list[str],
        ttl_seconds: int,
        sources: list[dict[str, Any]],
        transform: Callable[[Any], tuple[Any, list[str]]] | None = None,
        stdin_payload: str | None = None,
        extra_flags: list[str] | None = None,
    ) -> dict[str, Any]:
        cache_key = json.dumps(
            [tool_name, normalized_args],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        cached = self.cache.get(cache_key)
        now_epoch = time.time()
        if cached is not None and cached[0] > now_epoch:
            result = copy.deepcopy(cached[1])
            result["request_id"] = str(uuid.uuid4())
            result["cache"]["hit"] = True
            return result
        if not script.is_file():
            return self._error_envelope(
                "script_unavailable",
                f"required script not found: {script}",
                False,
            )
        command = [self.python_bin, str(script), *command_args]
        try:
            completed = subprocess.run(
                command,
                input=stdin_payload,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                cwd=str(script.parent),
                check=False,
            )
        except subprocess.TimeoutExpired:
            return self._error_envelope(
                "upstream_timeout",
                f"financial script exceeded {self.timeout_seconds}s timeout",
                True,
            )
        except OSError as exc:
            return self._error_envelope("execution_failed", str(exc), False)
        if completed.returncode != 0:
            message = completed.stderr.strip() or completed.stdout.strip()
            return self._error_envelope(
                "upstream_error",
                message or f"financial script exited with {completed.returncode}",
                True,
                {"exit_code": completed.returncode},
            )
        try:
            data = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            return self._error_envelope(
                "invalid_upstream_response",
                f"financial script returned invalid JSON: {exc}",
                False,
            )
        flags = list(extra_flags or [])
        if transform is not None:
            data, transform_flags = transform(data)
            flags.extend(transform_flags)
        result = self._success_envelope(data, sources, ttl_seconds, flags)
        if ttl_seconds > 0:
            self.cache[cache_key] = (now_epoch + ttl_seconds, copy.deepcopy(result))
        return result

    def _success_envelope(
        self,
        data: Any,
        sources: list[dict[str, Any]],
        ttl_seconds: int,
        flags: list[str] | None = None,
    ) -> dict[str, Any]:
        now = utc_now()
        quality_flags = list(dict.fromkeys([*(flags or []), *self._data_flags(data)]))
        return {
            "schema_version": SCHEMA_VERSION,
            "ok": True,
            "request_id": str(uuid.uuid4()),
            "as_of": isoformat(now),
            "stale_after": isoformat(now + timedelta(seconds=ttl_seconds))
            if ttl_seconds > 0
            else None,
            "data": data,
            "sources": sources,
            "quality": {
                "completeness": self._completeness(data),
                "flags": quality_flags,
            },
            "errors": [],
            "cache": {"hit": False, "ttl_seconds": ttl_seconds},
        }

    def _error_envelope(
        self,
        code: str,
        message: str,
        retriable: bool,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = utc_now()
        error = {
            "code": code,
            "message": message,
            "retriable": retriable,
        }
        if details:
            error["details"] = details
        return {
            "schema_version": SCHEMA_VERSION,
            "ok": False,
            "request_id": str(uuid.uuid4()),
            "as_of": isoformat(now),
            "stale_after": None,
            "data": None,
            "sources": [],
            "quality": {"completeness": 0.0, "flags": [code]},
            "errors": [error],
            "cache": {"hit": False, "ttl_seconds": 0},
        }

    def _state_envelope(
        self,
        data: Any,
        flags: list[str] | None = None,
    ) -> dict[str, Any]:
        return self._success_envelope(
            data,
            [{"name": "finance-tools-ledger", "kind": "user_research_state"}],
            0,
            ["tenant_isolated", *(flags or [])],
        )

    def _state(self) -> FinanceStateStore:
        if self.state_store is None:
            raise ToolStateError(
                "state_unavailable",
                "finance state store is not initialized",
                True,
            )
        return self.state_store

    def _tenant(self, call_context: dict[str, Any] | None) -> dict[str, str]:
        if not isinstance(call_context, dict):
            raise ToolStateError(
                "missing_tenant_context",
                "stateful finance tools require runtime tenant context",
            )
        user_id = str(call_context.get("userId") or "").strip()
        agent_id = str(call_context.get("agentId") or "").strip()
        session_id = str(call_context.get("sessionId") or "").strip()
        if not user_id or not agent_id:
            raise ToolStateError(
                "missing_tenant_context",
                "stateful finance tools require trusted userId and agentId",
            )
        return {
            "user_id": user_id,
            "agent_id": agent_id,
            "session_id": session_id,
        }

    def _choice(self, value: Any, label: str, choices: set[str]) -> str:
        normalized = str(value or "").strip().lower()
        if normalized not in choices:
            raise ToolInputError(
                f"{label} must be one of: {', '.join(sorted(choices))}"
            )
        return normalized

    def _bounded_int(
        self,
        value: Any,
        label: str,
        minimum: int,
        maximum: int,
    ) -> int:
        if isinstance(value, bool):
            raise ToolInputError(f"{label} must be an integer")
        try:
            number = int(value)
        except (TypeError, ValueError) as exc:
            raise ToolInputError(f"{label} must be an integer") from exc
        if number < minimum or number > maximum:
            raise ToolInputError(f"{label} must be from {minimum} to {maximum}")
        return number

    def _required_text(self, value: Any, label: str, max_length: int) -> str:
        text = str(value or "").strip()
        if not text:
            raise ToolInputError(f"{label} is required")
        if len(text) > max_length:
            raise ToolInputError(f"{label} exceeds {max_length} characters")
        return text

    def _optional_text(self, value: Any, label: str, max_length: int) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        if len(text) > max_length:
            raise ToolInputError(f"{label} exceeds {max_length} characters")
        return text

    def _future_review_at(self, value: Any) -> str | None:
        text = self._optional_text(value, "next_review_at", 100)
        if text is None:
            return None
        try:
            when = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ToolInputError("next_review_at must be an ISO date or timestamp") from exc
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        if when.astimezone(timezone.utc) <= datetime.now(timezone.utc):
            raise ToolInputError(
                "next_review_at must be in the future; historical source dates belong in evidence"
            )
        return text

    def _string_list(self, value: Any, label: str, max_items: int) -> list[str]:
        if not isinstance(value, list):
            raise ToolInputError(f"{label} must be an array")
        if len(value) > max_items:
            raise ToolInputError(f"{label} exceeds {max_items} items")
        return [
            self._required_text(item, f"{label}[{index}]", 2_000)
            for index, item in enumerate(value)
        ]

    def _metric_names(self, value: Any, label: str) -> list[str]:
        names = self._string_list(value, label, 50)
        for name in names:
            if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", name):
                raise ToolInputError(f"{label} must use canonical snake_case metric names")
        if len(set(names)) != len(names):
            raise ToolInputError(f"{label} contains duplicate metric names")
        return names

    def _observed_metrics(self, value: Any) -> dict[str, dict[str, Any]]:
        if not isinstance(value, dict) or len(value) > 50:
            raise ToolInputError("observed_metrics must be an object with at most 50 metrics")
        self._metric_names(list(value), "observed_metrics")
        result = {}
        for name, item in value.items():
            if not isinstance(item, dict):
                raise ToolInputError(f"observed_metrics.{name} must be an object")
            if isinstance(item.get("value"), bool) or item.get("value") is None:
                raise ToolInputError(f"observed_metrics.{name}.value is required")
            result[name] = {
                "value": self._required_text(str(item["value"]), f"observed_metrics.{name}.value", 100),
                "unit": self._required_text(item.get("unit"), f"observed_metrics.{name}.unit", 64),
                "fact_id": self._required_text(item.get("fact_id"), f"observed_metrics.{name}.fact_id", 100),
            }
            if "statement_line" in item:
                allowed_lines = set().union(*_lineage.ALLOWED_DRIVER_LINES.values()) | {
                    "balance_sheet", "unknown"
                }
                result[name]["statement_line"] = self._choice(
                    item["statement_line"], f"observed_metrics.{name}.statement_line",
                    allowed_lines,
                )
                for field in ("source_explicit_targets", "reconciled_targets"):
                    if field in item:
                        targets = self._string_list(
                            item[field], f"observed_metrics.{name}.{field}", 8
                        )
                        if any(target not in _lineage.ALLOWED_DRIVER_LINES for target in targets):
                            raise ToolInputError(
                                f"observed_metrics.{name}.{field} has unsupported target"
                            )
                        result[name][field] = targets
        return result

    def _source_claims(self, value: Any, sources: list[dict[str, Any]]) -> list[dict[str, str]]:
        if not isinstance(value, list) or len(value) > 100:
            raise ToolInputError("source_claims must be an array with at most 100 claims")
        known_hashes = {
            str(source.get("sha256", "")).lower()
            for source in sources
            if re.fullmatch(r"[0-9a-fA-F]{64}", str(source.get("sha256", "")))
        }
        claims = []
        for index, item in enumerate(value):
            if not isinstance(item, dict):
                raise ToolInputError(f"source_claims[{index}] must be an object")
            metric = self._required_text(item.get("metric"), f"source_claims[{index}].metric", 64)
            if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", metric):
                raise ToolInputError("source_claims metric must use canonical snake_case")
            source_hash = self._required_text(
                item.get("source_sha256"), f"source_claims[{index}].source_sha256", 64
            ).lower()
            if source_hash not in known_hashes:
                raise ToolInputError("source_claims source_sha256 must match an event source")
            raw_value = item.get("value")
            if raw_value is None or isinstance(raw_value, bool):
                raise ToolInputError("source_claims value must be numeric")
            try:
                numeric_value = Decimal(str(raw_value))
            except InvalidOperation as exc:
                raise ToolInputError("source_claims value must be numeric") from exc
            if not numeric_value.is_finite():
                raise ToolInputError("source_claims value must be finite")
            claims.append({
                "metric": metric,
                "period": self._required_text(item.get("period"), f"source_claims[{index}].period", 100),
                "value": str(numeric_value),
                "unit": self._required_text(item.get("unit"), f"source_claims[{index}].unit", 64),
                "fact_id": self._required_text(item.get("fact_id"), f"source_claims[{index}].fact_id", 100),
                "source_sha256": source_hash,
            })
        return claims

    @staticmethod
    def _conflicting_claims(claims: list[dict[str, str]]) -> list[dict[str, Any]]:
        grouped: dict[tuple[str, str, str], list[dict[str, str]]] = {}
        for claim in claims:
            grouped.setdefault((claim["metric"], claim["period"], claim["unit"]), []).append(claim)
        conflicts = []
        for (metric, period, unit), group in sorted(grouped.items()):
            if any(
                Decimal(left["value"]) != Decimal(right["value"])
                for index, left in enumerate(group)
                for right in group[index + 1:]
            ):
                conflicts.append({"metric": metric, "period": period, "unit": unit, "claims": group})
        return conflicts

    def _evidence_list(self, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            raise ToolInputError("evidence and sources must be arrays")
        if len(value) > 200:
            raise ToolInputError("evidence exceeds 200 items")
        normalized = []
        for index, item in enumerate(value):
            if not isinstance(item, dict):
                raise ToolInputError(f"evidence[{index}] must be an object")
            normalized.append(item)
        serialized = json.dumps(normalized, ensure_ascii=False)
        if len(serialized) > 1_000_000:
            raise ToolInputError("evidence exceeds 1 MB")
        return normalized

    def _record_id(self, value: Any, prefix: str) -> str:
        record_id = str(value or "").strip()
        if not re.fullmatch(re.escape(prefix) + r"[a-f0-9]{20}", record_id):
            raise ToolInputError(f"invalid record id: {record_id!r}")
        return record_id

    def _script(self, market: str, capability: str) -> Path:
        relative = SCRIPT_PATHS.get((market, capability))
        if relative is None:
            raise ToolInputError(f"{capability} is not supported for market {market}")
        return self.finskills_path / relative

    def _market(self, args: dict[str, Any]) -> str:
        market = str(args.get("market") or "").upper()
        if market not in MARKET_PROVIDERS:
            raise ToolInputError("market must be US or CN")
        return market

    def _symbols(self, value: Any) -> list[str]:
        if isinstance(value, str):
            raw_symbols = [item.strip() for item in value.split(",") if item.strip()]
        elif isinstance(value, list):
            raw_symbols = value
        else:
            raise ToolInputError("symbols must be a non-empty array")
        if not raw_symbols or len(raw_symbols) > 50:
            raise ToolInputError("symbols must contain from 1 to 50 items")
        return [self._symbol(item) for item in raw_symbols]

    def _symbol(self, value: Any) -> str:
        symbol = str(value or "").strip().upper()
        if not SYMBOL_PATTERN.fullmatch(symbol):
            raise ToolInputError(f"invalid security symbol: {symbol!r}")
        return symbol

    def _period(self, value: Any) -> str:
        period = str(value or "1y").strip().lower()
        if not re.fullmatch(r"(1d|5d|1m|1mo|3m|3mo|6m|6mo|1y|2y|5y|10y|ytd|max)", period):
            raise ToolInputError(f"unsupported history period: {period}")
        return period

    def _market_sources(self, market: str, kind: str) -> list[dict[str, Any]]:
        if self.evaluation_fixture:
            return [{"name": "local_evaluation_fixture", "kind": kind}]
        provider = "FRED" if market == "US" and kind == "macro" else MARKET_PROVIDERS[market]
        return [
            {"name": provider, "kind": "market_data"},
            {"name": "finskills", "kind": kind},
        ]

    def _enforce_screen_completeness(
        self, market: str, data: Any, require_complete: bool
    ) -> tuple[Any, list[str]]:
        if not require_complete or not isinstance(data, dict):
            return data, []
        required_paths = {
            "CN": {
                "pe_ttm": ("valuation", "pe_ttm"),
                "pb": ("valuation", "pb"),
                "roe": ("profitability", "roe"),
                "debt_to_asset_ratio": ("leverage", "debt_to_asset_ratio"),
            },
            "US": {
                "pe_trailing": ("valuation", "pe_trailing"),
                "revenue_growth_yoy": ("growth", "revenue_growth_yoy"),
                "earnings_growth_yoy": ("growth", "earnings_growth_yoy"),
                "debt_to_equity": ("leverage", "debt_to_equity"),
                "free_cash_flow": ("cash_flow", "free_cash_flow"),
                "roic": ("profitability", "roic"),
                "analyst_upside_pct": ("analyst_consensus", "upside_pct"),
            },
        }[market]
        passing = data.get("results")
        if not isinstance(passing, list):
            return data, []
        retained = []
        rejected = list(data.get("rejected") or [])
        moved = 0
        for candidate in passing:
            missing = [
                label
                for label, path in required_paths.items()
                if self._nested_value(candidate, path) is None
            ]
            if missing:
                moved += 1
                rejected.append(
                    {
                        "symbol": candidate.get("symbol", "")
                        if isinstance(candidate, dict)
                        else "",
                        "reason": "insufficient_data",
                        "missing_metrics": missing,
                    }
                )
            else:
                retained.append(candidate)
        data["results"] = retained
        data["rejected"] = rejected
        data["passed"] = len(retained)
        data["failed"] = len(rejected)
        data["runtime_quality_policy"] = {
            "require_complete": True,
            "required_metrics": list(required_paths),
            "moved_to_rejected": moved,
        }
        flags = ["incomplete_screen_candidates_rejected"] if moved else []
        return data, flags

    def _nested_value(self, data: Any, path: tuple[str, ...]) -> Any:
        current = data
        for key in path:
            if not isinstance(current, dict):
                return None
            current = current.get(key)
        return current

    def _completeness(self, data: Any) -> float:
        present = 0
        total = 0
        stack = [data]
        while stack and total < 5000:
            value = stack.pop()
            if isinstance(value, dict):
                stack.extend(value.values())
            elif isinstance(value, list):
                if value:
                    stack.extend(value)
                else:
                    total += 1
            else:
                total += 1
                if value is not None and value != "":
                    present += 1
        if total == 0:
            return 1.0
        return round(present / total, 4)

    def _data_flags(self, data: Any) -> list[str]:
        flags = []
        if isinstance(data, dict):
            if data.get("error"):
                flags.append("upstream_partial_error")
            quality = data.get("data_quality")
            if isinstance(quality, dict) and quality.get("issues"):
                flags.append("upstream_data_quality_issues")
        return flags


def send(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def rpc_response(plugin: FinanceToolsPlugin, request: dict[str, Any]) -> dict[str, Any]:
    method = request.get("method", "")
    request_id = request.get("id")
    params = request.get("params") or {}
    try:
        if method == "initialize":
            result = plugin.initialize(params.get("config") or {})
        elif method == "tool.list":
            result = {"tools": tool_definitions()}
        elif method == "tool.execute":
            tool_name = str(params.get("name") or "")
            tool_args = params.get("args") or {}
            if not isinstance(tool_args, dict):
                raise ToolInputError("tool args must be an object")
            call_context = params.get("context") or {}
            result = {
                "result": json.dumps(
                    plugin.execute(tool_name, tool_args, call_context),
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            }
        elif method == "shutdown":
            result = {"status": "ok"}
        else:
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": f"unknown method: {method}"},
                "id": request_id,
            }
        return {"jsonrpc": "2.0", "result": result, "id": request_id}
    except ToolInputError as exc:
        return {
            "jsonrpc": "2.0",
            "error": {"code": -32602, "message": str(exc)},
            "id": request_id,
        }
    except Exception as exc:
        return {
            "jsonrpc": "2.0",
            "error": {"code": -32603, "message": str(exc)},
            "id": request_id,
        }


def main() -> None:
    plugin = FinanceToolsPlugin()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            send(
                {
                    "jsonrpc": "2.0",
                    "error": {"code": -32700, "message": "parse error"},
                    "id": None,
                }
            )
            continue
        response = rpc_response(plugin, request)
        send(response)
        if request.get("method") == "shutdown":
            return


if __name__ == "__main__":
    main()
