"""Tests for the interactive profile interview tool."""

from unittest.mock import MagicMock, call, patch

import pytest

from beacon.db.connection import get_connection, init_db
from beacon.interview import (
    _validate_date,
    interview_education,
    interview_project,
    interview_publication,
    interview_skill,
    interview_work_experience,
    run_full_interview,
)


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_beacon.db"
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn
    conn.close()


@pytest.fixture
def console():
    return MagicMock()


class TestDateValidation:
    def test_valid_yyyy_mm(self):
        assert _validate_date("2022-01") is True

    def test_valid_yyyy_mm_dd(self):
        assert _validate_date("2022-01-15") is True

    def test_invalid_format(self):
        assert _validate_date("Jan 2022") is False
        assert _validate_date("2022") is False
        assert _validate_date("") is False


class TestInterviewWorkExperience:
    @patch("beacon.interview.Confirm.ask")
    @patch("beacon.interview.Prompt.ask")
    def test_adds_work_experience(self, mock_prompt, mock_confirm, console, db):
        mock_prompt.side_effect = ["Acme Corp", "Data Engineer", "2022-01", "2024-01", "Built pipelines", "", "", ""]
        mock_confirm.return_value = False  # not current role

        result = interview_work_experience(console, db)
        assert result is not None
        row = db.execute("SELECT * FROM work_experiences WHERE id = ?", (result,)).fetchone()
        assert row["company"] == "Acme Corp"
        assert row["title"] == "Data Engineer"

    @patch("beacon.interview.Prompt.ask")
    def test_returns_none_on_empty_company(self, mock_prompt, console, db):
        mock_prompt.return_value = ""
        result = interview_work_experience(console, db)
        assert result is None

    @patch("beacon.interview._collect_list_input")
    @patch("beacon.interview.Confirm.ask")
    @patch("beacon.interview.Prompt.ask")
    def test_current_role_no_end_date(self, mock_prompt, mock_confirm, mock_list, console, db):
        mock_prompt.side_effect = ["Acme", "Engineer", "2023-01", ""]
        mock_confirm.return_value = True  # is current role
        mock_list.return_value = []

        result = interview_work_experience(console, db)
        assert result is not None
        row = db.execute("SELECT * FROM work_experiences WHERE id = ?", (result,)).fetchone()
        assert row["end_date"] is None


class TestInterviewProject:
    @patch("beacon.interview.get_work_experiences")
    @patch("beacon.interview.Confirm.ask")
    @patch("beacon.interview._collect_list_input")
    @patch("beacon.interview.Prompt.ask")
    def test_adds_project(self, mock_prompt, mock_list, mock_confirm, mock_get_exps, console, db):
        mock_prompt.side_effect = ["Beacon", "Job search tool", ""]
        mock_list.return_value = ["Python", "SQLite"]
        mock_confirm.side_effect = [False, False]  # not public, no link
        mock_get_exps.return_value = []

        result = interview_project(console, db)
        assert result is not None
        row = db.execute("SELECT * FROM projects WHERE id = ?", (result,)).fetchone()
        assert row["name"] == "Beacon"


class TestInterviewSkill:
    @patch("beacon.interview._collect_list_input")
    @patch("beacon.interview.Prompt.ask")
    def test_adds_skill(self, mock_prompt, mock_list, console, db):
        mock_prompt.side_effect = ["Python", "language", "expert", "10"]
        mock_list.return_value = ["Built data pipelines"]

        result = interview_skill(console, db)
        assert result is not None
        row = db.execute("SELECT * FROM skills WHERE id = ?", (result,)).fetchone()
        assert row["name"] == "Python"
        assert row["proficiency"] == "expert"

    @patch("beacon.interview.Prompt.ask")
    def test_returns_none_on_empty_name(self, mock_prompt, console, db):
        mock_prompt.return_value = ""
        result = interview_skill(console, db)
        assert result is None


class TestInterviewEducation:
    @patch("beacon.interview._collect_list_input")
    @patch("beacon.interview.Prompt.ask")
    def test_adds_education(self, mock_prompt, mock_list, console, db):
        mock_prompt.side_effect = ["MIT", "MS", "Computer Science", "2018-09", "2020-06", "3.9"]
        mock_list.return_value = ["Machine Learning", "Databases"]

        result = interview_education(console, db)
        assert result is not None
        row = db.execute("SELECT * FROM education WHERE id = ?", (result,)).fetchone()
        assert row["institution"] == "MIT"
        assert row["degree"] == "MS"


class TestInterviewPublication:
    @patch("beacon.interview.Prompt.ask")
    def test_adds_publication(self, mock_prompt, console, db):
        mock_prompt.side_effect = ["My Talk", "talk", "PyCon 2024", "https://example.com", "2024-03", "Spoke about data"]

        result = interview_publication(console, db)
        assert result is not None
        row = db.execute("SELECT * FROM publications_talks WHERE id = ?", (result,)).fetchone()
        assert row["title"] == "My Talk"
        assert row["pub_type"] == "talk"


class TestRunFullInterview:
    @patch("beacon.interview.Confirm.ask")
    @patch("beacon.interview.interview_work_experience")
    def test_single_section(self, mock_interview, mock_confirm, console, db):
        mock_interview.return_value = 1
        mock_confirm.return_value = False  # don't add another

        counts = run_full_interview(console, db, section="work")
        assert counts == {"work": 1}
        mock_interview.assert_called_once()

    @patch("beacon.interview.Confirm.ask")
    @patch("beacon.interview.interview_work_experience")
    def test_multiple_entries(self, mock_interview, mock_confirm, console, db):
        mock_interview.side_effect = [1, 2]
        mock_confirm.side_effect = [True, False]  # add another, then stop

        counts = run_full_interview(console, db, section="work")
        assert counts == {"work": 2}

    @patch("beacon.interview.Confirm.ask")
    @patch("beacon.interview.interview_publication")
    @patch("beacon.interview.interview_education")
    @patch("beacon.interview.interview_skill")
    @patch("beacon.interview.interview_project")
    @patch("beacon.interview.interview_work_experience")
    def test_full_interview_all_sections(self, mock_work, mock_proj, mock_skill, mock_edu, mock_pub, mock_confirm, console, db):
        mock_work.return_value = 1
        mock_proj.return_value = 1
        mock_skill.return_value = 1
        mock_edu.return_value = 1
        mock_pub.return_value = 1
        mock_confirm.return_value = False  # don't add another in any section

        counts = run_full_interview(console, db)
        assert len(counts) == 5
        assert all(v == 1 for v in counts.values())
