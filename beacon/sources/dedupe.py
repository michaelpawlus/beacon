"""Dedupe + evidence-based scoring for discovery candidates.

Two-pass dedupe (called for each freshly-fetched Candidate):

1. **Hard match against existing companies** — exact name, normalized name, or
   exact domain hit means the company is already tracked. Skip.
2. **Source-uniqueness** — `UNIQUE(source, source_ref)` in the schema enforces
   the upstream dedupe; `INSERT OR IGNORE` rides that constraint.

Already-rejected candidates re-surfaced by an adapter are NOT re-inserted (the
unique constraint blocks them) but their `status` stays `rejected`, so they
won't appear in `candidates --status pending`.

Scoring philosophy: cast a wide net, then rank by evidence so high-signal
candidates float to the top of `beacon companies candidates`. The score is
intentionally simple (sum of weighted components, no ML) so it stays
inspectable and easy to tune.
"""

import re
import sqlite3
from collections.abc import Iterable

from beacon.sources.base import Candidate

# ----- Scoring -----

# Per-source weights — higher means "this source is more curated, trust it more"
SOURCE_WEIGHTS: dict[str, float] = {
    "yaml": 1.5,        # human-curated, every entry is intentional
    "crunchbase": 1.0,  # broad firehose, evidence-poor on Basic tier
}


def score_candidate(candidate: Candidate) -> float:
    """Compute a discovery score for a candidate.

    Higher = more evidence + more curation. Used to sort candidates so the
    most promotable ones surface first in `beacon companies candidates`.

    Breakdown (max ~10):
      • +source weight (0–1.5)
      • +1 per attached signal (capped at 5)
      • +0.5 for each of: domain, careers_url, industry, hq_location
      • +1.0 if signals include any with `strength >= 4`
    """
    score = SOURCE_WEIGHTS.get(candidate.source, 1.0)

    signal_count = min(len(candidate.signals), 5)
    score += signal_count

    for field_value in (
        candidate.domain,
        candidate.careers_url,
        candidate.industry,
        candidate.hq_location,
    ):
        if field_value:
            score += 0.5

    has_strong_signal = any(
        (s.get("signal_strength") or s.get("strength") or 0) >= 4
        for s in candidate.signals
    )
    if has_strong_signal:
        score += 1.0

    return round(score, 2)


# ----- Dedupe -----

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize_name(name: str) -> str:
    """Lowercase, alphanumerics-only — for fuzzy name matching."""
    return _NON_ALNUM.sub("", (name or "").lower())


def existing_company_match(
    conn: sqlite3.Connection,
    candidate: Candidate,
) -> int | None:
    """Return the matching companies.id if the candidate already exists, else None.

    Match strategy (any one is a hit):
      1. Exact case-insensitive name match.
      2. Normalized name (alphanumerics-only) match — catches "Cursor (Anysphere)" vs "Cursor".
      3. Exact domain match (when both have a domain).
    """
    cand_norm = normalize_name(candidate.name)

    rows = conn.execute(
        "SELECT id, name, domain FROM companies WHERE LOWER(name) = LOWER(?)",
        (candidate.name,),
    ).fetchall()
    if rows:
        return rows[0]["id"]

    if candidate.domain:
        rows = conn.execute(
            "SELECT id FROM companies WHERE LOWER(domain) = LOWER(?)",
            (candidate.domain,),
        ).fetchall()
        if rows:
            return rows[0]["id"]

    # Normalized name fuzzy match — pull a narrowed set to keep the in-Python
    # loop small. We only consider companies whose first 4 chars overlap.
    prefix = (candidate.name or "")[:4].lower()
    if prefix:
        rows = conn.execute(
            "SELECT id, name FROM companies WHERE LOWER(SUBSTR(name, 1, 4)) = ?",
            (prefix,),
        ).fetchall()
        for r in rows:
            if normalize_name(r["name"]) == cand_norm:
                return r["id"]
    return None


# ----- Persist -----

def upsert_candidates(
    conn: sqlite3.Connection,
    candidates: Iterable[Candidate],
    *,
    dry_run: bool = False,
) -> dict[str, list[dict]]:
    """Dedupe and (optionally) insert a stream of candidates.

    Returns a dict with three lists:
      • inserted — newly written candidate rows
      • skipped_existing — candidate matched an already-tracked company
      • skipped_duplicate — already in `discovery_candidates` (any status)

    With `dry_run=True`, no rows are written. The classification still happens
    so the caller can show what *would* be inserted.
    """
    inserted: list[dict] = []
    skipped_existing: list[dict] = []
    skipped_duplicate: list[dict] = []

    for cand in candidates:
        company_id = existing_company_match(conn, cand)
        if company_id is not None:
            skipped_existing.append({
                "name": cand.name,
                "source": cand.source,
                "source_ref": cand.source_ref,
                "matched_company_id": company_id,
            })
            continue

        existing_row = conn.execute(
            "SELECT id, status FROM discovery_candidates WHERE source = ? AND source_ref = ?",
            (cand.source, cand.source_ref),
        ).fetchone()
        if existing_row:
            skipped_duplicate.append({
                "name": cand.name,
                "source": cand.source,
                "source_ref": cand.source_ref,
                "candidate_id": existing_row["id"],
                "status": existing_row["status"],
            })
            continue

        row = cand.to_row()
        row["discovery_score"] = score_candidate(cand)

        if not dry_run:
            cursor = conn.execute(
                """
                INSERT INTO discovery_candidates
                    (source, source_ref, name, domain, careers_url, hq_location,
                     industry, signals_json, raw_json, discovery_score)
                VALUES (:source, :source_ref, :name, :domain, :careers_url,
                        :hq_location, :industry, :signals_json, :raw_json,
                        :discovery_score)
                """,
                row,
            )
            row["id"] = cursor.lastrowid
        inserted.append({
            "id": row.get("id"),
            "name": cand.name,
            "source": cand.source,
            "source_ref": cand.source_ref,
            "domain": cand.domain,
            "discovery_score": row["discovery_score"],
            "signal_count": len(cand.signals),
        })

    if not dry_run:
        conn.commit()

    return {
        "inserted": inserted,
        "skipped_existing": skipped_existing,
        "skipped_duplicate": skipped_duplicate,
    }
