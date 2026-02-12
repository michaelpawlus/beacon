"""Scanner orchestrator — coordinates adapters, scoring, and DB operations."""

import sqlite3
from dataclasses import dataclass

from beacon.db.jobs import mark_stale_jobs, upsert_job
from beacon.research.job_scoring import compute_job_relevance
from beacon.scrapers.registry import get_adapter


@dataclass
class ScanResult:
    """Result of scanning a single company."""
    company_name: str
    platform: str
    jobs_found: int = 0
    new_jobs: int = 0
    updated_jobs: int = 0
    stale_jobs: int = 0
    error: str | None = None


def scan_company(conn: sqlite3.Connection, company: sqlite3.Row) -> ScanResult:
    """Scan a single company for job listings.

    Pipeline: adapter.fetch_jobs() -> score each -> upsert_job() -> mark_stale_jobs()
    """
    result = ScanResult(
        company_name=company["name"],
        platform=company["careers_platform"] or "unknown",
    )

    adapter = get_adapter(result.platform)
    if adapter is None:
        result.error = f"No adapter for platform: {result.platform}"
        return result

    try:
        raw_jobs = adapter.fetch_jobs(dict(company))
    except Exception as e:
        result.error = str(e)
        return result

    result.jobs_found = len(raw_jobs)
    active_urls = set()

    for job_data in raw_jobs:
        # Score the job
        relevance = compute_job_relevance(job_data)

        # Upsert into DB
        upsert_result = upsert_job(
            conn,
            company_id=company["id"],
            title=job_data["title"],
            url=job_data.get("url"),
            location=job_data.get("location"),
            department=job_data.get("department"),
            description_text=job_data.get("description_text"),
            date_posted=job_data.get("date_posted"),
            relevance_score=relevance["score"],
            match_reasons=relevance["reasons"],
        )

        if upsert_result["is_new"]:
            result.new_jobs += 1
        else:
            result.updated_jobs += 1

        active_urls.add(job_data.get("url"))

    # Mark jobs not seen in this scan as stale
    result.stale_jobs = mark_stale_jobs(conn, company["id"], active_urls)

    return result


def scan_all(
    conn: sqlite3.Connection,
    platform: str | None = None,
    company_name: str | None = None,
    min_score: float | None = None,
) -> list[ScanResult]:
    """Scan all (or filtered) companies for job listings."""
    query = "SELECT * FROM companies WHERE 1=1"
    params: list = []

    if company_name:
        query += " AND name LIKE ?"
        params.append(f"%{company_name}%")
    if platform:
        query += " AND careers_platform = ?"
        params.append(platform)
    if min_score is not None:
        query += " AND ai_first_score >= ?"
        params.append(min_score)

    query += " ORDER BY ai_first_score DESC"
    companies = conn.execute(query, params).fetchall()

    results = []
    for company in companies:
        result = scan_company(conn, company)
        results.append(result)

    return results
