"""Tests for the Crunchbase source adapter."""

from unittest.mock import MagicMock, patch

import pytest

from beacon.sources.base import SourceAuthError, SourceFetchError
from beacon.sources.crunchbase import CrunchbaseAdapter, _domain_from_url

SAMPLE_RESPONSE = {
    "entities": [
        {
            "uuid": "uuid-1",
            "properties": {
                "name": "Anthropic",
                "short_description": "AI safety company",
                "website": {"value": "https://www.anthropic.com"},
                "location_identifiers": [{"value": "San Francisco"}],
                "categories": [{"value": "Artificial Intelligence"}, {"value": "Machine Learning"}],
                "founded_on": "2021-01-01",
                "last_funding_at": "2026-01-15",
            },
        },
        {
            "uuid": "uuid-2",
            "properties": {
                "name": "MysteryCo",
                "short_description": "AI for accountants",
                "website": {"value": "http://mystery.io/about"},
                "location_identifiers": [],
                "categories": [],
                "founded_on": "2023-06-01",
                "last_funding_at": "2025-12-01",
            },
        },
    ]
}


def test_missing_key_raises_auth_error(monkeypatch):
    monkeypatch.delenv("CRUNCHBASE_API_KEY", raising=False)
    adapter = CrunchbaseAdapter()
    with pytest.raises(SourceAuthError, match="CRUNCHBASE_API_KEY unset"):
        list(adapter.fetch())


@patch("beacon.sources.crunchbase.httpx.post")
def test_fetch_returns_candidates(mock_post):
    mock_resp = MagicMock()
    mock_resp.json.return_value = SAMPLE_RESPONSE
    mock_resp.raise_for_status = MagicMock()
    mock_post.return_value = mock_resp

    adapter = CrunchbaseAdapter(api_key="test-key", page_size=5)
    candidates = list(adapter.fetch(limit=5))

    assert len(candidates) == 2
    assert candidates[0].name == "Anthropic"
    assert candidates[0].source == "crunchbase"
    assert candidates[0].source_ref == "uuid-1"
    assert candidates[0].domain == "anthropic.com"
    assert candidates[0].hq_location == "San Francisco"
    assert "Artificial Intelligence" in candidates[0].industry


@patch("beacon.sources.crunchbase.httpx.post")
def test_fetch_attaches_signals_from_basic_fields(mock_post):
    mock_resp = MagicMock()
    mock_resp.json.return_value = SAMPLE_RESPONSE
    mock_resp.raise_for_status = MagicMock()
    mock_post.return_value = mock_resp

    adapter = CrunchbaseAdapter(api_key="test-key")
    candidates = list(adapter.fetch(limit=5))

    # Each candidate gets at least the description + funding signals when present.
    anthropic = candidates[0]
    assert len(anthropic.signals) == 2
    titles = [s["title"] for s in anthropic.signals]
    assert any("AI safety company" in t for t in titles)
    assert any("Recent funding: 2026-01-15" in t for t in titles)


@patch("beacon.sources.crunchbase.httpx.post")
def test_fetch_respects_limit(mock_post):
    mock_resp = MagicMock()
    mock_resp.json.return_value = SAMPLE_RESPONSE
    mock_resp.raise_for_status = MagicMock()
    mock_post.return_value = mock_resp

    adapter = CrunchbaseAdapter(api_key="test-key")
    candidates = list(adapter.fetch(limit=1))
    assert len(candidates) == 1


@patch("beacon.sources.crunchbase.httpx.post")
def test_http_error_raises_fetch_error(mock_post):
    import httpx as _httpx

    mock_post.side_effect = _httpx.ConnectError("network down")
    adapter = CrunchbaseAdapter(api_key="test-key")
    with pytest.raises(SourceFetchError, match="Crunchbase request failed"):
        list(adapter.fetch(limit=5))


@patch("beacon.sources.crunchbase.httpx.post")
def test_fetch_handles_empty_entities(mock_post):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"entities": []}
    mock_resp.raise_for_status = MagicMock()
    mock_post.return_value = mock_resp

    adapter = CrunchbaseAdapter(api_key="test-key")
    candidates = list(adapter.fetch())
    assert candidates == []


class TestDomainFromUrl:
    def test_strips_https(self):
        assert _domain_from_url("https://example.com") == "example.com"

    def test_strips_www(self):
        assert _domain_from_url("https://www.example.com") == "example.com"

    def test_strips_path(self):
        assert _domain_from_url("https://example.com/about") == "example.com"

    def test_none_in_none_out(self):
        assert _domain_from_url(None) is None

    def test_lowercases(self):
        assert _domain_from_url("https://EXAMPLE.com") == "example.com"
