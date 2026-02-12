"""Generic scraper adapter — best-effort HTML extraction for custom career pages."""

import re

import httpx

from beacon.scrapers.base import BaseAdapter


class GenericScraperAdapter(BaseAdapter):
    """Best-effort scraper for career pages without a known API.

    Strategies tried in order:
    1. JSON-LD structured data
    2. Common job link patterns (href containing /jobs/, /careers/, /positions/)
    3. CSS class heuristics for job listings
    """

    def fetch_jobs(self, company: dict) -> list[dict]:
        """Scrape jobs from a company's careers page using heuristics.

        Returns whatever jobs can be extracted; may return empty list for
        JS-heavy pages (Workday, etc.) since we don't use a browser engine.
        """
        careers_url = company.get("careers_url")
        if not careers_url:
            return []

        try:
            resp = httpx.get(careers_url, timeout=30, follow_redirects=True)
            resp.raise_for_status()
        except (httpx.HTTPError, httpx.TimeoutException):
            return []

        html = resp.text
        jobs = []

        # Strategy 1: JSON-LD
        jobs = self._extract_jsonld(html, careers_url)
        if jobs:
            return jobs

        # Strategy 2: Link patterns
        jobs = self._extract_job_links(html, careers_url)
        return jobs

    def _extract_jsonld(self, html: str, base_url: str) -> list[dict]:
        """Extract jobs from JSON-LD structured data."""
        try:
            import json

            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")
            scripts = soup.find_all("script", type="application/ld+json")

            jobs = []
            for script in scripts:
                try:
                    data = json.loads(script.string or "")
                except (json.JSONDecodeError, TypeError):
                    continue

                items = []
                if isinstance(data, list):
                    items = data
                elif isinstance(data, dict):
                    if data.get("@type") == "JobPosting":
                        items = [data]
                    elif data.get("@type") == "ItemList":
                        items = data.get("itemListElement", [])

                for item in items:
                    if isinstance(item, dict) and item.get("@type") == "JobPosting":
                        jobs.append(self._normalize_jsonld(item))
                    elif isinstance(item, dict) and item.get("item", {}).get("@type") == "JobPosting":
                        jobs.append(self._normalize_jsonld(item["item"]))

            return jobs
        except ImportError:
            return []

    def _normalize_jsonld(self, data: dict) -> dict:
        """Normalize a JSON-LD JobPosting to our standard format."""
        location = ""
        job_location = data.get("jobLocation", {})
        if isinstance(job_location, dict):
            address = job_location.get("address", {})
            if isinstance(address, dict):
                parts = [address.get("addressLocality", ""), address.get("addressRegion", "")]
                location = ", ".join(p for p in parts if p)
            elif isinstance(address, str):
                location = address
        elif isinstance(job_location, list) and job_location:
            first = job_location[0]
            if isinstance(first, dict):
                address = first.get("address", {})
                if isinstance(address, dict):
                    parts = [address.get("addressLocality", ""), address.get("addressRegion", "")]
                    location = ", ".join(p for p in parts if p)

        date_posted = data.get("datePosted", "")
        if date_posted:
            date_posted = date_posted[:10]

        description = data.get("description", "")
        if "<" in description:
            try:
                from bs4 import BeautifulSoup
                description = BeautifulSoup(description, "html.parser").get_text(separator=" ", strip=True)
            except ImportError:
                description = re.sub(r"<[^>]+>", " ", description).strip()

        return {
            "title": data.get("title", ""),
            "url": data.get("url", ""),
            "location": location,
            "department": (
                data.get("employmentUnit", {}).get("name", "")
                if isinstance(data.get("employmentUnit"), dict) else ""
            ),
            "description_text": description[:5000],
            "date_posted": date_posted or None,
        }

    def _extract_job_links(self, html: str, base_url: str) -> list[dict]:
        """Extract jobs from common link patterns on career pages."""
        try:
            from urllib.parse import urljoin

            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")
            job_patterns = re.compile(
                r"/(jobs?|careers?|positions?|openings?|roles?)/[a-zA-Z0-9\-_]+",
                re.IGNORECASE,
            )

            seen_urls = set()
            jobs = []

            for link in soup.find_all("a", href=True):
                href = link["href"]
                if not job_patterns.search(href):
                    continue

                full_url = urljoin(base_url, href)
                if full_url in seen_urls:
                    continue
                seen_urls.add(full_url)

                title = link.get_text(strip=True)
                if not title or len(title) < 3 or len(title) > 200:
                    continue

                # Skip navigation-style links
                if title.lower() in {"apply", "learn more", "view", "see all", "back", "home", "jobs", "careers"}:
                    continue

                jobs.append({
                    "title": title,
                    "url": full_url,
                    "location": "",
                    "department": "",
                    "description_text": "",
                    "date_posted": None,
                })

            return jobs
        except ImportError:
            return []
