"""Tests for the Beacon scoring algorithm and database operations."""


import pytest

from beacon.db.connection import get_connection, init_db, reset_db
from beacon.db.seed import seed_database
from beacon.research.scoring import (
    WEIGHTS,
    compute_composite_score,
    compute_evidence_depth_score,
    compute_leadership_score,
    compute_recency_score,
    compute_tool_adoption_score,
    refresh_all_scores,
    refresh_score,
)


@pytest.fixture
def db(tmp_path):
    """Create a fresh test database."""
    db_path = tmp_path / "test_beacon.db"
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn
    conn.close()


@pytest.fixture
def seeded_db(db):
    """Database with seed data loaded."""
    seed_database(db)
    return db


def _insert_company(conn, name="TestCo", tier=3):
    conn.execute(
        "INSERT INTO companies (name, tier, remote_policy, size_bucket) VALUES (?, ?, 'hybrid', 'mid-200-1000')",
        (name, tier),
    )
    conn.commit()
    return conn.execute("SELECT id FROM companies WHERE name = ?", (name,)).fetchone()["id"]


class TestDatabaseInit:
    def test_schema_creates_all_tables(self, db):
        tables = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = {r["name"] for r in tables}
        assert "companies" in table_names
        assert "ai_signals" in table_names
        assert "leadership_signals" in table_names
        assert "tools_adopted" in table_names
        assert "score_breakdown" in table_names

    def test_foreign_keys_enabled(self, db):
        fk = db.execute("PRAGMA foreign_keys").fetchone()
        assert fk[0] == 1


class TestSeeding:
    def test_seed_creates_companies(self, seeded_db):
        count = seeded_db.execute("SELECT COUNT(*) as cnt FROM companies").fetchone()["cnt"]
        assert count >= 30

    def test_seed_creates_signals(self, seeded_db):
        signals = seeded_db.execute("SELECT COUNT(*) as cnt FROM ai_signals").fetchone()["cnt"]
        leadership = seeded_db.execute("SELECT COUNT(*) as cnt FROM leadership_signals").fetchone()["cnt"]
        tools = seeded_db.execute("SELECT COUNT(*) as cnt FROM tools_adopted").fetchone()["cnt"]
        total = signals + leadership + tools
        assert total >= 100

    def test_tier1_companies_have_signals(self, seeded_db):
        """Every Tier 1 company should have at least 2 signals."""
        companies = seeded_db.execute("SELECT id, name FROM companies WHERE tier = 1").fetchall()
        for c in companies:
            total = 0
            for table in ["ai_signals", "leadership_signals", "tools_adopted"]:
                row = seeded_db.execute(
                    f"SELECT COUNT(*) as cnt FROM {table} WHERE company_id = ?", (c["id"],)
                ).fetchone()
                total += row["cnt"]
            assert total >= 2, f"{c['name']} (Tier 1) has only {total} signals"

    def test_tier2_companies_have_signals(self, seeded_db):
        """Every Tier 2 company should have at least 2 signals."""
        companies = seeded_db.execute("SELECT id, name FROM companies WHERE tier = 2").fetchall()
        for c in companies:
            total = 0
            for table in ["ai_signals", "leadership_signals", "tools_adopted"]:
                row = seeded_db.execute(
                    f"SELECT COUNT(*) as cnt FROM {table} WHERE company_id = ?", (c["id"],)
                ).fetchone()
                total += row["cnt"]
            assert total >= 2, f"{c['name']} (Tier 2) has only {total} signals"

    def test_all_companies_have_scores(self, seeded_db):
        rows = seeded_db.execute(
            "SELECT name, ai_first_score FROM companies WHERE ai_first_score = 0 AND tier <= 3"
        ).fetchall()
        zero_scored = [r["name"] for r in rows]
        assert len(zero_scored) == 0, f"Companies with 0 score: {zero_scored}"

    def test_seed_is_idempotent(self, seeded_db):
        """Seeding twice shouldn't duplicate data."""
        count_before = seeded_db.execute("SELECT COUNT(*) as cnt FROM companies").fetchone()["cnt"]
        seed_database(seeded_db)
        count_after = seeded_db.execute("SELECT COUNT(*) as cnt FROM companies").fetchone()["cnt"]
        assert count_after == count_before


class TestScoring:
    def test_weights_sum_to_one(self):
        total = sum(WEIGHTS.values())
        assert abs(total - 1.0) < 0.001

    def test_leadership_score_empty(self, db):
        cid = _insert_company(db)
        assert compute_leadership_score(db, cid) == 0.0

    def test_leadership_score_company_wide(self, db):
        cid = _insert_company(db)
        db.execute(
            "INSERT INTO leadership_signals (company_id, leader_name, content, impact_level) VALUES (?, 'CEO', 'AI first', 'company-wide')",
            (cid,),
        )
        db.commit()
        score = compute_leadership_score(db, cid)
        assert score == 10.0

    def test_tool_adoption_score_empty(self, db):
        cid = _insert_company(db)
        assert compute_tool_adoption_score(db, cid) == 0.0

    def test_tool_adoption_score_required(self, db):
        cid = _insert_company(db)
        db.execute(
            "INSERT INTO tools_adopted (company_id, tool_name, adoption_level) VALUES (?, 'Claude', 'required')",
            (cid,),
        )
        db.commit()
        score = compute_tool_adoption_score(db, cid)
        assert score == 10.0

    def test_tool_diversity_bonus(self, db):
        cid = _insert_company(db)
        db.execute("INSERT INTO tools_adopted (company_id, tool_name, adoption_level) VALUES (?, 'Claude', 'encouraged')", (cid,))
        db.execute("INSERT INTO tools_adopted (company_id, tool_name, adoption_level) VALUES (?, 'Copilot', 'encouraged')", (cid,))
        db.commit()
        score = compute_tool_adoption_score(db, cid)
        assert score > 8.0  # base 8 + diversity bonus

    def test_evidence_depth_logarithmic(self, db):
        cid = _insert_company(db)
        for i in range(15):
            db.execute(
                "INSERT INTO ai_signals (company_id, signal_type, title, signal_strength) VALUES (?, 'press_coverage', ?, 3)",
                (cid, f"Signal {i}"),
            )
        db.commit()
        score = compute_evidence_depth_score(db, cid)
        assert 7.0 < score <= 10.0

    def test_recency_recent_scores_high(self, db):
        cid = _insert_company(db)
        db.execute(
            "INSERT INTO ai_signals (company_id, signal_type, title, signal_strength, date_observed) VALUES (?, 'press_coverage', 'Recent', 3, date('now'))",
            (cid,),
        )
        db.commit()
        score = compute_recency_score(db, cid)
        assert score >= 9.0

    def test_composite_score_computed(self, db):
        cid = _insert_company(db)
        db.execute("INSERT INTO leadership_signals (company_id, leader_name, content, impact_level) VALUES (?, 'CEO', 'AI mandate', 'company-wide')", (cid,))
        db.execute("INSERT INTO tools_adopted (company_id, tool_name, adoption_level) VALUES (?, 'Claude', 'required')", (cid,))
        db.execute("INSERT INTO ai_signals (company_id, signal_type, title, signal_strength, date_observed) VALUES (?, 'company_policy', 'AI policy', 5, date('now'))", (cid,))
        db.commit()
        scores = compute_composite_score(db, cid)
        assert scores["composite_score"] > 0
        assert scores["leadership_score"] > 0
        assert scores["tool_adoption_score"] > 0

    def test_refresh_score_updates_company(self, db):
        cid = _insert_company(db)
        db.execute("INSERT INTO leadership_signals (company_id, leader_name, content, impact_level) VALUES (?, 'CEO', 'AI', 'company-wide')", (cid,))
        db.commit()
        composite = refresh_score(db, cid)
        assert composite > 0
        row = db.execute("SELECT ai_first_score FROM companies WHERE id = ?", (cid,)).fetchone()
        assert row["ai_first_score"] == composite

    def test_refresh_all_scores(self, seeded_db):
        count = refresh_all_scores(seeded_db)
        assert count >= 30

    def test_tier1_scores_higher_than_tier4(self, seeded_db):
        tier1_avg = seeded_db.execute(
            "SELECT AVG(ai_first_score) as avg FROM companies WHERE tier = 1"
        ).fetchone()["avg"]
        tier4_avg = seeded_db.execute(
            "SELECT AVG(ai_first_score) as avg FROM companies WHERE tier = 4"
        ).fetchone()["avg"]
        assert tier1_avg > tier4_avg


class TestResetDb:
    def test_reset_clears_and_reinitializes(self, tmp_path):
        db_path = tmp_path / "test_reset.db"
        init_db(db_path)
        conn = get_connection(db_path)
        conn.execute("INSERT INTO companies (name, remote_policy, size_bucket) VALUES ('Test', 'hybrid', 'mid-200-1000')")
        conn.commit()
        conn.close()
        reset_db(db_path)
        conn = get_connection(db_path)
        count = conn.execute("SELECT COUNT(*) as cnt FROM companies").fetchone()["cnt"]
        conn.close()
        assert count == 0
