# -*- coding: utf-8 -*-
"""FTS5 + jieba 分词。"""

from __future__ import annotations

import re
import sqlite3

_jieba = None


def _jieba_mod():
    global _jieba
    if _jieba is None:
        import jieba

        _jieba = jieba
    return _jieba


def tokenize_for_fts(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    jieba = _jieba_mod()
    parts = jieba.cut_for_search(text)
    tokens = [p.strip() for p in parts if p.strip()]
    return " ".join(tokens)


def _escape_fts_query(tokenized: str) -> str:
    """将分词结果拼成 FTS5 MATCH 安全查询（AND 连接）。"""
    words = [w for w in tokenized.split() if w]
    if not words:
        return ""
    escaped = []
    for w in words:
        w = w.replace('"', '""')
        escaped.append(f'"{w}"')
    return " AND ".join(escaped)


def upsert_article_fts(
    conn: sqlite3.Connection,
    article_id: str,
    title: str,
    digest: str,
    body_text: str,
) -> None:
    conn.execute("DELETE FROM article_fts WHERE article_id = ?", (article_id,))
    conn.execute(
        """
        INSERT INTO article_fts (article_id, title_tok, digest_tok, body_tok)
        VALUES (?, ?, ?, ?)
        """,
        (
            article_id,
            tokenize_for_fts(title),
            tokenize_for_fts(digest),
            tokenize_for_fts(body_text),
        ),
    )


def delete_article_fts(conn: sqlite3.Connection, article_id: str) -> None:
    conn.execute("DELETE FROM article_fts WHERE article_id = ?", (article_id,))


def search_article_ids(
    conn: sqlite3.Connection,
    query: str,
    *,
    limit: int = 50,
) -> list[str]:
    tokenized = tokenize_for_fts(query)
    match = _escape_fts_query(tokenized)
    if not match:
        return []
    rows = conn.execute(
        """
        SELECT article_id
        FROM article_fts
        WHERE article_fts MATCH ?
        ORDER BY bm25(article_fts)
        LIMIT ?
        """,
        (match, limit),
    ).fetchall()
    return [r["article_id"] for r in rows]
