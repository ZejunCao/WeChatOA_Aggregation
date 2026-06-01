# -*- coding: utf-8 -*-
"""SQLite 连接与库初始化。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 2

_BASE = Path(__file__).resolve().parents[2]
DATA_DIR = _BASE / "data"
DEFAULT_DB_PATH = DATA_DIR / "wechatoa.db"
_SCHEMA_FILE = Path(__file__).with_name("schema.sql")


def db_path() -> Path:
    return DEFAULT_DB_PATH


def get_connection(*, readonly: bool = False) -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = db_path()
    if readonly:
        uri = f"file:{path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
    else:
        conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    if not readonly:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_database(conn: sqlite3.Connection | None = None) -> None:
    own = conn is None
    conn = conn or get_connection()
    schema_sql = _SCHEMA_FILE.read_text(encoding="utf-8")
    conn.executescript(schema_sql)
    from src.db.migrations import apply_migrations

    apply_migrations(conn)
    row = conn.execute(
        "SELECT MAX(version) AS v FROM schema_migrations"
    ).fetchone()
    if not row or row["v"] is None:
        from src.utils.helpers import time_now

        conn.execute(
            """
            INSERT OR IGNORE INTO schema_migrations (version, applied_at)
            VALUES (?, ?)
            """,
            (SCHEMA_VERSION, time_now()),
        )
        conn.commit()
    if own:
        conn.close()


def database_exists() -> bool:
    return db_path().is_file()
