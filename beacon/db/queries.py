"""SQL-backed query helpers that return shaped dataclasses.

Keeps DB shape out of the CLI module — `beacon companies diff` calls
``companies_diff`` and renders the result.
"""

from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass, field


@dataclass
class NewCompany:
    id: int
    name: str
    domain: str | None
    tier: int
    ai_first_score: float
    created_at: str
    active_jobs_at_creation: int
    active_jobs_now: int
    first_signal: str | None


@dataclass
class ChangedCompany:
    id: int
    name: str
    tier: int
    jobs_opened: int
    jobs_closed: int
    net_delta: int
    opened_titles: list[str] = field(default_factory=list)
    closed_titles: list[str] = field(default_factory=list)
    relevant_opened: int = 0


@dataclass
class DiffSummary:
    new_company_count: int
    changed_company_count: int
    total_jobs_opened: int
    total_jobs_closed: int
    net_job_delta: int


@dataclass
class CompaniesDiff:
    since: str
    until: str
    filters: dict
    new_companies: list[NewCompany]
    changed_companies: list[ChangedCompany]
    summary: DiffSummary

    def to_dict(self) -> dict:
        return {
            "since": self.since,
            "until": self.until,
            "filters": self.filters,
            "new_companies": [asdict(c) for c in self.new_companies],
            "changed_companies": [asdict(c) for c in self.changed_companies],
            "summary": asdict(self.summary),
        }


# Relevance cutoff for `relevant_opened`. Mirrors the spec's `>= 0.5` — note
# this is the raw `job_listings.relevance_score` (0-10 scale), so 0.5 is
# effectively "any non-zero relevance signal". Bump in step with
# `beacon match-jobs` if its cutoff ever firms up.
_RELEVANCE_CUTOFF = 0.5


def companies_diff(
    conn: sqlite3.Connection,
    since_sql: str,
    until_iso: str,
    *,
    since_iso: str | None = None,
    tier: int | None = None,
    min_score: float | None = None,
    include_closed: bool = False,
    limit: int = 50,
) -> CompaniesDiff:
    """Compute the new-companies + changed-roles diff against existing tables.

    ``since_sql`` is the cutoff in SQLite's ``YYYY-MM-DD HH:MM:SS`` form (so
    lexical comparison against ``created_at`` / ``date_first_seen`` works).
    ``since_iso`` is the same instant in ``YYYY-MM-DDTHH:MM:SSZ`` form for
    JSON echo; falls back to ``since_sql`` if not provided.
    """
    company_filter_sql = ""
    company_filter_params: list = []
    if tier is not None:
        company_filter_sql += " AND tier = ?"
        company_filter_params.append(tier)
    if min_score is not None:
        company_filter_sql += " AND ai_first_score >= ?"
        company_filter_params.append(min_score)

    # --- new_companies ----------------------------------------------------
    new_rows = conn.execute(
        f"""
        SELECT id, name, domain, tier, ai_first_score, created_at
        FROM companies
        WHERE created_at >= ?{company_filter_sql}
        ORDER BY created_at DESC
        LIMIT ?
        """,
        [since_sql, *company_filter_params, limit],
    ).fetchall()

    new_companies: list[NewCompany] = []
    for r in new_rows:
        cid = r["id"]
        at_create = conn.execute(
            "SELECT COUNT(*) AS cnt FROM job_listings "
            "WHERE company_id = ? AND date_first_seen <= ?",
            (cid, r["created_at"]),
        ).fetchone()["cnt"]
        now_active = conn.execute(
            "SELECT COUNT(*) AS cnt FROM job_listings "
            "WHERE company_id = ? AND status = 'active'",
            (cid,),
        ).fetchone()["cnt"]
        first_sig = conn.execute(
            "SELECT signal_type FROM ai_signals "
            "WHERE company_id = ? ORDER BY created_at ASC LIMIT 1",
            (cid,),
        ).fetchone()
        new_companies.append(
            NewCompany(
                id=cid,
                name=r["name"],
                domain=r["domain"],
                tier=r["tier"],
                ai_first_score=float(r["ai_first_score"] or 0.0),
                created_at=r["created_at"],
                active_jobs_at_creation=at_create,
                active_jobs_now=now_active,
                first_signal=first_sig["signal_type"] if first_sig else None,
            )
        )

    # --- changed_companies ------------------------------------------------
    company_join_filter = company_filter_sql.replace(" AND tier", " AND c.tier") \
                                            .replace(" AND ai_first_score", " AND c.ai_first_score")

    if include_closed:
        closed_clause = (
            "(j.status = 'closed' AND j.date_last_seen >= ?) "
            "OR (j.status = 'active' AND j.date_last_seen >= ? "
            "    AND j.date_last_seen < datetime('now', '-1 day'))"
        )
        closed_params = [since_sql, since_sql]
    else:
        closed_clause = "(j.status = 'closed' AND j.date_last_seen >= ?)"
        closed_params = [since_sql]

    rows = conn.execute(
        f"""
        SELECT c.id AS company_id, c.name, c.tier,
               j.id AS job_id, j.title, j.status, j.relevance_score,
               j.date_first_seen, j.date_last_seen
        FROM job_listings j
        JOIN companies c ON c.id = j.company_id
        WHERE (j.date_first_seen >= ? OR ({closed_clause})){company_join_filter}
        ORDER BY c.name, j.date_first_seen DESC
        """,
        [since_sql, *closed_params, *company_filter_params],
    ).fetchall()

    by_company: dict[int, ChangedCompany] = {}
    for r in rows:
        cid = r["company_id"]
        entry = by_company.get(cid)
        if entry is None:
            entry = ChangedCompany(
                id=cid, name=r["name"], tier=r["tier"],
                jobs_opened=0, jobs_closed=0, net_delta=0,
            )
            by_company[cid] = entry

        opened_in_window = r["date_first_seen"] is not None and r["date_first_seen"] >= since_sql
        firm_closed = r["status"] == "closed" and (r["date_last_seen"] or "") >= since_sql
        loose_closed = (
            include_closed
            and r["status"] == "active"
            and (r["date_last_seen"] or "") >= since_sql
        )

        if opened_in_window:
            entry.jobs_opened += 1
            entry.opened_titles.append(r["title"])
            if (r["relevance_score"] or 0) >= _RELEVANCE_CUTOFF:
                entry.relevant_opened += 1
        if firm_closed or loose_closed:
            entry.jobs_closed += 1
            entry.closed_titles.append(r["title"])

    for entry in by_company.values():
        entry.net_delta = entry.jobs_opened - entry.jobs_closed

    changed_companies = sorted(
        by_company.values(),
        key=lambda e: (-(e.jobs_opened + e.jobs_closed), e.name),
    )[:limit]

    summary = DiffSummary(
        new_company_count=len(new_companies),
        changed_company_count=len(changed_companies),
        total_jobs_opened=sum(c.jobs_opened for c in changed_companies),
        total_jobs_closed=sum(c.jobs_closed for c in changed_companies),
        net_job_delta=0,
    )
    summary.net_job_delta = summary.total_jobs_opened - summary.total_jobs_closed

    return CompaniesDiff(
        since=since_iso or since_sql,
        until=until_iso,
        filters={"tier": tier, "min_score": min_score, "include_closed": include_closed},
        new_companies=new_companies,
        changed_companies=changed_companies,
        summary=summary,
    )


def has_any_companies_matching(
    conn: sqlite3.Connection,
    *,
    tier: int | None,
    min_score: float | None,
) -> bool:
    """Return True if at least one company row satisfies the tier/min_score filter."""
    sql = "SELECT 1 FROM companies WHERE 1=1"
    params: list = []
    if tier is not None:
        sql += " AND tier = ?"
        params.append(tier)
    if min_score is not None:
        sql += " AND ai_first_score >= ?"
        params.append(min_score)
    sql += " LIMIT 1"
    return conn.execute(sql, params).fetchone() is not None
