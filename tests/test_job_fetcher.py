"""Tests for the single-URL job fetcher/extractor."""

from unittest.mock import MagicMock, patch

import pytest

from beacon.research.job_fetcher import (
    _extract_heuristic,
    _extract_jsonld,
    detect_platform,
    fetch_job_from_url,
)

JSONLD_HTML = """
<html><head>
<script type="application/ld+json">
{
    "@context": "https://schema.org/",
    "@type": "JobPosting",
    "title": "Senior AI Engineer",
    "url": "https://example.com/jobs/42",
    "datePosted": "2026-03-15",
    "hiringOrganization": {"@type": "Organization", "name": "Acme AI"},
    "jobLocation": {
        "@type": "Place",
        "address": {
            "@type": "PostalAddress",
            "addressLocality": "San Francisco",
            "addressRegion": "CA",
            "addressCountry": "US"
        }
    },
    "description": "<p>Build <strong>LLM agents</strong> with Python and TypeScript.</p>"
}
</script>
</head><body><h1>Careers</h1></body></html>
"""

GRAPH_JSONLD_HTML = """
<html><head>
<script type="application/ld+json">
{
    "@context": "https://schema.org/",
    "@graph": [
        {"@type": "Organization", "name": "Foo Corp"},
        {"@type": "JobPosting", "title": "Staff Engineer",
         "hiringOrganization": {"name": "Foo Corp"},
         "description": "Lead platform work."}
    ]
}
</script>
</head><body></body></html>
"""

HEURISTIC_HTML = """
<html><head>
<title>Machine Learning Engineer - MegaCo</title>
<meta property="og:title" content="Machine Learning Engineer" />
<meta property="og:site_name" content="MegaCo" />
<meta property="og:description" content="Build ML systems at scale." />
</head><body>
<h1>Machine Learning Engineer</h1>
<div class="job-description">Detailed body goes here.</div>
</body></html>
"""


class TestDetectPlatform:
    def test_greenhouse(self):
        assert detect_platform("https://boards.greenhouse.io/acme/jobs/123") == "greenhouse"
        assert detect_platform("https://job-boards.greenhouse.io/acme/jobs/123") == "greenhouse"

    def test_lever(self):
        assert detect_platform("https://jobs.lever.co/acme/uuid") == "lever"

    def test_ashby(self):
        assert detect_platform("https://jobs.ashbyhq.com/acme/uuid") == "ashby"

    def test_workday_subdomain(self):
        assert (
            detect_platform("https://acme.wd1.myworkdayjobs.com/en-US/jobs/details/X")
            == "workday"
        )

    def test_linkedin(self):
        assert detect_platform("https://www.linkedin.com/jobs/view/12345") == "linkedin"

    def test_unknown(self):
        assert detect_platform("https://careers.acme.io/positions/42") is None
        assert detect_platform("not a url") is None


class TestExtractJsonLD:
    def test_basic_jobposting(self):
        extracted = _extract_jsonld(JSONLD_HTML)
        assert extracted is not None
        assert extracted["title"] == "Senior AI Engineer"
        assert extracted["company"] == "Acme AI"
        assert extracted["url"] == "https://example.com/jobs/42"
        assert "San Francisco" in extracted["location"]
        assert extracted["date_posted"] == "2026-03-15"
        assert "LLM agents" in extracted["description_text"]
        # HTML tags should be stripped
        assert "<p>" not in extracted["description_text"]

    def test_graph_container(self):
        extracted = _extract_jsonld(GRAPH_JSONLD_HTML)
        assert extracted is not None
        assert extracted["title"] == "Staff Engineer"
        assert extracted["company"] == "Foo Corp"

    def test_no_jsonld(self):
        assert _extract_jsonld("<html><body>no structured data</body></html>") is None

    def test_malformed_jsonld_is_skipped(self):
        html = '<html><head><script type="application/ld+json">not json{</script></head></html>'
        assert _extract_jsonld(html) is None


class TestExtractHeuristic:
    def test_opengraph_preferred(self):
        extracted = _extract_heuristic(HEURISTIC_HTML, "https://megaco.com/jobs/1")
        assert extracted["title"] == "Machine Learning Engineer"
        assert extracted["company"] == "MegaCo"
        assert "Build ML systems" in extracted["description_text"]
        assert extracted["url"] == "https://megaco.com/jobs/1"

    def test_title_fallback_to_h1_strips_suffix(self):
        html = "<html><head><title>ML Engineer | MegaCo</title></head><body></body></html>"
        extracted = _extract_heuristic(html, "https://x.com/1")
        assert extracted["title"] == "ML Engineer"

    def test_description_container_fallback(self):
        html = (
            "<html><head></head><body>"
            "<div class='job-description-body'>Specific duties here.</div>"
            "</body></html>"
        )
        extracted = _extract_heuristic(html, "https://x.com/1")
        assert "Specific duties" in extracted["description_text"]


class TestFetchJobFromUrl:
    @patch("httpx.get")
    def test_uses_jsonld(self, mock_get):
        resp = MagicMock()
        resp.text = JSONLD_HTML
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        out = fetch_job_from_url("https://boards.greenhouse.io/acme/jobs/42")
        assert out["title"] == "Senior AI Engineer"
        assert out["company"] == "Acme AI"
        assert out["platform"] == "greenhouse"
        assert out["date_posted"] == "2026-03-15"

    @patch("httpx.get")
    def test_heuristic_fallback(self, mock_get):
        resp = MagicMock()
        resp.text = HEURISTIC_HTML
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        out = fetch_job_from_url("https://megaco.com/jobs/1")
        assert out["title"] == "Machine Learning Engineer"
        assert out["company"] == "MegaCo"
        assert out["platform"] is None

    @patch("httpx.get")
    def test_http_error_raises_runtime(self, mock_get):
        import httpx as _httpx

        mock_get.side_effect = _httpx.ConnectError("nope")
        with pytest.raises(RuntimeError, match="Failed to fetch"):
            fetch_job_from_url("https://example.com/broken")

    @patch("httpx.get")
    def test_url_fallback_to_input(self, mock_get):
        """If JSON-LD omits url, returned dict uses the input URL."""
        html = (
            '<html><head><script type="application/ld+json">'
            '{"@type":"JobPosting","title":"T","hiringOrganization":{"name":"C"},'
            '"description":"D"}'
            "</script></head><body></body></html>"
        )
        resp = MagicMock()
        resp.text = html
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        out = fetch_job_from_url("https://foo.com/jobs/9")
        assert out["url"] == "https://foo.com/jobs/9"
