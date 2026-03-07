#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
轻量 FastAPI 后端，供前端管理公众号列表使用。

启动方式：
    uvicorn api:app --reload --port 8000
"""

import json
import threading
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

DATA_DIR = Path(__file__).parent / "data"
NAME2FAKEID_FILE = DATA_DIR / "name2fakeid.json"
MESSAGE_INFO_FILE = DATA_DIR / "message_info.json"
COVERS_DIR = DATA_DIR / "covers"
LOGS_FILE = DATA_DIR / "operation_logs.jsonl"

app = FastAPI(title="微信公众号聚合 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _read_name2fakeid() -> dict[str, str]:
    if not NAME2FAKEID_FILE.exists():
        return {}
    with open(NAME2FAKEID_FILE, encoding="utf-8") as f:
        return json.load(f)


def _write_name2fakeid(data: dict[str, str]) -> None:
    with open(NAME2FAKEID_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def _read_message_info() -> dict:
    if not MESSAGE_INFO_FILE.exists():
        return {}
    with open(MESSAGE_INFO_FILE, encoding="utf-8") as f:
        return json.load(f)


# ---------- 数据模型 ----------

class SearchRequest(BaseModel):
    query: str


class SearchCandidate(BaseModel):
    fakeid: str
    nickname: str
    alias: str
    avatar: str          # round_head_img
    signature: str
    service_type: int    # 0=订阅号, 1=服务号, 2=其他


class ConfirmAddRequest(BaseModel):
    name: str    # 用户确认使用的名称（即 nickname）
    fakeid: str  # 从搜索结果中选定的 fakeid


class AccountStatus(BaseModel):
    name: str
    fakeid: str
    has_articles: bool
    article_count: int
    latest_update_time: str


class CrawlStatus(BaseModel):
    running: bool
    total: int
    done: int
    current: str
    errors: list[str]
    started_at: str
    finished_at: str
    new_articles: int


# ---------- 日志 ----------

_log_lock = threading.Lock()

# 日志类型常量
LOG_CRAWL_START   = "crawl_start"
LOG_CRAWL_FINISH  = "crawl_finish"
LOG_CRAWL_ERROR   = "crawl_error"
LOG_ACCOUNT_ADD   = "account_add"
LOG_ACCOUNT_REMOVE = "account_remove"
LOG_CACHE_CLEAR   = "cache_clear"


def _append_log(log_type: str, message: str, details: dict | None = None) -> None:
    """向 data/operation_logs.jsonl 追加一条日志（线程安全）。"""
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": log_type,
        "message": message,
        "details": details or {},
    }
    with _log_lock:
        LOGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOGS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ---------- 工具函数 ----------

_DOWNLOAD_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36',
    'Referer': 'https://mp.weixin.qq.com/',
}


def _download_cover(article_id: str, cover_url: str) -> None:
    """下载单篇文章的封面图到 data/covers/{id}.jpg，宽度超过 640px 时等比缩放。"""
    if not cover_url:
        return
    COVERS_DIR.mkdir(parents=True, exist_ok=True)
    filename = article_id.replace("/", "_") + ".jpg"
    dest = COVERS_DIR / filename
    if dest.exists():
        return
    try:
        import io
        import requests
        from PIL import Image

        resp = requests.get(cover_url, timeout=15, headers=_DOWNLOAD_HEADERS)
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


def _get_wechat():
    try:
        from src import WechatRequest
        return WechatRequest()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"初始化微信请求失败：{e}，请确认 data/id_info.json 有效")


# ---------- 路由 ----------

@app.get("/api/accounts", response_model=list[AccountStatus])
def list_accounts():
    """返回所有已添加的公众号及其状态。"""
    name2fakeid = _read_name2fakeid()
    message_info = _read_message_info()

    result = []
    for name, fakeid in name2fakeid.items():
        entry = message_info.get(name, {})
        blogs = entry.get("blogs", [])
        active_blogs = [b for b in blogs if not b.get("is_deleted", False)]
        result.append(
            AccountStatus(
                name=name,
                fakeid=fakeid,
                has_articles=len(active_blogs) > 0,
                article_count=len(active_blogs),
                latest_update_time=entry.get("latest_update_time", ""),
            )
        )
    return result


@app.post("/api/accounts/search", response_model=list[SearchCandidate])
def search_accounts(body: SearchRequest):
    """
    搜索公众号，返回候选列表（最多 5 条）。
    前端展示给用户选择，用户确认后再调用 POST /api/accounts 添加。
    """
    query = body.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="搜索关键词不能为空")

    _get_wechat()  # 验证 id_info 有效，初始化失败时直接抛 503
    try:
        import requests as req
        from src.utils.data_manager import data_manager, headers as wechat_headers
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
        ).json()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"微信接口请求失败：{e}")

    if response.get('base_resp', {}).get('ret') != 0:
        raise HTTPException(
            status_code=502,
            detail=f"微信接口返回错误：{response.get('base_resp', {}).get('err_msg', '未知')}，请检查 token/cookie 是否过期",
        )

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
    确认添加：直接使用前端传入的 name + fakeid 写入 name2fakeid.json。
    在此之前应先调用 /api/accounts/search 并由用户选择。
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
    _append_log(LOG_ACCOUNT_ADD, f"添加公众号「{name}」", {"name": name, "fakeid": fakeid})

    return AccountStatus(
        name=name,
        fakeid=fakeid,
        has_articles=False,
        article_count=0,
        latest_update_time="",
    )


@app.delete("/api/accounts/{name}", status_code=204)
def remove_account(name: str):
    """从跟踪列表中移除公众号（不删除已爬取的文章数据）。"""
    name2fakeid = _read_name2fakeid()
    if name not in name2fakeid:
        raise HTTPException(status_code=404, detail=f"公众号「{name}」不在列表中")

    del name2fakeid[name]
    _write_name2fakeid(name2fakeid)
    _append_log(LOG_ACCOUNT_REMOVE, f"移除公众号「{name}」", {"name": name})


# ---------- 爬取任务 ----------

_crawl_state: dict = {
    "running": False,
    "total": 0,
    "done": 0,
    "current": "",
    "errors": [],
    "started_at": "",
    "finished_at": "",
    "new_articles": 0,
}
_crawl_lock = threading.Lock()


def _run_crawl() -> None:
    """后台线程：遍历所有公众号爬取近一月文章，基于文章 id 去重。"""
    global _crawl_state
    try:
        # 立即更新状态（使用直接读文件的方式获取账号数），让前端第一次轮询就能看到正确的 total
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
        })

        from src.crawler.wechat_request import WechatRequest
        from src.utils.data_manager import data_manager
        from src.utils.helpers import time_now

        # 从磁盘重新加载，避免内存数据过期
        data_manager.reload("name2fakeid")
        data_manager.reload("message_info")
        data_manager.reload("issues_message")

        name2fakeid: dict[str, str] = dict(data_manager.name2fakeid)
        # reload 后账号数可能有变化，同步更新 total
        _crawl_state["total"] = len(name2fakeid)

        _append_log(LOG_CRAWL_START, f"开始爬取，共 {len(name2fakeid)} 个公众号",
                    {"accounts": list(name2fakeid.keys())})

        wechat = WechatRequest()
        new_total = 0

        for oa_name, fakeid in name2fakeid.items():
            _crawl_state["current"] = oa_name
            try:
                # 初始化公众号记录（首次爬取时）
                if oa_name not in data_manager.message_info:
                    data_manager.message_info[oa_name] = {
                        "latest_update_time": "2000-01-01 00:00",
                        "blogs": [],
                    }

                existing_blogs: list = data_manager.message_info[oa_name]["blogs"]
                # fakeid2message_update 内部已按 id 去重，只返回新文章
                new_articles = wechat.fakeid2message_update(fakeid, existing_blogs)

                if new_articles:
                    data_manager.message_info[oa_name]["blogs"].extend(new_articles)
                    new_total += len(new_articles)
                    # 下载新文章的封面图（已存在则跳过）
                    for article in new_articles:
                        _download_cover(article["id"], article.get("cover", ""))

                data_manager.message_info[oa_name]["latest_update_time"] = time_now()
                data_manager.write("message_info")

            except Exception as e:
                err_msg = f"{oa_name}: {e}"
                _crawl_state["errors"].append(err_msg)
                _append_log(LOG_CRAWL_ERROR, f"爬取「{oa_name}」失败：{e}",
                            {"account": oa_name, "error": str(e)})
            finally:
                _crawl_state["done"] += 1
                _crawl_state["new_articles"] = new_total

    except Exception as e:
        _crawl_state["errors"].append(f"初始化失败: {e}")
        _append_log(LOG_CRAWL_ERROR, f"爬取初始化失败：{e}", {"error": str(e)})
    finally:
        finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _crawl_state["current"] = ""
        _crawl_state["finished_at"] = finished_at
        _crawl_state["running"] = False
        errors = _crawl_state["errors"]
        _append_log(
            LOG_CRAWL_FINISH,
            f"爬取完成：新增 {_crawl_state['new_articles']} 篇，"
            f"{'成功' if not errors else f'{len(errors)} 个账号失败'}",
            {
                "new_articles": _crawl_state["new_articles"],
                "total_accounts": _crawl_state["total"],
                "error_count": len(errors),
                "errors": errors,
                "started_at": _crawl_state.get("started_at", ""),
                "finished_at": finished_at,
            },
        )


@app.post("/api/crawl")
def start_crawl():
    """启动后台爬取任务（每次只允许一个任务运行）。"""
    with _crawl_lock:
        if _crawl_state["running"]:
            raise HTTPException(status_code=409, detail="爬取任务正在进行中，请等待完成后再试")
        t = threading.Thread(target=_run_crawl, daemon=True)
        t.start()
    return {"status": "started", "message": "爬取任务已开始"}


@app.get("/api/crawl/status", response_model=CrawlStatus)
def get_crawl_status():
    """获取当前爬取任务的进度。"""
    return CrawlStatus(**_crawl_state)


# ---------- 缓存清理 ----------

class CachePreview(BaseModel):
    keep_days: int
    cutoff_date: str          # 截止日期（此日期之前的文章会被删除）
    total_articles: int       # 当前全部文章数
    removable_articles: int   # 将被删除的文章数
    removable_covers: int     # 将被删除的封面图数
    removable_detail_texts: int  # 将被删除的详情缓存数


class CacheClearRequest(BaseModel):
    keep_days: int = 90


class CacheClearResult(BaseModel):
    removed_articles: int
    removed_covers: int
    removed_detail_texts: int


def _collect_removable_ids(keep_days: int) -> tuple[str, set[str]]:
    """返回 (cutoff_date_str, set_of_ids_to_remove)。"""
    cutoff = (datetime.now() - timedelta(days=keep_days)).strftime("%Y-%m-%d %H:%M")
    message_info = _read_message_info()
    removable: set[str] = set()
    for account in message_info.values():
        for blog in account.get("blogs", []):
            if blog.get("create_time", "9999") < cutoff:
                removable.add(blog["id"])
    return cutoff, removable


@app.get("/api/cache/preview", response_model=CachePreview)
def cache_preview(keep_days: int = 90):
    """预览清理结果：返回将被删除的文章数、封面图数、详情缓存数（不执行实际删除）。"""
    if keep_days < 1:
        raise HTTPException(status_code=400, detail="keep_days 必须 >= 1")

    cutoff, removable_ids = _collect_removable_ids(keep_days)
    message_info = _read_message_info()
    total_articles = sum(len(v.get("blogs", [])) for v in message_info.values())

    # 统计可删除的封面图
    removable_covers = 0
    if COVERS_DIR.exists():
        cover_files = {f.stem: f for f in COVERS_DIR.glob("*.jpg")}
        for rid in removable_ids:
            if rid.replace("/", "_") in cover_files:
                removable_covers += 1

    # 统计可删除的详情缓存
    detail_text_file = DATA_DIR / "message_detail_text.json"
    removable_detail_texts = 0
    if detail_text_file.exists():
        with open(detail_text_file, encoding="utf-8") as f:
            detail_texts: dict = json.load(f)
        removable_detail_texts = sum(1 for rid in removable_ids if rid in detail_texts)

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
    删除早于 keep_days 天的文章记录，同时清理对应的封面图和详情缓存。
    爬取任务运行期间禁止清理，以免数据冲突。
    """
    if _crawl_state["running"]:
        raise HTTPException(status_code=409, detail="爬取任务正在进行中，请等待完成后再清理")
    if body.keep_days < 1:
        raise HTTPException(status_code=400, detail="keep_days 必须 >= 1")

    _, removable_ids = _collect_removable_ids(body.keep_days)
    if not removable_ids:
        return CacheClearResult(removed_articles=0, removed_covers=0, removed_detail_texts=0)

    # 1. 清理 message_info.json
    message_info = _read_message_info()
    for account in message_info.values():
        account["blogs"] = [b for b in account.get("blogs", []) if b["id"] not in removable_ids]
    with open(MESSAGE_INFO_FILE, "w", encoding="utf-8") as f:
        json.dump(message_info, f, ensure_ascii=False, indent=4)

    # 2. 清理封面图
    removed_covers = 0
    if COVERS_DIR.exists():
        for rid in removable_ids:
            cover_path = COVERS_DIR / (rid.replace("/", "_") + ".jpg")
            if cover_path.exists():
                cover_path.unlink()
                removed_covers += 1

    # 3. 清理 message_detail_text.json
    removed_detail_texts = 0
    detail_text_file = DATA_DIR / "message_detail_text.json"
    if detail_text_file.exists():
        with open(detail_text_file, encoding="utf-8") as f:
            detail_texts: dict = json.load(f)
        before = len(detail_texts)
        detail_texts = {k: v for k, v in detail_texts.items() if k not in removable_ids}
        removed_detail_texts = before - len(detail_texts)
        with open(detail_text_file, "w", encoding="utf-8") as f:
            json.dump(detail_texts, f, ensure_ascii=False, indent=4)

    # 4. 同步刷新 data_manager 内存（避免旧数据残留）
    try:
        from src.utils.data_manager import data_manager
        data_manager.reload("message_info")
        data_manager.reload("message_detail_text")
    except Exception:
        pass

    _append_log(
        LOG_CACHE_CLEAR,
        f"清理缓存：删除 {len(removable_ids)} 篇文章（{body.keep_days} 天前），"
        f"封面图 {removed_covers} 张，详情缓存 {removed_detail_texts} 条",
        {
            "keep_days": body.keep_days,
            "cutoff_date": (datetime.now() - timedelta(days=body.keep_days)).strftime("%Y-%m-%d"),
            "removed_articles": len(removable_ids),
            "removed_covers": removed_covers,
            "removed_detail_texts": removed_detail_texts,
        },
    )

    return CacheClearResult(
        removed_articles=len(removable_ids),
        removed_covers=removed_covers,
        removed_detail_texts=removed_detail_texts,
    )


# ---------- 日志查询 ----------

class LogEntry(BaseModel):
    timestamp: str
    type: str
    message: str
    details: dict


@app.get("/api/logs", response_model=list[LogEntry])
def get_logs(limit: int = 200):
    """返回最近 limit 条操作日志（倒序，最新在前）。"""
    if not LOGS_FILE.exists():
        return []
    with open(LOGS_FILE, encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    entries = []
    for line in reversed(lines[-limit:]):
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries
