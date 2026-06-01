# -*- coding: utf-8 -*-
"""存储辅助函数（SQLite）。"""

from __future__ import annotations

import re
from typing import Any


def get_article_body(article_id: str, data_manager: Any = None) -> str | list | None:
    del data_manager  # 保留参数以兼容旧调用签名
    if not article_id:
        return None
    from src.db.repository import ArticleRepository

    with ArticleRepository() as repo:
        return repo.get_body_text(article_id)


def compute_word_count(article: dict, data_manager: Any = None) -> int:
    article_id = str(article.get("id") or "")
    text_data = get_article_body(article_id, data_manager)
    if isinstance(text_data, list):
        text = "".join(str(x) for x in text_data)
        cleaned = re.sub(r"\s+", "", text)
        if cleaned:
            return len(cleaned)
    elif isinstance(text_data, str):
        cleaned = re.sub(r"\s+", "", text_data)
        if cleaned:
            return len(cleaned)
    title = str(article.get("title") or "")
    return len(re.sub(r"\s+", "", title))
