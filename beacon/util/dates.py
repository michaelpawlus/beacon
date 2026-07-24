"""Date parsing helpers for windowed CLI commands.

Used by `beacon companies diff` and reserved for future `beacon gaps diff` /
`beacon jobs diff` commands so they share `--since` semantics.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

_RELATIVE_DAYS_RE = re.compile(r"^(\d+)\s*d$")

_NAMED_SHORTCUTS = {
    "yesterday": 1,
    "last-week": 7,
    "last-month": 30,
    "last-quarter": 90,
}


def parse_since(value: str, *, now: datetime | None = None) -> datetime:
    """Parse a --since input into a tz-aware UTC datetime.

    Accepts:
      - ISO date (``2026-05-15``) or ISO datetime (``2026-05-15T12:00:00Z``)
      - Relative day shortcut (``7d``, ``30d``)
      - Bare integer (read as days, e.g. ``7`` → 7 days ago)
      - Named shortcuts: ``yesterday``, ``last-week``, ``last-month``,
        ``last-quarter``

    Raises ``ValueError`` on unparseable input.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError("--since must be a non-empty string")

    raw = value.strip().lower()
    base = (now or datetime.now(timezone.utc)).replace(microsecond=0)
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)

    if raw in _NAMED_SHORTCUTS:
        return base - timedelta(days=_NAMED_SHORTCUTS[raw])

    if raw.isdigit():
        return base - timedelta(days=int(raw))

    m = _RELATIVE_DAYS_RE.match(raw)
    if m:
        return base - timedelta(days=int(m.group(1)))

    try:
        dt = datetime.fromisoformat(raw.replace("z", "+00:00"))
    except ValueError as e:
        raise ValueError(
            f"--since must be an ISO date (2026-05-15), Nd shortcut (7d), "
            f"or named window (last-week); got {value!r}"
        ) from e

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def utcnow() -> datetime:
    """Current time as a tz-aware UTC datetime.

    Replaces ``datetime.utcnow()``, which returns a *naive* datetime (deprecated
    since 3.12) and, worse, invites comparison against naive local ``datetime.now()``.
    """
    return datetime.now(timezone.utc)


def days_since(stored: str, *, now: datetime | None = None) -> int:
    """Whole days between a timestamp written by SQLite and now.

    Every ``created_at`` / ``computed_at`` / ``date_first_seen`` column defaults to
    ``datetime('now')``, which SQLite evaluates in **UTC**. Diffing those against a
    naive local ``datetime.now()`` yields an offset-sized error — and west of
    Greenwich it goes *negative*, so ``.days`` floors to ``-1`` for a row written
    seconds ago. Staleness gates ("snapshot older than 90 days") then silently
    compare against a number that is wrong by the UTC offset.

    Values are read as UTC when they carry no offset, which is the case for
    everything SQLite writes.
    """
    ts = datetime.fromisoformat(stored)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ((now or utcnow()) - ts).days


def format_iso(dt: datetime) -> str:
    """Format a tz-aware datetime as ``YYYY-MM-DDTHH:MM:SSZ`` (UTC)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def format_sqlite(dt: datetime) -> str:
    """Format a tz-aware datetime as ``YYYY-MM-DD HH:MM:SS`` for SQLite text comparison.

    SQLite's ``datetime('now')`` and the default ``created_at`` / ``date_first_seen``
    columns use a space separator and no ``Z`` suffix. ISO-with-T strings sort
    lexically *after* space-separated ones, so windowed comparisons must use this
    format on the right-hand side.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
