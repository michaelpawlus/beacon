"""Tests for beacon.stories — STAR+Reflection interview story bank (#30)."""

import json

import pytest

from beacon.career import add_win
from beacon.db.connection import get_connection, init_db
from beacon.stories import (
    add_story,
    coverage,
    get_story,
    list_stories,
    promote_win,
    suggest_stories,
    update_story,
)


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_beacon.db"
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn
    conn.close()


def _add_sample(conn, **overrides):
    defaults = {
        "title": "Claims agent rollout",
        "situation": "Claims team drowning in manual triage",
        "task": "Ship an agent pilot",
        "action": "Built a claude-agent-sdk triage agent with evals",
        "result": "12 adjusters onboarded, 4h/week saved each",
        "reflection": "Adoption needs a champion, not just working software",
        "archetypes": ["solutions_fde"],
        "tags": ["ambiguity", "cross-functional"],
    }
    defaults.update(overrides)
    return add_story(conn, **defaults)


def _add_job(conn, title="Forward Deployed Engineer", description="", archetype=None):
    conn.execute("INSERT INTO companies (name) VALUES ('TestCo')")
    company_id = conn.execute("SELECT id FROM companies WHERE name='TestCo'").fetchone()["id"]
    cur = conn.execute(
        "INSERT INTO job_listings (company_id, title, description_text, archetype) VALUES (?, ?, ?, ?)",
        (company_id, title, description, archetype),
    )
    conn.commit()
    return conn.execute("SELECT * FROM job_listings WHERE id = ?", (cur.lastrowid,)).fetchone()


# ── add_story / reflection gate ─────────────────────────────────────


class TestAddStory:
    def test_polished_when_reflection_present(self, db):
        sid = _add_sample(db)
        assert get_story(db, sid)["status"] == "polished"

    def test_draft_without_reflection(self, db):
        sid = _add_sample(db, reflection=None)
        assert get_story(db, sid)["status"] == "draft"

    def test_explicit_polished_without_reflection_raises(self, db):
        with pytest.raises(ValueError, match="gate"):
            _add_sample(db, reflection=None, status="polished")

    def test_invalid_archetype_raises(self, db):
        with pytest.raises(ValueError, match="Unknown archetype"):
            _add_sample(db, archetypes=["wizard"])

    def test_invalid_status_raises(self, db):
        with pytest.raises(ValueError, match="Unknown status"):
            _add_sample(db, status="legendary")

    def test_stores_json_fields(self, db):
        sid = _add_sample(db)
        story = get_story(db, sid)
        assert json.loads(story["archetypes"]) == ["solutions_fde"]
        assert json.loads(story["tags"]) == ["ambiguity", "cross-functional"]


# ── list_stories ────────────────────────────────────────────────────


class TestListStories:
    def test_filter_by_tag(self, db):
        _add_sample(db)
        _add_sample(db, title="Other", tags=["failure"])
        assert [s["title"] for s in list_stories(db, tag="failure")] == ["Other"]

    def test_filter_by_archetype(self, db):
        _add_sample(db)
        _add_sample(db, title="Platform story", archetypes=["data_platform"])
        assert [s["title"] for s in list_stories(db, archetype="data_platform")] == ["Platform story"]

    def test_filter_by_status(self, db):
        _add_sample(db)
        _add_sample(db, title="Draft story", reflection=None)
        assert [s["title"] for s in list_stories(db, status="draft")] == ["Draft story"]

    def test_search(self, db):
        _add_sample(db)
        _add_sample(db, title="Other", situation="Migrated the warehouse", action=None, result=None)
        assert len(list_stories(db, search="warehouse")) == 1


# ── update_story ────────────────────────────────────────────────────


class TestUpdateStory:
    def test_not_found(self, db):
        assert update_story(db, 999, title="x") is False

    def test_reflection_auto_promotes_draft(self, db):
        sid = _add_sample(db, reflection=None)
        update_story(db, sid, reflection="Lesson learned")
        assert get_story(db, sid)["status"] == "polished"

    def test_polish_without_reflection_raises(self, db):
        sid = _add_sample(db, reflection=None)
        with pytest.raises(ValueError, match="gate"):
            update_story(db, sid, status="polished")

    def test_polish_with_existing_reflection_ok(self, db):
        sid = _add_sample(db, status="draft")
        update_story(db, sid, status="polished")
        assert get_story(db, sid)["status"] == "polished"

    def test_retire(self, db):
        sid = _add_sample(db)
        update_story(db, sid, status="retired")
        assert get_story(db, sid)["status"] == "retired"


# ── promote_win ─────────────────────────────────────────────────────


class TestPromoteWin:
    def _win(self, db, **overrides):
        defaults = {
            "title": "Shipped agent pilot",
            "category": "adoption",
            "description": "Rolled out triage agent to claims",
            "impact": "First production agent",
            "metrics": ["12 adjusters", "4h/week saved"],
            "tags": ["agents"],
        }
        defaults.update(overrides)
        return add_win(db, **defaults)

    def test_prefills_star_from_win(self, db):
        win_id = self._win(db)
        sid = promote_win(db, win_id)
        story = get_story(db, sid)
        assert story["task"] == "Shipped agent pilot"
        assert story["situation"] == "Rolled out triage agent to claims"
        assert "First production agent" in story["result"]
        assert "12 adjusters" in story["result"]
        assert story["win_id"] == win_id
        assert story["status"] == "draft"
        assert story["action"] is None

    def test_sets_win_story_id(self, db):
        win_id = self._win(db)
        sid = promote_win(db, win_id)
        row = db.execute("SELECT story_id FROM wins WHERE id = ?", (win_id,)).fetchone()
        assert row["story_id"] == sid

    def test_reflection_makes_polished(self, db):
        win_id = self._win(db)
        sid = promote_win(db, win_id, reflection="Champions drive adoption")
        assert get_story(db, sid)["status"] == "polished"

    def test_double_promote_raises(self, db):
        win_id = self._win(db)
        promote_win(db, win_id)
        with pytest.raises(ValueError, match="already promoted"):
            promote_win(db, win_id)

    def test_missing_win_raises(self, db):
        with pytest.raises(ValueError, match="not found"):
            promote_win(db, 999)


# ── suggest_stories ─────────────────────────────────────────────────


class TestSuggestStories:
    def test_archetype_match_ranks_first(self, db):
        _add_sample(db, title="FDE story")  # solutions_fde
        _add_sample(db, title="ML story", archetypes=["ml_ds"], tags=None)
        job = _add_job(db, archetype="solutions_fde")
        payload = suggest_stories(db, job)
        assert payload["job_archetype"] == "solutions_fde"
        assert payload["suggestions"][0]["title"] == "FDE story"
        assert "archetype:solutions_fde" in payload["suggestions"][0]["reasons"]

    def test_classifies_job_without_archetype_column(self, db):
        _add_sample(db)
        job = _add_job(db, title="Forward Deployed Engineer", archetype=None)
        payload = suggest_stories(db, job)
        assert payload["job_archetype"] == "solutions_fde"

    def test_retired_stories_excluded(self, db):
        sid = _add_sample(db)
        update_story(db, sid, status="retired")
        job = _add_job(db, archetype="solutions_fde")
        assert suggest_stories(db, job)["suggestions"] == []

    def test_top_limits_results(self, db):
        for i in range(5):
            _add_sample(db, title=f"Story {i}")
        job = _add_job(db, archetype="solutions_fde")
        assert len(suggest_stories(db, job, top=3)["suggestions"]) == 3

    def test_mark_used_bumps_counters(self, db):
        sid = _add_sample(db)
        job = _add_job(db, archetype="solutions_fde")
        suggest_stories(db, job, mark_used=True)
        story = get_story(db, sid)
        assert story["times_used"] == 1
        assert story["last_used_at"] is not None

    def test_no_mutation_without_mark_used(self, db):
        sid = _add_sample(db)
        job = _add_job(db, archetype="solutions_fde")
        suggest_stories(db, job)
        assert get_story(db, sid)["times_used"] == 0


# ── coverage ────────────────────────────────────────────────────────


class TestCoverage:
    def test_empty_bank(self, db):
        report = coverage(db)
        assert report["total"] == 0
        assert len(report["uncovered_tags"]) == 5

    def test_counts_polished_only(self, db):
        _add_sample(db)  # polished: ambiguity, cross-functional
        _add_sample(db, title="Draft", reflection=None, tags=["leadership"])
        report = coverage(db)
        assert report["polished"] == 1
        assert report["by_tag"]["ambiguity"] == 1
        assert report["by_tag"]["leadership"] == 0  # draft doesn't count
        assert "leadership" in report["uncovered_tags"]
        assert report["by_archetype"] == {"solutions_fde": 1}
