# -*- coding: utf-8 -*-
"""SQLite 连接与库初始化。"""

from __future__ import annotations

import sqlite3
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

_init_lock = threading.Lock()
_db_ready = False

SCHEMA_VERSION = 5

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
    conn.execute("PRAGMA busy_timeout=15000")
    if not readonly:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def _apply_schema_and_migrations(conn: sqlite3.Connection) -> None:
    from src.db.migrations import apply_migrations

    # 旧库先迁移（补列），再跑 schema.sql；否则 CREATE INDEX 可能因列不存在而失败
    apply_migrations(conn)
    schema_sql = _SCHEMA_FILE.read_text(encoding="utf-8")
    conn.executescript(schema_sql)
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


def ensure_database_ready() -> None:
    """进程内只初始化一次，避免每个请求重复 executescript 抢锁。"""
    global _db_ready
    if _db_ready:
        return
    with _init_lock:
        if _db_ready:
            return
        conn = get_connection()
        try:
            _apply_schema_and_migrations(conn)
        finally:
            conn.close()
        _db_ready = True


def init_database(conn: sqlite3.Connection | None = None) -> None:
    """初始化 schema/迁移。传入 conn 时在该连接上执行；否则进程内只执行一次。"""
    if conn is not None:
        _apply_schema_and_migrations(conn)
        return
    ensure_database_ready()


def database_exists() -> bool:
    return db_path().is_file()


T = TypeVar("T")


def db_write_with_retry(
    fn: Callable[[], T],
    *,
    max_attempts: int = 8,
    base_delay: float = 0.05,
) -> T:
    """SQLite 写锁冲突时指数退避重试。"""
    last_err: sqlite3.OperationalError | None = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except sqlite3.OperationalError as e:
            if "locked" not in str(e).lower():
                raise
            last_err = e
            if attempt < max_attempts - 1:
                time.sleep(base_delay * (2**attempt))
    assert last_err is not None
    raise last_err
