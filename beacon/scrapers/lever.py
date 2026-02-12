"""Lever adapter — fetches jobs from the Lever public postings API."""

import httpx

from beacon.scrapers.base import BaseAdapter

API_BASE = "https://api.lever.co/v0/postings"


class LeverAdapter(BaseAdapter):
    """Adapter for companies using Lever ATS."""

    def fetch_jobs(self, company: dict) -> list[dict]:
        """Fetch jobs from the Lever postings API.

        The Lever slug is derived from the company domain (e.g., 'netflix.com' -> 'netflix').

        Raises:
            httpx.HTTPStatusError: On API errors.
        """
        slug = company["domain"].split(".")[0]
        url = f"{API_BASE}/{slug}"
        resp = httpx.get(url, params={"mode": "json"}, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        return [self._normalize(job) for job in data]

    def _normalize(self, raw: dict) -> dict:
        """Normalize a Lever posting to our standard format."""
        location = ""
        categories = raw.get("categories", {})
        if categories:
            location = categories.get("location", "")

        department = ""
        if categories:
            department = categories.get("department", "") or categories.get("team", "")

        description_text = raw.get("descriptionPlain", "") or ""

        date_posted = None
        if raw.get("createdAt"):
            from datetime import datetime, timezone
            ts = raw["createdAt"] / 1000
            date_posted = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")

        return {
            "title": raw.get("text", ""),
            "url": raw.get("hostedUrl", "") or raw.get("applyUrl", ""),
            "location": location,
            "department": department,
            "description_text": description_text[:5000],
            "date_posted": date_posted,
        }
