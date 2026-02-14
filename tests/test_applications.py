"""Tests for application tracking and supplementary materials."""

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from beacon.cli import app
from beacon.db.connection import get_connection, init_db
from beacon.db.jobs import upsert_job
from beacon.db.profile import (
    add_application,
    add_project,
    add_skill,
    add_work_experience,
    get_application_by_id,
    get_applications,
    update_application,
)
from beacon.llm.client import LLMResponse

runner = CliRunner()


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_beacon.db"
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn, db_path
    conn.close()


def _insert_company(conn, name="TestCo"):
    conn.execute(
        "INSERT INTO companies (name, remote_policy, size_bucket, description) "
        "VALUES (?, 'hybrid', 'mid-200-1000', 'Test company')",
        (name,),
    )
    conn.commit()
    return conn.execute("SELECT id FROM companies WHERE name = ?", (name,)).fetchone()["id"]


class TestApplicationCLI:
    @patch("beacon.cli.get_connection")
    def test_application_list_empty(self, mock_conn, db):
        conn, _ = db
        mock_conn.return_value = conn
        result = runner.invoke(app, ["application", "list"])
        assert result.exit_code == 0
        assert "No applications found" in result.output

    @patch("beacon.cli.get_connection")
    def test_application_list_with_data(self, mock_conn, db):
        conn, _ = db
        cid = _insert_company(conn)
        job = upsert_job(conn, cid, "Data Engineer", url="https://x.com/1")
        add_application(conn, job["id"], status="applied", applied_date="2025-01-15")
        mock_conn.return_value = conn
        result = runner.invoke(app, ["application", "list"])
        assert result.exit_code == 0
        assert "TestCo" in result.output
        assert "applied" in result.output

    @patch("beacon.cli.get_connection")
    def test_application_list_filter_by_status(self, mock_conn, db):
        conn, _ = db
        cid = _insert_company(conn)
        j1 = upsert_job(conn, cid, "Job A", url="https://x.com/a")
        j2 = upsert_job(conn, cid, "Job B", url="https://x.com/b")
        add_application(conn, j1["id"], status="applied")
        add_application(conn, j2["id"], status="interview")
        mock_conn.return_value = conn
        result = runner.invoke(app, ["application", "list", "--status", "interview"])
        assert result.exit_code == 0
        assert "Job B" in result.output

    @patch("beacon.cli.get_connection")
    def test_application_show(self, mock_conn, db):
        conn, _ = db
        cid = _insert_company(conn)
        job = upsert_job(conn, cid, "ML Engineer", url="https://x.com/1")
        app_id = add_application(conn, job["id"], status="applied",
                                  notes="Great opportunity", applied_date="2025-01-15")
        mock_conn.return_value = conn
        result = runner.invoke(app, ["application", "show", str(app_id)])
        assert result.exit_code == 0
        assert "ML Engineer" in result.output
        assert "applied" in result.output

    @patch("beacon.cli.get_connection")
    def test_application_show_not_found(self, mock_conn, db):
        conn, _ = db
        mock_conn.return_value = conn
        result = runner.invoke(app, ["application", "show", "999"])
        assert result.exit_code == 0
        assert "No application found" in result.output

    @patch("beacon.cli.get_connection")
    def test_application_update_status(self, mock_conn, db):
        conn, _ = db
        cid = _insert_company(conn)
        job = upsert_job(conn, cid, "Job", url="https://x.com/1")
        app_id = add_application(conn, job["id"], status="applied")
        mock_conn.return_value = conn
        result = runner.invoke(app, ["application", "update", str(app_id), "--status", "interview"])
        assert result.exit_code == 0
        assert "updated" in result.output

    @patch("beacon.cli.get_connection")
    def test_application_update_no_params(self, mock_conn, db):
        conn, _ = db
        mock_conn.return_value = conn
        result = runner.invoke(app, ["application", "update", "1"])
        assert result.exit_code == 0
        assert "Provide" in result.output


class TestJobApplyWithApplication:
    @patch("beacon.cli.get_connection")
    def test_job_apply_creates_application(self, mock_conn, db):
        conn, db_path = db
        cid = _insert_company(conn)
        job = upsert_job(conn, cid, "Data Engineer", url="https://x.com/1")
        mock_conn.return_value = conn
        result = runner.invoke(app, ["job", "apply", str(job["id"])])
        assert result.exit_code == 0
        assert "applied" in result.output
        assert "application #" in result.output

        # Verify application was created via a fresh connection (CLI closed the old one)
        conn2 = get_connection(db_path)
        apps = get_applications(conn2)
        assert len(apps) == 1
        assert apps[0]["job_title"] == "Data Engineer"
        conn2.close()


class TestSupplementaryMaterials:
    @patch("beacon.materials.supplementary.generate")
    @patch("beacon.materials.supplementary.extract_requirements")
    def test_generate_why_statement(self, mock_extract, mock_generate, db):
        conn, _ = db
        cid = _insert_company(conn)
        job = upsert_job(conn, cid, "Engineer", url="https://x.com/1",
                         description_text="Python role")
        add_work_experience(conn, "Co", "Eng", "2022-01")

        mock_generate.return_value = LLMResponse(
            text="I'm drawn to TestCo because of their AI-first culture.",
            model="test", input_tokens=50, output_tokens=30,
        )

        from beacon.materials.supplementary import generate_why_statement
        result = generate_why_statement(conn, job["id"])
        assert "TestCo" in result

    @patch("beacon.materials.supplementary.generate")
    @patch("beacon.materials.supplementary.extract_requirements")
    def test_generate_portfolio_summary(self, mock_extract, mock_generate, db):
        conn, _ = db
        cid = _insert_company(conn)
        job = upsert_job(conn, cid, "Engineer", url="https://x.com/1",
                         description_text="Python data role")
        add_project(conn, "Beacon", description="Job search tool",
                    technologies=["Python", "SQLite"])

        mock_extract.return_value = {
            "required_skills": ["Python"], "preferred_skills": [],
            "seniority": "senior", "keywords": ["data"],
        }
        mock_generate.return_value = LLMResponse(
            text="- **Beacon**: A Python-based job search tool...",
            model="test", input_tokens=50, output_tokens=40,
        )

        from beacon.materials.supplementary import generate_portfolio_summary
        result = generate_portfolio_summary(conn, job["id"])
        assert "Beacon" in result

    def test_why_statement_job_not_found(self, db):
        conn, _ = db
        from beacon.materials.supplementary import generate_why_statement
        with pytest.raises(ValueError, match="not found"):
            generate_why_statement(conn, 99999)

    def test_portfolio_summary_job_not_found(self, db):
        conn, _ = db
        from beacon.materials.supplementary import generate_portfolio_summary
        with pytest.raises(ValueError, match="not found"):
            generate_portfolio_summary(conn, 99999)
