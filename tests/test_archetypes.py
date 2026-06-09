"""Tests for the role archetype classifier (issue #29)."""

import json
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from beacon.cli import app
from beacon.db.connection import get_connection, init_db
from beacon.db.jobs import get_jobs, set_job_archetype, upsert_job
from beacon.research.archetypes import (
    ARCHETYPES,
    archetype_label,
    classify_job,
    framing_for,
    is_valid_archetype,
    list_archetypes,
)

runner = CliRunner()


# ---------------------------------------------------------------------------
# Classifier unit tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "title,description,expected",
    [
        ("Senior Data Engineer", "build dbt models on snowflake with airflow", "data_platform"),
        ("Data Scientist", "experimentation, a/b test, statistical modeling, regression", "ml_ds"),
        ("AI Agent Engineer", "multi-agent orchestration with langgraph and human-in-the-loop", "agentic"),
        ("LLMOps Engineer", "model serving, evals, observability, inference latency", "ai_engineer_llmops"),
        ("Forward Deployed Engineer", "client integration, onboarding, delivery, proof of concept", "solutions_fde"),
        ("Engineering Manager", "hiring, roadmap, mentor direct reports, org design", "eng_leadership"),
        ("Senior Product Manager", "roadmap discovery prioritization metrics trade-off backlog", "product_pm"),
    ],
)
def test_classify_by_title_and_keywords(title, description, expected):
    result = classify_job(title, description)
    assert result["archetype"] == expected
    assert result["label"] == archetype_label(expected)
    assert 0.0 < result["confidence"] <= 1.0
    assert result["framing"]


def test_unclassified_when_no_signal():
    result = classify_job("Office Receptionist", "answer phones and greet visitors")
    assert result["archetype"] is None
    assert result["confidence"] == 0.0
    assert result["label"] is None
    assert result["scores"] == {}


def test_empty_inputs_are_safe():
    result = classify_job("", "")
    assert result["archetype"] is None
    assert result["confidence"] == 0.0

    result_none = classify_job(None, None)
    assert result_none["archetype"] is None


def test_title_match_beats_keyword_only_confidence():
    # A title hit + keywords should be more confident than keyword-only.
    titled = classify_job("Data Engineer", "dbt airflow snowflake spark")
    keyword_only = classify_job("Generalist", "we use dbt and airflow a bit")
    assert titled["confidence"] > keyword_only["confidence"]
    # Keyword-only is capped at 0.5 because the title is the load-bearing signal.
    assert keyword_only["confidence"] <= 0.5


def test_keyword_cap_limits_keyword_stuffing():
    # Many data_platform keywords but a clear ml_ds title — title should win.
    desc = "dbt airflow snowflake spark redshift kafka etl elt data lake ingestion"
    result = classify_job("Senior Data Scientist", desc + " regression modeling")
    # data_platform has lots of keyword hits, but ml_ds has the title.
    assert result["archetype"] == "ml_ds"


def test_reasons_reference_matched_signals():
    result = classify_job("Data Engineer", "dbt and airflow pipelines")
    assert any(r.startswith("title:") for r in result["reasons"])
    assert any(r.startswith("keyword:") for r in result["reasons"])


def test_custom_archetypes_override():
    custom = (ARCHETYPES[0],)  # only "agentic"
    result = classify_job("AI Agent Engineer", "agentic orchestration", archetypes=custom)
    assert result["archetype"] == "agentic"
    result2 = classify_job("Data Engineer", "dbt airflow", archetypes=custom)
    assert result2["archetype"] is None


# ---------------------------------------------------------------------------
# Helper API
# ---------------------------------------------------------------------------


def test_taxonomy_helpers():
    taxonomy = list_archetypes()
    assert len(taxonomy) == len(ARCHETYPES)
    keys = {a["key"] for a in taxonomy}
    assert "data_platform" in keys
    assert is_valid_archetype("ml_ds")
    assert not is_valid_archetype("nonsense")
    assert archetype_label("ml_ds") == "ML / Data Science"
    assert archetype_label(None) is None
    assert archetype_label("nonsense") == "nonsense"
    assert framing_for("ml_ds")
    assert framing_for(None) is None


# ---------------------------------------------------------------------------
# DB integration
# ---------------------------------------------------------------------------


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_beacon.db"
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn, db_path
    conn.close()


def _company(conn, name="Anthropic"):
    conn.execute("INSERT INTO companies (name, industry) VALUES (?, 'AI')", (name,))
    conn.commit()
    return conn.execute("SELECT id FROM companies WHERE name = ?", (name,)).fetchone()["id"]


def test_upsert_persists_archetype(db):
    conn, _ = db
    cid = _company(conn)
    job_id = upsert_job(
        conn, company_id=cid, title="Data Engineer",
        url="https://x/1", description_text="dbt airflow snowflake",
        archetype="data_platform", archetype_confidence=0.7,
    )["id"]
    row = conn.execute(
        "SELECT archetype, archetype_confidence FROM job_listings WHERE id = ?", (job_id,)
    ).fetchone()
    assert row["archetype"] == "data_platform"
    assert row["archetype_confidence"] == 0.7


def test_get_jobs_archetype_filter(db):
    conn, _ = db
    cid = _company(conn)
    upsert_job(conn, company_id=cid, title="Data Engineer", url="https://x/1",
               archetype="data_platform", archetype_confidence=0.7)
    upsert_job(conn, company_id=cid, title="Data Scientist", url="https://x/2",
               archetype="ml_ds", archetype_confidence=0.6)

    platform = get_jobs(conn, archetype="data_platform")
    assert len(platform) == 1
    assert platform[0]["title"] == "Data Engineer"
    assert len(get_jobs(conn)) == 2


def test_set_job_archetype(db):
    conn, _ = db
    cid = _company(conn)
    job_id = upsert_job(conn, company_id=cid, title="Engineer", url="https://x/1")["id"]
    assert set_job_archetype(conn, job_id, "ml_ds", 0.5) is True
    row = conn.execute("SELECT archetype FROM job_listings WHERE id = ?", (job_id,)).fetchone()
    assert row["archetype"] == "ml_ds"
    assert set_job_archetype(conn, 9999, "ml_ds", 0.5) is False


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_archetype_list(db):
    _, db_path = db
    with patch("beacon.cli.get_connection", side_effect=lambda: get_connection(db_path)):
        result = runner.invoke(app, ["job", "archetype", "--list", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    keys = {a["key"] for a in payload["archetypes"]}
    assert "data_platform" in keys


def test_cli_archetype_backfill_and_show(db):
    conn, db_path = db
    cid = _company(conn)
    # Insert without an archetype (simulating pre-feature rows).
    j1 = upsert_job(conn, company_id=cid, title="Data Engineer", url="https://x/1",
                    description_text="dbt airflow snowflake spark")["id"]
    upsert_job(conn, company_id=cid, title="Receptionist", url="https://x/2",
               description_text="answer phones")
    conn.close()

    with patch("beacon.cli.get_connection", side_effect=lambda: get_connection(db_path)):
        backfill = runner.invoke(app, ["job", "archetype", "--backfill", "--json"])
        assert backfill.exit_code == 0
        payload = json.loads(backfill.stdout)
        assert payload["classified"] == 2
        assert payload["distribution"].get("data_platform") == 1

        show = runner.invoke(app, ["job", "archetype", str(j1), "--json"])
        assert show.exit_code == 0
        shown = json.loads(show.stdout)
        assert shown["archetype"] == "data_platform"
        assert shown["framing"]


def test_cli_archetype_set_and_validate(db):
    conn, db_path = db
    cid = _company(conn)
    j1 = upsert_job(conn, company_id=cid, title="Generalist", url="https://x/1")["id"]
    conn.close()

    with patch("beacon.cli.get_connection", side_effect=lambda: get_connection(db_path)):
        ok = runner.invoke(app, ["job", "archetype", str(j1), "--set", "ml_ds", "--json"])
        assert ok.exit_code == 0
        assert json.loads(ok.stdout)["archetype"] == "ml_ds"

        bad = runner.invoke(app, ["job", "archetype", str(j1), "--set", "nope", "--json"])
        assert bad.exit_code == 1
        assert "error" in json.loads(bad.stdout)


def test_cli_jobs_archetype_filter(db):
    conn, db_path = db
    cid = _company(conn)
    upsert_job(conn, company_id=cid, title="Data Engineer", url="https://x/1",
               archetype="data_platform", archetype_confidence=0.7, relevance_score=8.0)
    upsert_job(conn, company_id=cid, title="Data Scientist", url="https://x/2",
               archetype="ml_ds", archetype_confidence=0.6, relevance_score=7.0)
    conn.close()

    with patch("beacon.cli.get_connection", side_effect=lambda: get_connection(db_path)):
        result = runner.invoke(app, ["jobs", "--archetype", "ml_ds", "--json"])
    assert result.exit_code == 0
    rows = json.loads(result.stdout)
    assert len(rows) == 1
    assert rows[0]["title"] == "Data Scientist"
