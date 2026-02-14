"""Tests for profile import/export utility."""

import json

import pytest

from beacon.db.connection import get_connection, init_db
from beacon.db.profile import (
    add_education,
    add_project,
    add_publication,
    add_skill,
    add_work_experience,
    get_education,
    get_projects,
    get_publications,
    get_skills,
    get_work_experiences,
)
from beacon.importer import (
    _validate_education,
    _validate_project,
    _validate_publication,
    _validate_skill,
    _validate_work_experience,
    export_profile_json,
    import_profile,
)


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_beacon.db"
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn
    conn.close()


SAMPLE_PROFILE = {
    "work_experiences": [
        {"company": "Acme Corp", "title": "Data Engineer", "start_date": "2022-01",
         "end_date": "2024-06", "description": "Built pipelines",
         "key_achievements": ["Reduced latency 50%"], "technologies": ["Python", "Spark"]},
    ],
    "projects": [
        {"name": "Beacon", "description": "Job search tool", "technologies": ["Python", "SQLite"],
         "outcomes": ["Found dream job"], "is_public": True},
    ],
    "skills": [
        {"name": "Python", "category": "language", "proficiency": "expert", "years_experience": 10},
        {"name": "SQL", "category": "language", "proficiency": "advanced"},
    ],
    "education": [
        {"institution": "MIT", "degree": "MS", "field_of_study": "CS",
         "relevant_coursework": ["ML", "Databases"]},
    ],
    "publications_talks": [
        {"title": "My Talk", "pub_type": "talk", "venue": "PyCon"},
    ],
}


class TestValidation:
    def test_valid_work_experience(self):
        assert _validate_work_experience({"company": "X", "title": "Y", "start_date": "2022-01"}) == []

    def test_invalid_work_experience_missing_fields(self):
        errors = _validate_work_experience({})
        assert len(errors) == 3

    def test_valid_project(self):
        assert _validate_project({"name": "X"}) == []

    def test_invalid_project(self):
        assert len(_validate_project({})) == 1

    def test_valid_skill(self):
        assert _validate_skill({"name": "Python"}) == []

    def test_invalid_skill_bad_proficiency(self):
        errors = _validate_skill({"name": "Python", "proficiency": "godlike"})
        assert len(errors) == 1

    def test_valid_education(self):
        assert _validate_education({"institution": "MIT"}) == []

    def test_valid_publication(self):
        assert _validate_publication({"title": "X", "pub_type": "talk"}) == []

    def test_invalid_publication_bad_type(self):
        errors = _validate_publication({"title": "X", "pub_type": "invalid"})
        assert len(errors) == 1


class TestImport:
    def test_import_full_profile(self, db, tmp_path):
        json_file = tmp_path / "profile.json"
        json_file.write_text(json.dumps(SAMPLE_PROFILE))

        counts = import_profile(db, json_file)
        assert counts["work_experiences"] == 1
        assert counts["projects"] == 1
        assert counts["skills"] == 2
        assert counts["education"] == 1
        assert counts["publications_talks"] == 1

        assert len(get_work_experiences(db)) == 1
        assert len(get_projects(db)) == 1
        assert len(get_skills(db)) == 2
        assert len(get_education(db)) == 1
        assert len(get_publications(db)) == 1

    def test_import_partial_profile(self, db, tmp_path):
        data = {"skills": [{"name": "Python"}, {"name": "SQL"}]}
        json_file = tmp_path / "skills.json"
        json_file.write_text(json.dumps(data))

        counts = import_profile(db, json_file)
        assert counts["skills"] == 2
        assert len(get_skills(db)) == 2

    def test_import_with_validation_errors(self, db, tmp_path):
        data = {"work_experiences": [{"company": "X"}]}  # missing title and start_date
        json_file = tmp_path / "bad.json"
        json_file.write_text(json.dumps(data))

        counts = import_profile(db, json_file)
        assert "errors" in counts
        assert len(get_work_experiences(db)) == 0

    def test_import_file_not_found(self, db, tmp_path):
        with pytest.raises(FileNotFoundError):
            import_profile(db, tmp_path / "nonexistent.json")

    def test_import_unsupported_format(self, db, tmp_path):
        csv_file = tmp_path / "profile.csv"
        csv_file.write_text("data")
        with pytest.raises(ValueError, match="Unsupported"):
            import_profile(db, csv_file)


class TestExport:
    def test_export_empty_profile(self, db):
        result = json.loads(export_profile_json(db))
        assert result["work_experiences"] == []
        assert result["skills"] == []

    def test_export_populated_profile(self, db):
        add_work_experience(db, "Acme", "Engineer", "2022-01", technologies=["Python"])
        add_project(db, "Beacon", technologies=["Python"])
        add_skill(db, "Python", category="language")
        add_education(db, "MIT", degree="MS")
        add_publication(db, "Talk", "talk")

        result = json.loads(export_profile_json(db))
        assert len(result["work_experiences"]) == 1
        assert result["work_experiences"][0]["technologies"] == ["Python"]
        assert len(result["projects"]) == 1
        assert len(result["skills"]) == 1
        assert len(result["education"]) == 1
        assert len(result["publications_talks"]) == 1


class TestRoundtrip:
    def test_import_export_roundtrip(self, db, tmp_path):
        # Import sample data
        json_file = tmp_path / "profile.json"
        json_file.write_text(json.dumps(SAMPLE_PROFILE))
        import_profile(db, json_file)

        # Export
        exported = export_profile_json(db)
        result = json.loads(exported)

        # Verify key data survives roundtrip
        assert result["work_experiences"][0]["company"] == "Acme Corp"
        assert result["work_experiences"][0]["technologies"] == ["Python", "Spark"]
        assert result["projects"][0]["name"] == "Beacon"
        assert result["projects"][0]["is_public"] is True
        assert len(result["skills"]) == 2
        assert result["education"][0]["institution"] == "MIT"
        assert result["publications_talks"][0]["pub_type"] == "talk"
