"""Ashby adapter — fetches jobs from the Ashby posting API."""

import httpx

from beacon.scrapers.base import BaseAdapter

API_URL = "https://api.ashbyhq.com/posting-api/job-board"


class AshbyAdapter(BaseAdapter):
    """Adapter for companies using Ashby ATS."""

    def fetch_jobs(self, company: dict) -> list[dict]:
        """Fetch jobs from the Ashby job board API.

        The Ashby slug is derived from the company domain (e.g., 'linear.app' -> 'linear').

        Raises:
            httpx.HTTPStatusError: On API errors.
        """
        slug = company["domain"].split(".")[0]
        url = f"{API_URL}/{slug}"
        resp = httpx.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        return [self._normalize(job) for job in data.get("jobs", [])]

    def _normalize(self, raw: dict) -> dict:
        """Normalize an Ashby posting to our standard format."""
        location = raw.get("location", "")

        department = ""
        if raw.get("department"):
            department = raw["department"]

        description_text = ""
        if raw.get("descriptionPlain"):
            description_text = raw["descriptionPlain"]

        date_posted = None
        if raw.get("publishedAt"):
            date_posted = raw["publishedAt"][:10]

        job_url = raw.get("jobUrl", "")
        if not job_url and raw.get("id"):
            job_url = f"https://jobs.ashbyhq.com/{raw.get('boardSlug', '')}/{raw['id']}"

        return {
            "title": raw.get("title", ""),
            "url": job_url,
            "location": location,
            "department": department,
            "description_text": description_text[:5000],
            "date_posted": date_posted,
        }
