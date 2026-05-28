"""Tests for the `beacon scores` flag upgrade (--since / --company / --json)."""

from __future__ import annotations

import json
import sqlite3

import pytest
from typer.testing import CliRunner

from beacon.cli import app
from beacon.db.connection import init_db
from beacon.research.scoring import refresh_score

runner = CliRunner()


@pytest.fixture
def db(tmp_path, monkeypatch):
    db_path = tmp_path / "beacon.db"
    init_db(db_path)
    monkeypatch.setattr("beacon.db.connection.DEFAULT_DB_PATH", db_path)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    ids = {}
    for name in ("Stale Co", "Fresh Co", "Newest Signal Co"):
        cur = conn.execute(
            "INSERT INTO companies (name, tier) VALUES (?, 1)", (name,)
        )
        ids[name] = cur.lastrowid

    # Seed initial signals so composites aren't all zero.
    for cid in ids.values():
        conn.execute(
            "INSERT INTO ai_signals (company_id, signal_type, title, "
            "date_observed, signal_strength) "
            "VALUES (?, 'engineering_blog', 'seed', date('now', '-200 days'), 3)",
            (cid,),
        )
    conn.commit()

    # Compute initial scores so score_breakdown rows exist.
    for cid in ids.values():
        refresh_score(conn, cid)

    # Backdate Stale Co's last_computed_at well past `--since 7`.
    conn.execute(
        "UPDATE score_breakdown SET last_computed_at = datetime('now', '-30 days') "
        "WHERE company_id = ?",
        (ids["Stale Co"],),
    )
    # Newest Signal Co was computed yesterday, BUT it has a brand new signal today
    # — should still be picked up by --since.
    conn.execute(
        "UPDATE score_breakdown SET last_computed_at = datetime('now', '-1 days') "
        "WHERE company_id = ?",
        (ids["Newest Signal Co"],),
    )
    conn.execute(
        "INSERT INTO ai_signals (company_id, signal_type, title, "
        "date_observed, signal_strength) "
        "VALUES (?, 'engineering_blog', 'today', date('now'), 5)",
        (ids["Newest Signal Co"],),
    )
    conn.commit()
    yield conn, db_path, ids
    conn.close()


def test_bare_command_unchanged(db):
    conn, _, ids = db
    result = runner.invoke(app, ["scores"])
    assert result.exit_code == 0
    # All three got recomputed.
    rows = conn.execute(
        "SELECT company_id, last_computed_at FROM score_breakdown"
    ).fetchall()
    assert len(rows) == 3


def test_since_only_recomputes_stale(db):
    conn, _, ids = db
    result = runner.invoke(app, ["scores", "--since", "7", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    names = {r["name"] for r in payload["results"]}
    # Stale Co (30d old compute) and Newest Signal Co (signal newer than compute) qualify.
    assert "Stale Co" in names
    assert "Newest Signal Co" in names
    # Fresh Co was computed seconds ago — should be skipped.
    assert "Fresh Co" not in names
    assert payload["recomputed"] == 2
    assert payload["skipped"] == 1


def test_company_filter_single_row(db):
    result = runner.invoke(app, ["scores", "--company", "Stale Co", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["recomputed"] == 1
    assert payload["results"][0]["name"] == "Stale Co"
    assert "composite_before" in payload["results"][0]
    assert "composite_after" in payload["results"][0]
    assert "delta" in payload["results"][0]


def test_company_no_match_exits_2(db):
    result = runner.invoke(app, ["scores", "--company", "Nobody", "--json"])
    assert result.exit_code == 2
    payload = json.loads(result.stdout)
    assert payload["code"] == 2


def test_json_emits_parseable_output(db):
    result = runner.invoke(app, ["scores", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    # Bare-form JSON envelope still carries the contract keys.
    for k in ("since_days", "filters", "recomputed", "skipped", "results"):
        assert k in payload
    assert payload["since_days"] is None
    assert payload["filters"]["company"] is None
