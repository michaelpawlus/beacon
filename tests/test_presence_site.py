"""Tests for beacon.presence.site — personal website data export."""

import json

import pytest

from beacon.db.connection import get_connection, init_db
from beacon.db.profile import (
    add_education,
    add_project,
    add_publication,
    add_skill,
    add_work_experience,
)
from beacon.presence.site import (
    export_site_content,
    generate_about_page,
    generate_project_page,
    generate_resume_page,
)


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_beacon.db"
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn
    conn.close()


def _populate_profile(conn):
    add_work_experience(
        conn, "Acme Corp", "Data Scientist", "2023-01",
        description="Building AI tools.",
        key_achievements=["Led AI project", "Built data warehouse"],
        technologies=["Python", "Databricks"],
        metrics=["50K users"],
    )
    add_work_experience(
        conn, "BigCo", "Analyst", "2020-01", end_date="2022-12",
        description="Analytics work.",
        technologies=["Python", "R"],
    )
    add_project(
        conn, "Beacon",
        description="AI job search platform",
        technologies=["Python", "SQLite"],
        outcomes=["38 companies scored"],
        repo_url="https://github.com/example/beacon",
        is_public=True,
    )
    add_project(
        conn, "Internal Tool",
        description="Private tool",
        technologies=["Python"],
        is_public=False,
    )
    add_skill(conn, "Python", category="language", proficiency="expert", years_experience=7)
    add_skill(conn, "SQL", category="language", proficiency="expert")
    add_skill(conn, "Databricks", category="tool", proficiency="advanced")
    add_education(conn, "State University", degree="BS", field_of_study="Computer Science",
                   start_date="2008", end_date="2012")
    add_publication(conn, "DRIVE Talk", "talk", venue="DRIVE 2017", date_published="2017")


class TestGenerateResumePage:
    def test_has_frontmatter(self, db):
        _populate_profile(db)
        result = generate_resume_page(db)
        assert result.startswith("---")
        assert 'title: "Resume"' in result

    def test_includes_work_experience(self, db):
        _populate_profile(db)
        result = generate_resume_page(db)
        assert "Acme Corp" in result
        assert "Data Scientist" in result
        assert "Present" in result

    def test_includes_achievements(self, db):
        _populate_profile(db)
        result = generate_resume_page(db)
        assert "Led AI project" in result

    def test_includes_skills(self, db):
        _populate_profile(db)
        result = generate_resume_page(db)
        assert "Python" in result
        assert "Databricks" in result

    def test_includes_education(self, db):
        _populate_profile(db)
        result = generate_resume_page(db)
        assert "State University" in result
        assert "Computer Science" in result

    def test_includes_publications(self, db):
        _populate_profile(db)
        result = generate_resume_page(db)
        assert "DRIVE Talk" in result

    def test_empty_profile(self, db):
        result = generate_resume_page(db)
        assert "---" in result
        assert "Resume" in result


class TestGenerateProjectPage:
    def test_has_frontmatter(self, db):
        _populate_profile(db)
        from beacon.db.profile import get_projects
        projects = get_projects(db)
        result = generate_project_page(projects[0])
        assert result.startswith("---")

    def test_includes_project_name(self, db):
        _populate_profile(db)
        from beacon.db.profile import get_projects
        projects = get_projects(db)
        beacon_proj = [p for p in projects if p["name"] == "Beacon"][0]
        result = generate_project_page(beacon_proj)
        assert "# Beacon" in result

    def test_includes_technologies(self, db):
        _populate_profile(db)
        from beacon.db.profile import get_projects
        projects = get_projects(db)
        beacon_proj = [p for p in projects if p["name"] == "Beacon"][0]
        result = generate_project_page(beacon_proj)
        assert "Python" in result
        assert "SQLite" in result

    def test_includes_outcomes(self, db):
        _populate_profile(db)
        from beacon.db.profile import get_projects
        projects = get_projects(db)
        beacon_proj = [p for p in projects if p["name"] == "Beacon"][0]
        result = generate_project_page(beacon_proj)
        assert "38 companies scored" in result

    def test_includes_repo_link(self, db):
        _populate_profile(db)
        from beacon.db.profile import get_projects
        projects = get_projects(db)
        beacon_proj = [p for p in projects if p["name"] == "Beacon"][0]
        result = generate_project_page(beacon_proj)
        assert "github.com" in result


class TestGenerateAboutPage:
    def test_has_frontmatter(self, db):
        _populate_profile(db)
        result = generate_about_page(db)
        assert result.startswith("---")
        assert 'title: "About"' in result

    def test_includes_current_role(self, db):
        _populate_profile(db)
        result = generate_about_page(db)
        assert "Acme Corp" in result

    def test_includes_skills(self, db):
        _populate_profile(db)
        result = generate_about_page(db)
        assert "Python" in result


class TestExportSiteContent:
    def test_creates_files(self, db, tmp_path):
        _populate_profile(db)
        output_dir = tmp_path / "site_content"
        files = export_site_content(db, str(output_dir))
        assert len(files) >= 3  # resume, about, and at least 1 project

    def test_creates_resume(self, db, tmp_path):
        _populate_profile(db)
        output_dir = tmp_path / "site_content"
        files = export_site_content(db, str(output_dir))
        resume_files = [f for f in files if f.endswith("resume.md")]
        assert len(resume_files) == 1

    def test_creates_about(self, db, tmp_path):
        _populate_profile(db)
        output_dir = tmp_path / "site_content"
        files = export_site_content(db, str(output_dir))
        about_files = [f for f in files if f.endswith("about.md")]
        assert len(about_files) == 1

    def test_creates_project_pages(self, db, tmp_path):
        _populate_profile(db)
        output_dir = tmp_path / "site_content"
        files = export_site_content(db, str(output_dir))
        project_files = [f for f in files if "projects" in f]
        assert len(project_files) == 2  # Beacon + Internal Tool

    def test_creates_output_directory(self, db, tmp_path):
        output_dir = tmp_path / "new_dir" / "content"
        files = export_site_content(db, str(output_dir))
        assert output_dir.exists()

    def test_file_content_has_frontmatter(self, db, tmp_path):
        _populate_profile(db)
        output_dir = tmp_path / "site_content"
        export_site_content(db, str(output_dir))
        resume_content = (output_dir / "resume.md").read_text()
        assert resume_content.startswith("---")
