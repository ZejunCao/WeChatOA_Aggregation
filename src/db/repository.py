# -*- coding: utf-8 -*-
"""文章 / 公众号 SQLite 仓储。"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from src.db.body_text import normalize_body_text
from src.db.connection import DATA_DIR, ensure_database_ready, get_connection
from src.db import fts as fts_mod
from src.utils.helpers import time_now

# 与 api.COVERS_DIR 一致
COVERS_DIR = DATA_DIR / "covers"


def _parse_create_time_unix(create_time: str) -> int | None:
    create_time = (create_time or "").strip()
    if not create_time:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return int(datetime.strptime(create_time, fmt).timestamp())
        except ValueError:
            continue
    return None


def _cover_path_for_id(article_id: str) -> str | None:
    rel = f"covers/{article_id.replace('/', '_')}.jpg"
    if (DATA_DIR / rel).is_file():
        return rel
    return None


class ArticleRepository:
    def __init__(self, conn: sqlite3.Connection | None = None) -> None:
        self._own_conn = conn is None
        ensure_database_ready()
        self.conn = conn or get_connection()

    def close(self) -> None:
        if self._own_conn:
            self.conn.close()

    def __enter__(self) -> ArticleRepository:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    # ── 公众号 ─────────────────────────────────────────────────────────────

    def upsert_account(
        self,
        name: str,
        fakeid: str,
        latest_crawl_at: str = "",
        *,
        in_crawl_config: int = 1,
    ) -> None:
        now = time_now()
        self.conn.execute(
            """
            INSERT INTO accounts (name, fakeid, latest_crawl_at, in_crawl_config, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
              fakeid=excluded.fakeid,
              latest_crawl_at=COALESCE(NULLIF(excluded.latest_crawl_at,''), accounts.latest_crawl_at),
              in_crawl_config=MAX(accounts.in_crawl_config, excluded.in_crawl_config),
              updated_at=excluded.updated_at
            """,
            (name, fakeid, latest_crawl_at or "", int(in_crawl_config), now, now),
        )

    def upsert_import_account(self, name: str) -> None:
        """链接导入：仅满足外键的占位账号，不加入批量爬取配置。"""
        now = time_now()
        fakeid = f"import:{name}"
        self.conn.execute(
            """
            INSERT INTO accounts (name, fakeid, latest_crawl_at, in_crawl_config, created_at, updated_at)
            VALUES (?, ?, '', 0, ?, ?)
            ON CONFLICT(name) DO NOTHING
            """,
            (name, fakeid, now, now),
        )

    def enable_crawl_account(self, name: str, fakeid: str) -> None:
        """用户主动添加：加入批量爬取配置。"""
        now = time_now()
        self.conn.execute(
            """
            INSERT INTO accounts (name, fakeid, latest_crawl_at, in_crawl_config, created_at, updated_at)
            VALUES (?, ?, '', 1, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
              fakeid=excluded.fakeid,
              in_crawl_config=1,
              updated_at=excluded.updated_at
            """,
            (name, fakeid, now, now),
        )

    def account_in_crawl_config(self, name: str) -> bool:
        row = self.conn.execute(
            "SELECT in_crawl_config FROM accounts WHERE name=?",
            (name,),
        ).fetchone()
        return bool(row and int(row["in_crawl_config"] or 0) == 1)

    def list_accounts(self, *, crawl_config_only: bool = True) -> list[dict[str, Any]]:
        where = "WHERE a.in_crawl_config = 1" if crawl_config_only else ""
        rows = self.conn.execute(
            f"""
            SELECT a.name, a.fakeid, a.latest_crawl_at, a.in_crawl_config,
                   COUNT(ar.id) AS article_count
            FROM accounts a
            LEFT JOIN articles ar ON ar.account_name = a.name
              AND ar.is_wx_deleted = 0 AND ar.is_user_deleted = 0
            {where}
            GROUP BY a.name, a.fakeid, a.latest_crawl_at, a.in_crawl_config
            ORDER BY a.name
            """
        ).fetchall()
        return [
            {
                "name": r["name"],
                "fakeid": r["fakeid"],
                "latest_update_time": r["latest_crawl_at"] or "",
                "article_count": r["article_count"],
                "in_crawl_config": int(r["in_crawl_config"] or 0),
            }
            for r in rows
        ]

    def get_name2fakeid(self, *, crawl_config_only: bool = True) -> dict[str, str]:
        if crawl_config_only:
            rows = self.conn.execute(
                "SELECT name, fakeid FROM accounts WHERE in_crawl_config = 1"
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT name, fakeid FROM accounts").fetchall()
        return {r["name"]: r["fakeid"] for r in rows}

    def set_account_latest_crawl(self, name: str, t: str) -> None:
        self.conn.execute(
            "UPDATE accounts SET latest_crawl_at=?, updated_at=? WHERE name=?",
            (t, time_now(), name),
        )

    def remove_account_from_list(self, name: str) -> None:
        """仅从订阅列表移除，保留已爬文章。"""
        self.conn.execute("PRAGMA foreign_keys=OFF")
        self.conn.execute("DELETE FROM accounts WHERE name=?", (name,))
        self.conn.execute("PRAGMA foreign_keys=ON")

    # ── 文章写入 ─────────────────────────────────────────────────────────────

    def _tags_for_row(self, article_id: str) -> list[str]:
        rows = self.conn.execute(
            "SELECT tag FROM article_llm_tags WHERE article_id=? ORDER BY tag",
            (article_id,),
        ).fetchall()
        return [r["tag"] for r in rows]

    def row_to_blog_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        tags = self._tags_for_row(row["id"])
        d: dict[str, Any] = {
            "id": row["id"],
            "title": row["title"],
            "digest": row["digest"],
            "link": row["link"],
            "cover": row["cover_url"],
            "create_time": row["create_time"],
            "is_deleted": bool(row["is_wx_deleted"]),
            "item_show_type": row["item_show_type"],
            "word_count": row["word_count"],
        }
        if row["llm_summary"]:
            d["summary"] = row["llm_summary"]
        if tags:
            d["tags"] = tags
        return d

    def row_to_feed_item(self, row: sqlite3.Row) -> dict[str, Any]:
        item = self.row_to_blog_dict(row)
        item["account"] = row["account_name"]
        keys = row.keys()
        if "is_read" in keys:
            item["is_read"] = bool(row["is_read"])
        if "starred" in keys:
            item["starred"] = bool(row["starred"])
        if "source" in keys:
            item["source"] = str(row["source"] or "crawl")
        if "import_listed" in keys:
            item["import_listed"] = bool(row["import_listed"])
        if "has_note" in keys:
            item["has_note"] = bool(row["has_note"])
        return item

    def upsert_article_from_blog(
        self,
        account_name: str,
        blog: dict[str, Any],
        *,
        update_fts: bool = True,
        source: str = "crawl",
    ) -> None:
        aid = str(blog.get("id") or "").strip()
        if not aid:
            return
        now = time_now()
        create_time = str(blog.get("create_time") or "")
        cover_url = str(blog.get("cover") or "")
        cover_path = _cover_path_for_id(aid)
        article_source = "import" if source == "import" else "crawl"
        import_listed = 1 if source == "import" else 0
        self.conn.execute(
            """
            INSERT INTO articles (
              id, account_name, title, digest, link, cover_url, cover_path,
              create_time, create_time_unix, is_wx_deleted, is_user_deleted,
              item_show_type, llm_summary, word_count, ingested_at, updated_at,
              source, import_listed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              account_name=excluded.account_name,
              title=excluded.title,
              digest=excluded.digest,
              link=excluded.link,
              cover_url=excluded.cover_url,
              cover_path=COALESCE(excluded.cover_path, articles.cover_path),
              create_time=excluded.create_time,
              create_time_unix=excluded.create_time_unix,
              is_wx_deleted=excluded.is_wx_deleted,
              item_show_type=excluded.item_show_type,
              llm_summary=COALESCE(excluded.llm_summary, articles.llm_summary),
              word_count=COALESCE(excluded.word_count, articles.word_count),
              updated_at=excluded.updated_at,
              source=articles.source,
              import_listed=CASE
                WHEN excluded.import_listed = 1 THEN 1
                ELSE articles.import_listed
              END
            """,
            (
                aid,
                account_name,
                str(blog.get("title") or ""),
                str(blog.get("digest") or ""),
                str(blog.get("link") or ""),
                cover_url,
                cover_path,
                create_time,
                _parse_create_time_unix(create_time),
                1 if blog.get("is_deleted") else 0,
                int(blog.get("item_show_type") or 0),
                str(blog.get("summary") or "") or None,
                blog.get("word_count"),
                now,
                now,
                article_source,
                import_listed,
            ),
        )
        tags = blog.get("tags")
        if isinstance(tags, list) and tags:
            self.set_llm_tags(aid, [str(t) for t in tags if str(t).strip()])

        if update_fts:
            body = self.get_body_text(aid) or ""
            fts_mod.upsert_article_fts(
                self.conn,
                aid,
                str(blog.get("title") or ""),
                str(blog.get("digest") or ""),
                body,
            )

    def set_llm_tags(self, article_id: str, tags: list[str]) -> None:
        self.conn.execute(
            "DELETE FROM article_llm_tags WHERE article_id=?", (article_id,)
        )
        for tag in tags:
            t = tag.strip()
            if t:
                self.conn.execute(
                    "INSERT OR IGNORE INTO article_llm_tags (article_id, tag) VALUES (?, ?)",
                    (article_id, t),
                )

    def update_llm_fields(
        self, article_id: str, summary: str, tags: list[str]
    ) -> None:
        self.conn.execute(
            "UPDATE articles SET llm_summary=?, updated_at=? WHERE id=?",
            (summary or None, time_now(), article_id),
        )
        if tags:
            self.set_llm_tags(article_id, tags)
        row = self.conn.execute(
            "SELECT title, digest FROM articles WHERE id=?", (article_id,)
        ).fetchone()
        if row:
            body = self.get_body_text(article_id) or ""
            fts_mod.upsert_article_fts(
                self.conn, article_id, row["title"], row["digest"], body
            )

    def set_body_text(self, article_id: str, raw: Any) -> None:
        text = normalize_body_text(raw)
        now = time_now()
        self.conn.execute(
            """
            INSERT INTO article_bodies (article_id, body_text, source_kind, fetched_at, updated_at)
            VALUES (?, ?, 'crawl', ?, ?)
            ON CONFLICT(article_id) DO UPDATE SET
              body_text=excluded.body_text,
              updated_at=excluded.updated_at
            """,
            (article_id, text, now, now),
        )
        row = self.conn.execute(
            "SELECT title, digest FROM articles WHERE id=?", (article_id,)
        ).fetchone()
        if row:
            fts_mod.upsert_article_fts(
                self.conn, article_id, row["title"], row["digest"], text
            )

    def get_body_text(self, article_id: str) -> str | None:
        row = self.conn.execute(
            "SELECT body_text FROM article_bodies WHERE article_id=?",
            (article_id,),
        ).fetchone()
        return row["body_text"] if row else None

    def get_body_html(self, article_id: str) -> str | None:
        row = self.conn.execute(
            "SELECT body_html FROM article_bodies WHERE article_id=?",
            (article_id,),
        ).fetchone()
        if not row:
            return None
        html = row["body_html"]
        return html if html else None

    def has_body_html(self, article_id: str) -> bool:
        row = self.conn.execute(
            """
            SELECT 1 FROM article_bodies
            WHERE article_id=? AND body_html IS NOT NULL AND length(trim(body_html)) > 0
            LIMIT 1
            """,
            (article_id,),
        ).fetchone()
        return row is not None

    def set_body_html(self, article_id: str, html: str) -> None:
        now = time_now()
        self.conn.execute(
            """
            INSERT INTO article_bodies (article_id, body_text, body_html, source_kind, fetched_at, updated_at)
            VALUES (?, '', ?, 'crawl', ?, ?)
            ON CONFLICT(article_id) DO UPDATE SET
              body_html=excluded.body_html,
              updated_at=excluded.updated_at
            """,
            (article_id, html, now, now),
        )

    def has_body(self, article_id: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM article_bodies WHERE article_id=? LIMIT 1",
            (article_id,),
        ).fetchone()
        return row is not None

    def get_blogs_for_account(self, account_name: str) -> list[dict[str, Any]]:
        """供 fakeid2message_update 去重用的现有文章列表。"""
        rows = self.conn.execute(
            """
            SELECT * FROM articles
            WHERE account_name=? AND is_user_deleted=0
            ORDER BY create_time
            """,
            (account_name,),
        ).fetchall()
        return [self.row_to_blog_dict(r) for r in rows]

    def is_deleted_blacklist(self, article_id: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM deleted_articles WHERE article_id=?",
            (article_id,),
        ).fetchone()
        if row:
            return True
        row = self.conn.execute(
            "SELECT is_user_deleted FROM articles WHERE id=?", (article_id,)
        ).fetchone()
        return bool(row and row["is_user_deleted"])

    def add_deleted_blacklist(self, article_id: str) -> None:
        self.conn.execute(
            """
            INSERT OR IGNORE INTO deleted_articles (article_id, deleted_at)
            VALUES (?, ?)
            """,
            (article_id, time_now()),
        )
        self.conn.execute(
            "UPDATE articles SET is_user_deleted=1, updated_at=? WHERE id=?",
            (time_now(), article_id),
        )
        fts_mod.delete_article_fts(self.conn, article_id)

    def remove_article(self, article_id: str, account: str) -> bool:
        row = self.conn.execute(
            "SELECT id FROM articles WHERE id=? AND account_name=?",
            (article_id, account),
        ).fetchone()
        if not row:
            return False
        self.add_deleted_blacklist(article_id)
        self.conn.execute("DELETE FROM articles WHERE id=?", (article_id,))
        self.conn.execute(
            "DELETE FROM article_bodies WHERE article_id=?", (article_id,)
        )
        self.conn.execute(
            "DELETE FROM article_llm_tags WHERE article_id=?", (article_id,)
        )
        return True

    def set_word_count(self, article_id: str, count: int) -> None:
        self.conn.execute(
            "UPDATE articles SET word_count=?, updated_at=? WHERE id=?",
            (count, time_now(), article_id),
        )

    def update_cover_path(self, article_id: str) -> None:
        path = _cover_path_for_id(article_id)
        if path:
            self.conn.execute(
                "UPDATE articles SET cover_path=?, updated_at=? WHERE id=?",
                (path, time_now(), article_id),
            )

    # ── 列表 / 搜索 ─────────────────────────────────────────────────────────

    def _articles_where(
        self,
        *,
        account: str | None = None,
        tag: str | None = None,
        date_from: str = "",
        date_to: str = "",
        article_ids: list[str] | None = None,
        cursor: str | None = None,
        read_filter: str | None = None,
        starred_only: bool = False,
        import_only: bool = False,
        noted_only: bool = False,
    ) -> tuple[str, list[str], list[Any]]:
        where = ["ar.is_wx_deleted=0", "ar.is_user_deleted=0"]
        if import_only:
            where.append("ar.import_listed=1")
        params: list[Any] = []
        need_ann = bool(read_filter) or starred_only

        if account:
            where.append("ar.account_name=?")
            params.append(account)
        if date_from:
            where.append("ar.create_time>=?")
            params.append(date_from)
        if date_to:
            where.append("ar.create_time<=?")
            params.append(date_to + " 23:59" if len(date_to) <= 10 else date_to)
        if tag:
            where.append(
                """
                EXISTS (
                  SELECT 1 FROM article_llm_tags t
                  WHERE t.article_id=ar.id AND t.tag=?
                )
                """
            )
            params.append(tag)
        if article_ids is not None:
            if not article_ids:
                where.append("0")
            else:
                placeholders = ",".join("?" * len(article_ids))
                where.append(f"ar.id IN ({placeholders})")
                params.extend(article_ids)

        if read_filter == "unread":
            where.append("COALESCE(ann.is_read, 0) = 0")
            need_ann = True
        elif read_filter == "read":
            where.append("COALESCE(ann.is_read, 0) = 1")
            need_ann = True
        if starred_only:
            where.append("COALESCE(ann.starred, 0) = 1")
            need_ann = True
        if noted_only:
            where.append(
                """
                EXISTS (
                  SELECT 1 FROM article_notes nt
                  WHERE nt.article_id=ar.id
                    AND length(trim(COALESCE(nt.content, ''))) > 0
                )
                """
            )

        if cursor:
            try:
                left, aid = cursor.split("|", 1)
                if import_only:
                    order_no = int(left)
                    where.append(
                        "(COALESCE(ar.import_order, 0) < ? OR (COALESCE(ar.import_order, 0) = ? AND ar.id < ?))"
                    )
                    params.extend([order_no, order_no, aid])
                else:
                    ct = left
                    where.append(
                        "(ar.create_time < ? OR (ar.create_time = ? AND ar.id < ?))"
                    )
                    params.extend([ct, ct, aid])
            except ValueError:
                pass

        from_sql = (
            """
            FROM articles ar
            LEFT JOIN article_annotations ann ON ann.article_id = ar.id
            """
            if need_ann
            else "FROM articles ar"
        )
        return from_sql, where, params

    def count_articles(
        self,
        *,
        account: str | None = None,
        tag: str | None = None,
        date_from: str = "",
        date_to: str = "",
        article_ids: list[str] | None = None,
        read_filter: str | None = None,
        starred_only: bool = False,
        import_only: bool = False,
        noted_only: bool = False,
    ) -> int:
        if article_ids is not None and not article_ids:
            return 0
        from_sql, where, params = self._articles_where(
            account=account,
            tag=tag,
            date_from=date_from,
            date_to=date_to,
            article_ids=article_ids,
            read_filter=read_filter,
            starred_only=starred_only,
            import_only=import_only,
            noted_only=noted_only,
        )
        row = self.conn.execute(
            f"SELECT COUNT(*) AS c {from_sql} WHERE {' AND '.join(where)}",
            params,
        ).fetchone()
        return int(row["c"])

    def list_articles(
        self,
        *,
        limit: int = 30,
        cursor: str | None = None,
        account: str | None = None,
        tag: str | None = None,
        date_from: str = "",
        date_to: str = "",
        article_ids: list[str] | None = None,
        read_filter: str | None = None,
        starred_only: bool = False,
        import_only: bool = False,
        noted_only: bool = False,
    ) -> tuple[list[dict[str, Any]], str | None]:
        limit = max(1, min(limit, 100))
        from_sql, where, params = self._articles_where(
            account=account,
            tag=tag,
            date_from=date_from,
            date_to=date_to,
            article_ids=article_ids,
            cursor=cursor,
            read_filter=read_filter,
            starred_only=starred_only,
            import_only=import_only,
            noted_only=noted_only,
        )
        if article_ids is not None and not article_ids:
            return [], None

        order_by = (
            "COALESCE(ar.import_order, 0) DESC, ar.id DESC"
            if import_only
            else "ar.create_time DESC, ar.id DESC"
        )
        sql = f"""
            SELECT ar.*,
                   COALESCE(ann.is_read, 0) AS is_read,
                   COALESCE(ann.starred, 0) AS starred,
                   EXISTS (
                     SELECT 1 FROM article_notes nt
                     WHERE nt.article_id=ar.id
                       AND length(trim(COALESCE(nt.content, ''))) > 0
                   ) AS has_note
            FROM articles ar
            LEFT JOIN article_annotations ann ON ann.article_id = ar.id
            WHERE {' AND '.join(where)}
            ORDER BY {order_by}
            LIMIT ?
        """
        params.append(limit + 1)
        rows = self.conn.execute(sql, params).fetchall()
        has_more = len(rows) > limit
        rows = rows[:limit]
        items = [self.row_to_feed_item(r) for r in rows]
        next_cursor = None
        if has_more and rows:
            last = rows[-1]
            if import_only:
                next_cursor = f"{int(last['import_order'] or 0)}|{last['id']}"
            else:
                next_cursor = f"{last['create_time']}|{last['id']}"
        return items, next_cursor

    def search_articles(
        self,
        query: str,
        *,
        limit: int = 30,
        cursor: str | None = None,
        account: str | None = None,
        read_filter: str | None = None,
        starred_only: bool = False,
        import_only: bool = False,
        noted_only: bool = False,
    ) -> tuple[list[dict[str, Any]], str | None]:
        ids = fts_mod.search_article_ids(self.conn, query, limit=500)
        if not ids:
            return [], None
        return self.list_articles(
            limit=limit,
            cursor=cursor,
            account=account,
            article_ids=ids,
            read_filter=read_filter,
            starred_only=starred_only,
            import_only=import_only,
            noted_only=noted_only,
        )

    def find_article_by_link(self, link: str) -> dict[str, Any] | None:
        from src.utils.article_import import extract_mp_article_slug, link_lookup_variants

        for variant in link_lookup_variants(link):
            row = self.conn.execute(
                """
                SELECT id, account_name, title, link FROM articles
                WHERE link=? AND is_user_deleted=0
                """,
                (variant,),
            ).fetchone()
            if row:
                return dict(row)

        slug = extract_mp_article_slug(link)
        if slug:
            row = self.conn.execute(
                """
                SELECT id, account_name, title, link FROM articles
                WHERE is_user_deleted=0 AND link LIKE ?
                ORDER BY create_time DESC
                LIMIT 1
                """,
                (f"%/s/{slug}%",),
            ).fetchone()
            if row:
                return dict(row)
        return None

    def mark_article_as_imported(self, article_id: str) -> None:
        """链接导入命中已存在文章时，仅加入「导入」列表，不改变 origin。"""
        row = self.conn.execute(
            "SELECT COALESCE(MAX(import_order), 0) AS max_import_order FROM articles"
        ).fetchone()
        next_order = int(row["max_import_order"] or 0) + 1 if row else 1
        self.conn.execute(
            """
            UPDATE articles SET import_listed=1, import_order=?, updated_at=?
            WHERE id=? AND is_user_deleted=0
            """,
            (next_order, time_now(), article_id),
        )

    def remove_from_import(self, article_id: str, account: str) -> str | None:
        """
        从「导入」移出。
        - origin=import：彻底删除
        - origin=crawl：仅 import_listed=0
        返回 'deleted' | 'unlisted'；不存在时返回 None。
        """
        row = self.conn.execute(
            """
            SELECT id, source FROM articles
            WHERE id=? AND account_name=? AND is_user_deleted=0
            """,
            (article_id, account),
        ).fetchone()
        if not row:
            return None
        origin = str(row["source"] or "crawl")
        if origin == "import":
            if not self.remove_article(article_id, account):
                return None
            return "deleted"
        self.conn.execute(
            """
            UPDATE articles SET import_listed=0, updated_at=?
            WHERE id=? AND account_name=?
            """,
            (time_now(), article_id, account),
        )
        return "unlisted"

    def get_article_detail(self, article_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            """
            SELECT ar.*,
                   COALESCE(ann.is_read, 0) AS is_read,
                   COALESCE(ann.starred, 0) AS starred
            FROM articles ar
            LEFT JOIN article_annotations ann ON ann.article_id = ar.id
            WHERE ar.id=?
            """,
            (article_id,),
        ).fetchone()
        if not row:
            return None
        item = self.row_to_feed_item(row)
        item["body_text"] = self.get_body_text(article_id) or ""
        item["body_html"] = self.get_body_html(article_id) or ""
        return item

    def all_llm_tags(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT DISTINCT tag FROM article_llm_tags ORDER BY tag"
        ).fetchall()
        return [r["tag"] for r in rows]

    # ── 已读 / 收藏（article_annotations）────────────────────────────────────

    def set_article_read(self, article_id: str, is_read: bool) -> None:
        now = time_now()
        row = self.conn.execute(
            "SELECT article_id FROM article_annotations WHERE article_id=?",
            (article_id,),
        ).fetchone()
        if row:
            self.conn.execute(
                """
                UPDATE article_annotations
                SET is_read=?, read_at=?, updated_at=?
                WHERE article_id=?
                """,
                (1 if is_read else 0, now if is_read else None, now, article_id),
            )
        else:
            self.conn.execute(
                """
                INSERT INTO article_annotations (
                  article_id, is_read, read_at, starred, updated_at
                ) VALUES (?, ?, ?, 0, ?)
                """,
                (article_id, 1 if is_read else 0, now if is_read else None, now),
            )

    def set_article_starred(self, article_id: str, starred: bool) -> None:
        now = time_now()
        row = self.conn.execute(
            "SELECT article_id FROM article_annotations WHERE article_id=?",
            (article_id,),
        ).fetchone()
        if row:
            self.conn.execute(
                """
                UPDATE article_annotations
                SET starred=?, starred_at=?, updated_at=?
                WHERE article_id=?
                """,
                (1 if starred else 0, now if starred else None, now, article_id),
            )
        else:
            self.conn.execute(
                """
                INSERT INTO article_annotations (
                  article_id, is_read, starred, starred_at, updated_at
                ) VALUES (?, 0, ?, ?, ?)
                """,
                (article_id, 1 if starred else 0, now if starred else None, now),
            )

    def mark_articles_read(self, article_ids: list[str]) -> int:
        n = 0
        for aid in article_ids:
            if aid.strip():
                self.set_article_read(aid.strip(), True)
                n += 1
        return n

    def count_unread(self, **kwargs: Any) -> int:
        return self.count_articles(read_filter="unread", **kwargs)

    def count_starred(self, **kwargs: Any) -> int:
        return self.count_articles(starred_only=True, **kwargs)

    def get_reading_state(self) -> dict[str, Any]:
        read_rows = self.conn.execute(
            "SELECT article_id FROM article_annotations WHERE is_read=1"
        ).fetchall()
        starred_rows = self.conn.execute(
            "SELECT article_id FROM article_annotations WHERE starred=1"
        ).fetchall()
        return {
            "read_ids": [r["article_id"] for r in read_rows],
            "starred_ids": [r["article_id"] for r in starred_rows],
            "unread_count": self.count_unread(),
            "starred_count": len(starred_rows),
        }

    def import_reading_state(
        self, read_ids: list[str], starred_ids: list[str]
    ) -> dict[str, int]:
        read_n = self.mark_articles_read(read_ids)
        star_n = 0
        for aid in starred_ids:
            if aid.strip():
                self.set_article_starred(aid.strip(), True)
                star_n += 1
        return {"read_imported": read_n, "starred_imported": star_n}

    # ── 笔记（article_notes）──────────────────────────────────────────────────

    def list_notes(
        self,
        *,
        limit: int = 100,
        account: str | None = None,
        article_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """笔记时间线：按笔记最近编辑时间倒序，返回文章信息 + 笔记内容。"""
        limit = max(1, min(limit, 200))
        where = [
            "ar.is_user_deleted=0",
            "length(trim(COALESCE(nt.content, ''))) > 0",
        ]
        params: list[Any] = []
        if account:
            where.append("ar.account_name=?")
            params.append(account)
        if article_ids is not None:
            if not article_ids:
                return []
            placeholders = ",".join("?" * len(article_ids))
            where.append(f"ar.id IN ({placeholders})")
            params.extend(article_ids)
        sql = f"""
            SELECT ar.*,
                   COALESCE(ann.is_read, 0) AS is_read,
                   COALESCE(ann.starred, 0) AS starred,
                   1 AS has_note,
                   nt.content AS note_content,
                   nt.updated_at AS note_updated_at
            FROM article_notes nt
            JOIN articles ar ON ar.id = nt.article_id
            LEFT JOIN article_annotations ann ON ann.article_id = ar.id
            WHERE {' AND '.join(where)}
            ORDER BY nt.updated_at DESC, ar.id DESC
            LIMIT ?
        """
        params.append(limit)
        rows = self.conn.execute(sql, params).fetchall()
        items: list[dict[str, Any]] = []
        for r in rows:
            item = self.row_to_feed_item(r)
            item["note_content"] = str(r["note_content"] or "")
            item["note_updated_at"] = str(r["note_updated_at"] or "")
            items.append(item)
        return items

    def search_note_article_ids(
        self, query: str, *, account: str | None = None
    ) -> list[str]:
        """在笔记正文内做关键词匹配（FTS 不索引笔记，故用 LIKE 兜底）。"""
        q = (query or "").strip()
        if not q:
            return []
        where = [
            "ar.is_user_deleted=0",
            "length(trim(COALESCE(nt.content, ''))) > 0",
            "nt.content LIKE ?",
        ]
        params: list[Any] = [f"%{q}%"]
        if account:
            where.append("ar.account_name=?")
            params.append(account)
        sql = f"""
            SELECT nt.article_id AS id
            FROM article_notes nt
            JOIN articles ar ON ar.id = nt.article_id
            WHERE {' AND '.join(where)}
            ORDER BY nt.updated_at DESC
            LIMIT 500
        """
        rows = self.conn.execute(sql, params).fetchall()
        return [str(r["id"]) for r in rows]

    def get_article_note(self, article_id: str) -> dict[str, Any]:
        row = self.conn.execute(
            """
            SELECT content, updated_at
            FROM article_notes
            WHERE article_id=?
            """,
            (article_id,),
        ).fetchone()
        if not row:
            return {"content": "", "updated_at": ""}
        return {
            "content": str(row["content"] or ""),
            "updated_at": str(row["updated_at"] or ""),
        }

    def set_article_note(self, article_id: str, content: str) -> dict[str, Any]:
        now = time_now()
        body = str(content or "")
        self.conn.execute(
            """
            INSERT INTO article_notes (article_id, content, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(article_id) DO UPDATE SET
              content=excluded.content,
              updated_at=excluded.updated_at
            """,
            (article_id, body, now, now),
        )
        return {"content": body, "updated_at": now}

    def article_has_note(self, article_id: str) -> bool:
        row = self.conn.execute(
            """
            SELECT 1
            FROM article_notes
            WHERE article_id=?
              AND length(trim(COALESCE(content, ''))) > 0
            LIMIT 1
            """,
            (article_id,),
        ).fetchone()
        return row is not None

    # ── 缓存清理 ─────────────────────────────────────────────────────────────

    def ids_older_than(self, cutoff: str) -> set[str]:
        rows = self.conn.execute(
            """
            SELECT ar.id
            FROM articles ar
            LEFT JOIN article_annotations ann ON ann.article_id = ar.id
            WHERE ar.create_time < ?
              AND ar.is_user_deleted=0
              AND ar.import_listed=0
              AND COALESCE(ann.starred, 0)=0
              AND NOT EXISTS (
                SELECT 1 FROM article_notes nt
                WHERE nt.article_id=ar.id
                  AND length(trim(COALESCE(nt.content, ''))) > 0
              )
            """,
            (cutoff,),
        ).fetchall()
        return {r["id"] for r in rows}

    def delete_articles_by_ids(self, ids: set[str]) -> int:
        if not ids:
            return 0
        removed = 0
        for aid in ids:
            fts_mod.delete_article_fts(self.conn, aid)
            self.conn.execute("DELETE FROM article_bodies WHERE article_id=?", (aid,))
            self.conn.execute(
                "DELETE FROM article_llm_tags WHERE article_id=?", (aid,)
            )
            cur = self.conn.execute("DELETE FROM articles WHERE id=?", (aid,))
            removed += cur.rowcount
        return removed

    def commit(self) -> None:
        self.conn.commit()

    def rebuild_all_fts(self) -> int:
        rows = self.conn.execute(
            """
            SELECT a.id, a.title, a.digest, COALESCE(b.body_text, '') AS body_text
            FROM articles a
            LEFT JOIN article_bodies b ON b.article_id = a.id
            WHERE a.is_user_deleted=0
            """
        ).fetchall()
        self.conn.execute("DELETE FROM article_fts")
        for r in rows:
            fts_mod.upsert_article_fts(
                self.conn, r["id"], r["title"], r["digest"], r["body_text"]
            )
        return len(rows)
