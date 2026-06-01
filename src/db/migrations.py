# -*- coding: utf-8 -*-
"""SQLite 增量迁移。"""

from __future__ import annotations

import sqlite3

from src.utils.helpers import time_now

LATEST_SCHEMA_VERSION = 5


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
        current = 2

    if current < 3:
        _migrate_to_v3(conn)
        conn.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            (3, time_now()),
        )
        conn.commit()
        current = 3

    if current < 4:
        _migrate_to_v4(conn)
        conn.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            (4, time_now()),
        )
        conn.commit()
        current = 4

    if current < 5:
        _migrate_to_v5(conn)
        conn.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            (5, time_now()),
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


def _migrate_to_v3(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='article_bodies'"
    ).fetchone()
    if not row:
        return
    cols = {r[1] for r in conn.execute("PRAGMA table_info(article_bodies)").fetchall()}
    if "body_html" not in cols:
        conn.execute("ALTER TABLE article_bodies ADD COLUMN body_html TEXT")


def _migrate_to_v4(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='articles'"
    ).fetchone()
    if not row:
        return
    cols = {r[1] for r in conn.execute("PRAGMA table_info(articles)").fetchall()}
    if "source" not in cols:
        conn.execute(
            "ALTER TABLE articles ADD COLUMN source TEXT NOT NULL DEFAULT 'crawl'"
        )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_articles_source_time
        ON articles (source, create_time DESC, id DESC)
        """
    )
    conn.execute(
        """
        UPDATE articles
        SET source = 'import'
        WHERE source = 'crawl'
          AND (
            account_name = '链接导入'
            OR account_name IN (
              SELECT name FROM accounts WHERE fakeid LIKE 'import:%'
            )
          )
        """
    )


def _migrate_to_v5(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='articles'"
    ).fetchone()
    if not row:
        return
    cols = {r[1] for r in conn.execute("PRAGMA table_info(articles)").fetchall()}
    if "import_listed" not in cols:
        conn.execute(
            "ALTER TABLE articles ADD COLUMN import_listed INTEGER NOT NULL DEFAULT 0"
        )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_articles_import_listed_time
        ON articles (import_listed, create_time DESC, id DESC)
        WHERE import_listed = 1
        """
    )
    # 曾在「导入」中的文章：import_listed=1
    conn.execute("UPDATE articles SET import_listed=1 WHERE source='import'")
    # 订阅文章被误标 source=import：恢复 origin=crawl，保留在导入列表
    conn.execute(
        """
        UPDATE articles
        SET source='crawl', import_listed=1
        WHERE source='import'
          AND account_name != '链接导入'
          AND account_name NOT IN (
            SELECT name FROM accounts WHERE fakeid LIKE 'import:%'
          )
        """
    )
