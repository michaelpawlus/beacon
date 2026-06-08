"""Tests for the posting-strategy radar (beacon presence radar)."""

import json
from datetime import date, timedelta

import pytest

from beacon.db.connection import get_connection, init_db
from beacon.db.content import add_calendar_entry
from beacon.db.profile import add_project, add_skill
from beacon.db.speaker import add_presentation
from beacon.media import add_media
from beacon.presence.radar import (
    build_radar,
    external_radar,
    internal_sweep,
    render_radar_markdown,
    score_opportunity,
    seed_calendar,
    sweep_media,
    sweep_presentations,
    sweep_projects,
    sweep_sessions,
)
from beacon.session import save_session_to_db


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_beacon.db"
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn
    conn.close()


TODAY = date(2026, 6, 8)


def _d(days_ago: int) -> str:
    return (TODAY - timedelta(days=days_ago)).isoformat()


# --- Internal sweep ---------------------------------------------------------

class TestSweeps:
    def test_sessions_recent_only(self, db):
        save_session_to_db(db, "Built radar feature", "Shipped the radar",
                           technologies=["python", "sqlite"], impact="Saved hours",
                           session_date=_d(5))
        save_session_to_db(db, "Old work", "stale", session_date=_d(120))
        opps = sweep_sessions(db, since_days=30, today=TODAY)
        assert len(opps) == 1
        o = opps[0]
        assert o["source"] == "session"
        assert o["title"] == "Built radar feature"
        assert "linkedin" in o["platforms"]
        assert any("Saved hours" in e for e in o["evidence"])

    def test_projects_route_github_when_public(self, db):
        add_project(db, "Beacon", description="job intel",
                    technologies=["python"], outcomes=["38 companies"],
                    repo_url="https://github.com/x/beacon", is_public=True)
        opps = sweep_projects(db, since_days=30, today=TODAY)
        assert len(opps) == 1
        assert "github" in opps[0]["platforms"]
        assert any("38 companies" in e for e in opps[0]["evidence"])

    def test_presentations_delivered_only(self, db):
        add_presentation(db, "AI talk", status="delivered", date=_d(3),
                         event_name="AI Tinkerers", recording_url="https://rec/1")
        add_presentation(db, "Planned talk", status="planned", date=_d(2))
        opps = sweep_presentations(db, since_days=30, today=TODAY)
        assert len(opps) == 1
        assert opps[0]["source"] == "presentation"
        assert "twitter" in opps[0]["platforms"]  # has recording

    def test_media_high_signal_only(self, db):
        add_media(db, "Great video", "video", rating=5,
                  why_it_matters="shifts how teams think", date_consumed=_d(2))
        add_media(db, "Meh article", "article", rating=2, date_consumed=_d(1))
        opps = sweep_media(db, since_days=30, today=TODAY)
        assert len(opps) == 1
        assert opps[0]["title"] == "Great video"

    def test_internal_sweep_aggregates(self, db):
        save_session_to_db(db, "S", "x", session_date=_d(1))
        add_project(db, "P", technologies=["go"])
        opps = internal_sweep(db, since_days=30, today=TODAY)
        assert {o["source"] for o in opps} == {"session", "project"}


# --- Scoring ----------------------------------------------------------------

class TestScoring:
    def test_recency_and_timeliness_increase_score(self, db):
        fresh = {"source": "session", "recency_days": 0, "evidence": [], "timely": True}
        stale = {"source": "session", "recency_days": 29, "evidence": []}
        assert score_opportunity(fresh, 30) > score_opportunity(stale, 30)

    def test_covered_penalty(self, db):
        base = {"source": "project", "recency_days": 0, "evidence": ["a"]}
        covered = {**base, "already_covered": True}
        assert score_opportunity(base, 30) > score_opportunity(covered, 30)


# --- Dedupe against calendar ------------------------------------------------

class TestDedupe:
    def test_already_planned_flagged(self, db):
        add_project(db, "Quantum Scheduler", description="d", technologies=["rust"])
        add_calendar_entry(db, "How I built Quantum Scheduler", "blog", "post",
                           topic="Quantum Scheduler deep dive")
        payload = build_radar(db, since_days=30, web=False, today=TODAY)
        proj = next(o for o in payload["opportunities"] if o["source"] == "project")
        assert proj["already_covered"] is True
        # shipped_unposted excludes the covered project
        assert payload["shipped_unposted"] == 0


# --- External radar (mocked) ------------------------------------------------

class TestExternalRadar:
    def test_external_radar_cleans_items(self):
        def fake(keywords, max_terms):
            return [
                {"term": "Agentic RAG", "summary": "hot", "hook": "post it",
                 "keywords": ["RAG", "Agents"]},
                {"summary": "no term — dropped"},
            ]
        items = external_radar(["rag"], search_fn=fake)
        assert len(items) == 1
        assert items[0]["term"] == "Agentic RAG"
        assert items[0]["keywords"] == ["rag", "agents"]

    def test_external_radar_empty_without_keywords(self):
        assert external_radar([], search_fn=lambda k, m: [{"term": "x"}]) == []

    def test_build_radar_with_web_marks_timely_and_adds_trend_opp(self, db):
        save_session_to_db(db, "Shipped a RAG pipeline", "built retrieval",
                           technologies=["rag", "python"], session_date=_d(2))

        def fake(keywords, max_terms):
            return [{"term": "Agentic RAG", "summary": "everyone debating it",
                     "hook": "share your pipeline", "keywords": ["rag"]}]

        payload = build_radar(db, since_days=30, web=True, search_fn=fake, today=TODAY)
        assert payload["trending"]
        sources = {o["source"] for o in payload["opportunities"]}
        assert "trend" in sources
        session_opp = next(o for o in payload["opportunities"] if o["source"] == "session")
        assert session_opp["timely"] is True
        assert session_opp["trending_hook"] == "Agentic RAG"

    def test_build_radar_web_failure_degrades(self, db):
        save_session_to_db(db, "work", "x", technologies=["python"], session_date=_d(1))

        def boom(keywords, max_terms):
            raise RuntimeError("ANTHROPIC_API_KEY not set")

        payload = build_radar(db, since_days=30, web=True, search_fn=boom, today=TODAY)
        assert payload["warnings"]
        assert payload["opportunities"]  # still has internal opps


# --- search_fn signature: build_radar must thread it through ----------------

def test_build_radar_threads_search_fn(db):
    add_skill(db, "Python", category="language", proficiency="expert")
    save_session_to_db(db, "w", "x", technologies=["python"], session_date=_d(1))
    captured = {}

    def fake(keywords, max_terms):
        captured["keywords"] = keywords
        return []

    build_radar(db, since_days=30, web=True, search_fn=fake, today=TODAY)
    assert "python" in captured["keywords"]


# --- Calendar seeding -------------------------------------------------------

def test_seed_calendar_creates_entries(db):
    save_session_to_db(db, "Shipped X", "did X", session_date=_d(1))
    payload = build_radar(db, since_days=30, web=False, today=TODAY)
    n = seed_calendar(db, payload["opportunities"])
    assert n == len(payload["opportunities"])
    from beacon.db.content import get_calendar_entries
    assert len(get_calendar_entries(db)) == n


# --- Rendering + JSON safety ------------------------------------------------

def test_render_markdown(db):
    save_session_to_db(db, "Shipped X", "did X", impact="big", session_date=_d(1))
    payload = build_radar(db, since_days=30, web=False, today=TODAY)
    md = render_radar_markdown(payload)
    assert "# Posting Strategy Radar" in md
    assert "Ranked posting backlog" in md


def test_payload_is_json_serializable(db):
    save_session_to_db(db, "Shipped X", "did X", session_date=_d(1))
    payload = build_radar(db, since_days=30, web=False, today=TODAY)
    json.dumps(payload)  # must not raise


def test_platform_filter(db):
    add_project(db, "P", technologies=["go"], repo_url="https://x", is_public=True)
    payload = build_radar(db, since_days=30, web=False, platform="github", today=TODAY)
    assert all("github" in o["platforms"] for o in payload["opportunities"])
