"""Pytest configuration for the beacon test suite.

Speeds up the suite by relaxing SQLite durability for *test* databases only.

Every test's ``db`` fixture calls ``init_db``, which fsyncs on commit. On slow
filesystems (notably WSL2) that single fsync dominates wall-clock at ~2s per
call; multiplied across the ~1064-test suite it turns a one-minute run into a
~40-minute one. Tests never need crash durability, so we disable synchronous
fsync and keep the rollback journal in memory for every connection opened
during the test session.

This patches the stdlib ``sqlite3.connect`` so it also covers the connections
``init_db`` opens internally (not just the fixture's). It is loaded only by
pytest, so production code and the real ``data/beacon.db`` are untouched.
"""

import sqlite3

_real_connect = sqlite3.connect


def _fast_connect(*args, **kwargs):
    conn = _real_connect(*args, **kwargs)
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA journal_mode=MEMORY")
    return conn


sqlite3.connect = _fast_connect
