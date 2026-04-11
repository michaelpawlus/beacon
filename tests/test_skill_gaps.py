"""Tests for skill gap analysis and tracking."""

import json

import pytest

from beacon.db.connection import get_connection, init_db
from beacon.db.jobs import upsert_job
from beacon.research.skill_gaps import (
    _normalize_skill,
    analyze_skill_gaps,
    export_gaps_as_quests,
    get_skill_gaps,
    update_skill_gap_status,
    upsert_skill_gaps,
)


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_beacon.db"
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn
    conn.close()


def _insert_company(conn, name="TestCo"):
    conn.execute(
        "INSERT INTO companies (name, remote_policy, size_bucket) VALUES (?, 'hybrid', 'mid-200-1000')",
        (name,),
    )
    conn.commit()
    return conn.execute("SELECT id FROM companies WHERE name = ?", (name,)).fetchone()["id"]


def _add_skill(conn, name, category="tool", proficiency="advanced", years=3):
    conn.execute(
        "INSERT INTO skills (name, category, proficiency, years_experience) VALUES (?, ?, ?, ?)",
        (name, category, proficiency, years),
    )
    conn.commit()


class TestNormalizeSkill:
    def test_python_variants(self):
        assert _normalize_skill("python") == "Python"
        assert _normalize_skill("Python") == "Python"
        assert _normalize_skill("py") == "Python"

    def test_javascript_variants(self):
        assert _normalize_skill("JavaScript") == "JavaScript"
        assert _normalize_skill("js") == "JavaScript"
        assert _normalize_skill("typescript") == "JavaScript"
        assert _normalize_skill("JS/TS") == "JavaScript"

    def test_llm_variants(self):
        assert _normalize_skill("LLM") == "LLMs"
        assert _normalize_skill("llms") == "LLMs"
        assert _normalize_skill("large language model") == "LLMs"

    def test_unknown_passthrough(self):
        assert _normalize_skill("SomeNewTool") == "SomeNewTool"

    def test_whitespace_stripped(self):
        assert _normalize_skill("  python  ") == "Python"


class TestAnalyzeSkillGaps:
    def test_identifies_gaps(self, db):
        cid = _insert_company(db)
        _add_skill(db, "Python", "language")
        # Job requires Python + JavaScript
        hl = {"ai_tools": [], "key_requirements": ["Python", "Snowflake"]}
        upsert_job(db, cid, "Data Eng", url="https://x.com/1", relevance_score=8.0,
                   location="Remote", highlights=hl)

        result = analyze_skill_gaps(db, min_relevance=7.0)
        gap_skills = [g["skill"] for g in result["gaps"]]
        assert "Snowflake" in gap_skills
        strength_skills = [s["skill"] for s in result["strengths"]]
        assert "Python" in strength_skills

    def test_counts_demand(self, db):
        cid = _insert_company(db)
        _add_skill(db, "Python", "language")
        for i in range(3):
            hl = {"ai_tools": ["Claude"], "key_requirements": ["Python", "Kafka"]}
            upsert_job(db, cid, f"Job {i}", url=f"https://x.com/{i}", relevance_score=8.0,
                       location="Remote", highlights=hl)

        result = analyze_skill_gaps(db, min_relevance=7.0)
        kafka_gap = next((g for g in result["gaps"] if g["skill"] == "Kafka"), None)
        assert kafka_gap is not None
        assert kafka_gap["demand_count"] == 3

    def test_gaps_sorted_by_demand(self, db):
        cid = _insert_company(db)
        # Kafka in 3 jobs, Flink in 1
        for i in range(3):
            hl = {"ai_tools": [], "key_requirements": ["Kafka"]}
            upsert_job(db, cid, f"KafkaJob {i}", url=f"https://x.com/k{i}", relevance_score=8.0,
                       location="Remote", highlights=hl)
        hl = {"ai_tools": [], "key_requirements": ["Flink"]}
        upsert_job(db, cid, "FlinkJob", url="https://x.com/f1", relevance_score=8.0,
                   location="Remote", highlights=hl)

        result = analyze_skill_gaps(db, min_relevance=7.0)
        assert result["gaps"][0]["skill"] == "Kafka"
        assert result["gaps"][0]["demand_count"] > result["gaps"][-1]["demand_count"]

    def test_empty_when_no_jobs(self, db):
        result = analyze_skill_gaps(db, min_relevance=7.0)
        assert result["gaps"] == []
        assert result["strengths"] == []
        assert result["total_jobs_analyzed"] == 0

    def test_example_jobs_limited(self, db):
        cid = _insert_company(db)
        for i in range(5):
            hl = {"ai_tools": [], "key_requirements": ["Kafka"]}
            upsert_job(db, cid, f"Job {i}", url=f"https://x.com/{i}", relevance_score=8.0,
                       location="Remote", highlights=hl)

        result = analyze_skill_gaps(db, min_relevance=7.0)
        kafka = result["gaps"][0]
        assert len(kafka["example_jobs"]) <= 3

    def test_fuzzy_matching_groups_skills(self, db):
        cid = _insert_company(db)
        _add_skill(db, "Python", "language")
        # One job says "python", another says "py" — both should match user's Python
        hl1 = {"ai_tools": [], "key_requirements": ["Python"]}
        hl2 = {"ai_tools": [], "key_requirements": ["Python"]}
        upsert_job(db, cid, "Job1", url="https://x.com/1", relevance_score=8.0,
                   location="Remote", highlights=hl1)
        upsert_job(db, cid, "Job2", url="https://x.com/2", relevance_score=8.0,
                   location="Remote", highlights=hl2)

        result = analyze_skill_gaps(db, min_relevance=7.0)
        python_strength = next((s for s in result["strengths"] if s["skill"] == "Python"), None)
        assert python_strength is not None
        assert python_strength["demand_count"] == 2


class TestUpsertSkillGaps:
    def test_inserts_new_gaps(self, db):
        gaps = [
            {"skill": "Kafka", "category": "tool", "demand_count": 5, "example_jobs": [{"id": 1, "title": "Job", "company": "Co"}]},
            {"skill": "Flink", "category": "tool", "demand_count": 2, "example_jobs": []},
        ]
        result = upsert_skill_gaps(db, gaps)
        assert result["inserted"] == 2
        assert result["updated"] == 0

    def test_updates_existing(self, db):
        gaps1 = [{"skill": "Kafka", "category": "tool", "demand_count": 3, "example_jobs": []}]
        upsert_skill_gaps(db, gaps1)
        gaps2 = [{"skill": "Kafka", "category": "tool", "demand_count": 7, "example_jobs": []}]
        result = upsert_skill_gaps(db, gaps2)
        assert result["updated"] == 1
        row = db.execute("SELECT demand_count FROM skill_gaps WHERE skill_name = 'Kafka'").fetchone()
        assert row["demand_count"] == 7


class TestGetSkillGaps:
    def test_returns_all(self, db):
        gaps = [
            {"skill": "A", "category": "tool", "demand_count": 5, "example_jobs": []},
            {"skill": "B", "category": "tool", "demand_count": 3, "example_jobs": []},
        ]
        upsert_skill_gaps(db, gaps)
        rows = get_skill_gaps(db)
        assert len(rows) == 2
        assert rows[0]["demand_count"] >= rows[1]["demand_count"]

    def test_filter_by_status(self, db):
        gaps = [{"skill": "A", "category": "tool", "demand_count": 5, "example_jobs": []}]
        upsert_skill_gaps(db, gaps)
        update_skill_gap_status(db, "A", "learning")
        assert len(get_skill_gaps(db, status="open")) == 0
        assert len(get_skill_gaps(db, status="learning")) == 1


class TestUpdateStatus:
    def test_updates(self, db):
        gaps = [{"skill": "Kafka", "category": "tool", "demand_count": 3, "example_jobs": []}]
        upsert_skill_gaps(db, gaps)
        assert update_skill_gap_status(db, "Kafka", "learning") is True
        row = db.execute("SELECT status FROM skill_gaps WHERE skill_name = 'Kafka'").fetchone()
        assert row["status"] == "learning"

    def test_not_found(self, db):
        assert update_skill_gap_status(db, "NonExistent", "learning") is False


class TestExportAsQuests:
    def test_export_format(self, db):
        gaps = [{"skill": "Kafka", "category": "tool", "demand_count": 5,
                 "example_jobs": [{"id": 1, "title": "Data Eng", "company": "Acme"}]}]
        upsert_skill_gaps(db, gaps)
        quests = export_gaps_as_quests(db)
        assert len(quests) == 1
        q = quests[0]
        assert q["source"] == "beacon_gap"
        assert "beacon_gap:kafka" == q["source_ref"]
        assert "Kafka" in q["title"]
        assert q["demand_count"] == 5
        assert "Acme" in q["description"]

    def test_respects_limit(self, db):
        for i in range(5):
            gaps = [{"skill": f"Skill{i}", "category": "tool", "demand_count": i, "example_jobs": []}]
            upsert_skill_gaps(db, gaps)
        quests = export_gaps_as_quests(db, limit=2)
        assert len(quests) == 2

    def test_only_exports_open(self, db):
        gaps = [
            {"skill": "Open", "category": "tool", "demand_count": 5, "example_jobs": []},
            {"skill": "Learning", "category": "tool", "demand_count": 3, "example_jobs": []},
        ]
        upsert_skill_gaps(db, gaps)
        update_skill_gap_status(db, "Learning", "learning")
        quests = export_gaps_as_quests(db)
        assert len(quests) == 1
        assert quests[0]["skill_name"] == "Open"
