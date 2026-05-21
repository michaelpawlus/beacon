"""Tests for the `beacon match-jobs` CLI command."""

import json
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from beacon.cli import app
from beacon.db.connection import get_connection, init_db
from beacon.db.jobs import upsert_job
from beacon.db.profile import add_skill, add_work_experience

runner = CliRunner()


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_beacon.db"
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn, db_path
    conn.close()


def _insert_company(conn, name="Anthropic"):
    conn.execute(
        "INSERT INTO companies (name, industry) VALUES (?, 'AI')",
        (name,),
    )
    conn.commit()
    return conn.execute("SELECT id FROM companies WHERE name = ?", (name,)).fetchone()["id"]


def _seed_jobs(conn):
    cid = _insert_company(conn, "Anthropic")
    upsert_job(
        conn, company_id=cid, title="Senior Data Engineer",
        url="https://anthropic.com/jobs/1", location="Remote",
        description_text="python sql spark dbt mlops",
        relevance_score=9.0,
    )
    upsert_job(
        conn, company_id=cid, title="Marketing Manager",
        url="https://anthropic.com/jobs/2", location="SF",
        description_text="campaigns brand",
        relevance_score=2.0,
    )


def _seed_profile(conn):
    add_work_experience(conn, "DataCo", "Senior Data Engineer", "2022-01",
                        technologies=["Python", "SQL", "Spark", "dbt"])
    for s in ("Python", "SQL", "Spark", "dbt", "MLOps"):
        add_skill(conn, s, category="language")


class TestMatchJobsCli:
    def test_json_output_schema(self, db):
        conn, db_path = db
        _seed_profile(conn)
        _seed_jobs(conn)

        with patch("beacon.cli.get_connection", return_value=get_connection(db_path)):
            result = runner.invoke(app, ["match-jobs", "--json"])

        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert "generated_at" in payload
        assert payload["profile_snapshot"]["skills"] == 5
        assert isinstance(payload["matches"], list)
        # Top match should be the Senior Data Engineer (skills match), not Marketing.
        assert payload["matches"][0]["title"] == "Senior Data Engineer"
        m = payload["matches"][0]
        for key in ("job_id", "company", "title", "fit_score", "relevance_score", "reasons", "missing"):
            assert key in m

    def test_empty_profile_returns_warning(self, db):
        conn, db_path = db
        _seed_jobs(conn)

        with patch("beacon.cli.get_connection", return_value=get_connection(db_path)):
            result = runner.invoke(app, ["match-jobs", "--json"])

        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["warning"].startswith("profile is empty")
        # We still return matches (the warning is advisory, not blocking).
        assert "matches" in payload

    def test_min_fit_filters(self, db):
        conn, db_path = db
        _seed_profile(conn)
        _seed_jobs(conn)

        with patch("beacon.cli.get_connection", return_value=get_connection(db_path)):
            result = runner.invoke(app, ["match-jobs", "--json", "--min-fit", "9.5"])

        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        for m in payload["matches"]:
            assert m["fit_score"] >= 9.5

    def test_status_all_includes_closed(self, db):
        conn, db_path = db
        _seed_profile(conn)
        _seed_jobs(conn)
        conn.execute("UPDATE job_listings SET status = 'closed' WHERE title = 'Senior Data Engineer'")
        conn.commit()

        with patch("beacon.cli.get_connection", side_effect=lambda: get_connection(db_path)):
            active_only = runner.invoke(app, ["match-jobs", "--json"])
            all_status = runner.invoke(app, ["match-jobs", "--json", "--status", "all"])

        active_titles = [m["title"] for m in json.loads(active_only.stdout)["matches"]]
        all_titles = [m["title"] for m in json.loads(all_status.stdout)["matches"]]
        assert "Senior Data Engineer" not in active_titles
        assert "Senior Data Engineer" in all_titles
