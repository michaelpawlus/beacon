"""Tests for the interview brief generator."""

import json

import pytest

from beacon.db.connection import get_connection, init_db
from beacon.db.jobs import upsert_job
from beacon.db.profile import add_project, add_skill, add_work_experience
from beacon.materials.interview_brief import (
    build_brief,
    detect_role_family,
    load_question_templates,
    pick_arc,
    pick_questions,
    render_brief_markdown,
)


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_beacon.db"
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def templates():
    return load_question_templates()


def _insert_company(conn, name="Anthropic"):
    conn.execute(
        "INSERT INTO companies (name, remote_policy, description, ai_first_score, tier) "
        "VALUES (?, 'remote-first', 'AI safety lab', 9.5, 1)",
        (name,),
    )
    conn.commit()
    return conn.execute("SELECT id FROM companies WHERE name = ?", (name,)).fetchone()["id"]


def _make_match_row(conn, company_id, *, title="Research Engineer", missing=None, reasons=None):
    job = upsert_job(conn, company_id, title, url="https://x/job/1",
                     description_text="kafka kubeflow python")
    return {
        "job_id": job["id"],
        "company": "Anthropic",
        "title": title,
        "location": "Remote",
        "fit_score": 7.44,
        "reasons": reasons or ["python overlap", "remote-first match"],
        "missing": missing if missing is not None else ["kafka", "kubeflow"],
        "sub_scores": {"skill_overlap": 6.2, "domain_overlap": 8.0},
        "url": "https://x/job/1",
        "status": "active",
    }


class TestRoleFamily:
    @pytest.mark.parametrize("title,expected", [
        ("Senior Software Engineer", "engineer"),
        ("Research Scientist, Interpretability", "scientist"),
        ("Data Analyst", "analyst"),
        ("Engineering Manager", "manager"),
        ("Principal Architect", "architect"),
        ("Forward Deployed Wizard", "default"),
        (None, "default"),
    ])
    def test_detect(self, title, expected):
        assert detect_role_family(title) == expected

    def test_pick_questions_fallback(self, templates):
        qs = pick_questions("Some Made Up Title", templates)
        assert qs
        assert qs == templates["default"]

    def test_pick_questions_family(self, templates):
        qs = pick_questions("Senior Engineer", templates)
        assert qs == templates["engineer"]


class TestPickArc:
    def test_match(self):
        arcs = [{"id": "kafka-cdc", "target_skill": "Kafka"}, {"id": "rust-basics", "target_skill": "rust"}]
        assert pick_arc(arcs, ["kafka", "kubeflow"]) == arcs[0]

    def test_no_match(self):
        arcs = [{"id": "rust-basics", "target_skill": "rust"}]
        assert pick_arc(arcs, ["kafka"]) is None

    def test_empty_inputs(self):
        assert pick_arc(None, ["kafka"]) is None
        assert pick_arc([{"id": "x", "target_skill": "kafka"}], []) is None


class TestBuildBrief:
    def test_happy_path(self, db, templates):
        cid = _insert_company(db)
        db.execute(
            "INSERT INTO leadership_signals (company_id, leader_name, leader_title, signal_type, content, impact_level) "
            "VALUES (?, 'Dario Amodei', 'CEO', 'quote', 'AI safety is the priority', 'company-wide')",
            (cid,),
        )
        db.execute(
            "INSERT INTO ai_signals (company_id, signal_type, title, signal_strength) "
            "VALUES (?, 'engineering_blog', 'Constitutional AI', 5)",
            (cid,),
        )
        db.execute(
            "INSERT INTO tools_adopted (company_id, tool_name, adoption_level) "
            "VALUES (?, 'Claude Code', 'required')",
            (cid,),
        )
        db.commit()
        add_work_experience(db, "DataCo", "Senior Engineer", "2022-01",
                            key_achievements=["Shipped Kafka pipeline"],
                            technologies=["python", "kafka"])
        add_project(db, "GhostGPT", description="LLM agent", technologies=["python"])
        add_skill(db, "python")

        match = _make_match_row(db, cid)
        gaps = [{"skill_name": "Kafka", "status": "open", "priority": 5, "demand_count": 12}]
        arc = {"id": "kafka-cdc", "target_skill": "kafka", "time_estimate": "4h",
               "why": "build a CDC pipeline"}

        brief = build_brief(db, match, gaps=gaps, arc_suggestion=arc, question_templates=templates)

        assert brief["company"] == "Anthropic"
        assert brief["fit_score"] == 7.44
        assert brief["gap_analysis"][0]["skill"] == "kafka"
        assert brief["gap_analysis"][0]["status"] == "open"
        # Talking points should pick up the kafka-laden work experience first
        assert brief["talking_points"]
        assert brief["talking_points"][0]["title"] == "Senior Engineer"
        assert "kafka" in brief["talking_points"][0]["overlap"]
        # Prep questions = engineer family (engineer in title) + dynamic question from leadership signal
        engineer_qs = templates["engineer"]
        assert brief["prep_questions"][:len(engineer_qs)] == engineer_qs
        # At least one dynamic question referencing Dario
        assert any("Dario Amodei" in q for q in brief["prep_questions"])
        # And the strong-signal AI culture question
        assert any("Constitutional AI" in q for q in brief["prep_questions"])
        assert brief["arc"] == arc

    def test_empty_profile(self, db, templates):
        cid = _insert_company(db)
        match = _make_match_row(db, cid)
        brief = build_brief(db, match, gaps=[], arc_suggestion=None, question_templates=templates)
        assert brief["gap_analysis"][0]["status"] is None
        assert brief["talking_points"] == []
        assert brief["arc"] is None
        assert brief["prep_questions"]  # always has the base templated list

    def test_no_gaps_no_arc(self, db, templates):
        cid = _insert_company(db)
        add_work_experience(db, "DataCo", "Senior Engineer", "2022-01",
                            technologies=["python"])
        match = _make_match_row(db, cid, missing=[])
        brief = build_brief(db, match, gaps=[], arc_suggestion=None, question_templates=templates)
        assert brief["gap_analysis"] == []
        assert brief["arc"] is None

    def test_unknown_job_id(self, db, templates):
        match = _make_match_row(db, _insert_company(db))
        match["job_id"] = 999999  # nonexistent
        brief = build_brief(db, match, gaps=[], question_templates=templates)
        # Company context lookup fails but the brief still composes
        assert brief["company_context"]["company"] is None
        assert brief["prep_questions"]


class TestRenderMarkdown:
    def test_all_sections_present(self, db, templates):
        cid = _insert_company(db)
        match = _make_match_row(db, cid)
        brief = build_brief(db, match, gaps=[], question_templates=templates)
        body = render_brief_markdown(brief)
        for header in [
            "## Snapshot",
            "## Why this matches",
            "## Company posture",
            "## Gap analysis",
            "## Suggested next move",
            "## Talking points",
            "## Prep questions to ask",
            "## Application checklist",
        ]:
            assert header in body
        # Top-line heading + listing URL
        assert "Interview Brief — Anthropic" in body
        assert "https://x/job/1" in body
        # Missing skills surfaced in gap analysis
        assert "kafka" in body
        # Checklist items use empty checkboxes
        assert "- [ ] Tailor resume" in body

    def test_handles_missing_arc(self, db, templates):
        cid = _insert_company(db)
        match = _make_match_row(db, cid)
        brief = build_brief(db, match, gaps=[], arc_suggestion=None, question_templates=templates)
        body = render_brief_markdown(brief)
        assert "stack-quest arcs suggest" in body

    def test_serializable(self, db, templates):
        """JSON envelope from `materials interview-brief --json` must be serializable."""
        cid = _insert_company(db)
        match = _make_match_row(db, cid)
        brief = build_brief(db, match, gaps=[], question_templates=templates)
        # The brief itself is what we summarize in JSON output; ensure round-trip works.
        json.dumps({"job_id": brief["job_id"], "missing_skills": brief["missing"],
                    "fit_score": brief["fit_score"]})
