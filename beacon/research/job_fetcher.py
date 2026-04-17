"""Fetch and extract a single job listing from a URL.

Used by `beacon job add --fetch`. Strategies tried in order:
1. JSON-LD structured data (JobPosting schema). Works on most modern ATS.
2. Heuristic HTML extraction (OpenGraph meta, h1, description containers).

The scanner adapters under beacon/scrapers/ fetch full listings pages;
this module extracts a single job from a single URL.
"""

from __future__ import annotations

import json
import re
from urllib.parse import urlparse

PLATFORM_HOSTS: dict[str, tuple[str, ...]] = {
    "greenhouse": ("boards.greenhouse.io", "job-boards.greenhouse.io"),
    "lever": ("jobs.lever.co",),
    "ashby": ("jobs.ashbyhq.com",),
    "workday": ("myworkdayjobs.com",),
    "linkedin": ("linkedin.com",),
}


def detect_platform(url: str) -> str | None:
    """Return the job board platform for a URL hostname, or None if unknown."""
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return None
    for platform, hosts in PLATFORM_HOSTS.items():
        for h in hosts:
            if host == h or host.endswith("." + h):
                return platform
    return None


def fetch_job_from_url(url: str, timeout: float = 30.0) -> dict:
    """Fetch a job URL and extract structured details.

    Returns a dict with keys: title, company, location, department,
    description_text, date_posted, platform, url. Missing fields come back
    as empty strings (or None for date_posted/platform).

    Raises:
        ImportError: if scraping deps (httpx, beautifulsoup4) are missing.
        RuntimeError: on network/HTTP failure.
    """
    try:
        import httpx
    except ImportError as e:
        raise ImportError(
            "Scraping dependencies not installed. Run: pip install beacon[scraping]"
        ) from e
    try:
        from bs4 import BeautifulSoup  # noqa: F401
    except ImportError as e:
        raise ImportError(
            "Scraping dependencies not installed. Run: pip install beacon[scraping]"
        ) from e

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; beacon-bot/1.0; +https://github.com/)"
        ),
        "Accept": "text/html,application/xhtml+xml",
    }
    try:
        resp = httpx.get(url, timeout=timeout, follow_redirects=True, headers=headers)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        raise RuntimeError(f"Failed to fetch URL: {e}") from e

    html = resp.text
    platform = detect_platform(url)

    extracted = _extract_jsonld(html)
    if extracted and extracted.get("title"):
        extracted["platform"] = platform
        extracted["url"] = extracted.get("url") or url
        return extracted

    extracted = _extract_heuristic(html, url)
    extracted["platform"] = platform
    return extracted


def _extract_jsonld(html: str) -> dict | None:
    """Extract job details from JSON-LD JobPosting structured data."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    scripts = soup.find_all("script", type="application/ld+json")
    for script in scripts:
        raw = script.string or script.get_text() or ""
        if not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        jobs = _find_jobpostings(data)
        if jobs:
            return _normalize_jsonld(jobs[0])
    return None


def _find_jobpostings(data) -> list[dict]:
    """Recursively collect JobPosting dicts from JSON-LD (handles @graph, ItemList, arrays)."""
    results: list[dict] = []
    if isinstance(data, list):
        for item in data:
            results.extend(_find_jobpostings(item))
    elif isinstance(data, dict):
        if data.get("@type") == "JobPosting":
            results.append(data)
        if "@graph" in data:
            results.extend(_find_jobpostings(data["@graph"]))
        if data.get("@type") == "ItemList":
            for item in data.get("itemListElement", []) or []:
                if isinstance(item, dict) and "item" in item:
                    results.extend(_find_jobpostings(item["item"]))
                else:
                    results.extend(_find_jobpostings(item))
    return results


def _normalize_jsonld(data: dict) -> dict:
    """Normalize a JSON-LD JobPosting dict to beacon's standard shape."""
    from bs4 import BeautifulSoup

    location = ""
    job_location = data.get("jobLocation")
    if isinstance(job_location, dict):
        location = _format_address(job_location.get("address", job_location))
    elif isinstance(job_location, list) and job_location:
        first = job_location[0]
        if isinstance(first, dict):
            location = _format_address(first.get("address", first))
        elif isinstance(first, str):
            location = first
    elif isinstance(job_location, str):
        location = job_location

    date_posted = data.get("datePosted") or ""
    if date_posted:
        date_posted = str(date_posted)[:10]

    description = data.get("description") or ""
    if description and "<" in description:
        description = BeautifulSoup(description, "html.parser").get_text(separator=" ", strip=True)
    description = re.sub(r"\s+", " ", description).strip()

    company = ""
    hiring = data.get("hiringOrganization")
    if isinstance(hiring, dict):
        company = hiring.get("name", "") or ""
    elif isinstance(hiring, str):
        company = hiring

    department = ""
    unit = data.get("employmentUnit")
    if isinstance(unit, dict):
        department = unit.get("name", "") or ""
    elif isinstance(unit, str):
        department = unit

    return {
        "title": (data.get("title") or "").strip(),
        "company": company.strip(),
        "url": (data.get("url") or "").strip(),
        "location": location.strip(),
        "department": department.strip(),
        "description_text": description,
        "date_posted": date_posted or None,
    }


def _format_address(address) -> str:
    """Format a JSON-LD PostalAddress into 'Locality, Region, Country'."""
    if isinstance(address, str):
        return address
    if not isinstance(address, dict):
        return ""
    parts = [
        address.get("addressLocality"),
        address.get("addressRegion"),
        address.get("addressCountry"),
    ]
    return ", ".join(
        p if isinstance(p, str) else (p.get("name", "") if isinstance(p, dict) else "")
        for p in parts
        if p
    )


def _extract_heuristic(html: str, url: str) -> dict:
    """Fallback extraction using OpenGraph + common HTML patterns."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")

    title = _meta(soup, "og:title")
    if not title:
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)
    if not title:
        title_tag = soup.find("title")
        if title_tag:
            title = title_tag.get_text(strip=True)
    title = _strip_site_suffix(title)

    company = _meta(soup, "og:site_name") or ""

    description = _meta(soup, "og:description") or ""
    if not description:
        container = soup.find(
            ["div", "section", "article"],
            attrs={"class": re.compile(r"job.?desc|description|content", re.I)},
        )
        if not container:
            container = soup.find(
                ["div", "section", "article"],
                attrs={"id": re.compile(r"job.?desc|description|content", re.I)},
            )
        if container:
            description = container.get_text(separator=" ", strip=True)
    if not description:
        body = soup.find("body")
        if body:
            description = body.get_text(separator=" ", strip=True)[:5000]
    description = re.sub(r"\s+", " ", description).strip()

    return {
        "title": title,
        "company": company,
        "url": url,
        "location": "",
        "department": "",
        "description_text": description,
        "date_posted": None,
    }


def _meta(soup, key: str) -> str:
    """Read a meta tag by property (og:*) or name."""
    tag = soup.find("meta", attrs={"property": key})
    if tag and tag.get("content"):
        return tag["content"].strip()
    tag = soup.find("meta", attrs={"name": key})
    if tag and tag.get("content"):
        return tag["content"].strip()
    return ""


def _strip_site_suffix(title: str) -> str:
    """Trim trailing ' - Company' / ' | Company' / ' at Company' from page titles."""
    if not title:
        return ""
    return re.sub(r"\s+[|\-–—]\s+.+$", "", title).strip()
