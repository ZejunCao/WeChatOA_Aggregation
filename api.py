#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
轻量 FastAPI 后端，供前端管理公众号列表使用。
"""

import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ── 数据目录和文件路径 ──────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent / "data"
COVERS_DIR = DATA_DIR / "covers"
LOGS_FILE = DATA_DIR / "operation_logs.jsonl"

# ── FastAPI 应用初始化 ──────────────────────────────────────────────────────────
app = FastAPI(title="微信公众号聚合 API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── SQLite 存储 ────────────────────────────────────────────────────────────────

def _require_database() -> None:
    from src.storage import require_database

    try:
        require_database()
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


def _read_name2fakeid() -> dict[str, str]:
    """从 accounts 表读取公众号名称→fakeid 映射。"""
    from src.db.repository import ArticleRepository

    with ArticleRepository() as repo:
        return repo.get_name2fakeid()


def _write_name2fakeid(data: dict[str, str]) -> None:
    """将公众号名称→fakeid 映射写入 accounts 表。"""
    from src.db.repository import ArticleRepository

    with ArticleRepository() as repo:
        for name, fakeid in data.items():
            repo.upsert_account(str(name), str(fakeid))
        repo.commit()


@app.get("/api/storage/backend")
def get_storage_backend():
    _require_database()
    return {"backend": "sqlite"}


@app.get("/api/name2fakeid")
def get_name2fakeid_api():
    _require_database()
    return _read_name2fakeid()


class ArticleListResponse(BaseModel):
    items: list[dict]
    next_cursor: str | None = None
    total: int = 0


@app.get("/api/articles", response_model=ArticleListResponse)
def list_articles_api(
    limit: int = Query(30, ge=1, le=100),
    cursor: str | None = None,
    account: str | None = None,
    tag: str | None = None,
    date_from: str = "",
    date_to: str = "",
    read_filter: str | None = Query(
        None, description="unread=仅未读, read=仅已读；默认全部"
    ),
    starred_only: bool = Query(False, description="true=仅收藏"),
    import_only: bool = Query(False, description="true=仅链接导入的文章"),
):
    _require_database()
    rf = (read_filter or "").strip().lower() or None
    if rf not in (None, "unread", "read"):
        raise HTTPException(status_code=400, detail="read_filter 须为 unread 或 read")
    from src.db.repository import ArticleRepository

    with ArticleRepository() as repo:
        items, next_c = repo.list_articles(
            limit=limit,
            cursor=cursor,
            account=account or None,
            tag=tag or None,
            date_from=date_from,
            date_to=date_to,
            read_filter=rf,
            starred_only=starred_only,
            import_only=import_only,
        )
        total = repo.count_articles(
            account=account or None,
            tag=tag or None,
            date_from=date_from,
            date_to=date_to,
            read_filter=rf,
            starred_only=starred_only,
            import_only=import_only,
        )
        repo.commit()
    return ArticleListResponse(items=items, next_cursor=next_c, total=total)


@app.get("/api/articles/search", response_model=ArticleListResponse)
def search_articles_api(
    q: str = Query(..., min_length=1),
    limit: int = Query(30, ge=1, le=100),
    cursor: str | None = None,
    account: str | None = None,
    read_filter: str | None = None,
    starred_only: bool = False,
    import_only: bool = False,
):
    _require_database()
    rf = (read_filter or "").strip().lower() or None
    if rf not in (None, "unread", "read"):
        raise HTTPException(status_code=400, detail="read_filter 须为 unread 或 read")
    from src.db.repository import ArticleRepository

    with ArticleRepository() as repo:
        from src.db import fts as fts_mod

        q = q.strip()
        ids = fts_mod.search_article_ids(repo.conn, q, limit=500)
        items, next_c = repo.list_articles(
            limit=limit,
            cursor=cursor,
            account=account or None,
            article_ids=ids,
            read_filter=rf,
            starred_only=starred_only,
            import_only=import_only,
        )
        total = repo.count_articles(
            account=account or None,
            article_ids=ids,
            read_filter=rf,
            starred_only=starred_only,
            import_only=import_only,
        )
        repo.commit()
    return ArticleListResponse(items=items, next_cursor=next_c, total=total)


class ReadingPatchBody(BaseModel):
    is_read: bool | None = None
    starred: bool | None = None


class MarkAllReadBody(BaseModel):
    article_ids: list[str]


class ReadingImportBody(BaseModel):
    read_ids: list[str] = []
    starred_ids: list[str] = []


@app.get("/api/reading/state")
def get_reading_state_api():
    _require_database()
    from src.db.repository import ArticleRepository

    with ArticleRepository() as repo:
        state = repo.get_reading_state()
        repo.commit()
    return state


@app.patch("/api/articles/{article_id}/reading")
def patch_article_reading_api(article_id: str, body: ReadingPatchBody):
    _require_database()
    if body.is_read is None and body.starred is None:
        raise HTTPException(status_code=400, detail="至少提供 is_read 或 starred")
    from src.db.repository import ArticleRepository

    with ArticleRepository() as repo:
        row = repo.conn.execute(
            "SELECT id FROM articles WHERE id=?", (article_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="文章不存在")
        if body.is_read is not None:
            repo.set_article_read(article_id, bool(body.is_read))
        if body.starred is not None:
            repo.set_article_starred(article_id, bool(body.starred))
        repo.commit()
    return {"ok": True, "article_id": article_id}


@app.post("/api/reading/mark-all-read")
def mark_all_read_api(body: MarkAllReadBody):
    _require_database()
    from src.db.repository import ArticleRepository

    with ArticleRepository() as repo:
        n = repo.mark_articles_read(body.article_ids)
        repo.commit()
    return {"ok": True, "marked": n}


@app.post("/api/reading/import-local")
def import_reading_local_api(body: ReadingImportBody):
    """一次性：将浏览器 localStorage 中的已读/收藏导入数据库。"""
    _require_database()
    from src.db.repository import ArticleRepository

    with ArticleRepository() as repo:
        result = repo.import_reading_state(body.read_ids, body.starred_ids)
        repo.commit()
    return {"ok": True, **result}


@app.get("/api/articles/index")
def list_articles_index_api(account: str | None = None):
    """轻量文章索引（id/account/create_time），供未读、收藏等客户端状态筛选。"""
    _require_database()
    from src.db.repository import ArticleRepository

    with ArticleRepository() as repo:
        items = repo.list_article_index(account=account or None)
    return {"items": items}


@app.get("/api/articles/by-ids", response_model=ArticleListResponse)
def list_articles_by_ids_api(
    ids: str = Query(..., description="逗号分隔的文章 id，最多 100 个"),
):
    _require_database()
    id_list = [x.strip() for x in ids.split(",") if x.strip()]
    if not id_list:
        return ArticleListResponse(items=[], next_cursor=None, total=0)
    if len(id_list) > 100:
        raise HTTPException(status_code=400, detail="单次最多 100 个 id")
    from src.db.repository import ArticleRepository

    with ArticleRepository() as repo:
        items, _ = repo.list_articles(limit=len(id_list), article_ids=id_list)
        repo.commit()
    return ArticleListResponse(items=items, next_cursor=None, total=len(items))


@app.get("/api/articles/tags")
def list_article_tags_api():
    _require_database()
    from src.db.repository import ArticleRepository

    with ArticleRepository() as repo:
        tags = repo.all_llm_tags()
    return {"tags": tags}


class ImportArticleRequest(BaseModel):
    url: str = Field(..., min_length=8, description="微信公众号文章链接")
    run_llm: bool = Field(True, description="导入后是否自动跑 AI 摘要/标签")


class ImportArticleResponse(BaseModel):
    status: str  # created | exists
    article_id: str
    account: str
    title: str
    link: str
    message: str = ""


@app.post("/api/articles/import", response_model=ImportArticleResponse)
def import_article_api(body: ImportArticleRequest):
    """通过文章链接导入单篇（参考 wechat-article-exporter 单篇抓取）。"""
    _require_database()
    from src.db.repository import ArticleRepository
    from src.utils.article_import import ArticleImportError, build_blog_from_url

    try:
        blog = build_blog_from_url(body.url)
    except ArticleImportError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    account_name = (
        str(blog.get("_import_account") or "链接导入").strip() or "链接导入"
    )
    biz = str(blog.get("_import_biz") or "").strip()
    fakeid = biz if biz else f"import:{account_name}"
    blog_row = {k: v for k, v in blog.items() if not str(k).startswith("_import")}

    with ArticleRepository() as repo:
        existing = repo.find_article_by_link(str(blog_row["link"]))
        if existing:
            article_id = str(existing["id"])
            repo.mark_article_as_imported(article_id)
            repo.commit()
            return ImportArticleResponse(
                status="exists",
                article_id=article_id,
                account=str(existing["account_name"]),
                title=str(existing["title"]),
                link=str(existing["link"]),
                message="该链接已在库中，已归入「导入」",
            )

        repo.upsert_account(account_name, fakeid)
        repo.upsert_article_from_blog(
            account_name, blog_row, update_fts=False, source="import"
        )
        article_id = str(blog_row["id"])
        link = str(blog_row.get("link") or "")
        repo.commit()

        download_cover(
            article_id,
            str(blog_row.get("cover") or ""),
            COVERS_DIR,
            _DOWNLOAD_HEADERS,
        )
        _fetch_article_detail_text(article_id, link)

        from src.db import fts as fts_mod
        from src.utils.data_manager import data_manager

        repo.update_cover_path(article_id)
        body_raw = repo.get_body_text(article_id) or ""
        if isinstance(body_raw, list):
            body_for_fts = "\n".join(str(x) for x in body_raw)
        else:
            body_for_fts = str(body_raw)
        fts_mod.upsert_article_fts(
            repo.conn,
            article_id,
            str(blog_row.get("title") or ""),
            str(blog_row.get("digest") or ""),
            body_for_fts,
        )
        wc = article_word_count(blog_row, data_manager)
        repo.set_word_count(article_id, wc)

        if body.run_llm:
            from src.llm.article_tagging import tag_article
            from src.llm.llm_config import llm_tagging_enabled

            if llm_tagging_enabled():
                detail = repo.get_article_detail(article_id)
                if detail:
                    try:
                        analysis = tag_article(detail, data_manager)
                        if isinstance(analysis, dict):
                            repo.update_llm_fields(
                                article_id,
                                str(analysis.get("summary") or ""),
                                analysis.get("tags")
                                if isinstance(analysis.get("tags"), list)
                                else [],
                            )
                    except Exception as e:
                        print(f"[import] LLM 标注失败 {article_id}: {e}")

        repo.commit()

    return ImportArticleResponse(
        status="created",
        article_id=article_id,
        account=account_name,
        title=str(blog_row.get("title") or ""),
        link=str(blog_row.get("link") or ""),
        message="导入成功",
    )


@app.get("/api/articles/{article_id}")
def get_article_api(article_id: str):
    _require_database()
    from src.db.repository import ArticleRepository

    with ArticleRepository() as repo:
        item = repo.get_article_detail(article_id)
    if not item:
        raise HTTPException(status_code=404, detail="文章不存在")
    return item


@app.get("/api/articles/{article_id}/preview")
def get_article_preview_api(article_id: str, refresh: bool = Query(False)):
    """
    预览用 HTML：服务端抓取微信页并生成文档，前端 iframe srcdoc 展示。
    （微信禁止外链 iframe，不能直接加载 mp.weixin.qq.com）
    refresh=1 时忽略缓存并重新抓取。
    """
    _require_database()
    return _build_article_preview_html(article_id, refresh=refresh)


@app.post("/api/articles/{article_id}/ensure-html")
def ensure_article_html_api(article_id: str):
    """兼容旧接口：同 GET /preview。"""
    _require_database()
    data = _build_article_preview_html(article_id)
    return {"ok": True, "cached": data.get("cached"), "body_html": data.get("html")}


@app.get("/api/wechat-image")
def proxy_wechat_image(url: str = Query(..., min_length=8)):
    """代理微信 CDN 图片，避免预览里防盗链导致裂图。"""
    from src.utils.wechat_body import is_allowed_wechat_image_url

    if not is_allowed_wechat_image_url(url):
        raise HTTPException(status_code=400, detail="不允许的图片域名")
    try:
        import requests
        from fastapi.responses import Response

        from src.utils.data_manager import headers as wechat_headers

        h = dict(wechat_headers)
        h["Referer"] = "https://mp.weixin.qq.com/"
        resp = requests.get(url, headers=h, timeout=20)
        resp.raise_for_status()
        media = resp.headers.get("content-type") or "image/jpeg"
        return Response(
            content=resp.content,
            media_type=media,
            headers={"Cache-Control": "public, max-age=604800, immutable"},
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"图片加载失败：{e}") from e



# ── Pydantic 数据模型 ───────────────────────────────────────────────────────────
# FastAPI 用这些模型自动验证请求体/响应体，并生成 OpenAPI 文档。

class SearchRequest(BaseModel):
    """前端搜索公众号时传入的请求体。"""
    query: str  # 搜索关键词（公众号名称）


class SearchCandidate(BaseModel):
    """搜索结果中单个公众号候选项。"""
    fakeid: str        # 微信内部 ID，用于后续爬取
    nickname: str      # 公众号名称
    alias: str         # 微信号（英文 ID，可能为空）
    avatar: str        # 头像图片 URL（round_head_img）
    signature: str     # 简介
    service_type: int  # 0=订阅号, 1=服务号, 2=其他


class ConfirmAddRequest(BaseModel):
    """用户从搜索结果中选定后，确认添加时传入的请求体。"""
    name: str    # 用户确认使用的名称（即 nickname）
    fakeid: str  # 从搜索结果中选定的 fakeid


class AccountStatus(BaseModel):
    """单个公众号的状态摘要，供前端列表展示。"""
    name: str
    fakeid: str
    has_articles: bool      # 是否已有爬取到的文章
    article_count: int      # 当前有效文章数（已删除的不计）
    latest_update_time: str # 最后一次成功爬取的时间


class CrawlStatus(BaseModel):
    """爬取任务的实时进度，前端通过轮询获取。"""
    running: bool        # True = 任务进行中
    total: int           # 本次需要爬取的公众号总数
    done: int            # 已处理完的公众号数（包括失败的）
    current: str         # 正在爬取的公众号名称
    errors: list[str]    # 爬取失败的错误信息列表
    started_at: str      # 任务开始时间
    finished_at: str     # 任务结束时间（未结束时为空）
    new_articles: int    # 本次爬取新增的文章总数
    auth_error: bool = False  # True 表示因凭证失效而提前终止
    cancel_requested: bool = False  # 前端是否已请求取消
    cancelled: bool = False  # True 表示本次由用户取消


# ── 日志系统 ────────────────────────────────────────────────────────────────────
# 操作日志使用 JSONL 格式（每行一条 JSON），追加写入，不会覆盖历史。
# _log_lock 保证多线程同时写日志时不会出现文件内容交叉。

_log_lock = threading.Lock()

# 日志类型常量，对应前端日志页中的图标和颜色
LOG_CRAWL_START    = "crawl_start"
LOG_CRAWL_FINISH   = "crawl_finish"
LOG_CRAWL_ERROR    = "crawl_error"
LOG_ACCOUNT_ADD    = "account_add"
LOG_ACCOUNT_REMOVE = "account_remove"
LOG_CACHE_CLEAR    = "cache_clear"
LOG_ARTICLE_DELETE = "article_delete"


def _append_log(log_type: str, message: str, details: dict | None = None) -> None:
    """
    向 data/operation_logs.jsonl 追加一条日志（线程安全）。

    每条日志格式：
      {"timestamp": "...", "type": "crawl_start", "message": "...", "details": {...}}
    """
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": log_type,
        "message": message,
        "details": details or {},
    }
    with _log_lock:
        # 确保目录存在（初次运行时 data/ 可能还没有）
        LOGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOGS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ── 工具函数 ────────────────────────────────────────────────────────────────────

# 下载封面图时使用的 HTTP 请求头，模拟浏览器访问，避免微信服务器拒绝请求
_DOWNLOAD_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36',
    'Referer': 'https://mp.weixin.qq.com/',
}



def download_cover(article_id: str, cover_url: str, covers_dir: Path, request_headers: dict[str, str]) -> None:
    """下载封面图到 data/covers；失败时仅告警不阻断流程。"""
    if not article_id or not cover_url:
        return
    covers_dir.mkdir(parents=True, exist_ok=True)
    filename = article_id.replace("/", "_") + ".jpg"
    dest = covers_dir / filename
    if dest.exists():
        return
    try:
        import io
        import requests
        from PIL import Image

        resp = requests.get(cover_url, timeout=15, headers=request_headers)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        width, height = img.size
        if width > 640:
            new_height = int(height * 640.0 / width)
            img = img.resize((640, new_height), Image.Resampling.LANCZOS)
        img.save(dest, "JPEG", quality=85)
    except Exception as e:
        print(f"[cover] 下载失败 {article_id}: {e}")


def article_word_count(article: dict, data_manager) -> int:
    """优先统计正文，缺失时回退到标题长度。"""
    from src.storage.helpers import compute_word_count

    return compute_word_count(article, data_manager)


def _fetch_article_detail_text(article_id: str, link: str) -> bool:
    """
    根据文章链接拉取正文：纯文本（LLM/检索）+ HTML（预览排版），写入 article_bodies。
    """
    if not link or not article_id:
        return False
    from src.db.repository import ArticleRepository
    from src.utils.wechat_body import fetch_article_body

    with ArticleRepository() as repo:
        if repo.has_body(article_id):
            return False
        try:
            text, _html = fetch_article_body(link)
            repo.set_body_text(article_id, text)
            repo.commit()
            return True
        except Exception as e:
            print(f"[detail] 抓取正文失败 {article_id}: {e}")
            return False


def _build_article_preview_html(article_id: str, *, refresh: bool = False) -> dict:
    """生成可 srcdoc 嵌入的预览 HTML（对齐 wechat-article-exporter，非 iframe 外链）。"""
    from src.db.repository import ArticleRepository
    from src.utils.wechat_body import fetch_article_body
    from src.utils.wechat_preview import (
        build_preview_document,
        fetch_article_page_html,
        is_full_preview_document,
    )

    with ArticleRepository() as repo:
        row = repo.conn.execute(
            "SELECT link, title, create_time, create_time_unix, llm_summary FROM articles WHERE id=?",
            (article_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="文章不存在")
        link = str(row["link"] or "").strip()
        title = str(row["title"] or "")
        if not link:
            raise HTTPException(status_code=400, detail="文章无链接，无法预览")

        cached = repo.get_body_html(article_id) or ""
        if not refresh and is_full_preview_document(cached):
            return {"html": cached, "cached": True}

        raw_page = fetch_article_page_html(link)
        if not raw_page:
            if is_full_preview_document(cached):
                return {"html": cached, "cached": True}
            raise HTTPException(
                status_code=410,
                detail="无法获取原文（可能已删除或需检查 data/id_info.json 凭证）",
            )

        ai_tags = repo._tags_for_row(article_id)
        preview_html = build_preview_document(
            raw_page,
            title=title,
            ai_summary=str(row["llm_summary"] or ""),
            ai_tags=ai_tags,
            fallback_pub_time=str(row["create_time"] or ""),
            fallback_pub_unix=row["create_time_unix"],
        )
        if not preview_html.strip():
            raise HTTPException(status_code=502, detail="未能解析微信正文")

        if not repo.has_body(article_id):
            text, _frag = fetch_article_body(link)
            if text and not isinstance(text, str):
                repo.set_body_text(article_id, text)
            elif isinstance(text, str) and text not in ("已删除", "请求错误"):
                repo.set_body_text(article_id, text)
        repo.set_body_html(article_id, preview_html)
        repo.commit()
        return {"html": preview_html, "cached": False}


def _get_wechat():
    """
    初始化 WechatRequest 实例（会读取 data/id_info.json 中的 token/cookie）。
    初始化失败时抛出 503 错误，统一在调用处感知。
    """
    try:
        from src import WechatRequest
        return WechatRequest()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"初始化微信请求失败：{e}，请确认 data/id_info.json 有效")


# ── 账号管理 API ────────────────────────────────────────────────────────────────

@app.get("/api/accounts", response_model=list[AccountStatus])
def list_accounts():
    """
    返回所有已添加的公众号及其状态。

    数据来源：accounts / articles 表（SQLite）。
    """
    _require_database()
    from src.db.repository import ArticleRepository

    with ArticleRepository() as repo:
        rows = repo.list_accounts()
    result = []
    for row in rows:
        result.append(
            AccountStatus(
                name=row["name"],
                fakeid=row["fakeid"],
                has_articles=row["article_count"] > 0,
                article_count=row["article_count"],
                latest_update_time=row["latest_update_time"],
            )
        )
    return result


@app.post("/api/accounts/search", response_model=list[SearchCandidate])
def search_accounts(body: SearchRequest):
    """
    在微信公众平台搜索公众号，返回候选列表（最多 5 条）。

    这是添加公众号的第一步：前端展示候选列表，用户选择后再调用
    POST /api/accounts 确认添加。此接口不修改任何本地数据。
    """
    query = body.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="搜索关键词不能为空")

    # 先验证 id_info.json 是否有效，失败时直接抛 503，避免后续无效请求
    _get_wechat()
    try:
        import requests as req
        from src.utils.data_manager import data_manager, headers as wechat_headers

        # 复制全局 headers 并注入当前 Cookie
        h = dict(wechat_headers)
        h['Cookie'] = data_manager.id_info['cookie']
        params = {
            'action': 'search_biz',
            'begin': 0,
            'count': 5,
            'query': query,
            'token': data_manager.id_info['token'],
            'lang': 'zh_CN',
            'f': 'json',
            'ajax': 1,
        }
        response = req.get(
            'https://mp.weixin.qq.com/cgi-bin/searchbiz?',
            params=params,
            headers=h,
            timeout=15,
        ).json()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"微信接口请求失败：{e}")

    # 微信接口正常时 ret=0，非 0 表示 token/cookie 问题
    if response.get('base_resp', {}).get('ret') != 0:
        raise HTTPException(
            status_code=502,
            detail=f"微信接口返回错误：{response.get('base_resp', {}).get('err_msg', '未知')}，请检查 token/cookie 是否过期",
        )

    # 将微信返回的字段映射到前端友好的结构
    candidates = []
    for item in response.get('list', []):
        candidates.append(SearchCandidate(
            fakeid=item.get('fakeid', ''),
            nickname=item.get('nickname', ''),
            alias=item.get('alias', ''),
            avatar=item.get('round_head_img', ''),
            signature=item.get('signature', ''),
            service_type=item.get('service_type', 0),
        ))
    return candidates


@app.post("/api/accounts", response_model=AccountStatus, status_code=201)
def add_account(body: ConfirmAddRequest):
    """
    确认添加公众号：将用户选定的 name + fakeid 写入 accounts 表。

    调用时机：前端搜索并展示候选后，用户点击"确认添加"触发。
    重复添加同名公众号会返回 409 冲突错误。
    """
    name = body.name.strip()
    fakeid = body.fakeid.strip()
    if not name or not fakeid:
        raise HTTPException(status_code=400, detail="name 和 fakeid 不能为空")

    name2fakeid = _read_name2fakeid()
    if name in name2fakeid:
        raise HTTPException(status_code=409, detail=f"公众号「{name}」已在列表中")

    name2fakeid[name] = fakeid
    _write_name2fakeid(name2fakeid)

    # 记录操作日志
    _append_log(LOG_ACCOUNT_ADD, f"添加公众号「{name}」", {"name": name, "fakeid": fakeid})

    # 新添加的公众号没有文章，返回初始状态
    return AccountStatus(
        name=name,
        fakeid=fakeid,
        has_articles=False,
        article_count=0,
        latest_update_time="",
    )


@app.delete("/api/accounts/{name}", status_code=204)
def remove_account(name: str):
    """
    从跟踪列表中移除公众号（只删除 accounts 表中的记录，
    不删除已爬取的文章数据，如需清理可使用缓存清理功能）。
    """
    name2fakeid = _read_name2fakeid()
    if name not in name2fakeid:
        raise HTTPException(status_code=404, detail=f"公众号「{name}」不在列表中")

    from src.db.repository import ArticleRepository

    with ArticleRepository() as repo:
        repo.remove_account_from_list(name)
        repo.commit()
    _append_log(LOG_ACCOUNT_REMOVE, f"移除公众号「{name}」", {"name": name})


# ── 删除单篇文章 ────────────────────────────────────────────────────────────────

class ArticleDeleteRequest(BaseModel):
    """从前端移除一篇文章：写入黑名单并删除本地记录。"""
    article_id: str   # 文章唯一 id（msgid-aid-create_time）
    account: str      # 所属公众号名称（message_info 的 key）


@app.post("/api/articles/remove")
def remove_article(body: ArticleDeleteRequest):
    """
    写入 deleted_articles 表并从 articles 移除；同时删除本地封面。
    """
    aid = body.article_id.strip()
    acc = body.account.strip()
    if not aid or not acc:
        raise HTTPException(status_code=400, detail="article_id 和 account 不能为空")

    from src.db.repository import ArticleRepository

    with ArticleRepository() as repo:
        if not repo.remove_article(aid, acc):
            raise HTTPException(status_code=404, detail="文章不存在或已删除")
        repo.commit()
    cover_path = COVERS_DIR / (aid.replace("/", "_") + ".jpg")
    if cover_path.exists():
        try:
            cover_path.unlink()
        except OSError:
            pass
    _append_log(
        LOG_ARTICLE_DELETE,
        f"删除文章「{aid}」（{acc}）",
        {"article_id": aid, "account": acc},
    )
    return {"ok": True, "article_id": aid}


class RemoveFromImportRequest(BaseModel):
    article_id: str
    account: str


@app.post("/api/articles/remove-from-import")
def remove_from_import_api(body: RemoveFromImportRequest):
    """从「导入」分栏移出：订阅文章仅取消列出，纯导入文章则删除。"""
    aid = body.article_id.strip()
    acc = body.account.strip()
    if not aid or not acc:
        raise HTTPException(status_code=400, detail="article_id 和 account 不能为空")

    from src.db.repository import ArticleRepository

    with ArticleRepository() as repo:
        action = repo.remove_from_import(aid, acc)
        if not action:
            raise HTTPException(status_code=404, detail="文章不存在或已删除")
        repo.commit()

    if action == "deleted":
        cover_path = COVERS_DIR / (aid.replace("/", "_") + ".jpg")
        if cover_path.exists():
            try:
                cover_path.unlink()
            except OSError:
                pass
        _append_log(
            LOG_ARTICLE_DELETE,
            f"移出导入并删除「{aid}」（{acc}）",
            {"article_id": aid, "account": acc},
        )

    return {"ok": True, "article_id": aid, "action": action}


# ── 凭证状态（内存缓存） ─────────────────────────────────────────────────────────
# _auth_state 在进程内存中记录最近一次凭证检测结果。
# 程序重启后重置为初始值（valid=True 表示"尚未验证"）。
# 这个状态会在以下时机被更新：
#   - 每次爬取成功/失败时
#   - 调用 /api/auth/check 主动检测时
#   - 扫码登录完成时

_auth_state: dict = {
    "valid": True,    # 凭证是否有效（True 也可能是"尚未检测"的默认值）
    "checked_at": "", # 上次检测时间（空字符串表示本次启动后尚未检测）
    "error": "",      # 失败原因，如 "invalid csrf token"
}


def _mark_auth_failed(reason: str) -> None:
    """标记凭证失效，记录失败原因和时间。"""
    _auth_state["valid"] = False
    _auth_state["checked_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _auth_state["error"] = reason


def _mark_auth_ok() -> None:
    """标记凭证有效，清除之前的错误信息。"""
    _auth_state["valid"] = True
    _auth_state["checked_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _auth_state["error"] = ""


# ── 爬取任务 ────────────────────────────────────────────────────────────────────
# 爬取在后台线程中运行，前端通过轮询 /api/crawl/status 获取进度。
# _crawl_state 是共享状态，由后台线程写、API 线程读，
# 读写较简单（Python GIL 保护），暂不加锁。

_crawl_state: dict = {
    "running": False,      # 是否有爬取任务正在运行
    "total": 0,            # 本次需要处理的公众号总数
    "done": 0,             # 已处理完的公众号数（成功+失败）
    "current": "",         # 当前正在处理的公众号名称
    "errors": [],          # 本次爬取中出现的所有错误
    "started_at": "",      # 任务开始时间
    "finished_at": "",     # 任务结束时间（运行中为空）
    "new_articles": 0,     # 本次新增文章总数
    "auth_error": False,   # True = 因凭证失效提前终止（不是普通错误）
    "cancel_requested": False,  # 前端是否已请求取消
    "cancelled": False,  # True = 本次任务由用户取消
}
_crawl_lock = threading.Lock()  # 仅用于防止并发启动两个爬取任务

# 微信 API 返回这些 err_msg 时说明 token/cookie 已失效
_AUTH_FAIL_MSGS = {"invalid session", "invalid csrf token", "csrf token invalid"}


def _check_auth_valid() -> tuple[bool, str]:
    """
    向微信 API 发送一次轻量探测请求，检测 token/cookie 是否有效。

    为什么不用 WechatRequest？
    因为 WechatRequest 在检测到凭证失效时会自动调用 login()，
    而 login() 会尝试打开浏览器——在服务器进程中这会卡住或失败。
    这里直接用 requests 库发请求，只检测不登录。

    返回：(is_valid, reason)
      - is_valid=True, reason=""        → 凭证正常
      - is_valid=False, reason="..."    → 凭证失效，reason 说明原因
      - is_valid=True, reason="警告..."  → 网络异常，不确定，让主流程自行处理
    """
    try:
        import requests as req
        from src.utils.data_manager import data_manager

        id_info = data_manager.id_info
        token = id_info.get("token", "").strip()
        cookie = id_info.get("cookie", "").strip()
        if not token or not cookie:
            return False, "id_info.json 中 token 或 cookie 为空"

        h = dict(_DOWNLOAD_HEADERS)
        h["Cookie"] = cookie
        # 用 search_biz 接口做探测（参数随意，只看返回的 err_msg）
        params = {
            "action": "search_biz",
            "begin": 0,
            "count": 1,
            "query": "test",
            "token": token,
            "lang": "zh_CN",
            "f": "json",
            "ajax": 1,
        }
        resp = req.get(
            "https://mp.weixin.qq.com/cgi-bin/searchbiz?",
            params=params,
            headers=h,
            timeout=10,
        ).json()
        err_msg = resp.get("base_resp", {}).get("err_msg", "ok")
        if err_msg in _AUTH_FAIL_MSGS:
            return False, f"凭证已失效（{err_msg}）"
        return True, ""
    except Exception as e:
        # 网络超时等异常不等于凭证失效，返回 True 让主流程自行尝试
        return True, f"检测时出现异常（将尝试继续爬取）: {e}"


def _run_crawl_sqlite() -> None:
    """SQLite 存储下的爬取主流程（不写 message_info.json）。"""
    global _crawl_state
    from src.crawler.wechat_request import WechatRequest
    from src.db.repository import ArticleRepository
    from src.llm.article_tagging import tag_article
    from src.llm.llm_config import (
        llm_tagging_enabled,
        read_crawl_llm_multithread_enabled,
        read_crawl_llm_multithread_workers,
    )
    from src.utils.data_manager import data_manager
    from src.utils.helpers import time_now

    data_manager.reload("id_info")
    data_manager.reload("issues_message")

    auth_ok, auth_reason = _check_auth_valid()
    if not auth_ok:
        _crawl_state["auth_error"] = True
        _crawl_state["errors"].append(f"凭证失效，已终止爬取：{auth_reason}")
        _mark_auth_failed(auth_reason)
        _append_log(LOG_CRAWL_ERROR, f"凭证失效，爬取终止：{auth_reason}", {"reason": auth_reason})
        return

    with ArticleRepository() as repo:
        name2fakeid = repo.get_name2fakeid()
        _crawl_state["total"] = len(name2fakeid)
        _append_log(
            LOG_CRAWL_START,
            f"开始爬取，共 {len(name2fakeid)} 个公众号",
            {"accounts": list(name2fakeid.keys())},
        )

        wechat = WechatRequest()
        new_total = 0
        llm_enabled_for_crawl = llm_tagging_enabled()
        llm_multithread_for_crawl = read_crawl_llm_multithread_enabled()
        llm_multithread_workers_cap = read_crawl_llm_multithread_workers()

        for oa_name, fakeid in name2fakeid.items():
            if _crawl_state.get("cancel_requested"):
                _crawl_state["cancelled"] = True
                _crawl_state["errors"].append("用户手动取消爬取")
                _append_log(
                    LOG_CRAWL_FINISH,
                    "爬取被用户手动取消",
                    {"done": _crawl_state.get("done", 0), "total": _crawl_state.get("total", 0)},
                )
                break
            _crawl_state["current"] = oa_name
            try:
                repo.upsert_account(oa_name, fakeid)
                existing_blogs = repo.get_blogs_for_account(oa_name)
                new_articles = wechat.fakeid2message_update(fakeid, existing_blogs)

                if new_articles:
                    new_total += len(new_articles)
                    for article in new_articles:
                        repo.upsert_article_from_blog(
                            oa_name, article, update_fts=False
                        )
                        download_cover(
                            article["id"],
                            article.get("cover", ""),
                            COVERS_DIR,
                            _DOWNLOAD_HEADERS,
                        )
                        repo.update_cover_path(article["id"])
                        _fetch_article_detail_text(
                            article["id"], article.get("link", "")
                        )
                        wc = article_word_count(article, data_manager)
                        repo.set_word_count(article["id"], wc)
                        article["word_count"] = wc

                if llm_enabled_for_crawl:
                    try:
                        all_blogs = repo.get_blogs_for_account(oa_name)
                        need_analyze = [
                            a
                            for a in all_blogs
                            if not str(a.get("summary") or "").strip()
                        ]
                        if llm_multithread_for_crawl and len(need_analyze) > 1:
                            max_workers = min(
                                llm_multithread_workers_cap, len(need_analyze)
                            )
                            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                                future_to_article = {
                                    executor.submit(
                                        tag_article, article, data_manager
                                    ): article
                                    for article in need_analyze
                                }
                                for future in as_completed(future_to_article):
                                    if _crawl_state.get("cancel_requested"):
                                        _crawl_state["cancelled"] = True
                                        break
                                    article = future_to_article[future]
                                    try:
                                        analysis = future.result()
                                        tags = (
                                            analysis.get("tags")
                                            if isinstance(analysis, dict)
                                            else []
                                        )
                                        summary = (
                                            analysis.get("summary")
                                            if isinstance(analysis, dict)
                                            else ""
                                        )
                                        if tags or summary:
                                            repo.update_llm_fields(
                                                article["id"],
                                                str(summary or ""),
                                                tags or [],
                                            )
                                            article["summary"] = summary
                                            article["tags"] = tags
                                    except Exception as e:
                                        print(
                                            f"[tag] 单篇打标失败 {article.get('id')}: {e}"
                                        )
                        else:
                            for article in need_analyze:
                                if _crawl_state.get("cancel_requested"):
                                    _crawl_state["cancelled"] = True
                                    break
                                try:
                                    analysis = tag_article(article, data_manager)
                                    tags = (
                                        analysis.get("tags")
                                        if isinstance(analysis, dict)
                                        else []
                                    )
                                    summary = (
                                        analysis.get("summary")
                                        if isinstance(analysis, dict)
                                        else ""
                                    )
                                    if tags or summary:
                                        repo.update_llm_fields(
                                            article["id"],
                                            str(summary or ""),
                                            tags or [],
                                        )
                                except Exception as e:
                                    print(f"[tag] 单篇打标失败 {article.get('id')}: {e}")
                    except Exception as e:
                        print(f"[tag] 打标模块异常: {e}")

                repo.set_account_latest_crawl(oa_name, time_now())
                repo.commit()
                _mark_auth_ok()
            except Exception as e:
                err_str = str(e)
                _crawl_state["errors"].append(f"{oa_name}: {err_str}")
                _append_log(
                    LOG_CRAWL_ERROR,
                    f"爬取「{oa_name}」失败：{e}",
                    {"account": oa_name, "error": err_str},
                )
                if any(
                    kw in err_str.lower()
                    for kw in ("invalid session", "invalid csrf", "csrf token", "session")
                ):
                    _mark_auth_failed(err_str)
            finally:
                _crawl_state["done"] += 1
                _crawl_state["new_articles"] = new_total
                time.sleep(1.2)


def _run_crawl() -> None:
    """
    后台爬取线程的主函数，流程如下：

    1. 立即更新 _crawl_state.total，让前端第一次轮询就能看到账号总数
    2. 从磁盘重新加载最新凭证（data_manager.reload），支持手动更新 id_info.json
    3. 调用 _check_auth_valid() 做预检：凭证失效时立刻终止，不逐个账号重试
    4. 遍历所有公众号，调用 WechatRequest.fakeid2message_update() 获取新文章
    5. 对每篇新文章下载封面图、拉正文；可选 LLM 生成摘要+标签写入 SQLite
    6. 每处理完一个公众号（成功或失败），done += 1
    7. 全部完成后写入结束日志，设置 running=False
    """
    global _crawl_state
    try:
        quick_n2f = _read_name2fakeid()
        started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _crawl_state.update({
            "running": True,
            "total": len(quick_n2f),
            "done": 0,
            "current": "",
            "errors": [],
            "started_at": started_at,
            "finished_at": "",
            "new_articles": 0,
            "auth_error": False,
            "cancel_requested": False,
            "cancelled": False,
        })

        _run_crawl_sqlite()

    except Exception as e:
        # 初始化阶段（循环外）出现的异常
        err_str = str(e)
        _crawl_state["errors"].append(f"初始化失败: {err_str}")
        _append_log(LOG_CRAWL_ERROR, f"爬取初始化失败：{e}", {"error": err_str})
        if any(kw in err_str.lower() for kw in ("invalid session", "invalid csrf", "csrf token", "cookie", "token")):
            _mark_auth_failed(err_str)
    finally:
        # 无论正常结束还是抛出异常，都要更新结束状态
        finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _crawl_state["current"] = ""
        _crawl_state["finished_at"] = finished_at
        _crawl_state["running"] = False
        errors = _crawl_state["errors"]
        _append_log(
            LOG_CRAWL_FINISH,
            f"爬取完成：新增 {_crawl_state['new_articles']} 篇，"
            f"共 {_crawl_state['total']} 个公众号，{len(errors)} 个错误",
            {
                "new_articles": _crawl_state["new_articles"],
                "total_accounts": _crawl_state["total"],
                "errors": errors,
                "started_at": _crawl_state.get("started_at", ""),
                "finished_at": finished_at,
            },
        )


@app.post("/api/crawl")
def start_crawl():
    """
    启动后台爬取任务。
    同一时间只允许一个爬取任务运行，重复调用返回 409 冲突。
    """
    with _crawl_lock:
        if _crawl_state["running"]:
            raise HTTPException(status_code=409, detail="爬取任务正在进行中，请等待完成后再试")
        # daemon=True：主进程退出时后台线程自动终止，不会阻止程序退出
        t = threading.Thread(target=_run_crawl, daemon=True)
        t.start()
    return {"status": "started", "message": "爬取任务已开始"}


@app.post("/api/crawl/cancel")
def cancel_crawl():
    """请求取消当前爬取任务（协作式中断）。"""
    if not _crawl_state.get("running"):
        return {"status": "idle", "message": "当前没有运行中的爬取任务"}
    _crawl_state["cancel_requested"] = True
    return {"status": "cancelling", "message": "已请求取消，正在停止当前爬取"}


@app.get("/api/crawl/status", response_model=CrawlStatus)
def get_crawl_status():
    """返回当前爬取任务的实时进度，前端每隔 800ms 轮询一次。"""
    return CrawlStatus(**_crawl_state)


# ── 缓存清理 ─────────────────────────────────────────────────────────────────────
# 随着爬取积累，message_info.json 和封面图会越来越多。
# 这组接口允许用户按"保留最近 N 天"的策略清理旧数据。

class CachePreview(BaseModel):
    """清理预览结果，让用户在执行前看到将删除的数量。"""
    keep_days: int
    cutoff_date: str          # 截止日期（此日期之前的文章会被删除）
    total_articles: int       # 当前全部文章数
    removable_articles: int   # 将被删除的文章数
    removable_covers: int     # 将被删除的封面图数
    removable_detail_texts: int  # 将被删除的详情缓存数


class CacheClearRequest(BaseModel):
    """清理请求，指定要保留的天数。"""
    keep_days: int = 90


class CacheClearResult(BaseModel):
    """清理结果，返回实际删除的数量。"""
    removed_articles: int
    removed_covers: int
    removed_detail_texts: int


class LlmConfigResponse(BaseModel):
    """LLM 打标配置（GET 返回；api_key 仅示意，不返回明文）。"""
    profile_name: str
    active_profile: str
    profiles: list[dict]
    provider: str
    base_url: str
    model: str
    task_profile: str = ""
    crawl_llm_enabled: bool = False
    crawl_llm_multithread_enabled: bool = False
    crawl_llm_multithread_workers: int = 4
    temperature: float
    max_tokens: int
    timeout_seconds: int
    top_k: int = 20
    top_p: float = 0.8
    min_p: float = 0.0
    repetition_penalty: float = 1.0
    presence_penalty: float = 1.5
    enable_thinking: bool = False
    has_api_key: bool
    api_key_hint: str


class LlmConfigUpdate(BaseModel):
    """保存 LLM 配置；api_key 不传或 null 表示保留原值，空字符串表示清除。"""
    profile_name: str = "默认配置"
    source_profile_name: Optional[str] = Field(default=None)
    set_active: bool = True
    provider: str
    base_url: str
    model: str
    task_profile: str = ""
    crawl_llm_enabled: Optional[bool] = Field(default=None)
    crawl_llm_multithread_enabled: Optional[bool] = Field(default=None)
    crawl_llm_multithread_workers: Optional[int] = Field(default=None)
    temperature: float = 0.2
    max_tokens: int = 1024
    timeout_seconds: int = 120
    top_k: int = 20
    top_p: float = 0.8
    min_p: float = 0.0
    repetition_penalty: float = 1.0
    presence_penalty: float = 1.5
    enable_thinking: bool = False
    api_key: Optional[str] = Field(default=None)


class LlmTestResult(BaseModel):
    """连通性测试结果。"""
    ok: bool
    message: str
    preview: str = ""


class LlmTestRequest(BaseModel):
    """未保存表单上测试连通时可选覆盖的字段（未出现的项沿用当前 profile 已保存值）。"""

    provider: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    timeout_seconds: Optional[int] = None
    top_k: Optional[int] = None
    top_p: Optional[float] = None
    min_p: Optional[float] = None
    repetition_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    enable_thinking: Optional[bool] = None


class LlmDiscoverRequest(BaseModel):
    """vLLM 模式：OpenAI SDK 拉取模型列表。HTTP 直连模式不支持。"""

    provider: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    timeout_seconds: Optional[int] = None


class LlmDiscoverResult(BaseModel):
    ok: bool
    message: str = ""
    models: list[str] = []


class LlmProfileSelect(BaseModel):
    profile_name: str


class LlmProfileReset(BaseModel):
    profile_name: Optional[str] = Field(default=None)


class LlmTaskProfileUpdate(BaseModel):
    """仅更新任务统一绑定的 profile 名，立即写入 llm_config.json。"""

    task_profile: str = ""


class LlmCrawlEnabledUpdate(BaseModel):
    """仅更新“爬取时启用模型总结和打标”的全局开关。"""

    crawl_llm_enabled: bool


class LlmCrawlMultithreadEnabledUpdate(BaseModel):
    """更新爬取补总结/打标的多线程开关与并发数（可只传其中一项）。"""

    crawl_llm_multithread_enabled: Optional[bool] = None
    crawl_llm_multithread_workers: Optional[int] = None


def _mask_api_key_hint(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 4:
        return "****"
    return "****" + key[-4:]


def _collect_removable_ids(keep_days: int) -> tuple[str, set[str]]:
    """
    计算哪些文章 ID 需要被删除。

    返回 (cutoff_date_str, set_of_removable_ids)：
    - cutoff_date_str：截止日期字符串（格式 "YYYY-MM-DD HH:MM"）
    - set_of_removable_ids：所有早于截止日期的文章 ID 集合
    """
    cutoff = (datetime.now() - timedelta(days=keep_days)).strftime("%Y-%m-%d %H:%M")
    from src.db.repository import ArticleRepository

    with ArticleRepository() as repo:
        return cutoff, repo.ids_older_than(cutoff)


@app.get("/api/cache/preview", response_model=CachePreview)
def cache_preview(keep_days: int = 90):
    """
    预览清理结果：统计将被删除的文章数、封面图数、详情缓存数。
    不执行任何实际删除，只供前端展示确认弹窗。
    """
    if keep_days < 1:
        raise HTTPException(status_code=400, detail="keep_days 必须 >= 1")

    cutoff, removable_ids = _collect_removable_ids(keep_days)
    from src.db.repository import ArticleRepository

    with ArticleRepository() as repo:
        total_articles = repo.count_articles()
    removable_detail_texts = len(removable_ids)

    removable_covers = 0
    if COVERS_DIR.exists():
        cover_files = {f.stem: f for f in COVERS_DIR.glob("*.jpg")}
        for rid in removable_ids:
            if rid.replace("/", "_") in cover_files:
                removable_covers += 1

    return CachePreview(
        keep_days=keep_days,
        cutoff_date=cutoff[:10],
        total_articles=total_articles,
        removable_articles=len(removable_ids),
        removable_covers=removable_covers,
        removable_detail_texts=removable_detail_texts,
    )


@app.post("/api/cache/clear", response_model=CacheClearResult)
def clear_cache(body: CacheClearRequest):
    """
    执行缓存清理，删除早于 keep_days 天的文章（SQLite）及对应封面图。

    爬取任务运行期间禁止清理，以避免数据写入冲突。
    """
    if _crawl_state["running"]:
        raise HTTPException(status_code=409, detail="爬取任务正在进行中，请等待完成后再清理")
    if body.keep_days < 1:
        raise HTTPException(status_code=400, detail="keep_days 必须 >= 1")

    _, removable_ids = _collect_removable_ids(body.keep_days)
    if not removable_ids:
        return CacheClearResult(removed_articles=0, removed_covers=0, removed_detail_texts=0)

    from src.db.repository import ArticleRepository

    removed_covers = 0
    if COVERS_DIR.exists():
        for rid in removable_ids:
            cover_path = COVERS_DIR / (rid.replace("/", "_") + ".jpg")
            if cover_path.exists():
                cover_path.unlink()
                removed_covers += 1
    with ArticleRepository() as repo:
        removed_articles = repo.delete_articles_by_ids(removable_ids)
        repo.commit()
    _append_log(
        LOG_CACHE_CLEAR,
        f"清理缓存：删除 {removed_articles} 篇文章（{body.keep_days} 天前），封面图 {removed_covers} 张",
        {
            "keep_days": body.keep_days,
            "removed_articles": removed_articles,
            "removed_covers": removed_covers,
        },
    )
    return CacheClearResult(
        removed_articles=removed_articles,
        removed_covers=removed_covers,
        removed_detail_texts=removed_articles,
    )



# ── LLM 打标配置 API（读写 data/llm_config.json）──────────────────────────────

@app.get("/api/llm/config", response_model=LlmConfigResponse)
def get_llm_config_api():
    from src.llm.llm_config import (
        read_crawl_llm_enabled,
        read_crawl_llm_multithread_enabled,
        read_crawl_llm_multithread_workers,
        read_llm_config,
        read_llm_store,
    )

    c = read_llm_config()
    store = read_llm_store()
    profile_name = store["active_profile"]
    task_profile = str(store.get("task_profile") or "")
    profiles = []
    for p in store["profiles"]:
        key = str(p.get("api_key") or "")
        profiles.append({
            "name": p["name"],
            "provider": p["provider"],
            "base_url": p["base_url"],
            "model": p["model"],
            "has_api_key": bool(key),
            "api_key_hint": _mask_api_key_hint(key),
        })
    k = str(c.get("api_key") or "")
    return LlmConfigResponse(
        profile_name=profile_name,
        active_profile=store["active_profile"],
        profiles=profiles,
        provider=c["provider"],
        base_url=c["base_url"],
        model=c["model"],
        task_profile=task_profile,
        crawl_llm_enabled=read_crawl_llm_enabled(),
        crawl_llm_multithread_enabled=read_crawl_llm_multithread_enabled(),
        crawl_llm_multithread_workers=read_crawl_llm_multithread_workers(),
        temperature=float(c["temperature"]),
        max_tokens=int(c["max_tokens"]),
        timeout_seconds=int(c["timeout_seconds"]),
        top_k=int(c["top_k"]),
        top_p=float(c["top_p"]),
        min_p=float(c["min_p"]),
        repetition_penalty=float(c["repetition_penalty"]),
        presence_penalty=float(c["presence_penalty"]),
        enable_thinking=bool(c["enable_thinking"]),
        has_api_key=bool(k),
        api_key_hint=_mask_api_key_hint(k),
    )


@app.put("/api/llm/config", response_model=LlmConfigResponse)
def put_llm_config_api(body: LlmConfigUpdate):
    from src.llm.llm_config import (
        VALID_PROVIDERS,
        read_llm_config,
        set_llm_task_profile,
        write_crawl_llm_enabled,
        write_crawl_llm_multithread_enabled,
        write_crawl_llm_multithread_workers,
        write_llm_config,
    )

    prov = (body.provider or "").strip()
    if prov not in VALID_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail="provider 须为 vllm（OpenAI SDK，根地址 …/v1）或 http_requests（requests 直连完整 Chat URL）",
        )
    cur = read_llm_config()
    merged = {
        **cur,
        "provider": prov,
        "base_url": (body.base_url or "").strip(),
        "model": (body.model or "").strip(),
        "temperature": body.temperature,
        "max_tokens": body.max_tokens,
        "timeout_seconds": body.timeout_seconds,
        "top_k": body.top_k,
        "top_p": body.top_p,
        "min_p": body.min_p,
        "repetition_penalty": body.repetition_penalty,
        "presence_penalty": body.presence_penalty,
        "enable_thinking": bool(body.enable_thinking),
    }
    if body.api_key is not None:
        merged["api_key"] = (body.api_key or "").strip()
    try:
        write_llm_config(
            merged,
            profile_name=(body.profile_name or "默认配置").strip() or "默认配置",
            set_active=bool(body.set_active),
            source_profile_name=(body.source_profile_name or "").strip() or None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        set_llm_task_profile(body.task_profile)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if body.crawl_llm_enabled is not None:
        write_crawl_llm_enabled(bool(body.crawl_llm_enabled))
    if body.crawl_llm_multithread_enabled is not None:
        write_crawl_llm_multithread_enabled(bool(body.crawl_llm_multithread_enabled))
    if body.crawl_llm_multithread_workers is not None:
        write_crawl_llm_multithread_workers(int(body.crawl_llm_multithread_workers))
    return get_llm_config_api()


@app.put("/api/llm/config/task-profile", response_model=LlmConfigResponse)
def put_llm_task_profile_api(body: LlmTaskProfileUpdate):
    """仅更新任务绑定的 profile，不改动各 profile 的连接与模型字段。"""
    from src.llm.llm_config import set_llm_task_profile

    try:
        set_llm_task_profile(body.task_profile)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return get_llm_config_api()


@app.put("/api/llm/config/crawl-llm-enabled", response_model=LlmConfigResponse)
def put_llm_crawl_enabled_api(body: LlmCrawlEnabledUpdate):
    from src.llm.llm_config import write_crawl_llm_enabled

    write_crawl_llm_enabled(bool(body.crawl_llm_enabled))
    return get_llm_config_api()


@app.put("/api/llm/config/crawl-llm-multithread-enabled", response_model=LlmConfigResponse)
def put_llm_crawl_multithread_enabled_api(body: LlmCrawlMultithreadEnabledUpdate):
    from src.llm.llm_config import (
        write_crawl_llm_multithread_enabled,
        write_crawl_llm_multithread_workers,
    )

    if body.crawl_llm_multithread_enabled is None and body.crawl_llm_multithread_workers is None:
        raise HTTPException(
            status_code=400,
            detail="至少需要提供 crawl_llm_multithread_enabled 或 crawl_llm_multithread_workers",
        )
    if body.crawl_llm_multithread_enabled is not None:
        write_crawl_llm_multithread_enabled(bool(body.crawl_llm_multithread_enabled))
    if body.crawl_llm_multithread_workers is not None:
        write_crawl_llm_multithread_workers(int(body.crawl_llm_multithread_workers))
    return get_llm_config_api()


@app.post("/api/llm/config/select", response_model=LlmConfigResponse)
def select_llm_profile_api(body: LlmProfileSelect):
    from src.llm.llm_config import set_active_profile

    name = (body.profile_name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="profile_name 不能为空")
    if not set_active_profile(name):
        raise HTTPException(status_code=404, detail=f"配置「{name}」不存在")
    return get_llm_config_api()


@app.delete("/api/llm/config/{profile_name:path}", response_model=LlmConfigResponse)
def delete_llm_profile_api(profile_name: str):
    from src.llm.llm_config import delete_profile

    name = (profile_name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="profile_name 不能为空")
    ok, reason = delete_profile(name)
    if not ok:
        if reason == "last_profile":
            raise HTTPException(status_code=400, detail="至少保留一个配置，无法删除最后一个")
        raise HTTPException(status_code=404, detail=f"配置「{name}」不存在")
    return get_llm_config_api()


@app.post("/api/llm/config/reset", response_model=LlmConfigResponse)
def reset_llm_profile_api(body: LlmProfileReset):
    from src.llm.llm_config import reset_profile

    name = (body.profile_name or "").strip() or None
    ok, reason = reset_profile(name)
    if not ok:
        if name:
            raise HTTPException(status_code=404, detail=f"配置「{name}」不存在")
        raise HTTPException(status_code=404, detail="当前配置不存在")
    return get_llm_config_api()


@app.post("/api/llm/test", response_model=LlmTestResult)
def test_llm_api(body: Optional[LlmTestRequest] = Body(default=None)):
    """发送一条极简对话；请求体可带当前表单覆盖项，无需先保存（与 QwenPaw 测连思路一致）。"""
    from src.llm.model_client import (
        chat_completions_with_config,
        is_chat_test_ready,
        merge_llm_config_for_ephemeral,
    )

    payload = body.model_dump(exclude_unset=True) if body else {}
    cfg = merge_llm_config_for_ephemeral(payload)
    if not is_chat_test_ready(cfg):
        raise HTTPException(status_code=400, detail="请先填写接口地址与模型名（可在表单中填写后直接测试）")
    try:
        text = chat_completions_with_config(
            cfg,
            [{"role": "user", "content": "只回复一个字：好"}],
            require_enabled=False,
        )
        return LlmTestResult(ok=True, message="请求成功", preview=(text or "")[:300])
    except Exception as e:
        return LlmTestResult(ok=False, message=str(e), preview="")


@app.post("/api/llm/models/discover", response_model=LlmDiscoverResult)
def discover_llm_models_api(body: Optional[LlmDiscoverRequest] = Body(default=None)):
    """vLLM：OpenAI SDK ``models.list()``。HTTP 直连模式不支持拉列表。"""
    from src.llm.llm_config import PROVIDER_HTTP, PROVIDER_VLLM
    from src.llm.model_client import fetch_vllm_model_ids_sdk, merge_llm_config_for_ephemeral

    payload = body.model_dump(exclude_unset=True) if body else {}
    cfg = merge_llm_config_for_ephemeral(payload)
    prov = str(cfg.get("provider") or PROVIDER_HTTP)
    if prov == PROVIDER_HTTP:
        return LlmDiscoverResult(
            ok=False,
            message="HTTP 直连模式不拉取模型列表，请手动填写模型名（与 requests 调用一致）。",
            models=[],
        )
    if prov != PROVIDER_VLLM:
        return LlmDiscoverResult(ok=False, message=f"未知 provider: {prov}", models=[])
    base = str(cfg.get("base_url") or "").strip()
    if not base:
        return LlmDiscoverResult(ok=False, message="请先填写 vLLM 根地址（如 http://host:8055/v1）", models=[])
    timeout = float(cfg.get("timeout_seconds") or 120)
    timeout = max(5.0, min(timeout, 120.0))
    api_key = str(cfg.get("api_key") or "").strip()
    try:
        models = fetch_vllm_model_ids_sdk(base, api_key=api_key, timeout=timeout)
        if not models:
            return LlmDiscoverResult(ok=False, message="服务端返回的模型列表为空", models=[])
        return LlmDiscoverResult(
            ok=True,
            message=f"共 {len(models)} 个模型",
            models=models,
        )
    except Exception as e:
        return LlmDiscoverResult(ok=False, message=str(e), models=[])


# ── 日志查询 API ────────────────────────────────────────────────────────────────

class LogEntry(BaseModel):
    """单条操作日志的结构。"""
    timestamp: str
    type: str
    message: str
    details: dict


@app.get("/api/logs", response_model=list[LogEntry])
def get_logs(limit: int = 200):
    """
    返回最近 limit 条操作日志，按时间倒序（最新的在最前面）。
    日志文件为 JSONL 格式，每行一条。
    """
    if not LOGS_FILE.exists():
        return []
    with open(LOGS_FILE, encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    entries = []
    # 先取最后 limit 行（最新的），再反转让最新的排在最前
    for line in reversed(lines[-limit:]):
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


# ── 凭证状态查询 API ────────────────────────────────────────────────────────────

class AuthStatus(BaseModel):
    """凭证状态的完整信息，供前端状态横幅展示。"""
    has_credentials: bool  # id_info.json 中是否有非空的 token 和 cookie
    valid: bool            # 上次检测/爬取是否成功（False 表示凭证失效）
    checked_at: str        # 上次检测时间（空 = 本次启动后尚未检测）
    error: str             # 失败原因（空 = 正常）
    token_hint: str        # token 前 8 位，供用户确认是否是最新的值
    id_info_mtime: str     # id_info.json 文件的最后修改时间


def _build_auth_status() -> AuthStatus:
    """
    组合内存中的 _auth_state 和磁盘上的 id_info.json 元数据，
    构建完整的 AuthStatus 对象。
    """
    id_info_file = DATA_DIR / "id_info.json"
    has_credentials = False
    token_hint = ""
    mtime = ""

    if id_info_file.exists():
        try:
            with open(id_info_file, encoding="utf-8") as f:
                info = json.load(f)
            token = info.get("token", "").strip()
            cookie = info.get("cookie", "").strip()
            has_credentials = bool(token and cookie)
            # 只展示 token 前 8 位，防止完整 token 被截图泄露
            token_hint = token[:8] + "..." if len(token) > 8 else token
            mtime = datetime.fromtimestamp(id_info_file.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass

    return AuthStatus(
        has_credentials=has_credentials,
        valid=_auth_state["valid"],
        checked_at=_auth_state["checked_at"],
        error=_auth_state["error"],
        token_hint=token_hint,
        id_info_mtime=mtime,
    )


@app.get("/api/auth/status", response_model=AuthStatus)
def get_auth_status():
    """
    返回缓存的凭证状态，不发起实际微信请求。
    用于页面加载时快速展示状态，速度快但可能不是最新结果。
    """
    return _build_auth_status()


@app.post("/api/auth/check", response_model=AuthStatus)
def check_auth_now():
    """
    主动向微信 API 发起探测请求，实时验证 token/cookie 是否有效。
    用于用户手动点击"重新检测"时，会更新内存中的 _auth_state。
    调用前先从磁盘重新加载凭证，确保检测的是用户最新修改的值。
    """
    from src.utils.data_manager import data_manager
    # 先重新加载，确保使用的是用户最新修改的凭证
    data_manager.reload("id_info")

    ok, reason = _check_auth_valid()
    if ok:
        _mark_auth_ok()
    else:
        _mark_auth_failed(reason)

    return _build_auth_status()


# ── 扫码登录（对齐 wechat-article-exporter 四步流程）────────────────────────────
# ① POST /api/auth/login/session     → startlogin + 首屏二维码
# ② GET  /api/auth/login/qrcode      → 二维码过期时刷新（status 2/3）
# ③ GET  /api/auth/login/scan        → ask 单次轮询（前端约 2s 一次）
# ④ POST /api/auth/login/complete    → bizlogin，写入 id_info.json
#
# 同一会话共用服务端 MpScanLogin.session（uuid Cookie 由 requests 维护）。

_active_login = None
_login_lock = threading.Lock()


def _require_login_session():
    with _login_lock:
        if _active_login is None:
            raise HTTPException(status_code=404, detail="登录会话不存在或已结束，请重新扫码")
        return _active_login


def _clear_login_session() -> None:
    global _active_login
    with _login_lock:
        _active_login = None


def _qrcode_payload(login) -> dict:
    img = login.fetch_qrcode_data_url()
    return {
        "img": img,
        "refreshed_at": datetime.now().strftime("%H:%M:%S"),
    }


class LoginSessionResponse(BaseModel):
    ok: bool = True
    img: str
    refreshed_at: str
    scan_status: int = 0
    scan_message: str = ""


class ScanPollResponse(BaseModel):
    ret: int
    err_msg: str = ""
    status: int
    acct_size: int = 0
    message: str


class LoginCompleteResponse(BaseModel):
    ok: bool = True
    token_hint: str = ""


@app.post("/api/auth/login/session", response_model=LoginSessionResponse)
def create_login_session():
    """① 建立扫码会话并返回首张二维码。"""
    global _active_login
    from src.auth.mp_scan_login import MpScanLogin, scan_status_message

    with _login_lock:
        _active_login = MpScanLogin()
        login = _active_login
    try:
        login.start_session()
        payload = _qrcode_payload(login)
        return LoginSessionResponse(
            img=payload["img"],
            refreshed_at=payload["refreshed_at"],
            scan_status=0,
            scan_message=scan_status_message(0),
        )
    except Exception as e:
        _clear_login_session()
        raise HTTPException(status_code=502, detail=str(e)) from e


@app.get("/api/auth/login/qrcode")
def refresh_login_qrcode():
    """② 刷新二维码（status 为 2/3 时由前端调用）。"""
    login = _require_login_session()
    try:
        return _qrcode_payload(login)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@app.get("/api/auth/login/scan", response_model=ScanPollResponse)
def poll_login_scan():
    """③ 单次 ask 轮询，返回 status 与可读文案。"""
    login = _require_login_session()
    try:
        result = login.poll_scan()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    if result.ret != 0 and result.status < 0:
        raise HTTPException(
            status_code=502,
            detail=result.message or result.err_msg or "扫码状态查询失败",
        )

    return ScanPollResponse(
        ret=result.ret,
        err_msg=result.err_msg,
        status=result.status,
        acct_size=result.acct_size,
        message=result.message,
    )


@app.post("/api/auth/login/complete", response_model=LoginCompleteResponse)
def complete_login_session():
    """④ 手机确认后完成登录并持久化凭证。"""
    from src.utils.data_manager import data_manager

    login = _require_login_session()
    try:
        token, cookie_str = login.complete_login()
        data_manager.id_info["token"] = token
        data_manager.id_info["cookie"] = cookie_str
        data_manager.write("id_info")
        _mark_auth_ok()
        hint = token[:8] + "…" if len(token) > 8 else token
        return LoginCompleteResponse(ok=True, token_hint=hint)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    finally:
        _clear_login_session()


@app.post("/api/auth/login/cancel")
def cancel_login_session():
    """放弃当前扫码会话。"""
    _clear_login_session()
    return {"ok": True}
