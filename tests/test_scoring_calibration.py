"""Tests for scoring calibration and variant tracking (Phase 5, Step 7)."""

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from beacon.db.connection import get_connection, init_db
from beacon.db.feedback import record_outcome, record_resume_variant
from beacon.materials.variant_tracker import (
    analyze_variant_performance,
    generate_variant_report,
    suggest_variant_for_job,
)
from beacon.research.scoring_calibration import (
    compute_calibration_adjustments,
    generate_scoring_report,
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


def _insert_job(conn, company_id, title="Data Engineer", score=8.0):
    cursor = conn.execute(
        "INSERT INTO job_listings (company_id, title, relevance_score, status) VALUES (?, ?, ?, 'active')",
        (company_id, title, score),
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


# --- Scoring Calibration ---

class TestComputeCalibration:
    def test_no_data(self, db):
        conn, _ = db
        result = compute_calibration_adjustments(conn)
        assert result["has_data"] is False
        assert "No outcome data" in result["message"]

    def test_with_outcomes(self, db):
        conn, _ = db
        cid = _insert_company(conn)
        jid1 = _insert_job(conn, cid, "Job A", score=9.0)
        jid2 = _insert_job(conn, cid, "Job B", score=5.0)
        aid1 = _insert_application(conn, jid1)
        aid2 = _insert_application(conn, jid2)
        record_outcome(conn, aid1, "phone_screen", response_days=5)
        record_outcome(conn, aid2, "rejection_auto", response_days=1)

        result = compute_calibration_adjustments(conn)
        assert result["has_data"] is True
        assert result["total_outcomes"] == 2
        assert result["positive_count"] == 1
        assert result["negative_count"] == 1
        assert result["positive_avg_score"] == 9.0
        assert result["negative_avg_score"] == 5.0

    def test_by_outcome_type(self, db):
        conn, _ = db
        cid = _insert_company(conn)
        jid = _insert_job(conn, cid, score=8.0)
        aid = _insert_application(conn, jid)
        record_outcome(conn, aid, "phone_screen")
        record_outcome(conn, aid, "phone_screen")
        record_outcome(conn, aid, "technical")

        result = compute_calibration_adjustments(conn)
        assert "phone_screen" in result["by_outcome"]
        assert result["by_outcome"]["phone_screen"]["count"] == 2
        assert "technical" in result["by_outcome"]

    def test_suggestions_few_data(self, db):
        conn, _ = db
        cid = _insert_company(conn)
        jid = _insert_job(conn, cid, score=8.0)
        aid = _insert_application(conn, jid)
        record_outcome(conn, aid, "phone_screen")

        result = compute_calibration_adjustments(conn)
        assert any("10+" in s for s in result["suggestions"])

    def test_suggestions_low_positive_score(self, db):
        conn, _ = db
        cid = _insert_company(conn)
        # Low-scored job gets positive outcome
        jid = _insert_job(conn, cid, "Low Scored", score=3.0)
        aid = _insert_application(conn, jid)
        record_outcome(conn, aid, "phone_screen")
        # Need a negative for comparison
        jid2 = _insert_job(conn, cid, "Another", score=4.0)
        aid2 = _insert_application(conn, jid2)
        record_outcome(conn, aid2, "rejection_auto")

        result = compute_calibration_adjustments(conn)
        assert any("undervaluing" in s for s in result["suggestions"])


class TestScoringReport:
    def test_report_no_data(self, db):
        conn, _ = db
        report = generate_scoring_report(conn)
        assert "Scoring Calibration Report" in report
        assert "No outcome data" in report

    def test_report_with_data(self, db):
        conn, _ = db
        cid = _insert_company(conn)
        jid = _insert_job(conn, cid, score=8.0)
        aid = _insert_application(conn, jid)
        record_outcome(conn, aid, "phone_screen", response_days=5)

        report = generate_scoring_report(conn)
        assert "Summary" in report
        assert "phone_screen" in report
        assert "Suggestions" in report


# --- Variant Tracking ---

class TestVariantPerformance:
    def test_no_data(self, db):
        conn, _ = db
        result = analyze_variant_performance(conn)
        assert result["has_data"] is False

    def test_with_variants(self, db):
        conn, _ = db
        cid = _insert_company(conn)
        jid1 = _insert_job(conn, cid, "Job A")
        jid2 = _insert_job(conn, cid, "Job B")
        aid1 = _insert_application(conn, jid1)
        aid2 = _insert_application(conn, jid2)

        record_resume_variant(conn, aid1, "technical_focus")
        record_resume_variant(conn, aid2, "technical_focus")
        record_resume_variant(conn, aid2, "leadership_focus")

        record_outcome(conn, aid1, "phone_screen")  # positive
        record_outcome(conn, aid2, "rejection_auto")  # negative

        result = analyze_variant_performance(conn)
        assert result["has_data"] is True
        assert "technical_focus" in result["variants"]
        assert result["variants"]["technical_focus"]["total_uses"] == 2

    def test_success_rate_calculation(self, db):
        conn, _ = db
        cid = _insert_company(conn)
        jid1 = _insert_job(conn, cid, "Job A")
        jid2 = _insert_job(conn, cid, "Job B")
        aid1 = _insert_application(conn, jid1)
        aid2 = _insert_application(conn, jid2)

        record_resume_variant(conn, aid1, "tech")
        record_resume_variant(conn, aid2, "tech")
        record_outcome(conn, aid1, "phone_screen")  # positive
        record_outcome(conn, aid2, "rejection_auto")  # negative

        result = analyze_variant_performance(conn)
        assert result["variants"]["tech"]["success_rate"] == 50.0


class TestSuggestVariant:
    def test_no_data(self, db):
        conn, _ = db
        result = suggest_variant_for_job(conn, 1)
        assert result is None

    def test_suggest_best(self, db):
        conn, _ = db
        cid = _insert_company(conn)
        # Create multiple applications with variants
        for i in range(3):
            jid = _insert_job(conn, cid, f"Job {i}")
            aid = _insert_application(conn, jid)
            record_resume_variant(conn, aid, "tech")
            record_outcome(conn, aid, "phone_screen")

        for i in range(3, 6):
            jid = _insert_job(conn, cid, f"Job {i}")
            aid = _insert_application(conn, jid)
            record_resume_variant(conn, aid, "generic")
            record_outcome(conn, aid, "rejection_auto")

        result = suggest_variant_for_job(conn, 1)
        assert result == "tech"


class TestVariantReport:
    def test_report_no_data(self, db):
        conn, _ = db
        report = generate_variant_report(conn)
        assert "Variant Effectiveness" in report
        assert "No variant data" in report

    def test_report_with_data(self, db):
        conn, _ = db
        cid = _insert_company(conn)
        jid = _insert_job(conn, cid)
        aid = _insert_application(conn, jid)
        record_resume_variant(conn, aid, "technical")
        record_outcome(conn, aid, "phone_screen")

        report = generate_variant_report(conn)
        assert "Variant Performance" in report
        assert "technical" in report


# --- CLI Commands ---

class TestScoringCLI:
    def test_scoring_feedback_command(self, db):
        from beacon.cli import app
        conn, _ = db
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["report", "scoring-feedback"])
            assert result.exit_code == 0

    def test_variant_effectiveness_command(self, db):
        from beacon.cli import app
        conn, _ = db
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["report", "variant-effectiveness"])
            assert result.exit_code == 0
