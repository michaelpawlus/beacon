"""Tests for Beacon feedback tracking system (Phase 5, Step 2)."""

import pytest
from typer.testing import CliRunner
from unittest.mock import patch

from beacon.db.connection import get_connection, init_db
from beacon.db.feedback import (
    get_outcome_stats,
    get_outcomes,
    get_scoring_feedback,
    get_signal_refresh_log,
    get_variant_effectiveness,
    record_outcome,
    record_resume_variant,
    record_signal_refresh,
)

runner = CliRunner()


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_beacon.db"
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn, db_path
    conn.close()


def _insert_company(conn, name="TestCo"):
    cursor = conn.execute(
        "INSERT INTO companies (name, careers_platform, domain) VALUES (?, 'greenhouse', 'testco.com')",
        (name,),
    )
    conn.commit()
    return cursor.lastrowid


def _insert_job(conn, company_id, title="Data Engineer"):
    cursor = conn.execute(
        "INSERT INTO job_listings (company_id, title, relevance_score) VALUES (?, ?, 8.0)",
        (company_id, title),
    )
    conn.commit()
    return cursor.lastrowid


def _insert_application(conn, job_id, status="applied"):
    cursor = conn.execute(
        "INSERT INTO applications (job_id, status, applied_date) VALUES (?, ?, '2026-01-01')",
        (job_id, status),
    )
    conn.commit()
    return cursor.lastrowid


# --- Outcome CRUD ---

class TestRecordOutcome:
    def test_record_valid_outcome(self, db):
        conn, _ = db
        cid = _insert_company(conn)
        jid = _insert_job(conn, cid)
        aid = _insert_application(conn, jid)

        outcome_id = record_outcome(conn, aid, "phone_screen", response_days=5, notes="Went well")
        assert outcome_id > 0

    def test_record_outcome_without_days(self, db):
        conn, _ = db
        cid = _insert_company(conn)
        jid = _insert_job(conn, cid)
        aid = _insert_application(conn, jid)

        outcome_id = record_outcome(conn, aid, "rejection_auto")
        assert outcome_id > 0

    def test_invalid_outcome_type(self, db):
        conn, _ = db
        cid = _insert_company(conn)
        jid = _insert_job(conn, cid)
        aid = _insert_application(conn, jid)

        with pytest.raises(ValueError, match="Invalid outcome"):
            record_outcome(conn, aid, "bad_outcome")

    def test_nonexistent_application(self, db):
        conn, _ = db
        with pytest.raises(ValueError, match="not found"):
            record_outcome(conn, 9999, "phone_screen")

    def test_multiple_outcomes_same_application(self, db):
        conn, _ = db
        cid = _insert_company(conn)
        jid = _insert_job(conn, cid)
        aid = _insert_application(conn, jid)

        id1 = record_outcome(conn, aid, "phone_screen", response_days=5)
        id2 = record_outcome(conn, aid, "technical", response_days=12)
        assert id1 != id2


class TestGetOutcomes:
    def test_get_all_outcomes(self, db):
        conn, _ = db
        cid = _insert_company(conn)
        jid = _insert_job(conn, cid)
        aid = _insert_application(conn, jid)
        record_outcome(conn, aid, "phone_screen")
        record_outcome(conn, aid, "technical")

        outcomes = get_outcomes(conn)
        assert len(outcomes) == 2

    def test_filter_by_application(self, db):
        conn, _ = db
        cid = _insert_company(conn)
        jid1 = _insert_job(conn, cid, "Job A")
        jid2 = _insert_job(conn, cid, "Job B")
        aid1 = _insert_application(conn, jid1)
        aid2 = _insert_application(conn, jid2)
        record_outcome(conn, aid1, "phone_screen")
        record_outcome(conn, aid2, "rejection_auto")

        outcomes = get_outcomes(conn, application_id=aid1)
        assert len(outcomes) == 1
        assert outcomes[0]["outcome"] == "phone_screen"

    def test_filter_by_outcome_type(self, db):
        conn, _ = db
        cid = _insert_company(conn)
        jid = _insert_job(conn, cid)
        aid = _insert_application(conn, jid)
        record_outcome(conn, aid, "phone_screen")
        record_outcome(conn, aid, "rejection_auto")

        outcomes = get_outcomes(conn, outcome_filter="phone_screen")
        assert len(outcomes) == 1

    def test_empty_outcomes(self, db):
        conn, _ = db
        assert get_outcomes(conn) == []


class TestOutcomeStats:
    def test_stats_aggregation(self, db):
        conn, _ = db
        cid = _insert_company(conn)
        jid = _insert_job(conn, cid)
        aid = _insert_application(conn, jid)
        record_outcome(conn, aid, "phone_screen", response_days=5)
        record_outcome(conn, aid, "phone_screen", response_days=7)
        record_outcome(conn, aid, "rejection_auto", response_days=1)

        stats = get_outcome_stats(conn)
        assert len(stats) == 2
        # phone_screen should be first (count=2)
        assert stats[0]["outcome"] == "phone_screen"
        assert stats[0]["count"] == 2
        assert stats[0]["avg_days"] == 6.0

    def test_empty_stats(self, db):
        conn, _ = db
        assert get_outcome_stats(conn) == []


# --- Resume Variants ---

class TestResumeVariants:
    def test_record_variant(self, db):
        conn, _ = db
        cid = _insert_company(conn)
        jid = _insert_job(conn, cid)
        aid = _insert_application(conn, jid)

        vid = record_resume_variant(conn, aid, "technical_focus", "Emphasized Python and ML skills")
        assert vid > 0

    def test_variant_effectiveness(self, db):
        conn, _ = db
        cid = _insert_company(conn)
        jid1 = _insert_job(conn, cid, "Job A")
        jid2 = _insert_job(conn, cid, "Job B")
        aid1 = _insert_application(conn, jid1)
        aid2 = _insert_application(conn, jid2)

        record_resume_variant(conn, aid1, "technical_focus")
        record_resume_variant(conn, aid2, "technical_focus")
        record_resume_variant(conn, aid2, "leadership_focus")

        variants = get_variant_effectiveness(conn)
        assert len(variants) == 2
        assert variants[0]["variant_label"] == "technical_focus"
        assert variants[0]["count"] == 2


# --- Scoring Feedback ---

class TestScoringFeedback:
    def test_feedback_join(self, db):
        conn, _ = db
        cid = _insert_company(conn)
        jid = _insert_job(conn, cid)
        aid = _insert_application(conn, jid)
        record_outcome(conn, aid, "phone_screen", response_days=5)

        feedback = get_scoring_feedback(conn)
        assert len(feedback) == 1
        assert feedback[0]["outcome"] == "phone_screen"
        assert feedback[0]["relevance_score"] == 8.0
        assert feedback[0]["company_name"] == "TestCo"

    def test_empty_feedback(self, db):
        conn, _ = db
        assert get_scoring_feedback(conn) == []


# --- Signal Refresh Log ---

class TestSignalRefreshLog:
    def test_record_refresh(self, db):
        conn, _ = db
        cid = _insert_company(conn)
        log_id = record_signal_refresh(conn, cid, signals_added=3, signals_updated=1)
        assert log_id > 0

    def test_get_refresh_log(self, db):
        conn, _ = db
        cid = _insert_company(conn)
        record_signal_refresh(conn, cid, signals_added=3)
        record_signal_refresh(conn, cid, signals_added=1)

        logs = get_signal_refresh_log(conn)
        assert len(logs) == 2

    def test_filter_by_company(self, db):
        conn, _ = db
        cid1 = _insert_company(conn, "Co A")
        cid2 = _insert_company(conn, "Co B")
        record_signal_refresh(conn, cid1, signals_added=3)
        record_signal_refresh(conn, cid2, signals_added=1)

        logs = get_signal_refresh_log(conn, company_id=cid1)
        assert len(logs) == 1


# --- Cascade Delete ---

class TestCascadeDelete:
    def test_delete_application_cascades_outcomes(self, db):
        conn, _ = db
        cid = _insert_company(conn)
        jid = _insert_job(conn, cid)
        aid = _insert_application(conn, jid)
        record_outcome(conn, aid, "phone_screen")

        conn.execute("DELETE FROM applications WHERE id = ?", (aid,))
        conn.commit()

        outcomes = get_outcomes(conn)
        assert len(outcomes) == 0

    def test_delete_application_cascades_variants(self, db):
        conn, _ = db
        cid = _insert_company(conn)
        jid = _insert_job(conn, cid)
        aid = _insert_application(conn, jid)
        record_resume_variant(conn, aid, "test_variant")

        conn.execute("DELETE FROM applications WHERE id = ?", (aid,))
        conn.commit()

        variants = get_variant_effectiveness(conn)
        assert len(variants) == 0


# --- CLI Commands ---

class TestFeedbackCLI:
    def test_outcome_command(self, db):
        from beacon.cli import app
        conn, db_path = db
        cid = _insert_company(conn)
        jid = _insert_job(conn, cid)
        aid = _insert_application(conn, jid)

        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["application", "outcome", str(aid), "--outcome", "phone_screen", "--days", "5"])
            assert result.exit_code == 0
            assert "recorded" in result.output.lower()

    def test_outcomes_list_command(self, db):
        from beacon.cli import app
        conn, db_path = db
        cid = _insert_company(conn)
        jid = _insert_job(conn, cid)
        aid = _insert_application(conn, jid)
        record_outcome(conn, aid, "phone_screen")

        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["application", "outcomes"])
            assert result.exit_code == 0

    def test_effectiveness_command(self, db):
        from beacon.cli import app
        conn, db_path = db

        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["application", "effectiveness"])
            assert result.exit_code == 0
