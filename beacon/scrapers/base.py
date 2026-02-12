"""Base adapter class for career page scrapers."""

from abc import ABC, abstractmethod


class BaseAdapter(ABC):
    """Abstract base class for career page adapters."""

    @abstractmethod
    def fetch_jobs(self, company: dict) -> list[dict]:
        """Fetch job listings from a company's career page.

        Args:
            company: A dict/Row with at least 'careers_url' and 'domain'.

        Returns:
            List of normalized job dicts with keys:
                title, url, location, department, description_text, date_posted
        """
        ...
