"""Greenhouse adapter — fetches jobs from the public Greenhouse boards API."""

import httpx

from beacon.scrapers.base import BaseAdapter
from beacon.scrapers.tokens import get_board_token

API_BASE = "https://boards-api.greenhouse.io/v1/boards"


class GreenhouseAdapter(BaseAdapter):
    """Adapter for companies using Greenhouse ATS."""

    def fetch_jobs(self, company: dict) -> list[dict]:
        """Fetch jobs from the Greenhouse boards API.

        Args:
            company: Must have 'domain' and 'careers_platform' keys.

        Returns:
            Normalized list of job dicts.

        Raises:
            ValueError: If no board token found for this company.
            httpx.HTTPStatusError: On API errors.
        """
        token = get_board_token("greenhouse", company["domain"])
        if not token:
            raise ValueError(f"No Greenhouse token for domain: {company['domain']}")

        url = f"{API_BASE}/{token}/jobs"
        resp = httpx.get(url, params={"content": "true"}, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        return [self._normalize(job, token) for job in data.get("jobs", [])]

    def _normalize(self, raw: dict, token: str) -> dict:
        """Normalize a Greenhouse job object to our standard format."""
        location = ""
        if raw.get("location"):
            location = raw["location"].get("name", "")

        departments = raw.get("departments", [])
        department = departments[0]["name"] if departments else ""

        # Extract plain text from HTML content
        content = raw.get("content", "")
        description_text = _strip_html(content) if content else ""

        date_posted = None
        if raw.get("updated_at"):
            date_posted = raw["updated_at"][:10]

        return {
            "title": raw.get("title", ""),
            "url": raw.get("absolute_url", ""),
            "location": location,
            "department": department,
            "description_text": description_text[:5000],
            "date_posted": date_posted,
        }


def _strip_html(html: str) -> str:
    """Remove HTML tags to get plain text."""
    try:
        from bs4 import BeautifulSoup
        return BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)
    except ImportError:
        import re
        return re.sub(r"<[^>]+>", " ", html).strip()
