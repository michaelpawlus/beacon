"""Migration: Add 'book' to publications_talks pub_type CHECK constraint.

SQLite doesn't support ALTER CHECK constraints, so this recreates the table
with the updated constraint while preserving all existing data.

Usage: python3 migrations/add_book_pub_type.py
"""

import sqlite3
import shutil
from pathlib import Path

DB_PATH = Path("data/beacon.db")
BACKUP_PATH = DB_PATH.with_suffix(".db.bak")


def migrate():
    # Step 1: Backup
    shutil.copy2(DB_PATH, BACKUP_PATH)
    print(f"Backup created at {BACKUP_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Step 2: Verify existing data
    rows = conn.execute("SELECT * FROM publications_talks").fetchall()
    print(f"Found {len(rows)} existing publications")

    # Step 3: Recreate with new constraint
    conn.executescript("""
        CREATE TABLE publications_talks_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            pub_type TEXT NOT NULL CHECK(pub_type IN (
                'blog_post', 'paper', 'talk', 'panel', 'podcast', 'workshop', 'open_source', 'book'
            )),
            venue TEXT,
            url TEXT,
            date_published TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        INSERT INTO publications_talks_new SELECT * FROM publications_talks;

        DROP TABLE publications_talks;

        ALTER TABLE publications_talks_new RENAME TO publications_talks;
    """)

    # Step 4: Verify
    new_rows = conn.execute("SELECT * FROM publications_talks").fetchall()
    print(f"Migration complete: {len(new_rows)} publications preserved")
    conn.close()


if __name__ == "__main__":
    migrate()
