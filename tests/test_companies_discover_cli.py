"""End-to-end CLI tests for `beacon companies discover/candidates/promote/reject`.

Covers the spec acceptance criteria:
  • discover --source yaml writes >=1 row with status='pending'
  • second run inserts 0 (dedupe)
  • --dry-run writes 0
  • missing CRUNCHBASE_API_KEY exits 1 with error JSON
  • candidates --status pending lists them
  • promote → company row appears; signals copied into ai_signals
  • reject prevents re-surfacing
  • promoted company shows up in `beacon companies --json`
"""

import json
import textwrap
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from beacon.cli import app
from beacon.db.connection import init_db

runner = CliRunner()


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Point Beacon at a tmp SQLite DB with a single 'Anthropic' company.

    Anthropic is used to exercise the dedupe path against the YAML feed below.
    """
    db_path = tmp_path / "beacon.db"
    init_db(db_path)
    monkeypatch.setattr("beacon.db.connection.DEFAULT_DB_PATH", db_path)

    import sqlite3

    conn = sqlite3.connect(str(db_path))
    conn.execute("INSERT INTO companies (name, domain) VALUES (?, ?)", ("Anthropic", "anthropic.com"))
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def curated_dir(tmp_path):
    """Tmp YAML feed with 2 fresh + 1 already-in-DB candidate."""
    (tmp_path / "test.yml").write_text(textwrap.dedent("""
        companies:
          - name: Fresh AI Co
            domain: fresh-ai.example
            careers_url: https://fresh-ai.example/jobs
            industry: Developer Tools
            signals:
              - signal_type: engineering_blog
                title: How we build AI-native tools
                signal_strength: 4
          - name: Another Fresh One
            domain: another.example
          - name: Anthropic
            domain: anthropic.com
    """))
    return tmp_path


def _run(args, expect_exit=0):
    result = runner.invoke(app, args)
    assert result.exit_code == expect_exit, (
        f"exit={result.exit_code} stdout={result.stdout!r} exception={result.exception!r}"
    )
    return result


# ----- discover -----

def test_discover_yaml_writes_rows(temp_db, curated_dir):
    result = _run([
        "companies", "discover",
        "--source", "yaml",
        "--curated-dir", str(curated_dir),
        "--json",
    ])
    payload = json.loads(result.stdout)
    assert payload["source"] == "yaml"
    assert payload["fetched"] == 3
    assert payload["inserted_count"] == 2  # 3 fetched - 1 dupe of seeded "Anthropic"
    assert payload["skipped_existing_count"] == 1
    names = {row["name"] for row in payload["inserted"]}
    assert names == {"Fresh AI Co", "Another Fresh One"}


def test_discover_yaml_is_idempotent(temp_db, curated_dir):
    _run(["companies", "discover", "--source", "yaml", "--curated-dir", str(curated_dir), "--json"])
    result = _run(["companies", "discover", "--source", "yaml", "--curated-dir", str(curated_dir), "--json"])
    payload = json.loads(result.stdout)
    assert payload["inserted_count"] == 0
    assert payload["skipped_duplicate_count"] == 2


def test_discover_dry_run_leaves_db_unchanged(temp_db, curated_dir):
    result = _run([
        "companies", "discover",
        "--source", "yaml",
        "--curated-dir", str(curated_dir),
        "--dry-run",
        "--json",
    ])
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is True
    assert payload["inserted_count"] == 2  # 2 *would* be inserted

    # But DB should still be empty.
    import sqlite3

    conn = sqlite3.connect(str(temp_db))
    count = conn.execute("SELECT COUNT(*) FROM discovery_candidates").fetchone()[0]
    conn.close()
    assert count == 0


def test_discover_unknown_source_returns_error_json(temp_db):
    result = _run(["companies", "discover", "--source", "made-up", "--json"], expect_exit=1)
    payload = json.loads(result.stdout)
    assert payload["code"] == 1
    assert "made-up" in payload["error"]


def test_discover_crunchbase_without_key_exits_1(temp_db, monkeypatch):
    monkeypatch.delenv("CRUNCHBASE_API_KEY", raising=False)
    result = _run(["companies", "discover", "--source", "crunchbase", "--json"], expect_exit=1)
    payload = json.loads(result.stdout)
    assert payload["code"] == 1
    assert payload["error"] == "CRUNCHBASE_API_KEY unset"


def test_discover_crunchbase_with_mocked_api(temp_db, monkeypatch):
    """Spec: `--source crunchbase --limit 5 --json` returns candidates, skipping dupes."""
    from unittest.mock import MagicMock

    monkeypatch.setenv("CRUNCHBASE_API_KEY", "test-key")
    sample = {
        "entities": [
            {
                "uuid": f"uuid-{i}",
                "properties": {
                    "name": f"Crunchbase Co {i}",
                    "website": {"value": f"https://cbco{i}.example"},
                    "location_identifiers": [{"value": "SF"}],
                    "categories": [{"value": "AI"}],
                    "founded_on": "2022-01-01",
                    "last_funding_at": "2026-02-01",
                    "short_description": "AI thing",
                },
            }
            for i in range(5)
        ]
    }
    mock_resp = MagicMock()
    mock_resp.json.return_value = sample
    mock_resp.raise_for_status = MagicMock()

    with patch("beacon.sources.crunchbase.httpx.post", return_value=mock_resp):
        result = _run([
            "companies", "discover",
            "--source", "crunchbase",
            "--limit", "5",
            "--json",
        ])
    payload = json.loads(result.stdout)
    assert payload["inserted_count"] == 5
    assert payload["source"] == "crunchbase"


# ----- candidates listing -----

def test_candidates_lists_pending_sorted_by_score(temp_db, curated_dir):
    _run(["companies", "discover", "--source", "yaml", "--curated-dir", str(curated_dir), "--json"])

    result = _run(["companies", "candidates", "--json"])
    payload = json.loads(result.stdout)
    assert len(payload) == 2
    # Sorted DESC by discovery_score — Fresh AI Co has more fields + a signal
    assert payload[0]["name"] == "Fresh AI Co"
    assert payload[0]["discovery_score"] >= payload[1]["discovery_score"]


def test_candidates_filter_by_source(temp_db, curated_dir):
    _run(["companies", "discover", "--source", "yaml", "--curated-dir", str(curated_dir), "--json"])
    result = _run(["companies", "candidates", "--source", "crunchbase", "--json"])
    assert json.loads(result.stdout) == []


# ----- sources -----

def test_sources_lists_registered_adapters(temp_db, curated_dir):
    _run(["companies", "discover", "--source", "yaml", "--curated-dir", str(curated_dir), "--json"])
    result = _run(["companies", "sources", "--json"])
    payload = json.loads(result.stdout)
    names = {r["name"] for r in payload}
    assert names == {"yaml", "crunchbase"}
    yaml_row = next(r for r in payload if r["name"] == "yaml")
    assert yaml_row["pending_candidates"] == 2
    assert yaml_row["last_run"] is not None


# ----- promote -----

def test_promote_creates_company_with_signals(temp_db, curated_dir):
    _run(["companies", "discover", "--source", "yaml", "--curated-dir", str(curated_dir), "--json"])
    candidates = json.loads(_run(["companies", "candidates", "--json"]).stdout)
    fresh = next(c for c in candidates if c["name"] == "Fresh AI Co")

    result = _run(["companies", "promote", str(fresh["id"]), "--tier", "3", "--json"])
    payload = json.loads(result.stdout)
    assert payload["candidate_id"] == fresh["id"]
    assert payload["company_id"] > 0
    assert payload["tier"] == 3
    assert payload["signals_added"] == 1

    # Verify candidate row flipped + company appears in `beacon companies`
    companies_result = _run(["companies", "--json"])
    companies = json.loads(companies_result.stdout)
    names = {c["name"] for c in companies}
    assert "Fresh AI Co" in names

    # Verify candidate status is now 'promoted'
    pending = json.loads(_run(["companies", "candidates", "--status", "pending", "--json"]).stdout)
    assert all(c["name"] != "Fresh AI Co" for c in pending)

    promoted = json.loads(_run(["companies", "candidates", "--status", "promoted", "--json"]).stdout)
    assert any(c["name"] == "Fresh AI Co" for c in promoted)


def test_promote_missing_candidate_exits_2(temp_db):
    result = _run(["companies", "promote", "99999", "--json"], expect_exit=2)
    payload = json.loads(result.stdout)
    assert payload["code"] == 2


# ----- reject -----

def test_reject_flips_status_and_blocks_resurface(temp_db, curated_dir):
    _run(["companies", "discover", "--source", "yaml", "--curated-dir", str(curated_dir), "--json"])
    candidates = json.loads(_run(["companies", "candidates", "--json"]).stdout)
    target = candidates[0]

    _run([
        "companies", "reject", str(target["id"]),
        "--reason", "not actually AI-native",
        "--json",
    ])

    # Re-discover — should NOT re-surface (still rejected)
    result = _run(["companies", "discover", "--source", "yaml", "--curated-dir", str(curated_dir), "--json"])
    payload = json.loads(result.stdout)
    assert payload["inserted_count"] == 0

    pending = json.loads(_run(["companies", "candidates", "--status", "pending", "--json"]).stdout)
    assert all(c["id"] != target["id"] for c in pending)

    rejected = json.loads(_run(["companies", "candidates", "--status", "rejected", "--json"]).stdout)
    assert any(c["id"] == target["id"] and c["reject_reason"] == "not actually AI-native" for c in rejected)


def test_reject_missing_candidate_exits_2(temp_db):
    result = _run(["companies", "reject", "99999", "--json"], expect_exit=2)
    payload = json.loads(result.stdout)
    assert payload["code"] == 2
