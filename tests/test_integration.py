"""End-to-end integration tests for the Phase 2 job scanner pipeline."""

from unittest.mock import MagicMock, patch

import pytest

from beacon.db.connection import get_connection, init_db
from beacon.db.jobs import get_jobs
from beacon.export.formatters import export_jobs_digest, export_jobs_report
from beacon.scanner import scan_all


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_integration.db"
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn
    conn.close()


def _seed_companies(conn):
    """Seed a few test companies."""
    companies = [
        ("AlphaCo", "alpha.com", "greenhouse", "https://alpha.com/careers"),
        ("BetaCo", "beta.com", "greenhouse", "https://beta.com/careers"),
        ("GammaCo", "gamma.com", "custom", "https://gamma.com/jobs"),
    ]
    for name, domain, platform, url in companies:
        conn.execute(
            "INSERT INTO companies (name, domain, careers_platform, careers_url, remote_policy, size_bucket, ai_first_score) "
            "VALUES (?, ?, ?, ?, 'hybrid', 'mid-200-1000', 7.0)",
            (name, domain, platform, url),
        )
    conn.commit()
    return conn.execute("SELECT * FROM companies ORDER BY name").fetchall()


MOCK_ALPHA_JOBS = [
    {
        "title": "Senior Data Engineer",
        "url": "https://alpha.com/jobs/1",
        "location": "Remote",
        "department": "Engineering",
        "description_text": "Build data pipelines with python, sql, dbt, and spark.",
        "date_posted": "2025-03-01",
    },
    {
        "title": "ML Engineer",
        "url": "https://alpha.com/jobs/2",
        "location": "San Francisco, CA",
        "department": "ML",
        "description_text": "Develop ML models using pytorch and tensorflow.",
        "date_posted": "2025-03-05",
    },
    {
        "title": "Office Manager",
        "url": "https://alpha.com/jobs/3",
        "location": "NYC",
        "department": "Operations",
        "description_text": "Manage the office, schedule meetings, handle payroll.",
        "date_posted": "2025-03-01",
    },
]

MOCK_BETA_JOBS = [
    {
        "title": "Data Analyst",
        "url": "https://beta.com/jobs/1",
        "location": "Remote",
        "department": "Analytics",
        "description_text": "Analyze data using sql, python, and tableau.",
        "date_posted": "2025-03-10",
    },
]


class TestEndToEndPipeline:
    @patch("beacon.scanner.get_adapter")
    def test_full_pipeline(self, mock_get_adapter, db):
        """Seed -> scan -> verify jobs -> generate digest -> re-scan -> verify stale."""
        _seed_companies(db)

        # Set up mock adapter
        mock_adapter = MagicMock()

        def side_effect(company_dict):
            if company_dict["domain"] == "alpha.com":
                return MOCK_ALPHA_JOBS
            elif company_dict["domain"] == "beta.com":
                return MOCK_BETA_JOBS
            return []

        mock_adapter.fetch_jobs.side_effect = side_effect
        mock_get_adapter.return_value = mock_adapter

        # --- First scan ---
        results = scan_all(db)
        assert len(results) == 3  # 3 companies

        alpha_result = next(r for r in results if r.company_name == "AlphaCo")
        assert alpha_result.jobs_found == 3
        assert alpha_result.new_jobs == 3
        assert alpha_result.error is None

        beta_result = next(r for r in results if r.company_name == "BetaCo")
        assert beta_result.jobs_found == 1
        assert beta_result.new_jobs == 1

        # Verify jobs in DB
        all_jobs = get_jobs(db)
        assert len(all_jobs) == 4  # 3 alpha + 1 beta (gamma had 0)

        # Verify scoring: data/ML jobs should score higher than office manager
        relevant_jobs = get_jobs(db, min_relevance=7.0)
        irrelevant_jobs = [j for j in all_jobs if j["relevance_score"] < 4.0]
        assert len(relevant_jobs) >= 2  # Data Engineer + ML Engineer should be relevant
        assert len(irrelevant_jobs) >= 1  # Office Manager should be irrelevant

        # --- Generate digest ---
        digest = export_jobs_digest(db, "2020-01-01", min_relevance=7.0)
        assert "AlphaCo" in digest
        assert "Senior Data Engineer" in digest or "ML Engineer" in digest

        # --- Generate full report ---
        report = export_jobs_report(db)
        assert "active jobs" in report
        assert "AlphaCo" in report or "BetaCo" in report

        # --- Re-scan with fewer jobs (Alpha loses 2 jobs) ---
        def rescan_side_effect(company_dict):
            if company_dict["domain"] == "alpha.com":
                return [MOCK_ALPHA_JOBS[0]]  # Only keep first job
            elif company_dict["domain"] == "beta.com":
                return MOCK_BETA_JOBS
            return []

        mock_adapter.fetch_jobs.side_effect = rescan_side_effect

        results2 = scan_all(db)
        alpha_result2 = next(r for r in results2 if r.company_name == "AlphaCo")
        assert alpha_result2.stale_jobs == 2  # ML Engineer + Office Manager marked stale
        assert alpha_result2.new_jobs == 0
        assert alpha_result2.updated_jobs == 1  # Senior Data Engineer updated

        # Verify stale marking
        closed_jobs = db.execute("SELECT COUNT(*) as cnt FROM job_listings WHERE status = 'closed'").fetchone()["cnt"]
        assert closed_jobs == 2

    @patch("beacon.scanner.get_adapter")
    def test_scan_with_company_filter(self, mock_get_adapter, db):
        """Scanning with company name filter only scans matching companies."""
        _seed_companies(db)

        mock_adapter = MagicMock()
        mock_adapter.fetch_jobs.return_value = MOCK_ALPHA_JOBS
        mock_get_adapter.return_value = mock_adapter

        results = scan_all(db, company_name="Alpha")
        assert len(results) == 1
        assert results[0].company_name == "AlphaCo"

    @patch("beacon.scanner.get_adapter")
    def test_scan_with_platform_filter(self, mock_get_adapter, db):
        """Scanning with platform filter only scans matching platforms."""
        _seed_companies(db)

        mock_adapter = MagicMock()
        mock_adapter.fetch_jobs.return_value = []
        mock_get_adapter.return_value = mock_adapter

        results = scan_all(db, platform="greenhouse")
        company_names = {r.company_name for r in results}
        assert "AlphaCo" in company_names
        assert "BetaCo" in company_names
        assert "GammaCo" not in company_names

    @patch("beacon.scanner.get_adapter")
    def test_adapter_error_doesnt_crash_pipeline(self, mock_get_adapter, db):
        """An error in one company's scan shouldn't crash the whole pipeline."""
        _seed_companies(db)

        call_count = 0

        def flaky_fetch(company_dict):
            nonlocal call_count
            call_count += 1
            if company_dict["domain"] == "alpha.com":
                raise ConnectionError("Network error")
            return MOCK_BETA_JOBS

        mock_adapter = MagicMock()
        mock_adapter.fetch_jobs.side_effect = flaky_fetch
        mock_get_adapter.return_value = mock_adapter

        results = scan_all(db)
        errors = [r for r in results if r.error]
        successes = [r for r in results if not r.error]
        assert len(errors) >= 1
        assert len(successes) >= 1
