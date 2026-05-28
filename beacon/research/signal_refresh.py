"""Refresh evidence for already-promoted companies.

Once a company moves from `discovery_candidates` to `companies`, its
`ai_signals` / `leadership_signals` / `tools_adopted` rows are frozen. Over
calendar time the recency sub-score (`compute_recency_score`) decays even
when nothing else changes, silently re-ordering rankings.

`refresh_signals` re-asks the registered source adapters for current evidence
on a slice of known companies, deduping on the natural key
``(company_id, signal_type, source_name, source_url)`` so repeat asks don't
balloon the tables.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from beacon.sources import SourceError, get_adapter, list_sources
from beacon.sources.base import SourceAdapter

logger = logging.getLogger("beacon.research.signal_refresh")


_AI_SIGNAL_TYPES = {
    "leadership_statement",
    "engineering_blog",
    "job_posting_language",
    "conference_talk",
    "employee_report",
    "press_coverage",
    "github_activity",
    "company_policy",
    "product_integration",
    "tool_mandate",
}


@dataclass
class RefreshResult:
    """Per-company refresh outcome."""

    company_id: int
    name: str
    tier: int | None
    newest_signal_before: str | None
    newest_signal_after: str | None
    sources_queried: list[str] = field(default_factory=list)
    signals_added: dict[str, int] = field(default_factory=lambda: {
        "ai_signals": 0,
        "leadership_signals": 0,
        "tools_adopted": 0,
    })
    duplicates_skipped: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class RefreshSummary:
    """Aggregate refresh outcome for one CLI invocation."""

    since_days: int
    filters: dict[str, Any]
    started_at: str
    completed_at: str
    duration_seconds: float
    companies_considered: int
    companies_refreshed: int
    companies_skipped: list[dict[str, Any]] = field(default_factory=list)
    results: list[RefreshResult] = field(default_factory=list)
    totals: dict[str, int] = field(default_factory=lambda: {
        "ai_signals_added": 0,
        "leadership_signals_added": 0,
        "tools_adopted_added": 0,
        "duplicates_skipped": 0,
        "sources_failed": 0,
    })

    def to_dict(self) -> dict[str, Any]:
        return {
            **{k: v for k, v in asdict(self).items() if k != "results"},
            "results": [asdict(r) for r in self.results],
        }


def _newest_signal_date(conn: sqlite3.Connection, company_id: int) -> str | None:
    """Return the most recent date_observed across signal tables, or None."""
    row = conn.execute(
        """
        SELECT MAX(date_observed) AS d FROM (
            SELECT date_observed FROM ai_signals
                WHERE company_id = ? AND date_observed IS NOT NULL
            UNION ALL
            SELECT date_observed FROM leadership_signals
                WHERE company_id = ? AND date_observed IS NOT NULL
            UNION ALL
            SELECT date_observed FROM tools_adopted
                WHERE company_id = ? AND date_observed IS NOT NULL
        )
        """,
        (company_id, company_id, company_id),
    ).fetchone()
    return row["d"] if row and row["d"] else None


def _select_candidates(
    conn: sqlite3.Connection,
    *,
    since_days: int,
    company: str | None,
    tier: int | None,
    limit: int,
) -> list[sqlite3.Row]:
    """Pick companies to refresh, stalest-first.

    Companies with no dated signals at all are always considered.
    """
    if company:
        rows = conn.execute(
            "SELECT * FROM companies WHERE LOWER(name) = LOWER(?)",
            (company,),
        ).fetchall()
        return list(rows)

    query = [
        "SELECT c.*, (",
        "    SELECT MAX(date_observed) FROM (",
        "        SELECT date_observed FROM ai_signals WHERE company_id = c.id",
        "        UNION ALL",
        "        SELECT date_observed FROM leadership_signals WHERE company_id = c.id",
        "        UNION ALL",
        "        SELECT date_observed FROM tools_adopted WHERE company_id = c.id",
        "    )",
        ") AS newest_signal_date",
        "FROM companies c",
        "WHERE 1=1",
    ]
    params: list[Any] = []
    if tier is not None:
        query.append("  AND c.tier = ?")
        params.append(tier)

    query.append(
        "  AND (newest_signal_date IS NULL "
        "    OR newest_signal_date < date('now', ?))"
    )
    params.append(f"-{since_days} days")

    query.append("ORDER BY (newest_signal_date IS NULL) DESC, newest_signal_date ASC")
    query.append("LIMIT ?")
    params.append(limit)

    return list(conn.execute("\n".join(query), params).fetchall())


def _build_adapters(source: str | None) -> list[SourceAdapter]:
    names = [source] if source else list_sources()
    adapters: list[SourceAdapter] = []
    for name in names:
        try:
            adapters.append(get_adapter(name))
        except Exception as exc:  # pragma: no cover - registry misuse
            logger.warning("Could not init adapter %s: %s", name, exc)
    return adapters


def _ai_signal_exists(
    conn: sqlite3.Connection,
    company_id: int,
    signal_type: str,
    source_name: str | None,
    source_url: str | None,
    title: str,
) -> bool:
    row = conn.execute(
        """
        SELECT 1 FROM ai_signals
        WHERE company_id = ?
          AND signal_type = ?
          AND COALESCE(source_name, '') = COALESCE(?, '')
          AND COALESCE(source_url, '') = COALESCE(?, '')
          AND title = ?
        LIMIT 1
        """,
        (company_id, signal_type, source_name, source_url, title),
    ).fetchone()
    return row is not None


def _leadership_signal_exists(
    conn: sqlite3.Connection,
    company_id: int,
    leader_name: str,
    content: str,
) -> bool:
    row = conn.execute(
        """
        SELECT 1 FROM leadership_signals
        WHERE company_id = ? AND leader_name = ? AND content = ?
        LIMIT 1
        """,
        (company_id, leader_name, content),
    ).fetchone()
    return row is not None


def _tool_exists(conn: sqlite3.Connection, company_id: int, tool_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM tools_adopted WHERE company_id = ? AND tool_name = ? LIMIT 1",
        (company_id, tool_name),
    ).fetchone()
    return row is not None


def _insert_signal(
    conn: sqlite3.Connection,
    company_id: int,
    source_name: str,
    signal: dict[str, Any],
    result: RefreshResult,
) -> None:
    """Route a signal dict to the right table; bump counters in `result`."""
    # tools_adopted
    if signal.get("tool_name"):
        tool_name = signal["tool_name"]
        if _tool_exists(conn, company_id, tool_name):
            result.duplicates_skipped += 1
            return
        conn.execute(
            """
            INSERT INTO tools_adopted
                (company_id, tool_name, adoption_level, evidence_url,
                 evidence_excerpt, date_observed)
            VALUES (?, ?, ?, ?, ?, date('now'))
            """,
            (
                company_id,
                tool_name,
                signal.get("adoption_level") or "exploring",
                signal.get("source_url") or signal.get("evidence_url"),
                signal.get("excerpt") or signal.get("evidence_excerpt"),
            ),
        )
        result.signals_added["tools_adopted"] += 1
        return

    # leadership_signals
    if signal.get("leader_name"):
        leader_name = signal["leader_name"]
        content = signal.get("content") or signal.get("title") or ""
        if not content:
            return
        if _leadership_signal_exists(conn, company_id, leader_name, content):
            result.duplicates_skipped += 1
            return
        conn.execute(
            """
            INSERT INTO leadership_signals
                (company_id, leader_name, leader_title, signal_type, content,
                 source_url, date_observed, impact_level)
            VALUES (?, ?, ?, ?, ?, ?, date('now'), ?)
            """,
            (
                company_id,
                leader_name,
                signal.get("leader_title"),
                signal.get("signal_type") if signal.get("signal_type") in
                {"quote", "policy", "memo", "talk", "tweet", "interview"} else "quote",
                content,
                signal.get("source_url"),
                signal.get("impact_level") or "engineering",
            ),
        )
        result.signals_added["leadership_signals"] += 1
        return

    # ai_signals (default)
    title = signal.get("title")
    if not title:
        return
    stype = signal.get("signal_type")
    if stype not in _AI_SIGNAL_TYPES:
        stype = "press_coverage"
    sig_source = signal.get("source_name") or source_name
    sig_url = signal.get("source_url")
    if _ai_signal_exists(conn, company_id, stype, sig_source, sig_url, title):
        result.duplicates_skipped += 1
        return
    conn.execute(
        """
        INSERT INTO ai_signals
            (company_id, signal_type, title, source_url, source_name,
             excerpt, signal_strength, date_observed)
        VALUES (?, ?, ?, ?, ?, ?, ?, date('now'))
        """,
        (
            company_id,
            stype,
            title,
            sig_url,
            sig_source,
            signal.get("excerpt"),
            signal.get("signal_strength") or signal.get("strength"),
        ),
    )
    result.signals_added["ai_signals"] += 1


def refresh_signals_for_company(
    conn: sqlite3.Connection,
    company: sqlite3.Row | dict,
    adapters: Iterable[SourceAdapter],
    *,
    dry_run: bool = False,
) -> RefreshResult:
    """Re-fetch evidence for one company across the given adapters."""
    comp = dict(company)
    company_id = comp["id"]
    result = RefreshResult(
        company_id=company_id,
        name=comp["name"],
        tier=comp.get("tier"),
        newest_signal_before=_newest_signal_date(conn, company_id),
        newest_signal_after=None,
    )

    for adapter in adapters:
        result.sources_queried.append(adapter.name)
        try:
            candidate = adapter.fetch_for(comp)
        except SourceError as exc:
            result.errors.append(f"{adapter.name}: {exc}")
            continue
        except Exception as exc:  # noqa: BLE001 — surface, don't crash the run
            result.errors.append(f"{adapter.name}: {exc}")
            logger.exception("fetch_for crashed for %s/%s", adapter.name, comp["name"])
            continue
        if candidate is None:
            continue
        for signal in candidate.signals or []:
            if dry_run:
                # Pretend-write: still classify so counters reflect intent,
                # but skip the actual INSERT.
                if signal.get("tool_name"):
                    result.signals_added["tools_adopted"] += 1
                elif signal.get("leader_name"):
                    result.signals_added["leadership_signals"] += 1
                elif signal.get("title"):
                    result.signals_added["ai_signals"] += 1
                continue
            _insert_signal(conn, company_id, adapter.name, signal, result)

    if not dry_run:
        conn.execute(
            "UPDATE companies SET last_researched_at = datetime('now') WHERE id = ?",
            (company_id,),
        )
        conn.execute(
            "INSERT INTO signal_refresh_log (company_id, signals_added) VALUES (?, ?)",
            (company_id, sum(result.signals_added.values())),
        )
        conn.commit()

    result.newest_signal_after = _newest_signal_date(conn, company_id)
    return result


def refresh_signals(
    conn: sqlite3.Connection,
    *,
    since_days: int = 90,
    company: str | None = None,
    tier: int | None = None,
    source: str | None = None,
    limit: int = 50,
    dry_run: bool = False,
    adapters: Iterable[SourceAdapter] | None = None,
) -> RefreshSummary:
    """Refresh evidence across a slice of companies, stalest-first."""
    started = time.time()
    started_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if company and tier is not None:
        raise ValueError("--company and --tier are mutually exclusive")

    selected = _select_candidates(
        conn,
        since_days=since_days,
        company=company,
        tier=tier,
        limit=limit,
    )

    adapters_list: list[SourceAdapter] = (
        list(adapters) if adapters is not None else _build_adapters(source)
    )

    summary = RefreshSummary(
        since_days=since_days,
        filters={
            "company": company,
            "tier": tier,
            "source": source,
            "limit": limit,
            "dry_run": dry_run,
        },
        started_at=started_iso,
        completed_at=started_iso,
        duration_seconds=0.0,
        companies_considered=len(selected),
        companies_refreshed=0,
    )

    for row in selected:
        if not adapters_list:
            summary.companies_skipped.append({
                "id": row["id"],
                "name": row["name"],
                "reason": "no source adapter matched",
            })
            continue
        result = refresh_signals_for_company(conn, row, adapters_list, dry_run=dry_run)
        summary.results.append(result)
        summary.companies_refreshed += 1
        summary.totals["ai_signals_added"] += result.signals_added["ai_signals"]
        summary.totals["leadership_signals_added"] += result.signals_added["leadership_signals"]
        summary.totals["tools_adopted_added"] += result.signals_added["tools_adopted"]
        summary.totals["duplicates_skipped"] += result.duplicates_skipped
        if result.errors:
            summary.totals["sources_failed"] += len(result.errors)

    summary.completed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    summary.duration_seconds = round(time.time() - started, 2)
    return summary
