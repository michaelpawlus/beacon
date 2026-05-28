"""Tests for `beacon companies refresh-signals` and the underlying module."""

from __future__ import annotations

import json
import sqlite3

import pytest
from typer.testing import CliRunner

from beacon.cli import app
from beacon.db.connection import init_db
from beacon.research.signal_refresh import refresh_signals
from beacon.sources.base import Candidate, SourceAdapter

runner = CliRunner()


# ---------- fixtures ----------


class FakeAdapter(SourceAdapter):
    """In-memory adapter returning a hand-crafted candidate per company name."""

    name = "fake"

    def __init__(self, by_name: dict[str, Candidate]):
        self._by_name = {k.lower(): v for k, v in by_name.items()}

    def fetch(self, limit=None):  # pragma: no cover - unused
        yield from self._by_name.values()

    def fetch_for(self, company):
        return self._by_name.get((company.get("name") or "").lower())


@pytest.fixture
def db(tmp_path, monkeypatch):
    db_path = tmp_path / "beacon.db"
    init_db(db_path)
    monkeypatch.setattr("beacon.db.connection.DEFAULT_DB_PATH", db_path)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    # Three companies with progressively older newest signals.
    # Anthropic — very stale (400 days)
    cur = conn.execute(
        "INSERT INTO companies (name, domain, tier) VALUES (?, ?, ?)",
        ("Anthropic", "anthropic.com", 1),
    )
    anthropic_id = cur.lastrowid
    conn.execute(
        "INSERT INTO ai_signals (company_id, signal_type, title, date_observed) "
        "VALUES (?, 'engineering_blog', 'old blog', date('now', '-400 days'))",
        (anthropic_id,),
    )
    # Vercel — recently refreshed (10 days)
    cur = conn.execute(
        "INSERT INTO companies (name, domain, tier) VALUES (?, ?, ?)",
        ("Vercel", "vercel.com", 2),
    )
    vercel_id = cur.lastrowid
    conn.execute(
        "INSERT INTO ai_signals (company_id, signal_type, title, date_observed) "
        "VALUES (?, 'engineering_blog', 'fresh blog', date('now', '-10 days'))",
        (vercel_id,),
    )
    # Linear — no signals at all (always a candidate)
    cur = conn.execute(
        "INSERT INTO companies (name, domain, tier) VALUES (?, ?, ?)",
        ("Linear", "linear.app", 3),
    )
    linear_id = cur.lastrowid
    conn.commit()
    yield conn, db_path, {
        "anthropic": anthropic_id,
        "vercel": vercel_id,
        "linear": linear_id,
    }
    conn.close()


@pytest.fixture
def adapter():
    return FakeAdapter({
        "Anthropic": Candidate(
            name="Anthropic",
            source="fake",
            source_ref="anthropic",
            domain="anthropic.com",
            signals=[
                {
                    "signal_type": "engineering_blog",
                    "title": "Fresh post about Claude",
                    "source_url": "https://example.com/post",
                    "signal_strength": 4,
                },
                {
                    "signal_type": "press_coverage",
                    "title": "Funding announcement",
                    "source_url": "https://example.com/funding",
                    "signal_strength": 3,
                },
            ],
        ),
        "Linear": Candidate(
            name="Linear",
            source="fake",
            source_ref="linear",
            domain="linear.app",
            signals=[
                {
                    "signal_type": "engineering_blog",
                    "title": "Linear adopts agentic workflows",
                    "source_url": "https://linear.app/blog/agents",
                    "signal_strength": 4,
                },
            ],
        ),
    })


# ---------- module-level behavior ----------


def test_stalest_first_ordering(db, adapter):
    conn, _, ids = db
    summary = refresh_signals(conn, since_days=90, limit=10, adapters=[adapter])
    refreshed_names = [r.name for r in summary.results]
    # Anthropic (400d) and Linear (no signals) both qualify; Vercel (10d) doesn't.
    assert "Anthropic" in refreshed_names
    assert "Linear" in refreshed_names
    assert "Vercel" not in refreshed_names
    # Companies with no dated signals come first per the ORDER BY clause.
    assert refreshed_names[0] == "Linear"


def test_limit_is_honored(db, adapter):
    conn, _, _ = db
    summary = refresh_signals(conn, since_days=90, limit=1, adapters=[adapter])
    assert summary.companies_considered == 1
    assert len(summary.results) == 1


def test_company_targets_single(db, adapter):
    conn, _, _ = db
    summary = refresh_signals(conn, company="Anthropic", adapters=[adapter])
    assert summary.companies_considered == 1
    assert summary.results[0].name == "Anthropic"
    assert summary.results[0].signals_added["ai_signals"] == 2


def test_duplicate_signals_skipped_on_second_run(db, adapter):
    conn, _, _ = db
    refresh_signals(conn, company="Anthropic", adapters=[adapter])
    second = refresh_signals(conn, company="Anthropic", adapters=[adapter])
    r = second.results[0]
    assert r.signals_added["ai_signals"] == 0
    assert r.duplicates_skipped == 2


def test_dry_run_does_not_write(db, adapter):
    conn, _, ids = db
    before = conn.execute(
        "SELECT COUNT(*) AS c FROM ai_signals WHERE company_id = ?",
        (ids["anthropic"],),
    ).fetchone()["c"]
    refresh_signals(conn, company="Anthropic", dry_run=True, adapters=[adapter])
    after = conn.execute(
        "SELECT COUNT(*) AS c FROM ai_signals WHERE company_id = ?",
        (ids["anthropic"],),
    ).fetchone()["c"]
    assert before == after


def test_company_and_tier_mutually_exclusive(db, adapter):
    conn, _, _ = db
    with pytest.raises(ValueError):
        refresh_signals(conn, company="Anthropic", tier=1, adapters=[adapter])


# ---------- CLI contract ----------


def test_cli_json_contract(db, adapter, monkeypatch):
    # Inject the fake adapter so the CLI doesn't reach for live sources.
    monkeypatch.setattr(
        "beacon.research.signal_refresh._build_adapters",
        lambda source: [adapter],
    )
    result = runner.invoke(
        app,
        ["companies", "refresh-signals", "--since", "90", "--limit", "10", "--json"],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    # Top-level keys per spec
    for key in (
        "since_days", "filters", "started_at", "completed_at",
        "duration_seconds", "companies_considered", "companies_refreshed",
        "companies_skipped", "results", "totals",
    ):
        assert key in payload, f"missing key {key}"
    assert payload["since_days"] == 90
    assert payload["filters"]["limit"] == 10
    # Each result row carries the spec fields.
    assert payload["results"], "expected at least one refresh result"
    r0 = payload["results"][0]
    for key in (
        "company_id", "name", "tier", "newest_signal_before",
        "newest_signal_after", "sources_queried", "signals_added",
        "duplicates_skipped", "errors",
    ):
        assert key in r0
    for sub in ("ai_signals", "leadership_signals", "tools_adopted"):
        assert sub in r0["signals_added"]
    for tot in (
        "ai_signals_added", "leadership_signals_added",
        "tools_adopted_added", "duplicates_skipped", "sources_failed",
    ):
        assert tot in payload["totals"]


def test_cli_no_match_exits_2(db, adapter, monkeypatch):
    monkeypatch.setattr(
        "beacon.research.signal_refresh._build_adapters",
        lambda source: [adapter],
    )
    result = runner.invoke(
        app,
        ["companies", "refresh-signals", "--company", "DoesNotExist", "--json"],
    )
    assert result.exit_code == 2


def test_cli_mutex_company_tier(db):
    result = runner.invoke(
        app,
        ["companies", "refresh-signals", "--company", "Anthropic", "--tier", "1", "--json"],
    )
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["code"] == 1
