"""Tests for job report generators (digest and full report)."""

import pytest

from beacon.db.connection import get_connection, init_db
from beacon.db.jobs import upsert_job
from beacon.export.formatters import export_jobs_digest, export_jobs_report


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_beacon.db"
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn
    conn.close()


def _insert_company(conn, name="TestCo"):
    conn.execute(
        "INSERT INTO companies (name, remote_policy, size_bucket) VALUES (?, 'hybrid', 'mid-200-1000')",
        (name,),
    )
    conn.commit()
    return conn.execute("SELECT id FROM companies WHERE name = ?", (name,)).fetchone()["id"]


class TestJobsDigest:
    def test_empty_digest(self, db):
        content = export_jobs_digest(db, "2020-01-01", min_relevance=7.0)
        assert "Job Digest" in content
        assert "No matching jobs found" in content

    def test_digest_with_jobs(self, db):
        cid = _insert_company(db, "Anthropic")
        upsert_job(db, cid, "Data Engineer", url="https://x.com/1", relevance_score=8.5, location="Remote")
        upsert_job(db, cid, "ML Engineer", url="https://x.com/2", relevance_score=9.0, location="SF")

        content = export_jobs_digest(db, "2020-01-01", min_relevance=7.0)
        assert "Anthropic" in content
        assert "Data Engineer" in content
        assert "ML Engineer" in content
        assert "2 relevant jobs" in content

    def test_digest_groups_by_company(self, db):
        cid1 = _insert_company(db, "CompanyA")
        cid2 = _insert_company(db, "CompanyB")
        upsert_job(db, cid1, "Job A", url="https://a.com/1", relevance_score=8.0)
        upsert_job(db, cid2, "Job B", url="https://b.com/1", relevance_score=7.5)

        content = export_jobs_digest(db, "2020-01-01", min_relevance=7.0)
        assert "CompanyA" in content
        assert "CompanyB" in content
        assert "2 companies" in content

    def test_digest_filters_by_relevance(self, db):
        cid = _insert_company(db)
        upsert_job(db, cid, "High Score", url="https://x.com/1", relevance_score=9.0)
        upsert_job(db, cid, "Low Score", url="https://x.com/2", relevance_score=3.0)

        content = export_jobs_digest(db, "2020-01-01", min_relevance=7.0)
        assert "High Score" in content
        assert "Low Score" not in content

    def test_digest_filters_by_date(self, db):
        cid = _insert_company(db)
        upsert_job(db, cid, "Recent Job", url="https://x.com/1", relevance_score=8.0)

        # Use far-future date to filter out all jobs
        content = export_jobs_digest(db, "2099-01-01", min_relevance=0.0)
        assert "No matching jobs found" in content

    def test_digest_shows_summary_stats(self, db):
        cid1 = _insert_company(db, "A")
        cid2 = _insert_company(db, "B")
        upsert_job(db, cid1, "Job 1", url="https://x.com/1", relevance_score=8.0)
        upsert_job(db, cid1, "Job 2", url="https://x.com/2", relevance_score=7.5)
        upsert_job(db, cid2, "Job 3", url="https://x.com/3", relevance_score=9.0)

        content = export_jobs_digest(db, "2020-01-01", min_relevance=7.0)
        assert "3 relevant jobs" in content
        assert "2 companies" in content


class TestJobsReport:
    def test_empty_report(self, db):
        content = export_jobs_report(db)
        assert "Job Listings Report" in content
        assert "0 active jobs" in content

    def test_report_with_jobs(self, db):
        cid = _insert_company(db, "TestCo")
        upsert_job(db, cid, "Data Engineer", url="https://x.com/1", relevance_score=8.5, location="Remote")
        upsert_job(db, cid, "Office Manager", url="https://x.com/2", relevance_score=2.0, location="NYC")

        content = export_jobs_report(db)
        assert "2 active jobs" in content
        assert "Data Engineer" in content
        assert "Office Manager" in content
        assert "1 highly relevant" in content

    def test_report_table_format(self, db):
        cid = _insert_company(db)
        upsert_job(db, cid, "ML Engineer", url="https://x.com/1", relevance_score=9.0, location="SF")

        content = export_jobs_report(db)
        assert "| #" in content
        assert "ML Engineer" in content
        assert "9.0" in content
