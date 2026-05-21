"""Tests for the profile-aware job fit ranker."""

import json
from unittest.mock import MagicMock

import pytest

from beacon.db.connection import get_connection, init_db
from beacon.db.jobs import upsert_job
from beacon.db.profile import (
    add_application,
    add_project,
    add_skill,
    add_work_experience,
)
from beacon.db.feedback import record_outcome
from beacon.research import job_fit
from beacon.research.job_fit import compute_job_fit, get_or_extract_requirements


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_beacon.db"
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn, db_path
    conn.close()


def _insert_company(conn, name="Anthropic"):
    conn.execute(
        "INSERT INTO companies (name, industry, remote_policy, size_bucket) "
        "VALUES (?, 'AI', 'remote-first', 'mid-200-1000')",
        (name,),
    )
    conn.commit()
    return conn.execute("SELECT id FROM companies WHERE name = ?", (name,)).fetchone()["id"]


def _populate_profile(conn):
    add_work_experience(conn, "Anthropic", "Senior Data Engineer", "2022-01",
                        technologies=["Python", "SQL", "Spark", "dbt"])
    add_work_experience(conn, "DataCo", "Data Analyst", "2019-06", end_date="2021-12",
                        technologies=["Python", "SQL", "Tableau"])
    add_project(conn, "Beacon", technologies=["Python", "SQLite"])
    for s in ("Python", "SQL", "Spark", "dbt", "LLM", "MLOps"):
        add_skill(conn, s, category="language")


def _make_job(conn, *, title="Senior Data Engineer", company_id=None, description="python sql spark dbt llm mlops airflow snowflake"):
    return upsert_job(
        conn,
        company_id=company_id,
        title=title,
        url=f"https://example.com/{title.lower().replace(' ', '-')}",
        location="Remote",
        description_text=description,
        date_posted="2026-05-01",
        relevance_score=8.0,
    )["id"]


def _fetch_job(conn, job_id):
    return conn.execute(
        """SELECT j.*, c.name AS company_name
           FROM job_listings j JOIN companies c ON j.company_id = c.id
           WHERE j.id = ?""",
        (job_id,),
    ).fetchone()


class TestComputeJobFit:
    def test_skill_overlap_drives_score(self, db):
        conn, _ = db
        _populate_profile(conn)
        cid = _insert_company(conn)
        jid = _make_job(conn, company_id=cid)

        fit = compute_job_fit(conn, _fetch_job(conn, jid))

        assert 0.0 <= fit.fit_score <= 10.0
        assert any("skill_overlap" in r for r in fit.reasons)
        # User has python/sql/spark/dbt/llm/mlops as skills — should be a strong fit.
        assert fit.fit_score >= 5.0
        assert "airflow" in fit.missing or "snowflake" in fit.missing

    def test_empty_profile_returns_low_skill_signal(self, db):
        conn, _ = db
        cid = _insert_company(conn)
        jid = _make_job(conn, company_id=cid)

        fit = compute_job_fit(conn, _fetch_job(conn, jid))

        assert fit.sub_scores["title_trajectory"] == 5.0  # empty_profile path
        assert fit.sub_scores["skill_overlap"] <= 5.0

    def test_outcome_lift_changes_score(self, db):
        conn, _ = db
        _populate_profile(conn)
        cid = _insert_company(conn)
        jid = _make_job(conn, company_id=cid)
        row = _fetch_job(conn, jid)

        # Need an application + a positive outcome to engage the lift path.
        app_id = add_application(conn, job_id=jid, status="applied")
        record_outcome(conn, app_id, "phone_screen", response_days=3)

        baseline = compute_job_fit(conn, row, with_outcomes=False)
        weighted = compute_job_fit(conn, row, with_outcomes=True)

        assert weighted.fit_score != baseline.fit_score
        assert any("outcome_lift" in r for r in weighted.reasons)

    def test_extraction_cache_hit_does_not_reextract(self, db):
        conn, _ = db
        _populate_profile(conn)
        cid = _insert_company(conn)
        jid = _make_job(conn, company_id=cid)
        row = _fetch_job(conn, jid)

        spy = MagicMock(return_value={
            "required_skills": ["python", "sql"],
            "preferred_skills": [],
            "keywords": ["python", "sql"],
            "seniority": "senior",
        })

        # First call extracts + caches.
        get_or_extract_requirements(conn, row, profile_skills={"Python", "SQL"}, extract_fn=spy)
        # Second call should hit the cache and not call the extractor.
        get_or_extract_requirements(conn, row, profile_skills={"Python", "SQL"}, extract_fn=spy)

        assert spy.call_count == 1
        cached = conn.execute(
            "SELECT keywords FROM job_requirements WHERE job_id = ?", (jid,)
        ).fetchone()
        assert "python" in json.loads(cached["keywords"])

    def test_relevance_floor_preserved(self, db):
        conn, _ = db
        _populate_profile(conn)
        cid = _insert_company(conn)
        jid = _make_job(conn, company_id=cid, description="generic role")
        row = _fetch_job(conn, jid)

        fit = compute_job_fit(conn, row)
        # relevance_score 8.0 * 0.10 = 0.8 floor contribution
        assert fit.sub_scores["relevance_floor"] == 8.0


class TestHeuristicExtraction:
    def test_pulls_known_tech_keywords(self):
        out = job_fit._heuristic_extract(
            "We need someone with python, sql, dbt, spark experience.",
            profile_skills=set(),
        )
        assert "python" in out["keywords"]
        assert "sql" in out["keywords"]
        assert "dbt" in out["keywords"]

    def test_includes_profile_skills_found_in_text(self):
        out = job_fit._heuristic_extract(
            "Looking for a developer fluent in Rust and SQL.",
            profile_skills={"Rust"},
        )
        assert "rust" in out["keywords"]

    def test_empty_description(self):
        out = job_fit._heuristic_extract("", profile_skills={"Python"})
        assert out["keywords"] == []
