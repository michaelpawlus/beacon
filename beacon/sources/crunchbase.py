"""Crunchbase source adapter.

Uses the Crunchbase v4 API (https://data.crunchbase.com/docs). The Basic/free
tier is field-restricted but enough for the v0.1 contract — name, domain,
careers URL (when present), HQ location, industry, founding year. Anything
richer (signals about specific AI tools, leadership statements) waits for
post-promotion enrichment via the existing signal-gathering tools.

The adapter is intentionally tolerant of upstream schema drift: only `name`
and a stable identifier (`uuid` / `permalink`) are required. Missing fields
become `None`.

Auth: `CRUNCHBASE_API_KEY` env var. Missing key → `SourceAuthError`.

Rate limiting: a small sleep+jitter between pages stays well under the Basic
tier's documented QPS. Override with `request_delay_seconds=` for tests.
"""

from __future__ import annotations

import os
import random
import time
from collections.abc import Iterable
from typing import Any

import httpx

from beacon.sources.base import (
    Candidate,
    SourceAdapter,
    SourceAuthError,
    SourceFetchError,
)

CB_API_BASE = "https://api.crunchbase.com/api/v4"
CB_SEARCH_PATH = "/searches/organizations"

DEFAULT_INDUSTRY_TAGS = (
    "artificial-intelligence",
    "machine-learning",
    "developer-tools",
)
DEFAULT_MIN_FOUNDED_YEAR = 2018
DEFAULT_LAST_FUNDING_MONTHS = 18
DEFAULT_PAGE_SIZE = 50
REQUEST_DELAY_SECONDS = 0.6      # ~1.6 req/sec average
REQUEST_JITTER_SECONDS = 0.3


class CrunchbaseAdapter(SourceAdapter):
    name = "crunchbase"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        industry_tags: tuple[str, ...] = DEFAULT_INDUSTRY_TAGS,
        min_founded_year: int = DEFAULT_MIN_FOUNDED_YEAR,
        last_funding_months: int = DEFAULT_LAST_FUNDING_MONTHS,
        page_size: int = DEFAULT_PAGE_SIZE,
        request_delay_seconds: float = REQUEST_DELAY_SECONDS,
        request_jitter_seconds: float = REQUEST_JITTER_SECONDS,
    ) -> None:
        self.api_key = api_key or os.environ.get("CRUNCHBASE_API_KEY")
        self.industry_tags = industry_tags
        self.min_founded_year = min_founded_year
        self.last_funding_months = last_funding_months
        self.page_size = page_size
        self.request_delay_seconds = request_delay_seconds
        self.request_jitter_seconds = request_jitter_seconds

    def fetch(self, limit: int | None = None) -> Iterable[Candidate]:
        if not self.api_key:
            raise SourceAuthError("CRUNCHBASE_API_KEY unset")

        page_size = self.page_size
        if limit is not None:
            page_size = min(page_size, limit)

        yielded = 0
        after_id: str | None = None

        while True:
            page_size_request = page_size
            if limit is not None:
                page_size_request = min(page_size_request, limit - yielded)
                if page_size_request <= 0:
                    return

            body = self._build_search_body(page_size_request, after_id)
            try:
                response = httpx.post(
                    f"{CB_API_BASE}{CB_SEARCH_PATH}",
                    headers={
                        "X-cb-user-key": self.api_key,
                        "Content-Type": "application/json",
                    },
                    json=body,
                    timeout=30.0,
                )
                response.raise_for_status()
            except httpx.HTTPError as e:
                raise SourceFetchError(f"Crunchbase request failed: {e}") from e

            payload = response.json()
            entities = payload.get("entities") or []
            if not entities:
                return

            for entity in entities:
                cand = self._entity_to_candidate(entity)
                if cand is None:
                    continue
                yield cand
                yielded += 1
                if limit is not None and yielded >= limit:
                    return

            if len(entities) < page_size_request:
                return
            after_id = entities[-1].get("uuid") or entities[-1].get("permalink")
            if not after_id:
                return

            # Polite delay between pages.
            time.sleep(
                self.request_delay_seconds
                + random.uniform(0, self.request_jitter_seconds)
            )

    # ----- helpers -----

    def _build_search_body(self, page_size: int, after_id: str | None) -> dict[str, Any]:
        body: dict[str, Any] = {
            "field_ids": [
                "identifier",
                "name",
                "short_description",
                "website",
                "linkedin",
                "location_identifiers",
                "category_groups",
                "categories",
                "founded_on",
                "last_funding_at",
            ],
            "query": [
                {
                    "type": "predicate",
                    "field_id": "category_groups",
                    "operator_id": "includes",
                    "values": list(self.industry_tags),
                },
                {
                    "type": "predicate",
                    "field_id": "founded_on",
                    "operator_id": "gte",
                    "values": [f"{self.min_founded_year}-01-01"],
                },
            ],
            "order": [
                {"field_id": "last_funding_at", "sort": "desc"}
            ],
            "limit": page_size,
        }
        if after_id:
            body["after_id"] = after_id
        return body

    @staticmethod
    def _entity_to_candidate(entity: dict[str, Any]) -> Candidate | None:
        props = entity.get("properties") or entity
        name = props.get("name") or (props.get("identifier") or {}).get("value")
        if not name:
            return None

        source_ref = (
            entity.get("uuid")
            or (props.get("identifier") or {}).get("uuid")
            or (props.get("identifier") or {}).get("permalink")
            or name
        )

        website = props.get("website") or {}
        website_url = website.get("value") if isinstance(website, dict) else website
        domain = _domain_from_url(website_url)

        locations = props.get("location_identifiers") or []
        hq_location = ", ".join(
            loc.get("value")
            for loc in locations
            if isinstance(loc, dict) and loc.get("value")
        ) or None

        categories = props.get("categories") or []
        industry = ", ".join(
            cat.get("value")
            for cat in categories
            if isinstance(cat, dict) and cat.get("value")
        ) or None

        signals: list[dict[str, Any]] = []
        description = props.get("short_description")
        if description:
            signals.append({
                "signal_type": "press_coverage",
                "title": f"Crunchbase profile: {description[:140]}",
                "source_url": _crunchbase_url(source_ref),
                "signal_strength": 2,
            })
        last_funding = props.get("last_funding_at")
        if last_funding:
            signals.append({
                "signal_type": "press_coverage",
                "title": f"Recent funding: {last_funding}",
                "source_url": _crunchbase_url(source_ref),
                "signal_strength": 3,
            })

        return Candidate(
            name=name,
            source="crunchbase",
            source_ref=str(source_ref),
            domain=domain,
            careers_url=None,        # Basic tier doesn't expose; agent fills in post-promotion
            hq_location=hq_location,
            industry=industry,
            signals=signals,
            raw=entity,
        )


def _domain_from_url(url: str | None) -> str | None:
    if not url:
        return None
    cleaned = url.strip()
    for prefix in ("https://", "http://"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):]
            break
    cleaned = cleaned.split("/")[0]
    if cleaned.startswith("www."):
        cleaned = cleaned[4:]
    return cleaned.lower() or None


def _crunchbase_url(ref: str | None) -> str | None:
    if not ref:
        return None
    return f"https://www.crunchbase.com/organization/{ref}"
