"""End-to-end tests for `beacon companies diff`.

Covers the spec acceptance criteria from
``Project Ideas/beacon-companies-diff-cli-spec.md``:
  • JSON shape (since/until/filters/new_companies/changed_companies/summary)
  • Tier filter excludes off-tier in-window new companies
  • Future --since returns empty arrays, exit 0
  • Malformed --since exits 1 with {"error", "code": 1}
  • --include-closed broadens the closed count via the loose branch
  • Relevance cutoff drives relevant_opened
"""

import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from typer.testing import CliRunner

from beacon.cli import app
from beacon.db.connection import init_db

runner = CliRunner()


def _sqlite_fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "beacon.db"
    init_db(db_path)
    monkeypatch.setattr("beacon.db.connection.DEFAULT_DB_PATH", db_path)
    return db_path


def _seed(db_path):
    """Seed three companies + four job listings spanning the diff window."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    in_window = now - timedelta(days=3)
    pre_window = now - timedelta(days=20)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")

    # Three companies: two new-in-window (one tier-1, one tier-3), one pre-window
    conn.execute(
        "INSERT INTO companies (name, tier, ai_first_score, created_at) VALUES (?, ?, ?, ?)",
        ("InWindowAI", 1, 8.5, _sqlite_fmt(in_window)),
    )
    conn.execute(
        "INSERT INTO companies (name, tier, ai_first_score, created_at) VALUES (?, ?, ?, ?)",
        ("EstablishedAI", 1, 9.0, _sqlite_fmt(pre_window)),
    )
    conn.execute(
        "INSERT INTO companies (name, tier, ai_first_score, created_at) VALUES (?, ?, ?, ?)",
        ("NewTier3", 3, 4.0, _sqlite_fmt(in_window)),
    )

    established_id = conn.execute(
        "SELECT id FROM companies WHERE name = 'EstablishedAI'"
    ).fetchone()[0]

    # 1) opened-in-window, still active, relevant
    conn.execute(
        "INSERT INTO job_listings (company_id, title, url, date_first_seen, date_last_seen, status, relevance_score) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (established_id, "Forward Deployed Engineer", "u1",
         _sqlite_fmt(in_window), _sqlite_fmt(now), "active", 8.0),
    )
    # 2) opened-in-window, relevance below cutoff
    conn.execute(
        "INSERT INTO job_listings (company_id, title, url, date_first_seen, date_last_seen, status, relevance_score) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (established_id, "Office Manager", "u2",
         _sqlite_fmt(in_window), _sqlite_fmt(now), "active", 0.0),
    )
    # 3) closed-in-window (firm)
    conn.execute(
        "INSERT INTO job_listings (company_id, title, url, date_first_seen, date_last_seen, status, relevance_score) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (established_id, "RemovedRole", "u3",
         _sqlite_fmt(pre_window), _sqlite_fmt(in_window), "closed", 6.0),
    )
    # 4) unchanged-pre-window — should not surface
    conn.execute(
        "INSERT INTO job_listings (company_id, title, url, date_first_seen, date_last_seen, status, relevance_score) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (established_id, "OldRole", "u4",
         _sqlite_fmt(pre_window), _sqlite_fmt(pre_window), "active", 5.0),
    )
    # 5) loose-closed candidate: active but date_last_seen is in window AND > 1 day ago
    stale_seen = now - timedelta(days=2)
    conn.execute(
        "INSERT INTO job_listings (company_id, title, url, date_first_seen, date_last_seen, status, relevance_score) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (established_id, "GhostRole", "u5",
         _sqlite_fmt(pre_window), _sqlite_fmt(stale_seen), "active", 4.0),
    )

    conn.commit()
    conn.close()


# --- JSON shape -------------------------------------------------------------


def test_diff_json_shape(temp_db):
    _seed(temp_db)
    res = runner.invoke(app, ["companies", "diff", "--since", "7d", "--json"])
    assert res.exit_code == 0, res.stdout + res.stderr
    data = json.loads(res.stdout)

    for key in ("since", "until", "filters", "new_companies", "changed_companies", "summary"):
        assert key in data, f"missing top-level key {key}"

    new_names = {c["name"] for c in data["new_companies"]}
    assert "InWindowAI" in new_names
    assert "NewTier3" in new_names
    assert "EstablishedAI" not in new_names

    in_window = next(c for c in data["new_companies"] if c["name"] == "InWindowAI")
    for key in ("id", "name", "domain", "tier", "ai_first_score",
                "created_at", "active_jobs_at_creation", "active_jobs_now", "first_signal"):
        assert key in in_window

    changed_names = {c["name"] for c in data["changed_companies"]}
    assert "EstablishedAI" in changed_names

    est = next(c for c in data["changed_companies"] if c["name"] == "EstablishedAI")
    assert est["jobs_opened"] == 2  # FDE + Office Manager
    assert est["jobs_closed"] == 1  # RemovedRole (firm)
    assert est["net_delta"] == 1
    assert est["relevant_opened"] == 1  # only the FDE clears the 0.5 cutoff

    summary = data["summary"]
    assert summary["new_company_count"] == 2
    assert summary["changed_company_count"] == 1
    assert summary["total_jobs_opened"] == 2
    assert summary["total_jobs_closed"] == 1
    assert summary["net_job_delta"] == 1


def test_diff_filters_block_present_in_payload(temp_db):
    _seed(temp_db)
    res = runner.invoke(app, ["companies", "diff", "--since", "7d", "--json"])
    data = json.loads(res.stdout)
    assert data["filters"] == {
        "tier": None,
        "min_score": None,
        "include_closed": False,
    }


# --- tier filter ------------------------------------------------------------


def test_diff_tier_filter_excludes_off_tier_new_companies(temp_db):
    _seed(temp_db)
    res = runner.invoke(app, ["companies", "diff", "--since", "7d", "--tier", "1", "--json"])
    assert res.exit_code == 0
    data = json.loads(res.stdout)
    names = {c["name"] for c in data["new_companies"]}
    assert "InWindowAI" in names
    assert "NewTier3" not in names
    assert data["filters"]["tier"] == 1


# --- future / malformed ----------------------------------------------------


def test_diff_future_since_returns_empty(temp_db):
    _seed(temp_db)
    future = (datetime.now(timezone.utc) + timedelta(days=5)).strftime("%Y-%m-%d")
    res = runner.invoke(app, ["companies", "diff", "--since", future, "--json"])
    assert res.exit_code == 0
    data = json.loads(res.stdout)
    assert data["new_companies"] == []
    assert data["changed_companies"] == []
    assert data["summary"]["new_company_count"] == 0


def test_diff_malformed_since_exits_1(temp_db):
    res = runner.invoke(app, ["companies", "diff", "--since", "not-a-date", "--json"])
    assert res.exit_code == 1
    data = json.loads(res.stdout)
    assert "error" in data
    assert data["code"] == 1


def test_diff_no_companies_match_filter_exits_2(temp_db):
    _seed(temp_db)
    res = runner.invoke(
        app,
        ["companies", "diff", "--since", "7d", "--min-score", "99", "--json"],
    )
    assert res.exit_code == 2
    data = json.loads(res.stdout)
    assert data["code"] == 2


# --- include-closed --------------------------------------------------------


def test_diff_include_closed_picks_up_loose_branch(temp_db):
    _seed(temp_db)
    base = runner.invoke(app, ["companies", "diff", "--since", "7d", "--json"])
    base_data = json.loads(base.stdout)

    loose = runner.invoke(
        app,
        ["companies", "diff", "--since", "7d", "--include-closed", "--json"],
    )
    loose_data = json.loads(loose.stdout)

    # Loose branch should surface GhostRole as an additional close
    assert loose_data["summary"]["total_jobs_closed"] > base_data["summary"]["total_jobs_closed"]
    assert loose_data["filters"]["include_closed"] is True


# --- exit code 0 for zero deltas with no filters ---------------------------


def test_diff_zero_deltas_no_filters_exits_0(temp_db):
    # No data seeded — fresh DB with no companies created in window
    res = runner.invoke(app, ["companies", "diff", "--since", "7d", "--json"])
    assert res.exit_code == 0
    data = json.loads(res.stdout)
    assert data["new_companies"] == []
    assert data["changed_companies"] == []
