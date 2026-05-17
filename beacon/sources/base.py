"""Base types for company discovery source adapters.

A `SourceAdapter` pulls candidate companies from an external source (Crunchbase,
a curated YAML feed, etc.) and yields `Candidate` records that the CLI dedupes
against the existing `companies` table and persists to `discovery_candidates`
for human/agent review.

Discovery is intentionally a two-step process: adapters cast a wide net, the
`promote` command makes the deliberate "yes, this is an AI-first company" call.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Candidate:
    """One discovered company that may or may not deserve promotion."""

    name: str
    source: str
    source_ref: str
    domain: str | None = None
    careers_url: str | None = None
    hq_location: str | None = None
    industry: str | None = None
    signals: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    def to_row(self) -> dict[str, Any]:
        """Shape suitable for `discovery_candidates` INSERT (minus discovery_score)."""
        import json as _json

        return {
            "source": self.source,
            "source_ref": self.source_ref,
            "name": self.name,
            "domain": self.domain,
            "careers_url": self.careers_url,
            "hq_location": self.hq_location,
            "industry": self.industry,
            "signals_json": _json.dumps(self.signals),
            "raw_json": _json.dumps(self.raw),
        }


class SourceAdapter(ABC):
    """Pluggable source for discovering AI-first company candidates.

    Subclasses must define `name` and implement `fetch`. They should yield as
    much evidence as they can in `Candidate.signals` — the dedupe/scoring layer
    uses signal counts to rank candidates, so a wide net with rich signals beats
    a narrow net of bare names.
    """

    name: str = ""

    @abstractmethod
    def fetch(self, limit: int | None = None) -> Iterable[Candidate]:
        """Yield Candidate records from the source.

        Args:
            limit: Optional cap on the number of candidates returned. None = no cap.

        Raises:
            SourceAuthError: When required credentials are missing.
            SourceFetchError: When the upstream source fails.
        """
        ...


class SourceError(Exception):
    """Base class for source adapter errors."""


class SourceAuthError(SourceError):
    """Raised when an adapter is missing required credentials."""


class SourceFetchError(SourceError):
    """Raised when an upstream source fetch fails."""
