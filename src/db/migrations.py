# -*- coding: utf-8 -*-
"""SQLite 增量迁移。"""

from __future__ import annotations

import sqlite3

from src.utils.helpers import time_now

LATEST_SCHEMA_VERSION = 2


def apply_migrations(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT MAX(version) AS v FROM schema_migrations").fetchone()
    current = int(row["v"]) if row and row["v"] is not None else 0

    if current < 2:
        _migrate_to_v2(conn)
        conn.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            (2, time_now()),
        )
        conn.commit()


def _migrate_to_v2(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='article_annotations'"
    ).fetchone()
    if not row:
        return
    cols = {
        r[1] for r in conn.execute("PRAGMA table_info(article_annotations)").fetchall()
    }
    if "is_read" not in cols:
        conn.execute(
            "ALTER TABLE article_annotations ADD COLUMN is_read INTEGER NOT NULL DEFAULT 0"
        )
    if "read_at" not in cols:
        conn.execute("ALTER TABLE article_annotations ADD COLUMN read_at TEXT")
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_annotations_unread
        ON article_annotations (is_read) WHERE is_read = 0
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_annotations_starred
        ON article_annotations (starred) WHERE starred = 1
        """
    )
