"""Tests for Beacon agent orchestration (Phase 5, Step 6)."""

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from beacon.agents.application_prep import ApplicationPrepAgent
from beacon.agents.base import AgentResult, AgentTask, BaseAgent
from beacon.agents.job_analyst import JobAnalystAgent
from beacon.agents.orchestrator import Orchestrator
from beacon.agents.researcher import ResearchAgent
from beacon.config import BeaconConfig
from beacon.db.connection import get_connection, init_db

runner = CliRunner()


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_beacon.db"
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn, db_path
    conn.close()


def _insert_company(conn, name="TestCo", score=8.0, last_researched=None):
    cursor = conn.execute(
        "INSERT INTO companies (name, careers_platform, domain, ai_first_score, tier, last_researched_at) VALUES (?, 'greenhouse', 'testco.com', ?, 1, ?)",
        (name, score, last_researched),
    )
    conn.commit()
    return cursor.lastrowid


def _insert_job(conn, company_id, title="Data Engineer", score=8.0, status="active", description=None):
    cursor = conn.execute(
        "INSERT INTO job_listings (company_id, title, relevance_score, status, description_text) VALUES (?, ?, ?, ?, ?)",
        (company_id, title, score, status, description),
    )
    conn.commit()
    return cursor.lastrowid


def _insert_work(conn, company="TestCo", title="Engineer"):
    cursor = conn.execute(
        "INSERT INTO work_experiences (company, title, start_date) VALUES (?, ?, '2024-01')",
        (company, title),
    )
    conn.commit()
    return cursor.lastrowid


# --- ResearchAgent ---

class TestResearchAgent:
    def test_plan_stale_companies(self, db):
        conn, _ = db
        _insert_company(conn, "Stale Co", last_researched="2025-01-01")
        agent = ResearchAgent()
        tasks = agent.plan(conn, {"stale_days": 30})
        assert len(tasks) >= 1
        assert "Stale Co" in tasks[0].description

    def test_plan_never_researched(self, db):
        conn, _ = db
        _insert_company(conn, "New Co")
        agent = ResearchAgent()
        tasks = agent.plan(conn, {"stale_days": 30})
        assert len(tasks) == 1
        assert "Initial research" in tasks[0].description

    def test_plan_no_stale(self, db):
        conn, _ = db
        # Fresh company
        import datetime
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        _insert_company(conn, "Fresh Co", last_researched=today)
        agent = ResearchAgent()
        tasks = agent.plan(conn, {"stale_days": 30})
        assert len(tasks) == 0

    @patch("beacon.research.scoring.compute_composite_score", return_value=8.5)
    def test_execute(self, mock_score, db):
        conn, _ = db
        cid = _insert_company(conn, "TestCo", last_researched="2025-01-01")
        agent = ResearchAgent()
        task = AgentTask(description="test", data={"company_id": cid, "company_name": "TestCo", "action": "refresh"})
        result = agent.execute(conn, task)
        assert result["company"] == "TestCo"
        assert result["score"] == 8.5

    def test_summarize(self):
        agent = ResearchAgent()
        results = [{"company": "A", "score": 8.0}, {"company": "B", "error": "fail"}]
        summary = agent.summarize(results)
        assert "1 companies" in summary
        assert "1 errors" in summary


# --- JobAnalystAgent ---

class TestJobAnalystAgent:
    def test_plan_finds_borderline(self, db):
        conn, _ = db
        cid = _insert_company(conn)
        _insert_job(conn, cid, "Borderline Job", score=5.5)
        _insert_job(conn, cid, "High Job", score=9.0)  # should not be included
        agent = JobAnalystAgent()
        tasks = agent.plan(conn, {"borderline_low": 4.0, "borderline_high": 7.0})
        assert len(tasks) == 1
        assert "Borderline Job" in tasks[0].description

    def test_plan_no_borderline(self, db):
        conn, _ = db
        cid = _insert_company(conn)
        _insert_job(conn, cid, "High Job", score=9.0)
        agent = JobAnalystAgent()
        tasks = agent.plan(conn, {"borderline_low": 4.0, "borderline_high": 7.0})
        assert len(tasks) == 0

    @patch("beacon.research.job_scoring.compute_job_relevance")
    def test_execute_updates_score(self, mock_relevance, db):
        conn, _ = db
        cid = _insert_company(conn)
        jid = _insert_job(conn, cid, "Job", score=5.0)
        mock_relevance.return_value = {"score": 7.5, "reasons": ["better match"]}

        agent = JobAnalystAgent()
        task = AgentTask(
            description="test",
            data={"job_id": jid, "title": "Job", "company_name": "TestCo", "current_score": 5.0},
        )
        result = agent.execute(conn, task)
        assert result["changed"] is True
        assert result["new_score"] == 7.5

        # Verify DB updated
        job = conn.execute("SELECT relevance_score FROM job_listings WHERE id = ?", (jid,)).fetchone()
        assert job["relevance_score"] == 7.5

    @patch("beacon.research.job_scoring.compute_job_relevance")
    def test_execute_no_change(self, mock_relevance, db):
        conn, _ = db
        cid = _insert_company(conn)
        jid = _insert_job(conn, cid, "Job", score=5.0)
        mock_relevance.return_value = {"score": 5.0, "reasons": ["same"]}

        agent = JobAnalystAgent()
        task = AgentTask(
            description="test",
            data={"job_id": jid, "title": "Job", "company_name": "TestCo", "current_score": 5.0},
        )
        result = agent.execute(conn, task)
        assert result["changed"] is False

    def test_summarize(self):
        agent = JobAnalystAgent()
        results = [
            {"job_id": 1, "changed": True, "new_score": 8.0},
            {"job_id": 2, "changed": False, "new_score": 5.0},
            {"job_id": 3, "error": "fail"},
        ]
        summary = agent.summarize(results)
        assert "3 jobs" in summary
        assert "1 rescored" in summary
        assert "1 errors" in summary


# --- ApplicationPrepAgent ---

class TestApplicationPrepAgent:
    def test_plan_finds_unapplied(self, db):
        conn, _ = db
        cid = _insert_company(conn)
        _insert_job(conn, cid, "High Job", score=9.0)
        agent = ApplicationPrepAgent()
        tasks = agent.plan(conn, {"min_relevance": 7.0})
        assert len(tasks) == 1

    def test_plan_excludes_applied(self, db):
        conn, _ = db
        cid = _insert_company(conn)
        jid = _insert_job(conn, cid, "Applied Job", score=9.0)
        conn.execute("INSERT INTO applications (job_id, status) VALUES (?, 'applied')", (jid,))
        conn.commit()
        agent = ApplicationPrepAgent()
        tasks = agent.plan(conn, {"min_relevance": 7.0})
        assert len(tasks) == 0

    def test_execute_with_profile(self, db):
        conn, _ = db
        cid = _insert_company(conn)
        jid = _insert_job(conn, cid, "Job", score=9.0)
        _insert_work(conn)

        agent = ApplicationPrepAgent()
        task = AgentTask(
            description="test",
            data={"job_id": jid, "title": "Job", "company_name": "TestCo", "relevance_score": 9.0},
        )
        result = agent.execute(conn, task)
        assert result["status"] == "draft_created"
        assert result["application_id"] > 0

    def test_execute_without_profile(self, db):
        conn, _ = db
        cid = _insert_company(conn)
        jid = _insert_job(conn, cid, "Job", score=9.0)

        agent = ApplicationPrepAgent()
        task = AgentTask(
            description="test",
            data={"job_id": jid, "title": "Job", "company_name": "TestCo", "relevance_score": 9.0},
        )
        result = agent.execute(conn, task)
        assert result["status"] == "skipped"

    def test_summarize(self):
        agent = ApplicationPrepAgent()
        results = [
            {"status": "draft_created"},
            {"status": "skipped"},
            {"error": "fail"},
        ]
        summary = agent.summarize(results)
        assert "1 drafts" in summary


# --- Orchestrator ---

class TestOrchestrator:
    def test_dry_run(self, db):
        conn, _ = db
        _insert_company(conn, "TestCo", last_researched="2025-01-01")
        config = BeaconConfig()
        orchestrator = Orchestrator()
        results = orchestrator.run(conn, config, dry_run=True)
        assert "researcher" in results
        assert "[dry-run]" in results["researcher"]

    @patch("beacon.research.scoring.compute_composite_score", return_value=8.0)
    def test_full_run(self, mock_score, db):
        conn, _ = db
        _insert_company(conn, "TestCo", last_researched="2025-01-01")
        config = BeaconConfig()
        orchestrator = Orchestrator()
        results = orchestrator.run(conn, config)
        assert "researcher" in results
        assert "job_analyst" in results
        assert "application_prep" in results

    def test_error_isolation(self, db):
        conn, _ = db

        class FailingAgent(BaseAgent):
            name = "failing"

            def plan(self, conn, context):
                raise RuntimeError("planned failure")

            def execute(self, conn, task):
                return {}

        config = BeaconConfig()
        orchestrator = Orchestrator(agents=[FailingAgent(), ResearchAgent()])
        results = orchestrator.run(conn, config)
        assert "Error" in results["failing"]
        assert "researcher" in results

    def test_logs_to_automation_log(self, db):
        conn, _ = db
        config = BeaconConfig()
        orchestrator = Orchestrator()
        orchestrator.run(conn, config)

        log = conn.execute("SELECT * FROM automation_log WHERE run_type = 'full'").fetchone()
        assert log is not None
        assert log["duration_seconds"] is not None


# --- CLI Commands ---

class TestAgentsCLI:
    @patch("beacon.research.scoring.compute_composite_score", return_value=8.0)
    @patch("beacon.config.load_config")
    def test_agents_command(self, mock_config, mock_score, db):
        from beacon.cli import app
        conn, _ = db
        mock_config.return_value = BeaconConfig()
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["automation", "agents"])
            assert result.exit_code == 0
            assert "complete" in result.output.lower()

    @patch("beacon.config.load_config")
    def test_agents_dry_run(self, mock_config, db):
        from beacon.cli import app
        conn, _ = db
        mock_config.return_value = BeaconConfig()
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["automation", "agents", "--dry-run"])
            assert result.exit_code == 0
            assert "dry run" in result.output.lower()

    def test_agents_status(self, db):
        from beacon.cli import app
        conn, _ = db
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["automation", "agents-status"])
            assert result.exit_code == 0
