"""Tests for beacon.career — win/evidence log and brag-doc review."""

from datetime import date, timedelta

import pytest

from beacon.career import (
    add_win,
    category_mix,
    current_role,
    get_win,
    list_wins,
    render_review_markdown,
    resolve_since,
)
from beacon.db.connection import get_connection, init_db


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_beacon.db"
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn
    conn.close()


def _add_sample(conn, **overrides):
    defaults = {
        "title": "Shipped agent pilot to claims team",
        "category": "adoption",
        "description": "Rolled out the claims triage agent to the pilot group",
        "impact": "First production agent in the claims org",
        "metrics": ["12 adjusters onboarded", "4h/week saved each"],
        "stakeholders": ["VP Claims"],
        "technologies": ["claude-agent-sdk"],
    }
    defaults.update(overrides)
    return add_win(conn, **defaults)


# ── resolve_since ───────────────────────────────────────────────────


class TestResolveSince:
    def test_none_passes_through(self):
        assert resolve_since(None) is None

    def test_iso_date_passes_through(self):
        assert resolve_since("2026-01-15") == "2026-01-15"

    def test_relative_days(self):
        expected = (date.today() - timedelta(days=30)).isoformat()
        assert resolve_since("30d") == expected


# ── add_win ─────────────────────────────────────────────────────────


class TestAddWin:
    def test_returns_id(self, db):
        win_id = add_win(db, title="First win")
        assert win_id > 0

    def test_stores_all_fields(self, db):
        win_id = _add_sample(db)
        row = db.execute("SELECT * FROM wins WHERE id = ?", (win_id,)).fetchone()
        assert row["title"] == "Shipped agent pilot to claims team"
        assert row["category"] == "adoption"
        assert "12 adjusters onboarded" in row["metrics"]
        assert "VP Claims" in row["stakeholders"]
        assert row["visibility"] == "private"

    def test_defaults_win_date_to_today(self, db):
        win_id = add_win(db, title="Dated win")
        row = db.execute("SELECT win_date FROM wins WHERE id = ?", (win_id,)).fetchone()
        assert row["win_date"] == date.today().isoformat()

    def test_explicit_win_date(self, db):
        win_id = add_win(db, title="Old win", win_date="2026-01-01")
        row = db.execute("SELECT win_date FROM wins WHERE id = ?", (win_id,)).fetchone()
        assert row["win_date"] == "2026-01-01"

    def test_invalid_category_raises(self, db):
        with pytest.raises(ValueError, match="Unknown category"):
            add_win(db, title="Bad", category="winning")

    def test_invalid_visibility_raises(self, db):
        with pytest.raises(ValueError, match="Unknown visibility"):
            add_win(db, title="Bad", visibility="secret")

    def test_links_to_session(self, db):
        db.execute(
            "INSERT INTO sessions (title, summary, project) VALUES ('s', 'sum', 'beacon')"
        )
        session_id = db.execute("SELECT id FROM sessions").fetchone()["id"]
        win_id = add_win(db, title="From session", session_id=session_id)
        row = db.execute("SELECT session_id FROM wins WHERE id = ?", (win_id,)).fetchone()
        assert row["session_id"] == session_id


# ── list_wins ───────────────────────────────────────────────────────


class TestListWins:
    def test_empty(self, db):
        assert list_wins(db) == []

    def test_filter_by_category(self, db):
        _add_sample(db, category="adoption")
        _add_sample(db, title="Built dashboard", category="delivery")
        wins = list_wins(db, category="delivery")
        assert len(wins) == 1
        assert wins[0]["title"] == "Built dashboard"

    def test_filter_since_relative(self, db):
        _add_sample(db, title="Recent")
        _add_sample(db, title="Ancient", win_date="2020-01-01")
        wins = list_wins(db, since="30d")
        assert [w["title"] for w in wins] == ["Recent"]

    def test_untold_excludes_promoted(self, db):
        kept = _add_sample(db, title="Untold")
        promoted = _add_sample(db, title="Told")
        db.execute("UPDATE wins SET story_id = 1 WHERE id = ?", (promoted,))
        db.commit()
        wins = list_wins(db, untold=True)
        assert [w["id"] for w in wins] == [kept]

    def test_search(self, db):
        _add_sample(db)
        _add_sample(db, title="Taught prompt workshop", description="Enablement session", impact=None)
        wins = list_wins(db, search="workshop")
        assert len(wins) == 1

    def test_limit(self, db):
        for i in range(5):
            _add_sample(db, title=f"Win {i}")
        assert len(list_wins(db, limit=3)) == 3


# ── get_win / current_role ──────────────────────────────────────────


class TestGetWin:
    def test_found(self, db):
        win_id = _add_sample(db)
        win = get_win(db, win_id)
        assert win["title"] == "Shipped agent pilot to claims team"

    def test_not_found(self, db):
        assert get_win(db, 999) is None


class TestCurrentRole:
    def test_none_when_empty(self, db):
        assert current_role(db) is None

    def test_picks_open_ended_role(self, db):
        db.execute(
            "INSERT INTO work_experiences (company, title, start_date, end_date) "
            "VALUES ('Old Co', 'Analyst', '2020-01', '2026-05')"
        )
        db.execute(
            "INSERT INTO work_experiences (company, title, start_date) "
            "VALUES ('New Co', 'Forward Deployed Engineer', '2026-06')"
        )
        db.commit()
        role = current_role(db)
        assert role["company"] == "New Co"


# ── category_mix / render_review_markdown ───────────────────────────


class TestCategoryMix:
    def test_counts_and_split(self, db):
        _add_sample(db, category="adoption")
        _add_sample(db, title="Enabled team", category="enablement")
        _add_sample(db, title="Shipped feature", category="delivery")
        _add_sample(db, title="No category", category=None)
        mix = category_mix(list_wins(db))
        assert mix["by_category"]["adoption"] == 1
        assert mix["by_category"]["uncategorized"] == 1
        assert mix["diffusion"] == 2
        assert mix["delivery"] == 1


class TestRenderReview:
    def test_empty_state_nudges(self):
        md = render_review_markdown([], "since 2026-03-01")
        assert "No wins logged" in md
        assert "beacon career win add" in md

    def test_renders_wins_and_mix(self, db):
        _add_sample(db)
        _add_sample(db, title="Shipped feature", category="delivery", metrics=None)
        md = render_review_markdown(list_wins(db), "since 2026-03-01")
        assert "## Win Mix" in md
        assert "Shipped agent pilot to claims team" in md
        assert "12 adjusters onboarded" in md
        assert "VP Claims" in md

    def test_untold_section_only_for_metric_wins(self, db):
        _add_sample(db, title="Strong untold")
        _add_sample(db, title="Weak untold", metrics=None)
        md = render_review_markdown(list_wins(db), "window")
        assert "## Untold Stories" in md
        assert "Strong untold" in md
        assert "- [1] Weak untold" not in md and "Weak untold\n" not in md.split("## Untold Stories")[1]

    def test_includes_role_header(self, db):
        _add_sample(db)
        role = {"title": "Forward Deployed Engineer", "company": "New Co"}
        md = render_review_markdown(list_wins(db), "window", role=role)
        assert "Forward Deployed Engineer at New Co" in md
