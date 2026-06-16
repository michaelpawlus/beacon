"""CLI tests for the AI-posture surface (#46):

  • `beacon companies --posture ai_forward` filters by derived posture
  • `beacon companies candidates --posture ...` filters discovery candidates
  • `beacon companies evidence` logs a story, (re)derives posture, auto-creates
  • `beacon companies peers` lists like-posture companies with open-role counts
  • promote stamps a posture on the new company
"""

import json
import sqlite3
import textwrap

import pytest
from typer.testing import CliRunner

from beacon.cli import app
from beacon.db.connection import init_db

runner = CliRunner()


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "beacon.db"
    init_db(db_path)
    monkeypatch.setattr("beacon.db.connection.DEFAULT_DB_PATH", db_path)
    return db_path


def _run(args, expect_exit=0):
    result = runner.invoke(app, args)
    assert result.exit_code == expect_exit, (
        f"exit={result.exit_code} stdout={result.stdout!r} exception={result.exception!r}"
    )
    return result


# ----- evidence command -----

def test_evidence_creates_company_and_derives_forward(temp_db):
    """Acceptance: company-wide mandate + tools, no AI product → ai_forward, reachable."""
    _run([
        "companies", "evidence", "Scotts Test Co",
        "--type", "company_policy",
        "--title", "Company-wide AI adoption push",
        "--strength", "4",
        "--leader", "Jane CTO", "--impact", "company-wide",
        "--tool", "ChatGPT Enterprise", "--adoption", "encouraged",
        "--json",
    ])
    # Re-fetch via JSON to confirm
    result = _run(["companies", "evidence", "Scotts Test Co",
                   "--type", "employee_report", "--title", "Teams use AI daily",
                   "--strength", "3", "--json"])
    payload = json.loads(result.stdout)
    assert payload["created"] is False  # already created on first call
    assert payload["ai_posture"] == "ai_forward"
    assert payload["company_id"] > 0

    # Reachable via the posture filter
    listed = json.loads(_run(["companies", "--posture", "ai_forward", "--json"]).stdout)
    assert any(c["name"] == "Scotts Test Co" for c in listed)


def test_evidence_first_call_creates(temp_db):
    result = _run([
        "companies", "evidence", "Brand New Co",
        "--title", "One AI story", "--type", "company_policy", "--json",
    ])
    payload = json.loads(result.stdout)
    assert payload["created"] is True
    # A single thin story → circle back
    assert payload["ai_posture"] == "ai_curious"
    assert payload["circle_back"] is True


def test_evidence_no_create_errors_on_unknown(temp_db):
    result = _run([
        "companies", "evidence", "Does Not Exist",
        "--title", "x", "--no-create", "--json",
    ], expect_exit=2)
    assert json.loads(result.stdout)["code"] == 2


def test_evidence_invalid_type_exits_1(temp_db):
    result = _run([
        "companies", "evidence", "Whatever",
        "--title", "x", "--type", "not_a_real_type", "--json",
    ], expect_exit=1)
    assert json.loads(result.stdout)["code"] == 1


def test_evidence_invalid_impact_exits_1(temp_db):
    result = _run([
        "companies", "evidence", "Whatever",
        "--title", "x", "--leader", "Someone", "--impact", "galaxy-wide", "--json",
    ], expect_exit=1)
    assert json.loads(result.stdout)["code"] == 1


# ----- --posture filter validation -----

def test_companies_posture_invalid_exits_1(temp_db):
    result = _run(["companies", "--posture", "ai_bogus", "--json"], expect_exit=1)
    assert json.loads(result.stdout)["code"] == 1


def test_candidates_posture_invalid_exits_1(temp_db):
    result = _run(["companies", "candidates", "--posture", "ai_bogus", "--json"], expect_exit=1)
    assert json.loads(result.stdout)["code"] == 1


# ----- candidates posture filter -----

@pytest.fixture
def curated_dir(tmp_path):
    (tmp_path / "feed.yml").write_text(textwrap.dedent("""
        companies:
          - name: Native Product Co
            domain: native.example
            signals:
              - signal_type: product_integration
                title: The product is AI
                signal_strength: 5
          - name: Adopter Enterprise
            domain: adopter.example
            signals:
              - signal_type: company_policy
                title: Company-wide AI mandate
                signal_strength: 4
              - signal_type: tool_mandate
                title: LLM suite rolled out firm-wide
                signal_strength: 4
    """))
    return tmp_path


def test_candidates_filter_by_posture(temp_db, curated_dir):
    _run(["companies", "discover", "--source", "yaml",
          "--curated-dir", str(curated_dir), "--json"])

    forward = json.loads(_run([
        "companies", "candidates", "--posture", "ai_forward", "--json",
    ]).stdout)
    assert {c["name"] for c in forward} == {"Adopter Enterprise"}
    assert all(c["ai_posture"] == "ai_forward" for c in forward)

    native = json.loads(_run([
        "companies", "candidates", "--posture", "ai_native", "--json",
    ]).stdout)
    assert {c["name"] for c in native} == {"Native Product Co"}


def test_promote_stamps_posture(temp_db, curated_dir):
    _run(["companies", "discover", "--source", "yaml",
          "--curated-dir", str(curated_dir), "--json"])
    cands = json.loads(_run(["companies", "candidates", "--json"]).stdout)
    adopter = next(c for c in cands if c["name"] == "Adopter Enterprise")

    payload = json.loads(_run([
        "companies", "promote", str(adopter["id"]), "--json",
    ]).stdout)
    assert payload["ai_posture"] == "ai_forward"

    listed = json.loads(_run(["companies", "--posture", "ai_forward", "--json"]).stdout)
    assert any(c["name"] == "Adopter Enterprise" for c in listed)


# ----- peers command -----

def test_peers_lists_same_posture_with_job_counts(temp_db):
    # Two ai_forward companies + one ai_native; one forward company has a job.
    conn = sqlite3.connect(str(temp_db))
    conn.execute("INSERT INTO companies (name, ai_posture, ai_first_score, industry) VALUES (?,?,?,?)",
                 ("Forward A", "ai_forward", 7.0, "Finance"))
    conn.execute("INSERT INTO companies (name, ai_posture, ai_first_score, industry) VALUES (?,?,?,?)",
                 ("Forward B", "ai_forward", 6.0, "Retail"))
    conn.execute("INSERT INTO companies (name, ai_posture, ai_first_score, industry) VALUES (?,?,?,?)",
                 ("Native C", "ai_native", 8.0, "AI"))
    fb_id = conn.execute("SELECT id FROM companies WHERE name='Forward B'").fetchone()[0]
    conn.execute("INSERT INTO job_listings (company_id, title, status) VALUES (?,?,'active')",
                 (fb_id, "AI Solutions Lead"))
    conn.commit()
    conn.close()

    payload = json.loads(_run(["companies", "peers", "Forward A", "--json"]).stdout)
    assert payload["target"]["ai_posture"] == "ai_forward"
    names = [p["name"] for p in payload["peers"]]
    assert names == ["Forward B"]  # same posture, excludes target + the native co
    assert payload["peers"][0]["active_jobs"] == 1


def test_peers_same_industry_filters(temp_db):
    conn = sqlite3.connect(str(temp_db))
    conn.executemany(
        "INSERT INTO companies (name, ai_posture, ai_first_score, industry) VALUES (?,?,?,?)",
        [
            ("Fin A", "ai_forward", 7.0, "Finance"),
            ("Fin B", "ai_forward", 6.0, "Finance"),
            ("Retail C", "ai_forward", 8.0, "Retail"),
        ],
    )
    conn.commit()
    conn.close()
    payload = json.loads(_run(["companies", "peers", "Fin A", "--same-industry", "--json"]).stdout)
    assert payload["same_industry"] is True
    assert [p["name"] for p in payload["peers"]] == ["Fin B"]  # Retail C excluded


def test_peers_same_industry_unknown_industry_errors(temp_db):
    """--same-industry on a target with no industry must fail, not silently
    return cross-industry peers under same_industry=true."""
    conn = sqlite3.connect(str(temp_db))
    conn.execute(
        "INSERT INTO companies (name, ai_posture, ai_first_score) VALUES ('No Industry Co','ai_forward',5.0)"
    )
    conn.execute(
        "INSERT INTO companies (name, ai_posture, ai_first_score, industry) VALUES ('Other Co','ai_forward',6.0,'Retail')"
    )
    conn.commit()
    conn.close()
    result = _run(["companies", "peers", "No Industry Co", "--same-industry", "--json"], expect_exit=1)
    assert json.loads(result.stdout)["code"] == 1


def test_peers_unscored_company_errors(temp_db):
    """A bare company with no posture yet (NULL until `beacon scores`) errors
    with a helpful nudge rather than running an `ai_posture = NULL` query."""
    conn = sqlite3.connect(str(temp_db))
    conn.execute("INSERT INTO companies (name) VALUES ('Unscored Co')")
    conn.commit()
    conn.close()
    result = _run(["companies", "peers", "Unscored Co", "--json"], expect_exit=1)
    assert json.loads(result.stdout)["code"] == 1


def test_peers_missing_company_exits_2(temp_db):
    result = _run(["companies", "peers", "Nonexistent", "--json"], expect_exit=2)
    assert json.loads(result.stdout)["code"] == 2
