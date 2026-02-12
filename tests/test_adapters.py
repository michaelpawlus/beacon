"""Tests for career page adapters (Greenhouse, Lever, Ashby, registry)."""

from unittest.mock import MagicMock, patch

import pytest

from beacon.scrapers.ashby import AshbyAdapter
from beacon.scrapers.base import BaseAdapter
from beacon.scrapers.greenhouse import GreenhouseAdapter, _strip_html
from beacon.scrapers.lever import LeverAdapter
from beacon.scrapers.registry import get_adapter
from beacon.scrapers.tokens import GREENHOUSE_TOKENS, get_board_token

# --- ABC enforcement ---

class TestBaseAdapter:
    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            BaseAdapter()

    def test_concrete_subclass_works(self):
        class FakeAdapter(BaseAdapter):
            def fetch_jobs(self, company):
                return []
        adapter = FakeAdapter()
        assert adapter.fetch_jobs({}) == []


# --- Token mapping ---

class TestTokens:
    def test_greenhouse_token_lookup(self):
        assert get_board_token("greenhouse", "anthropic.com") == "anthropic"
        assert get_board_token("greenhouse", "openai.com") == "openai"

    def test_unknown_domain_returns_none(self):
        assert get_board_token("greenhouse", "unknown-corp.com") is None

    def test_non_greenhouse_returns_none(self):
        assert get_board_token("lever", "anthropic.com") is None

    def test_all_tokens_are_strings(self):
        for domain, token in GREENHOUSE_TOKENS.items():
            assert isinstance(domain, str)
            assert isinstance(token, str)
            assert len(token) > 0


# --- Registry ---

class TestRegistry:
    def test_greenhouse_adapter(self):
        adapter = get_adapter("greenhouse")
        assert isinstance(adapter, GreenhouseAdapter)

    def test_lever_adapter(self):
        adapter = get_adapter("lever")
        assert isinstance(adapter, LeverAdapter)

    def test_ashby_adapter(self):
        adapter = get_adapter("ashby")
        assert isinstance(adapter, AshbyAdapter)

    def test_unknown_platform_returns_none(self):
        assert get_adapter("workday") is None

    def test_custom_returns_generic(self):
        adapter = get_adapter("custom")
        assert adapter is not None


# --- Greenhouse adapter ---

SAMPLE_GREENHOUSE_RESPONSE = {
    "jobs": [
        {
            "id": 12345,
            "title": "Senior Data Engineer",
            "absolute_url": "https://boards.greenhouse.io/test/jobs/12345",
            "updated_at": "2025-03-15T10:00:00Z",
            "location": {"name": "San Francisco, CA"},
            "departments": [{"name": "Engineering"}],
            "content": "<p>We are looking for a <strong>data engineer</strong>.</p>",
        },
        {
            "id": 67890,
            "title": "ML Engineer",
            "absolute_url": "https://boards.greenhouse.io/test/jobs/67890",
            "updated_at": "2025-03-10T10:00:00Z",
            "location": {"name": "Remote"},
            "departments": [],
            "content": "",
        },
    ]
}


class TestGreenhouseAdapter:
    def test_normalize_job(self):
        adapter = GreenhouseAdapter()
        result = adapter._normalize(SAMPLE_GREENHOUSE_RESPONSE["jobs"][0], "test")
        assert result["title"] == "Senior Data Engineer"
        assert result["url"] == "https://boards.greenhouse.io/test/jobs/12345"
        assert result["location"] == "San Francisco, CA"
        assert result["department"] == "Engineering"
        assert "data engineer" in result["description_text"]
        assert result["date_posted"] == "2025-03-15"

    def test_normalize_job_no_department(self):
        adapter = GreenhouseAdapter()
        result = adapter._normalize(SAMPLE_GREENHOUSE_RESPONSE["jobs"][1], "test")
        assert result["department"] == ""

    @patch("beacon.scrapers.greenhouse.httpx.get")
    def test_fetch_jobs(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = SAMPLE_GREENHOUSE_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        adapter = GreenhouseAdapter()
        company = {"domain": "anthropic.com", "careers_platform": "greenhouse"}
        jobs = adapter.fetch_jobs(company)

        assert len(jobs) == 2
        assert jobs[0]["title"] == "Senior Data Engineer"
        mock_get.assert_called_once()

    def test_fetch_jobs_no_token(self):
        adapter = GreenhouseAdapter()
        with pytest.raises(ValueError, match="No Greenhouse token"):
            adapter.fetch_jobs({"domain": "unknown.com", "careers_platform": "greenhouse"})

    @patch("beacon.scrapers.greenhouse.httpx.get")
    def test_fetch_jobs_empty_response(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"jobs": []}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        adapter = GreenhouseAdapter()
        jobs = adapter.fetch_jobs({"domain": "anthropic.com"})
        assert jobs == []


class TestStripHtml:
    def test_strips_tags(self):
        assert "hello world" in _strip_html("<p>hello <b>world</b></p>")

    def test_handles_empty(self):
        assert _strip_html("") == ""


# --- Lever adapter ---

SAMPLE_LEVER_RESPONSE = [
    {
        "id": "abc-123",
        "text": "Data Scientist",
        "hostedUrl": "https://jobs.lever.co/test/abc-123",
        "createdAt": 1710460800000,
        "categories": {
            "location": "New York, NY",
            "department": "Data",
            "team": "Analytics",
        },
        "descriptionPlain": "We need a data scientist who loves ML.",
    },
    {
        "id": "def-456",
        "text": "Backend Engineer",
        "hostedUrl": "https://jobs.lever.co/test/def-456",
        "createdAt": 1710374400000,
        "categories": {
            "location": "Remote",
            "department": "",
            "team": "Platform",
        },
        "descriptionPlain": "",
    },
]


class TestLeverAdapter:
    def test_normalize_job(self):
        adapter = LeverAdapter()
        result = adapter._normalize(SAMPLE_LEVER_RESPONSE[0])
        assert result["title"] == "Data Scientist"
        assert result["url"] == "https://jobs.lever.co/test/abc-123"
        assert result["location"] == "New York, NY"
        assert result["department"] == "Data"
        assert "data scientist" in result["description_text"].lower()
        assert result["date_posted"] == "2024-03-15"

    def test_normalize_job_fallback_team(self):
        adapter = LeverAdapter()
        result = adapter._normalize(SAMPLE_LEVER_RESPONSE[1])
        assert result["department"] == "Platform"

    @patch("beacon.scrapers.lever.httpx.get")
    def test_fetch_jobs(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = SAMPLE_LEVER_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        adapter = LeverAdapter()
        jobs = adapter.fetch_jobs({"domain": "testco.com"})
        assert len(jobs) == 2
        assert jobs[0]["title"] == "Data Scientist"


# --- Ashby adapter ---

SAMPLE_ASHBY_RESPONSE = {
    "jobs": [
        {
            "id": "job-001",
            "title": "Platform Engineer",
            "jobUrl": "https://jobs.ashbyhq.com/testco/job-001",
            "location": "San Francisco, CA",
            "department": "Infrastructure",
            "descriptionPlain": "Build scalable infrastructure.",
            "publishedAt": "2025-02-20T00:00:00Z",
        },
        {
            "id": "job-002",
            "title": "Product Designer",
            "jobUrl": "",
            "location": "Remote",
            "department": "",
            "descriptionPlain": "",
            "publishedAt": None,
            "boardSlug": "testco",
        },
    ]
}


class TestAshbyAdapter:
    def test_normalize_job(self):
        adapter = AshbyAdapter()
        result = adapter._normalize(SAMPLE_ASHBY_RESPONSE["jobs"][0])
        assert result["title"] == "Platform Engineer"
        assert result["url"] == "https://jobs.ashbyhq.com/testco/job-001"
        assert result["location"] == "San Francisco, CA"
        assert result["department"] == "Infrastructure"
        assert result["date_posted"] == "2025-02-20"

    def test_normalize_job_fallback_url(self):
        adapter = AshbyAdapter()
        result = adapter._normalize(SAMPLE_ASHBY_RESPONSE["jobs"][1])
        assert "job-002" in result["url"]

    @patch("beacon.scrapers.ashby.httpx.get")
    def test_fetch_jobs(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = SAMPLE_ASHBY_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        adapter = AshbyAdapter()
        jobs = adapter.fetch_jobs({"domain": "testco.com"})
        assert len(jobs) == 2
        assert jobs[0]["title"] == "Platform Engineer"
