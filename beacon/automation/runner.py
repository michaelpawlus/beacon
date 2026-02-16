"""Automation runner — orchestrates scan, notify, and log cycles."""

import logging
import sqlite3
import time

from beacon.config import BeaconConfig

logger = logging.getLogger("beacon.automation.runner")


def _log_run(
    conn: sqlite3.Connection,
    run_type: str,
    started_at: float,
    jobs_found: int = 0,
    new_relevant_jobs: int = 0,
    notifications_sent: int = 0,
    signals_refreshed: int = 0,
    errors: str | None = None,
) -> int:
    """Record an automation run in the log."""
    duration = time.time() - started_at
    cursor = conn.execute(
        """INSERT INTO automation_log
           (run_type, jobs_found, new_relevant_jobs, notifications_sent,
            signals_refreshed, errors, duration_seconds, completed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
        (run_type, jobs_found, new_relevant_jobs, notifications_sent,
         signals_refreshed, errors, duration),
    )
    conn.commit()
    return cursor.lastrowid


def run_scan_only(conn: sqlite3.Connection, config: BeaconConfig) -> dict:
    """Run a scan-only cycle: scan all companies, return stats."""
    started_at = time.time()
    result = {"jobs_found": 0, "new_relevant_jobs": 0, "notifications_sent": 0, "errors": None}

    try:
        from beacon.scanner import scan_all
        scan_results = scan_all(conn)

        result["jobs_found"] = sum(r.jobs_found for r in scan_results)
        result["new_relevant_jobs"] = sum(r.new_jobs for r in scan_results)

        errors = [f"{r.company_name}: {r.error}" for r in scan_results if r.error]
        result["errors"] = "; ".join(errors) if errors else None

    except Exception as e:
        result["errors"] = str(e)
        logger.error("Scan failed: %s", e)

    _log_run(conn, "scan", started_at, **{k: v for k, v in result.items() if k != "errors"}, errors=result["errors"])
    return result


def run_digest(conn: sqlite3.Connection, config: BeaconConfig) -> dict:
    """Run a digest-only cycle: gather dashboard data, send digest notification."""
    started_at = time.time()
    result = {"jobs_found": 0, "new_relevant_jobs": 0, "notifications_sent": 0, "errors": None}

    try:
        from beacon.dashboard import gather_dashboard_data
        from beacon.notifications.formatters import format_digest
        from beacon.notifications.registry import notify_all

        data = gather_dashboard_data(conn)
        result["jobs_found"] = data.active_job_count

        body = format_digest(data)
        send_results = notify_all(config, "Daily Digest", body)
        result["notifications_sent"] = sum(1 for r in send_results if r)

    except Exception as e:
        result["errors"] = str(e)
        logger.error("Digest failed: %s", e)

    _log_run(conn, "digest", started_at, **{k: v for k, v in result.items() if k != "errors"}, errors=result["errors"])
    return result


def run_automation_cycle(conn: sqlite3.Connection, config: BeaconConfig) -> dict:
    """Run a full automation cycle: scan → filter → notify → log."""
    started_at = time.time()
    result = {"jobs_found": 0, "new_relevant_jobs": 0, "notifications_sent": 0, "errors": None}

    errors_list = []

    # Step 1: Scan
    try:
        from beacon.scanner import scan_all
        scan_results = scan_all(conn)
        result["jobs_found"] = sum(r.jobs_found for r in scan_results)
        result["new_relevant_jobs"] = sum(r.new_jobs for r in scan_results)

        scan_errors = [f"{r.company_name}: {r.error}" for r in scan_results if r.error]
        errors_list.extend(scan_errors)
    except Exception as e:
        errors_list.append(f"scan: {e}")
        logger.error("Scan step failed: %s", e)

    # Step 2: Notify if new relevant jobs
    try:
        if result["new_relevant_jobs"] > 0:
            from datetime import datetime, timedelta

            from beacon.db.jobs import get_new_jobs_since
            from beacon.notifications.formatters import format_new_jobs_alert
            from beacon.notifications.registry import notify_all

            since = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
            new_jobs = get_new_jobs_since(conn, since, min_relevance=config.min_relevance_alert)

            if new_jobs:
                jobs_data = [dict(j) for j in new_jobs]
                body = format_new_jobs_alert(jobs_data)
                send_results = notify_all(config, f"{len(new_jobs)} New Relevant Jobs", body, urgency="high")
                result["notifications_sent"] = sum(1 for r in send_results if r)
    except Exception as e:
        errors_list.append(f"notify: {e}")
        logger.error("Notification step failed: %s", e)

    result["errors"] = "; ".join(errors_list) if errors_list else None
    _log_run(conn, "full", started_at, **{k: v for k, v in result.items() if k != "errors"}, errors=result["errors"])
    return result
