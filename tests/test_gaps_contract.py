"""Contract tests for `beacon gaps list --json`.

These pin the JSON envelope, the per-gap field set, the filter
semantics, and the legacy-array fallback. Update with care — every
change here is a downstream-visible contract change consumed by
stack-quest and code-daily.
"""

import json
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from beacon.cli import GAPS_LIST_SCHEMA_VERSION, app
from beacon.db.connection import get_connection, init_db
from beacon.research.skill_gaps import upsert_skill_gaps

runner = CliRunner()

GAP_FIELDS = {
    "id",
    "skill_name",
    "category",
    "demand_count",
    "example_jobs",
    "status",
    "priority",
    "created_at",
    "updated_at",
}


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_beacon.db"
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn, db_path
    conn.close()


def _seed(conn, gaps):
    upsert_skill_gaps(conn, gaps)


def _invoke(conn_path, *args):
    """Run beacon CLI with patched get_connection."""
    with patch("beacon.cli.get_connection") as mock:
        mock.return_value = get_connection(conn_path)
        return runner.invoke(app, list(args))


class TestEnvelope:
    def test_envelope_shape(self, db):
        conn, path = db
        _seed(conn, [
            {"skill": "Kafka", "category": "tool", "demand_count": 5,
             "example_jobs": [{"id": 1, "title": "Data Eng", "company": "Acme"}]},
        ])
        result = _invoke(path, "gaps", "list", "--json")
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert isinstance(payload, dict)
        assert set(payload.keys()) == {"schema_version", "gaps"}
        assert payload["schema_version"] == GAPS_LIST_SCHEMA_VERSION
        assert payload["schema_version"] == 1
        assert isinstance(payload["gaps"], list)

    def test_gap_fields(self, db):
        conn, path = db
        _seed(conn, [
            {"skill": "Kafka", "category": "tool", "demand_count": 5,
             "example_jobs": [{"id": 1, "title": "Data Eng", "company": "Acme"}]},
        ])
        result = _invoke(path, "gaps", "list", "--json")
        gap = json.loads(result.stdout)["gaps"][0]
        assert set(gap.keys()) == GAP_FIELDS
        assert gap["skill_name"] == "Kafka"
        assert gap["category"] == "tool"
        assert gap["demand_count"] == 5
        assert gap["status"] == "open"
        assert gap["example_jobs"] == [
            {"id": 1, "title": "Data Eng", "company": "Acme"},
        ]

    def test_empty_gaps_list(self, db):
        _, path = db
        result = _invoke(path, "gaps", "list", "--json")
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload == {"schema_version": 1, "gaps": []}


class TestLegacyArray:
    def test_legacy_array_returns_bare_list(self, db):
        conn, path = db
        _seed(conn, [
            {"skill": "Kafka", "category": "tool", "demand_count": 5, "example_jobs": []},
            {"skill": "Flink", "category": "tool", "demand_count": 2, "example_jobs": []},
        ])
        result = _invoke(path, "gaps", "list", "--json", "--legacy-array")
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert isinstance(payload, list)
        assert len(payload) == 2
        assert set(payload[0].keys()) == GAP_FIELDS


class TestFilters:
    def test_category_filter(self, db):
        conn, path = db
        _seed(conn, [
            {"skill": "Kafka", "category": "tool", "demand_count": 5, "example_jobs": []},
            {"skill": "RAG", "category": "domain", "demand_count": 3, "example_jobs": []},
            {"skill": "Python", "category": "language", "demand_count": 8, "example_jobs": []},
        ])
        result = _invoke(path, "gaps", "list", "--json", "--category", "tool")
        skills = [g["skill_name"] for g in json.loads(result.stdout)["gaps"]]
        assert skills == ["Kafka"]

    def test_category_filter_repeatable(self, db):
        conn, path = db
        _seed(conn, [
            {"skill": "Kafka", "category": "tool", "demand_count": 5, "example_jobs": []},
            {"skill": "RAG", "category": "domain", "demand_count": 3, "example_jobs": []},
            {"skill": "Python", "category": "language", "demand_count": 8, "example_jobs": []},
        ])
        result = _invoke(
            path, "gaps", "list", "--json",
            "--category", "tool", "--category", "domain",
        )
        skills = sorted(g["skill_name"] for g in json.loads(result.stdout)["gaps"])
        assert skills == ["Kafka", "RAG"]

    def test_min_demand_filter(self, db):
        conn, path = db
        _seed(conn, [
            {"skill": "Kafka", "category": "tool", "demand_count": 5, "example_jobs": []},
            {"skill": "Flink", "category": "tool", "demand_count": 2, "example_jobs": []},
            {"skill": "Python", "category": "language", "demand_count": 8, "example_jobs": []},
        ])
        result = _invoke(path, "gaps", "list", "--json", "--min-demand", "5")
        skills = sorted(g["skill_name"] for g in json.loads(result.stdout)["gaps"])
        assert skills == ["Kafka", "Python"]

    def test_limit(self, db):
        conn, path = db
        for i in range(5):
            _seed(conn, [{"skill": f"Skill{i}", "category": "tool",
                          "demand_count": i + 1, "example_jobs": []}])
        result = _invoke(path, "gaps", "list", "--json", "--limit", "2")
        gaps = json.loads(result.stdout)["gaps"]
        assert len(gaps) == 2
        # default sort is demand DESC — top 2 by demand
        assert [g["demand_count"] for g in gaps] == [5, 4]

    def test_status_filter(self, db):
        conn, path = db
        _seed(conn, [
            {"skill": "Kafka", "category": "tool", "demand_count": 5, "example_jobs": []},
            {"skill": "Flink", "category": "tool", "demand_count": 2, "example_jobs": []},
        ])
        conn.execute("UPDATE skill_gaps SET status = 'learning' WHERE skill_name = 'Flink'")
        conn.commit()
        result = _invoke(path, "gaps", "list", "--json", "--status", "learning")
        gaps = json.loads(result.stdout)["gaps"]
        assert len(gaps) == 1
        assert gaps[0]["skill_name"] == "Flink"


class TestSort:
    def test_default_sort_is_demand(self, db):
        conn, path = db
        _seed(conn, [
            {"skill": "A", "category": "tool", "demand_count": 1, "example_jobs": []},
            {"skill": "B", "category": "tool", "demand_count": 5, "example_jobs": []},
            {"skill": "C", "category": "tool", "demand_count": 3, "example_jobs": []},
        ])
        result = _invoke(path, "gaps", "list", "--json")
        counts = [g["demand_count"] for g in json.loads(result.stdout)["gaps"]]
        assert counts == [5, 3, 1]

    def test_sort_priority(self, db):
        conn, path = db
        _seed(conn, [
            {"skill": "A", "category": "tool", "demand_count": 5, "example_jobs": []},
            {"skill": "B", "category": "tool", "demand_count": 3, "example_jobs": []},
        ])
        # priority defaults to demand_count on insert; bump A's priority manually
        conn.execute("UPDATE skill_gaps SET priority = 99 WHERE skill_name = 'B'")
        conn.commit()
        result = _invoke(path, "gaps", "list", "--json", "--sort", "priority")
        skills = [g["skill_name"] for g in json.loads(result.stdout)["gaps"]]
        assert skills == ["B", "A"]

    def test_sort_recent(self, db):
        conn, path = db
        _seed(conn, [
            {"skill": "Old", "category": "tool", "demand_count": 5, "example_jobs": []},
        ])
        conn.execute("UPDATE skill_gaps SET updated_at = '2020-01-01 00:00:00' WHERE skill_name = 'Old'")
        conn.commit()
        _seed(conn, [
            {"skill": "New", "category": "tool", "demand_count": 1, "example_jobs": []},
        ])
        result = _invoke(path, "gaps", "list", "--json", "--sort", "recent")
        skills = [g["skill_name"] for g in json.loads(result.stdout)["gaps"]]
        assert skills[0] == "New"

    def test_invalid_sort_returns_error(self, db):
        _, path = db
        result = _invoke(path, "gaps", "list", "--json", "--sort", "nonsense")
        assert result.exit_code == 1
        payload = json.loads(result.stdout)
        assert payload["code"] == 1
        assert "Invalid --sort" in payload["error"]


class TestComposability:
    def test_filters_compose_with_and(self, db):
        conn, path = db
        _seed(conn, [
            {"skill": "Kafka", "category": "tool", "demand_count": 5, "example_jobs": []},
            {"skill": "Flink", "category": "tool", "demand_count": 2, "example_jobs": []},
            {"skill": "RAG", "category": "domain", "demand_count": 8, "example_jobs": []},
        ])
        result = _invoke(
            path, "gaps", "list", "--json",
            "--category", "tool", "--min-demand", "3",
        )
        skills = [g["skill_name"] for g in json.loads(result.stdout)["gaps"]]
        assert skills == ["Kafka"]
