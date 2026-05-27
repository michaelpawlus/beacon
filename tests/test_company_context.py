"""Tests for the factored-out company_context helper."""

import pytest

from beacon.db.connection import get_connection, init_db
from beacon.materials.company_context import (
    build_company_context,
    build_company_context_dict,
)


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_beacon.db"
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn
    conn.close()


def _insert_company(conn, name="TestCo"):
    conn.execute(
        "INSERT INTO companies (name, remote_policy, size_bucket, description, ai_first_score, tier) "
        "VALUES (?, 'hybrid', 'mid-200-1000', 'AI-first data company', 8.5, 1)",
        (name,),
    )
    conn.commit()
    return conn.execute("SELECT id FROM companies WHERE name = ?", (name,)).fetchone()["id"]


def _populate_research(conn, company_id):
    conn.execute(
        "INSERT INTO leadership_signals (company_id, leader_name, leader_title, signal_type, content, impact_level) "
        "VALUES (?, 'CEO Smith', 'CEO', 'quote', 'AI is our top priority', 'company-wide')",
        (company_id,),
    )
    conn.execute(
        "INSERT INTO ai_signals (company_id, signal_type, title, signal_strength) "
        "VALUES (?, 'engineering_blog', 'How We Use AI in Data Engineering', 4)",
        (company_id,),
    )
    conn.execute(
        "INSERT INTO tools_adopted (company_id, tool_name, adoption_level) "
        "VALUES (?, 'GitHub Copilot', 'required')",
        (company_id,),
    )
    conn.commit()


class TestBuildCompanyContextDict:
    def test_empty_company(self, db):
        ctx = build_company_context_dict(db, 99999)
        assert ctx["company"] is None
        assert ctx["leadership_signals"] == []
        assert ctx["ai_signals"] == []
        assert ctx["tools"] == []

    def test_full_research(self, db):
        cid = _insert_company(db)
        _populate_research(db, cid)
        ctx = build_company_context_dict(db, cid)
        assert ctx["company"]["name"] == "TestCo"
        assert ctx["leadership_signals"][0]["leader_name"] == "CEO Smith"
        assert ctx["ai_signals"][0]["title"] == "How We Use AI in Data Engineering"
        assert ctx["tools"][0]["tool_name"] == "GitHub Copilot"

    def test_caps_at_five(self, db):
        cid = _insert_company(db)
        for i in range(7):
            db.execute(
                "INSERT INTO leadership_signals (company_id, leader_name, leader_title, signal_type, content, impact_level) "
                "VALUES (?, ?, 'CTO', 'quote', ?, 'company-wide')",
                (cid, f"Leader {i}", f"content {i}"),
            )
            db.execute(
                "INSERT INTO ai_signals (company_id, signal_type, title, signal_strength) "
                "VALUES (?, 'engineering_blog', ?, 3)",
                (cid, f"Post {i}"),
            )
        db.commit()
        ctx = build_company_context_dict(db, cid)
        assert len(ctx["leadership_signals"]) == 5
        assert len(ctx["ai_signals"]) == 5


class TestBuildCompanyContextString:
    def test_string_format_preserved(self, db):
        """Cover letter tests depend on the exact substring layout."""
        cid = _insert_company(db)
        _populate_research(db, cid)
        s = build_company_context(db, cid)
        assert "TestCo" in s
        assert "8.5" in s
        assert "Leadership Signals:" in s
        assert "AI Culture Signals:" in s
        assert "AI Tools Adopted:" in s
        assert "GitHub Copilot (required)" in s

    def test_empty_returns_empty_string(self, db):
        assert build_company_context(db, 99999) == ""
