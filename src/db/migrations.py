# -*- coding: utf-8 -*-
"""SQLite 增量迁移。"""

from __future__ import annotations

import sqlite3
import re

from src.utils.helpers import time_now

LATEST_SCHEMA_VERSION = 10


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
        current = 5

    if current < 6:
        _migrate_to_v6(conn)
        conn.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            (6, time_now()),
        )
        conn.commit()
        current = 6

    if current < 7:
        _migrate_to_v7(conn)
        conn.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            (7, time_now()),
        )
        conn.commit()
        current = 7

    if current < 8:
        _migrate_to_v8(conn)
        conn.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            (8, time_now()),
        )
        conn.commit()
        current = 8

    if current < 9:
        _migrate_to_v9(conn)
        conn.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            (9, time_now()),
        )
        conn.commit()
        current = 9

    if current < 10:
        _migrate_to_v10(conn)
        conn.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            (10, time_now()),
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


def _migrate_to_v6(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS article_notes (
          article_id   TEXT PRIMARY KEY REFERENCES articles(id) ON DELETE CASCADE,
          content      TEXT NOT NULL DEFAULT '',
          created_at   TEXT NOT NULL,
          updated_at   TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_article_notes_updated_at
        ON article_notes (updated_at DESC)
        """
    )


def _migrate_to_v7(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='articles'"
    ).fetchone()
    if not row:
        return
    cols = {r[1] for r in conn.execute("PRAGMA table_info(articles)").fetchall()}
    if "import_order" not in cols:
        conn.execute(
            "ALTER TABLE articles ADD COLUMN import_order INTEGER NOT NULL DEFAULT 0"
        )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_articles_import_listed_order
        ON articles (import_listed, import_order DESC, id DESC)
        WHERE import_listed = 1
        """
    )


def _migrate_to_v8(conn: sqlite3.Connection) -> None:
    """
    回填历史导入文章的 import_order，避免仍按发布时间观感排序。
    规则：按 updated_at/create_time 从旧到新分配递增序号，最新导入排最前。
    """
    conn.execute(
        """
        WITH ranked AS (
          SELECT
            id,
            ROW_NUMBER() OVER (
              ORDER BY
                COALESCE(NULLIF(updated_at, ''), NULLIF(create_time, ''), id) ASC,
                id ASC
            ) AS rn
          FROM articles
          WHERE import_listed = 1
            AND COALESCE(import_order, 0) = 0
        )
        UPDATE articles
        SET import_order = (
          SELECT rn FROM ranked WHERE ranked.id = articles.id
        )
        WHERE id IN (SELECT id FROM ranked)
        """
    )


def _migrate_to_v9(conn: sqlite3.Connection) -> None:
    """修复历史导入文章字数偏小（未提交事务导致回退到标题长度）的数据。"""
    rows = conn.execute(
        """
        SELECT ar.id, ar.title, ab.body_text
        FROM articles ar
        LEFT JOIN article_bodies ab ON ab.article_id = ar.id
        WHERE ar.import_listed = 1
        """
    ).fetchall()
    now = time_now()
    for row in rows:
        article_id = str(row["id"] or "")
        if not article_id:
            continue
        raw = row["body_text"]
        if raw is None:
            text = ""
        else:
            text = str(raw)
        cleaned = re.sub(r"\s+", "", text)
        if cleaned:
            wc = len(cleaned)
        else:
            wc = len(re.sub(r"\s+", "", str(row["title"] or "")))
        conn.execute(
            "UPDATE articles SET word_count=?, updated_at=? WHERE id=?",
            (wc, now, article_id),
        )


def _migrate_to_v10(conn: sqlite3.Connection) -> None:
    """区分爬取配置账号与链接导入占位账号。"""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(accounts)").fetchall()}
    if "in_crawl_config" not in cols:
        conn.execute(
            """
            ALTER TABLE accounts
            ADD COLUMN in_crawl_config INTEGER NOT NULL DEFAULT 1
            CHECK (in_crawl_config IN (0, 1))
            """
        )
    conn.execute(
        "UPDATE accounts SET in_crawl_config = 0 WHERE fakeid LIKE 'import:%'"
    )
    conn.execute(
        """
        UPDATE accounts SET in_crawl_config = 0
        WHERE in_crawl_config = 1
          AND (latest_crawl_at IS NULL OR latest_crawl_at = '')
          AND name IN (
            SELECT account_name FROM articles
            GROUP BY account_name
            HAVING SUM(CASE WHEN source != 'import' THEN 1 ELSE 0 END) = 0
               AND COUNT(*) > 0
          )
        """
    )
