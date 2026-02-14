"""Tests for profile browsing CLI commands."""

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from beacon.cli import app
from beacon.db.connection import get_connection, init_db
from beacon.db.profile import (
    add_education,
    add_project,
    add_publication,
    add_skill,
    add_work_experience,
)

runner = CliRunner()


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_beacon.db"
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn, db_path
    conn.close()


class TestProfileShow:
    @patch("beacon.cli.get_connection")
    def test_show_empty_profile(self, mock_conn, db):
        conn, _ = db
        mock_conn.return_value = conn
        result = runner.invoke(app, ["profile", "show"])
        assert result.exit_code == 0
        assert "Work Experiences: 0" in result.output

    @patch("beacon.cli.get_connection")
    def test_show_populated_profile(self, mock_conn, db):
        conn, _ = db
        add_work_experience(conn, "Acme", "Engineer", "2022-01")
        add_skill(conn, "Python", category="language")
        mock_conn.return_value = conn
        result = runner.invoke(app, ["profile", "show"])
        assert result.exit_code == 0
        assert "Work Experiences: 1" in result.output
        assert "Skills:           1" in result.output
        assert "Acme" in result.output


class TestProfileWork:
    @patch("beacon.cli.get_connection")
    def test_list_work_experiences(self, mock_conn, db):
        conn, _ = db
        add_work_experience(conn, "Acme", "Engineer", "2022-01")
        add_work_experience(conn, "Beta Corp", "Senior Engineer", "2024-01")
        mock_conn.return_value = conn
        result = runner.invoke(app, ["profile", "work"])
        assert result.exit_code == 0
        assert "Acme" in result.output
        assert "Beta Corp" in result.output

    @patch("beacon.cli.get_connection")
    def test_work_detail_view(self, mock_conn, db):
        conn, _ = db
        exp_id = add_work_experience(conn, "Acme", "Data Engineer", "2022-01",
                                      description="Built data pipelines",
                                      technologies=["Python", "Spark"])
        mock_conn.return_value = conn
        result = runner.invoke(app, ["profile", "work", str(exp_id)])
        assert result.exit_code == 0
        assert "Data Engineer" in result.output
        assert "Acme" in result.output

    @patch("beacon.cli.get_connection")
    def test_work_not_found(self, mock_conn, db):
        conn, _ = db
        mock_conn.return_value = conn
        result = runner.invoke(app, ["profile", "work", "999"])
        assert result.exit_code == 0
        assert "No work experience found" in result.output

    @patch("beacon.cli.get_connection")
    def test_work_empty_list(self, mock_conn, db):
        conn, _ = db
        mock_conn.return_value = conn
        result = runner.invoke(app, ["profile", "work"])
        assert result.exit_code == 0
        assert "No work experiences" in result.output


class TestProfileProjects:
    @patch("beacon.cli.get_connection")
    def test_list_projects(self, mock_conn, db):
        conn, _ = db
        add_project(conn, "Beacon", is_public=True)
        mock_conn.return_value = conn
        result = runner.invoke(app, ["profile", "projects"])
        assert result.exit_code == 0
        assert "Beacon" in result.output

    @patch("beacon.cli.get_connection")
    def test_project_not_found(self, mock_conn, db):
        conn, _ = db
        mock_conn.return_value = conn
        result = runner.invoke(app, ["profile", "projects", "999"])
        assert result.exit_code == 0
        assert "No project found" in result.output


class TestProfileSkills:
    @patch("beacon.cli.get_connection")
    def test_list_skills(self, mock_conn, db):
        conn, _ = db
        add_skill(conn, "Python", category="language", proficiency="expert")
        add_skill(conn, "SQL", category="language")
        mock_conn.return_value = conn
        result = runner.invoke(app, ["profile", "skills"])
        assert result.exit_code == 0
        assert "Python" in result.output
        assert "SQL" in result.output

    @patch("beacon.cli.get_connection")
    def test_skills_empty(self, mock_conn, db):
        conn, _ = db
        mock_conn.return_value = conn
        result = runner.invoke(app, ["profile", "skills"])
        assert result.exit_code == 0
        assert "No skills" in result.output


class TestProfileEducation:
    @patch("beacon.cli.get_connection")
    def test_list_education(self, mock_conn, db):
        conn, _ = db
        add_education(conn, "MIT", degree="MS", field_of_study="CS")
        mock_conn.return_value = conn
        result = runner.invoke(app, ["profile", "education"])
        assert result.exit_code == 0
        assert "MIT" in result.output


class TestProfilePublications:
    @patch("beacon.cli.get_connection")
    def test_list_publications(self, mock_conn, db):
        conn, _ = db
        add_publication(conn, "My Talk", "talk", venue="PyCon")
        mock_conn.return_value = conn
        result = runner.invoke(app, ["profile", "publications"])
        assert result.exit_code == 0
        assert "My Talk" in result.output


class TestProfileStats:
    @patch("beacon.cli.get_connection")
    def test_stats_empty_profile(self, mock_conn, db):
        conn, _ = db
        mock_conn.return_value = conn
        result = runner.invoke(app, ["profile", "stats"])
        assert result.exit_code == 0
        assert "Completeness" in result.output
        assert "0%" in result.output

    @patch("beacon.cli.get_connection")
    def test_stats_complete_profile(self, mock_conn, db):
        conn, _ = db
        add_work_experience(conn, "Acme", "Engineer", "2022-01")
        for i in range(5):
            add_skill(conn, f"Skill{i}", category="language")
        add_project(conn, "P1")
        add_project(conn, "P2")
        add_education(conn, "MIT")
        mock_conn.return_value = conn
        result = runner.invoke(app, ["profile", "stats"])
        assert result.exit_code == 0
        assert "100%" in result.output
