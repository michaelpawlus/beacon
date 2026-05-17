"""Tests for the dedupe + scoring layer."""

import pytest

from beacon.db.connection import get_connection, init_db
from beacon.sources.base import Candidate
from beacon.sources.dedupe import (
    existing_company_match,
    normalize_name,
    score_candidate,
    upsert_candidates,
)


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn
    conn.close()


def _candidate(**overrides) -> Candidate:
    base = dict(
        name="Example AI",
        source="yaml",
        source_ref="seed/example-ai",
        domain="example.ai",
        careers_url="https://example.ai/careers",
        hq_location="SF",
        industry="Developer Tools",
        signals=[],
        raw={},
    )
    base.update(overrides)
    return Candidate(**base)


class TestScoreCandidate:
    def test_baseline_includes_source_weight(self):
        c = _candidate(signals=[], domain=None, careers_url=None, hq_location=None, industry=None)
        assert score_candidate(c) == 1.5  # yaml weight, no signals, no fields

    def test_signals_increase_score(self):
        c1 = _candidate(signals=[])
        c2 = _candidate(signals=[{"signal_type": "engineering_blog", "title": "x"}])
        assert score_candidate(c2) > score_candidate(c1)

    def test_signal_cap_at_five(self):
        many = [{"signal_type": "engineering_blog", "title": f"s{i}"} for i in range(10)]
        c = _candidate(signals=many)
        # source(1.5) + 5 signals(5) + 4 fields(2.0) = 8.5
        assert score_candidate(c) == 8.5

    def test_strong_signal_bonus(self):
        weak = _candidate(signals=[{"signal_type": "engineering_blog", "title": "x", "signal_strength": 2}])
        strong = _candidate(signals=[{"signal_type": "engineering_blog", "title": "x", "signal_strength": 5}])
        assert score_candidate(strong) - score_candidate(weak) == 1.0

    def test_crunchbase_weight_lower_than_yaml(self):
        y = _candidate(source="yaml")
        c = _candidate(source="crunchbase")
        assert score_candidate(y) > score_candidate(c)


class TestNormalizeName:
    def test_strips_punctuation_and_spaces(self):
        assert normalize_name("Cursor (Anysphere)") == "cursoranysphere"

    def test_lowercases(self):
        assert normalize_name("OpenAI") == "openai"

    def test_none_safe(self):
        assert normalize_name("") == ""


class TestExistingCompanyMatch:
    def _insert_company(self, db, name, domain=None):
        cur = db.execute(
            "INSERT INTO companies (name, domain) VALUES (?, ?)", (name, domain)
        )
        db.commit()
        return cur.lastrowid

    def test_exact_name_match(self, db):
        cid = self._insert_company(db, "Anthropic")
        assert existing_company_match(db, _candidate(name="Anthropic")) == cid

    def test_case_insensitive_name(self, db):
        cid = self._insert_company(db, "Anthropic")
        assert existing_company_match(db, _candidate(name="anthropic")) == cid

    def test_domain_match(self, db):
        cid = self._insert_company(db, "Whatever", domain="anthropic.com")
        c = _candidate(name="Anthropic", domain="anthropic.com")
        assert existing_company_match(db, c) == cid

    def test_normalized_fuzzy_match(self, db):
        cid = self._insert_company(db, "Cursor (Anysphere)")
        # Candidate calls them just "Cursor" with no domain
        c = _candidate(name="Cursor", domain=None)
        # First 4 chars match → fuzzy compare against normalized name
        # normalize("Cursor (Anysphere)") = "cursoranysphere" ≠ "cursor", so should NOT match
        assert existing_company_match(db, c) is None
        # But if candidate fully matches the canonical normalized form...
        c2 = _candidate(name="Cursor Anysphere", domain=None)
        assert existing_company_match(db, c2) == cid

    def test_no_match_returns_none(self, db):
        self._insert_company(db, "Anthropic")
        assert existing_company_match(db, _candidate(name="Vercel")) is None


class TestUpsertCandidates:
    def test_inserts_new(self, db):
        result = upsert_candidates(db, [_candidate()])
        assert len(result["inserted"]) == 1
        assert result["inserted"][0]["id"] is not None
        row = db.execute("SELECT * FROM discovery_candidates").fetchone()
        assert row["name"] == "Example AI"
        assert row["status"] == "pending"
        assert row["discovery_score"] > 0

    def test_second_run_dedupes_by_source_ref(self, db):
        upsert_candidates(db, [_candidate()])
        result = upsert_candidates(db, [_candidate()])
        assert len(result["inserted"]) == 0
        assert len(result["skipped_duplicate"]) == 1
        count = db.execute("SELECT COUNT(*) AS c FROM discovery_candidates").fetchone()["c"]
        assert count == 1

    def test_skips_already_existing_company(self, db):
        db.execute("INSERT INTO companies (name, domain) VALUES (?, ?)", ("Example AI", "example.ai"))
        db.commit()
        result = upsert_candidates(db, [_candidate()])
        assert len(result["inserted"]) == 0
        assert len(result["skipped_existing"]) == 1
        assert result["skipped_existing"][0]["matched_company_id"] is not None

    def test_dry_run_does_not_write(self, db):
        result = upsert_candidates(db, [_candidate()], dry_run=True)
        assert len(result["inserted"]) == 1
        assert result["inserted"][0]["id"] is None
        count = db.execute("SELECT COUNT(*) AS c FROM discovery_candidates").fetchone()["c"]
        assert count == 0
