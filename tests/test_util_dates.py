"""Tests for beacon.util.dates.

The `days_since` cases are regression tests for a timezone bug that was
invisible on the original WSL2 host (whose clock ran UTC) and surfaced only
once the project moved to a machine with a real local timezone. See the
docstring on `days_since`.
"""

import sqlite3
from datetime import datetime, timedelta, timezone

from beacon.util.dates import days_since, format_iso, format_sqlite, utcnow


class TestUtcnow:
    def test_is_timezone_aware_utc(self):
        now = utcnow()
        assert now.tzinfo is not None
        assert now.utcoffset() == timedelta(0)


class TestDaysSince:
    def test_naive_input_is_read_as_utc_not_local(self):
        """A naive timestamp is UTC, because that is what SQLite writes.

        Reading it as *local* time is the original bug: west of Greenwich it
        makes a just-written row look like it is from the future.
        """
        now = datetime(2026, 7, 24, 16, 0, 0, tzinfo=timezone.utc)
        assert days_since("2026-07-24 16:00:00", now=now) == 0
        assert days_since("2026-07-14 16:00:00", now=now) == 10

    def test_sub_day_offset_never_floors_negative(self):
        """The exact failure mode: an offset-sized skew flooring to -1."""
        now = datetime(2026, 7, 24, 12, 0, 0, tzinfo=timezone.utc)
        # Written 4h before "now" in UTC — a UTC-4 local clock would have made
        # this diff negative and `.days` floor to -1.
        assert days_since("2026-07-24 08:00:00", now=now) == 0

    def test_respects_explicit_offset_when_present(self):
        now = datetime(2026, 7, 24, 16, 0, 0, tzinfo=timezone.utc)
        assert days_since("2026-07-24T12:00:00-04:00", now=now) == 0

    def test_matches_a_real_sqlite_now(self):
        """End-to-end against SQLite's own datetime('now') — must be 0 on any
        host, regardless of the machine's timezone."""
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE t (ts TEXT DEFAULT (datetime('now')))")
        conn.execute("INSERT INTO t DEFAULT VALUES")
        ts = conn.execute("SELECT ts FROM t").fetchone()[0]
        assert days_since(ts) == 0
        conn.close()


class TestFormatters:
    def test_format_iso_roundtrips_through_days_since(self):
        now = utcnow()
        assert days_since(format_iso(now).replace("Z", ""), now=now) == 0

    def test_format_sqlite_matches_sqlite_ordering(self):
        """format_sqlite output must sort lexically against datetime('now')."""
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE t (ts TEXT DEFAULT (datetime('now')))")
        conn.execute("INSERT INTO t DEFAULT VALUES")
        cutoff = format_sqlite(utcnow() - timedelta(days=1))
        cnt = conn.execute("SELECT COUNT(*) FROM t WHERE ts >= ?", (cutoff,)).fetchone()[0]
        assert cnt == 1
        conn.close()
