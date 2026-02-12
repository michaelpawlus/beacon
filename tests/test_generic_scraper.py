"""Tests for the generic (BeautifulSoup) career page scraper."""

import json
from unittest.mock import MagicMock, patch

from beacon.scrapers.generic import GenericScraperAdapter

JSONLD_HTML = """
<html>
<head>
<script type="application/ld+json">
{
    "@type": "JobPosting",
    "title": "Senior Data Engineer",
    "url": "https://example.com/jobs/123",
    "datePosted": "2025-03-01",
    "jobLocation": {
        "@type": "Place",
        "address": {
            "addressLocality": "San Francisco",
            "addressRegion": "CA"
        }
    },
    "description": "<p>Build data pipelines with Python and SQL.</p>"
}
</script>
</head>
<body><h1>Careers</h1></body>
</html>
"""

LINK_HTML = """
<html>
<body>
<h1>Careers at TestCo</h1>
<a href="/jobs/data-engineer">Senior Data Engineer</a>
<a href="/jobs/ml-engineer">ML Engineer</a>
<a href="/careers/office-manager">Office Manager</a>
<a href="/about">About Us</a>
<a href="/jobs/apply">Apply</a>
</body>
</html>
"""

EMPTY_HTML = """
<html>
<body>
<h1>No jobs here</h1>
<p>Check back later.</p>
</body>
</html>
"""


class TestGenericScraperJsonLD:
    @patch("beacon.scrapers.generic.httpx.get")
    def test_extracts_jsonld_job(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.text = JSONLD_HTML
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        adapter = GenericScraperAdapter()
        jobs = adapter.fetch_jobs({"careers_url": "https://example.com/careers", "domain": "example.com"})

        assert len(jobs) == 1
        assert jobs[0]["title"] == "Senior Data Engineer"
        assert jobs[0]["url"] == "https://example.com/jobs/123"
        assert "San Francisco" in jobs[0]["location"]
        assert jobs[0]["date_posted"] == "2025-03-01"
        assert "data pipelines" in jobs[0]["description_text"].lower()

    @patch("beacon.scrapers.generic.httpx.get")
    def test_jsonld_list(self, mock_get):
        jsonld_list = json.dumps([
            {"@type": "JobPosting", "title": "Job A", "url": "https://x.com/a"},
            {"@type": "JobPosting", "title": "Job B", "url": "https://x.com/b"},
        ])
        html = f'<html><head><script type="application/ld+json">{jsonld_list}</script></head><body></body></html>'
        mock_resp = MagicMock()
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        adapter = GenericScraperAdapter()
        jobs = adapter.fetch_jobs({"careers_url": "https://x.com/careers", "domain": "x.com"})
        assert len(jobs) == 2


class TestGenericScraperLinks:
    @patch("beacon.scrapers.generic.httpx.get")
    def test_extracts_job_links(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.text = LINK_HTML
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        adapter = GenericScraperAdapter()
        jobs = adapter.fetch_jobs({"careers_url": "https://testco.com/careers", "domain": "testco.com"})

        titles = [j["title"] for j in jobs]
        assert "Senior Data Engineer" in titles
        assert "ML Engineer" in titles
        assert "Office Manager" in titles
        # "Apply" and "About Us" should be excluded
        assert "Apply" not in titles
        assert "About Us" not in titles


class TestGenericScraperEdgeCases:
    @patch("beacon.scrapers.generic.httpx.get")
    def test_empty_page(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.text = EMPTY_HTML
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        adapter = GenericScraperAdapter()
        jobs = adapter.fetch_jobs({"careers_url": "https://empty.com/careers", "domain": "empty.com"})
        assert jobs == []

    @patch("beacon.scrapers.generic.httpx.get")
    def test_timeout_returns_empty(self, mock_get):
        import httpx
        mock_get.side_effect = httpx.TimeoutException("Connection timed out")

        adapter = GenericScraperAdapter()
        jobs = adapter.fetch_jobs({"careers_url": "https://slow.com/careers", "domain": "slow.com"})
        assert jobs == []

    def test_no_careers_url_returns_empty(self):
        adapter = GenericScraperAdapter()
        jobs = adapter.fetch_jobs({"domain": "nocareers.com"})
        assert jobs == []

    @patch("beacon.scrapers.generic.httpx.get")
    def test_http_error_returns_empty(self, mock_get):
        import httpx
        mock_get.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=MagicMock()
        )

        adapter = GenericScraperAdapter()
        jobs = adapter.fetch_jobs({"careers_url": "https://broken.com/careers", "domain": "broken.com"})
        assert jobs == []
