"""Tests for job listing database operations."""

import json

import pytest

from beacon.db.connection import get_connection, init_db
from beacon.db.jobs import (
    get_job_by_id,
    get_jobs,
    get_new_jobs_since,
    mark_stale_jobs,
    update_job_status,
    upsert_job,
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
        "INSERT INTO companies (name, remote_policy, size_bucket) VALUES (?, 'hybrid', 'mid-200-1000')",
        (name,),
    )
    conn.commit()
    return conn.execute("SELECT id FROM companies WHERE name = ?", (name,)).fetchone()["id"]


class TestUpsertJob:
    def test_insert_new_job(self, db):
        cid = _insert_company(db)
        result = upsert_job(db, cid, "Data Engineer", url="https://example.com/job/1")
        assert result["is_new"] is True
        assert result["id"] > 0

    def test_upsert_updates_existing(self, db):
        cid = _insert_company(db)
        r1 = upsert_job(db, cid, "Data Engineer", url="https://example.com/job/1", location="NYC")
        r2 = upsert_job(db, cid, "Data Engineer", url="https://example.com/job/1", location="Remote")
        assert r1["id"] == r2["id"]
        assert r2["is_new"] is False
        row = db.execute("SELECT location FROM job_listings WHERE id = ?", (r1["id"],)).fetchone()
        assert row["location"] == "Remote"

    def test_dedup_by_company_title_url(self, db):
        cid = _insert_company(db)
        upsert_job(db, cid, "ML Engineer", url="https://example.com/1")
        upsert_job(db, cid, "ML Engineer", url="https://example.com/1")
        count = db.execute("SELECT COUNT(*) as cnt FROM job_listings").fetchone()["cnt"]
        assert count == 1

    def test_different_urls_create_separate_jobs(self, db):
        cid = _insert_company(db)
        upsert_job(db, cid, "ML Engineer", url="https://example.com/1")
        upsert_job(db, cid, "ML Engineer", url="https://example.com/2")
        count = db.execute("SELECT COUNT(*) as cnt FROM job_listings").fetchone()["cnt"]
        assert count == 2

    def test_match_reasons_stored_as_json(self, db):
        cid = _insert_company(db)
        reasons = ["title_match", "keyword_match"]
        result = upsert_job(db, cid, "Data Scientist", url="https://x.com/1", match_reasons=reasons)
        row = db.execute("SELECT match_reasons FROM job_listings WHERE id = ?", (result["id"],)).fetchone()
        assert json.loads(row["match_reasons"]) == reasons

    def test_upsert_reopens_closed_job(self, db):
        cid = _insert_company(db)
        r = upsert_job(db, cid, "SWE", url="https://x.com/1")
        db.execute("UPDATE job_listings SET status = 'closed' WHERE id = ?", (r["id"],))
        db.commit()
        upsert_job(db, cid, "SWE", url="https://x.com/1")
        row = db.execute("SELECT status FROM job_listings WHERE id = ?", (r["id"],)).fetchone()
        assert row["status"] == "active"

    def test_upsert_preserves_applied_status(self, db):
        cid = _insert_company(db)
        r = upsert_job(db, cid, "SWE", url="https://x.com/1")
        db.execute("UPDATE job_listings SET status = 'applied' WHERE id = ?", (r["id"],))
        db.commit()
        upsert_job(db, cid, "SWE", url="https://x.com/1")
        row = db.execute("SELECT status FROM job_listings WHERE id = ?", (r["id"],)).fetchone()
        assert row["status"] == "applied"


class TestStaleMarking:
    def test_marks_missing_jobs_stale(self, db):
        cid = _insert_company(db)
        upsert_job(db, cid, "Job A", url="https://x.com/a")
        upsert_job(db, cid, "Job B", url="https://x.com/b")
        stale_count = mark_stale_jobs(db, cid, {"https://x.com/a"})
        assert stale_count == 1
        row = db.execute("SELECT status FROM job_listings WHERE url = 'https://x.com/b'").fetchone()
        assert row["status"] == "closed"

    def test_no_stale_when_all_active(self, db):
        cid = _insert_company(db)
        upsert_job(db, cid, "Job A", url="https://x.com/a")
        stale_count = mark_stale_jobs(db, cid, {"https://x.com/a"})
        assert stale_count == 0


class TestGetJobs:
    def test_get_all_jobs(self, db):
        cid = _insert_company(db)
        upsert_job(db, cid, "Job A", url="https://x.com/a", relevance_score=8.0)
        upsert_job(db, cid, "Job B", url="https://x.com/b", relevance_score=5.0)
        jobs = get_jobs(db)
        assert len(jobs) == 2
        assert jobs[0]["relevance_score"] >= jobs[1]["relevance_score"]

    def test_filter_by_status(self, db):
        cid = _insert_company(db)
        upsert_job(db, cid, "Job A", url="https://x.com/a")
        r = upsert_job(db, cid, "Job B", url="https://x.com/b")
        update_job_status(db, r["id"], "applied")
        jobs = get_jobs(db, status="applied")
        assert len(jobs) == 1
        assert jobs[0]["title"] == "Job B"

    def test_filter_by_min_relevance(self, db):
        cid = _insert_company(db)
        upsert_job(db, cid, "Job A", url="https://x.com/a", relevance_score=3.0)
        upsert_job(db, cid, "Job B", url="https://x.com/b", relevance_score=8.0)
        jobs = get_jobs(db, min_relevance=7.0)
        assert len(jobs) == 1
        assert jobs[0]["title"] == "Job B"

    def test_filter_by_company(self, db):
        cid1 = _insert_company(db, "CompanyA")
        cid2 = _insert_company(db, "CompanyB")
        upsert_job(db, cid1, "Job A", url="https://a.com/1")
        upsert_job(db, cid2, "Job B", url="https://b.com/1")
        jobs = get_jobs(db, company_id=cid1)
        assert len(jobs) == 1
        assert jobs[0]["company_name"] == "CompanyA"


class TestNewJobsSince:
    def test_gets_recent_jobs(self, db):
        cid = _insert_company(db)
        upsert_job(db, cid, "New Job", url="https://x.com/new", relevance_score=7.0)
        jobs = get_new_jobs_since(db, "2020-01-01")
        assert len(jobs) >= 1

    def test_respects_min_relevance(self, db):
        cid = _insert_company(db)
        upsert_job(db, cid, "Low", url="https://x.com/low", relevance_score=2.0)
        upsert_job(db, cid, "High", url="https://x.com/high", relevance_score=8.0)
        jobs = get_new_jobs_since(db, "2020-01-01", min_relevance=7.0)
        assert len(jobs) == 1
        assert jobs[0]["title"] == "High"


class TestJobStatus:
    def test_update_status(self, db):
        cid = _insert_company(db)
        r = upsert_job(db, cid, "Job", url="https://x.com/1")
        assert update_job_status(db, r["id"], "applied") is True
        row = db.execute("SELECT status FROM job_listings WHERE id = ?", (r["id"],)).fetchone()
        assert row["status"] == "applied"

    def test_update_nonexistent_returns_false(self, db):
        assert update_job_status(db, 99999, "applied") is False

    def test_get_job_by_id(self, db):
        cid = _insert_company(db)
        r = upsert_job(db, cid, "Data Engineer", url="https://x.com/1")
        job = get_job_by_id(db, r["id"])
        assert job is not None
        assert job["title"] == "Data Engineer"
        assert job["company_name"] == "TestCo"

    def test_get_nonexistent_job(self, db):
        assert get_job_by_id(db, 99999) is None
