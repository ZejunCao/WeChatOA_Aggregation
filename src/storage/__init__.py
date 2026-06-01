# -*- coding: utf-8 -*-
"""存储：文章数据仅使用 SQLite（data/wechatoa.db）。"""

from __future__ import annotations

from src.db.connection import database_exists, db_path


def storage_backend() -> str:
    return "sqlite"


def use_sqlite() -> bool:
    return True


def require_database() -> None:
    """无库时由 API 层抛出 503。"""
    if not database_exists():
        raise FileNotFoundError(
            f"未找到数据库 {db_path()}，请先运行 scripts/migrate_json_to_sqlite.py"
        )
