"""Curated YAML source — the always-available discovery fallback.

Reads one or more YAML files from `beacon/sources/curated/` (override with the
`curated_dir` ctor arg) and yields each entry as a Candidate. The schema is the
same shape as `Candidate`, so this is also the canonical place to dump
"saw this on HN, look later" companies.

YAML schema (one file may contain many entries):

```yaml
companies:
  - name: Example AI
    domain: example.ai
    careers_url: https://example.ai/careers
    hq_location: San Francisco, CA
    industry: Developer Tools
    source_ref: example-ai            # optional; defaults to slugified name
    signals:
      - signal_type: engineering_blog
        title: How we use Claude internally
        source_url: https://example.ai/blog/claude
        signal_strength: 4
```
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml

from beacon.sources.base import Candidate, SourceAdapter, SourceFetchError

DEFAULT_CURATED_DIR = Path(__file__).parent / "curated"


class YamlCuratedAdapter(SourceAdapter):
    name = "yaml"

    def __init__(self, curated_dir: Path | str | None = None) -> None:
        self.curated_dir = Path(curated_dir) if curated_dir else DEFAULT_CURATED_DIR

    def fetch(self, limit: int | None = None) -> Iterable[Candidate]:
        if not self.curated_dir.exists():
            raise SourceFetchError(
                f"Curated dir does not exist: {self.curated_dir}"
            )

        yml_files = sorted(
            list(self.curated_dir.glob("*.yml")) + list(self.curated_dir.glob("*.yaml"))
        )
        if not yml_files:
            raise SourceFetchError(
                f"No .yml/.yaml files found in {self.curated_dir}"
            )

        count = 0
        for path in yml_files:
            try:
                data = yaml.safe_load(path.read_text()) or {}
            except yaml.YAMLError as e:
                raise SourceFetchError(f"Failed to parse {path}: {e}") from e

            entries = data.get("companies") if isinstance(data, dict) else None
            if not entries:
                continue

            for entry in entries:
                if limit is not None and count >= limit:
                    return
                cand = self._entry_to_candidate(entry, path.stem)
                if cand is None:
                    continue
                count += 1
                yield cand

    @staticmethod
    def _entry_to_candidate(entry: dict[str, Any], file_stem: str) -> Candidate | None:
        name = (entry or {}).get("name")
        if not name:
            return None
        source_ref = entry.get("source_ref") or _slugify(name)
        return Candidate(
            name=name,
            source="yaml",
            source_ref=f"{file_stem}/{source_ref}",
            domain=entry.get("domain"),
            careers_url=entry.get("careers_url"),
            hq_location=entry.get("hq_location"),
            industry=entry.get("industry"),
            signals=list(entry.get("signals") or []),
            raw=dict(entry),
        )


def _slugify(value: str) -> str:
    import re

    s = (value or "").lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-") or "unknown"
