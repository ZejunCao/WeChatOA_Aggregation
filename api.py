#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
轻量 FastAPI 后端，供前端管理公众号列表使用。
"""

import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ── 数据目录和文件路径 ──────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent / "data"
NAME2FAKEID_FILE = DATA_DIR / "name2fakeid.json"
MESSAGE_INFO_FILE = DATA_DIR / "message_info.json"
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


# ── 数据文件读写工具 ────────────────────────────────────────────────────────────
# 这几个函数封装了对 JSON 文件的直接读写，每次调用都会从磁盘读取最新内容，
# 避免内存中的旧数据影响结果。

def _read_name2fakeid() -> dict[str, str]:
    """读取公众号名称→fakeid 映射，文件不存在时返回空字典。"""
    if not NAME2FAKEID_FILE.exists():
        return {}
    with open(NAME2FAKEID_FILE, encoding="utf-8") as f:
        return json.load(f)


def _write_name2fakeid(data: dict[str, str]) -> None:
    """将公众号名称→fakeid 映射写回磁盘（格式化 JSON，方便人工查看）。"""
    with open(NAME2FAKEID_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def _read_message_info() -> dict:
    """读取全部公众号的文章信息，文件不存在时返回空字典。"""
    if not MESSAGE_INFO_FILE.exists():
        return {}
    with open(MESSAGE_INFO_FILE, encoding="utf-8") as f:
        return json.load(f)


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
    article_id = str(article.get("id") or "")
    if article_id:
        text_data = data_manager.message_detail_text.get(article_id)
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


def _fetch_article_detail_text(article_id: str, link: str) -> bool:
    """
    根据文章链接拉取 HTML 正文（url2text），写入 data_manager.message_detail_text。

    存储格式与 deduplication / blog_generator 一致：正常为段落 list[str]；
    url2text 在文章删除、请求失败时可能返回 str（如「已删除」「请求错误」），原样写入。

    若该 article_id 在 message_detail_text 中已存在则跳过，避免重复抓取。
    返回 True 表示本次写入了新数据，需要随后 write("message_detail_text")。
    """
    if not link or not article_id:
        return False
    from src.utils.data_manager import data_manager
    from src.utils.helpers import url2text

    if article_id in data_manager.message_detail_text:
        return False

    try:
        text = url2text(link)
        data_manager.message_detail_text[article_id] = text
        return True
    except Exception as e:
        print(f"[detail] 抓取正文失败 {article_id}: {e}")
        return False


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

    数据来源：
    - name2fakeid.json  → 已添加的公众号列表
    - message_info.json → 各公众号的文章数量和最后更新时间
    """
    name2fakeid = _read_name2fakeid()
    message_info = _read_message_info()

    result = []
    for name, fakeid in name2fakeid.items():
        entry = message_info.get(name, {})
        blogs = entry.get("blogs", [])
        # 过滤掉已被微信删除的文章
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
    确认添加公众号：将用户选定的 name + fakeid 写入 name2fakeid.json。

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
    从跟踪列表中移除公众号（只删除 name2fakeid.json 中的记录，
    不删除已爬取的文章数据，如需清理可使用缓存清理功能）。
    """
    name2fakeid = _read_name2fakeid()
    if name not in name2fakeid:
        raise HTTPException(status_code=404, detail=f"公众号「{name}」不在列表中")

    del name2fakeid[name]
    _write_name2fakeid(name2fakeid)
    _append_log(LOG_ACCOUNT_REMOVE, f"移除公众号「{name}」", {"name": name})


# ── 删除单篇文章 ────────────────────────────────────────────────────────────────

class ArticleDeleteRequest(BaseModel):
    """从前端移除一篇文章：写入黑名单并删除本地记录。"""
    article_id: str   # 文章唯一 id（msgid-aid-create_time）
    account: str      # 所属公众号名称（message_info 的 key）


@app.post("/api/articles/remove")
def remove_article(body: ArticleDeleteRequest):
    """
    将文章 id 写入 data/deleted_article_ids.json，并从 message_info 中移除该条。
    后续爬取时若微信仍返回该文，会因 id 在黑名单中而跳过。
    同时尝试删除本地封面与详情缓存。
    """
    from src.utils.data_manager import data_manager

    aid = body.article_id.strip()
    acc = body.account.strip()
    if not aid or not acc:
        raise HTTPException(status_code=400, detail="article_id 和 account 不能为空")

    data_manager.reload("deleted_article_ids")
    data_manager.reload("message_info")

    if acc not in data_manager.message_info:
        raise HTTPException(status_code=404, detail=f"公众号「{acc}」不存在")

    blogs = data_manager.message_info[acc].get("blogs", [])
    if not any(b.get("id") == aid for b in blogs):
        raise HTTPException(status_code=404, detail="文章不存在或已删除")

    # 黑名单
    raw = data_manager.deleted_article_ids
    if not isinstance(raw, dict):
        raise HTTPException(status_code=500, detail="deleted_article_ids.json 格式异常，请检查 data 目录")
    if "ids" not in raw or not isinstance(raw["ids"], list):
        raw["ids"] = []
    ids_list: list = raw["ids"]
    if aid not in ids_list:
        ids_list.append(aid)
    data_manager.write("deleted_article_ids")

    # 从 message_info 移除
    data_manager.message_info[acc]["blogs"] = [b for b in blogs if b.get("id") != aid]
    data_manager.write("message_info")

    # 本地封面
    cover_path = COVERS_DIR / (aid.replace("/", "_") + ".jpg")
    if cover_path.exists():
        try:
            cover_path.unlink()
        except OSError:
            pass

    # 详情缓存
    detail_file = DATA_DIR / "message_detail_text.json"
    if detail_file.exists():
        try:
            with open(detail_file, encoding="utf-8") as f:
                detail_texts = json.load(f)
            if aid in detail_texts:
                del detail_texts[aid]
                with open(detail_file, "w", encoding="utf-8") as f:
                    json.dump(detail_texts, f, ensure_ascii=False, indent=4)
            data_manager.reload("message_detail_text")
        except (json.JSONDecodeError, OSError):
            pass

    _append_log(
        LOG_ARTICLE_DELETE,
        f"删除文章「{aid}」（{acc}）",
        {"article_id": aid, "account": acc},
    )

    return {"ok": True, "article_id": aid}


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


def _run_crawl() -> None:
    """
    后台爬取线程的主函数，流程如下：

    1. 立即更新 _crawl_state.total，让前端第一次轮询就能看到账号总数
    2. 从磁盘重新加载最新凭证（data_manager.reload），支持手动更新 id_info.json
    3. 调用 _check_auth_valid() 做预检：凭证失效时立刻终止，不逐个账号重试
    4. 遍历所有公众号，调用 WechatRequest.fakeid2message_update() 获取新文章
    5. 对每篇新文章下载封面图、拉正文；可选 LLM 生成摘要+标签写入 message_info.json
    6. 每处理完一个公众号（成功或失败），done += 1
    7. 全部完成后写入结束日志，设置 running=False
    """
    global _crawl_state
    try:
        # ── 第一步：立即更新 total，让前端尽快看到正确的进度分母 ──
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

        from src.crawler.wechat_request import WechatRequest
        from src.llm.article_tagging import tag_article
        from src.llm.llm_config import (
            llm_tagging_enabled,
            read_crawl_llm_multithread_enabled,
            read_crawl_llm_multithread_workers,
        )
        from src.utils.data_manager import data_manager
        from src.utils.helpers import time_now

        # ── 第二步：从磁盘重新加载，确保内存数据是最新的 ──
        # 特别是 id_info，用户可能在服务运行时手动修改了 token/cookie
        data_manager.reload("id_info")
        data_manager.reload("name2fakeid")
        data_manager.reload("message_info")
        data_manager.reload("issues_message")
        data_manager.reload("deleted_article_ids")
        data_manager.reload("message_detail_text")

        # ── 第三步：凭证预检 ──────────────────────────────────────────
        # 如果凭证已失效，提前终止，避免每个账号都等待超时再报错
        auth_ok, auth_reason = _check_auth_valid()
        if not auth_ok:
            _crawl_state["auth_error"] = True
            _crawl_state["errors"].append(f"凭证失效，已终止爬取：{auth_reason}")
            _mark_auth_failed(auth_reason)
            _append_log(LOG_CRAWL_ERROR, f"凭证失效，爬取终止：{auth_reason}", {"reason": auth_reason})
            return  # 直接结束，不进入主循环

        name2fakeid: dict[str, str] = dict(data_manager.name2fakeid)
        # reload 后账号数可能与 quick_n2f 不同，更新 total 保持一致
        _crawl_state["total"] = len(name2fakeid)

        _append_log(LOG_CRAWL_START, f"开始爬取，共 {len(name2fakeid)} 个公众号",
                    {"accounts": list(name2fakeid.keys())})

        wechat = WechatRequest()
        new_total = 0  # 本次爬取新增文章的累计数

        # 爬取时是否启用模型总结+打标（配置页开关）
        llm_enabled_for_crawl = llm_tagging_enabled()
        # 爬取补总结/打标是否启用多线程（全局开关）
        llm_multithread_for_crawl = read_crawl_llm_multithread_enabled()
        llm_multithread_workers_cap = read_crawl_llm_multithread_workers()

        # ── 第四步：逐个公众号爬取 ──────────────────────────────────────
        for oa_name, fakeid in name2fakeid.items():
            if _crawl_state.get("cancel_requested"):
                _crawl_state["cancelled"] = True
                _crawl_state["errors"].append("用户手动取消爬取")
                _append_log(LOG_CRAWL_FINISH, "爬取被用户手动取消", {"done": _crawl_state.get("done", 0), "total": _crawl_state.get("total", 0)})
                break
            _crawl_state["current"] = oa_name  # 更新"正在处理"的账号名，供前端展示
            try:
                # 首次爬取该公众号时，初始化其记录结构
                if oa_name not in data_manager.message_info:
                    data_manager.message_info[oa_name] = {
                        "latest_update_time": "2000-01-01 00:00",
                        "blogs": [],
                    }

                existing_blogs: list = data_manager.message_info[oa_name]["blogs"]
                # fakeid2message_update 内部通过 article_id 去重，只返回新增文章
                new_articles = wechat.fakeid2message_update(fakeid, existing_blogs)

                if new_articles:
                    data_manager.message_info[oa_name]["blogs"].extend(new_articles)
                    new_total += len(new_articles)
                    detail_dirty = False
                    # 新文章：下载封面 + 拉取正文写入 message_detail_text.json
                    for article in new_articles:
                        download_cover(article["id"], article.get("cover", ""), COVERS_DIR, _DOWNLOAD_HEADERS)
                        if _fetch_article_detail_text(article["id"], article.get("link", "")):
                            detail_dirty = True
                        article["word_count"] = article_word_count(article, data_manager)
                    if detail_dirty:
                        data_manager.write("message_detail_text")

                # 模型分析（摘要+标签）：
                # - 新文章会分析
                # - 已存在但缺少 summary 的文章，也会在后续爬取时补分析
                # 注意：这里不依赖 new_articles，避免“无新文时跳过补总结”
                if llm_enabled_for_crawl:
                    try:
                        all_blogs = data_manager.message_info[oa_name]["blogs"]
                        need_analyze = [a for a in all_blogs if not str(a.get("summary") or "").strip()]
                        if llm_multithread_for_crawl and len(need_analyze) > 1:
                            max_workers = min(llm_multithread_workers_cap, len(need_analyze))
                            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                                future_to_article = {
                                    executor.submit(tag_article, article, data_manager): article
                                    for article in need_analyze
                                }
                                for future in as_completed(future_to_article):
                                    if _crawl_state.get("cancel_requested"):
                                        _crawl_state["cancelled"] = True
                                        for f in future_to_article:
                                            if not f.done():
                                                f.cancel()
                                        break
                                    article = future_to_article[future]
                                    try:
                                        analysis = future.result()
                                        tags = analysis.get("tags") if isinstance(analysis, dict) else []
                                        summary = analysis.get("summary") if isinstance(analysis, dict) else ""
                                        if tags:
                                            article["tags"] = tags
                                        if summary:
                                            article["summary"] = summary
                                    except Exception as e:
                                        print(f"[tag] 单篇打标失败 {article.get('id')}: {e}")
                        else:
                            for article in need_analyze:
                                if _crawl_state.get("cancel_requested"):
                                    _crawl_state["cancelled"] = True
                                    break
                                try:
                                    analysis = tag_article(article, data_manager)
                                    tags = analysis.get("tags") if isinstance(analysis, dict) else []
                                    summary = analysis.get("summary") if isinstance(analysis, dict) else ""
                                    if tags:
                                        article["tags"] = tags
                                    if summary:
                                        article["summary"] = summary
                                except Exception as e:
                                    print(f"[tag] 单篇打标失败 {article.get('id')}: {e}")
                    except Exception as e:
                        print(f"[tag] 打标模块异常: {e}")

                # 更新最后爬取时间
                data_manager.message_info[oa_name]["latest_update_time"] = time_now()
                data_manager.write("message_info")

                # 爬取成功 → 凭证有效，更新状态
                _mark_auth_ok()

            except Exception as e:
                err_str = str(e)
                err_msg = f"{oa_name}: {err_str}"
                _crawl_state["errors"].append(err_msg)
                _append_log(LOG_CRAWL_ERROR, f"爬取「{oa_name}」失败：{e}",
                            {"account": oa_name, "error": err_str})
                # 判断是否是凭证失效导致的错误（微信 API 返回的特定错误字符串）
                if any(kw in err_str.lower() for kw in ("invalid session", "invalid csrf", "csrf token", "session")):
                    _mark_auth_failed(err_str)
            finally:
                # 无论成功还是失败，都算处理完一个，done + 1
                _crawl_state["done"] += 1
                _crawl_state["new_articles"] = new_total

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
    message_info = _read_message_info()
    removable: set[str] = set()
    for account in message_info.values():
        for blog in account.get("blogs", []):
            if blog.get("create_time", "9999") < cutoff:
                removable.add(blog["id"])
    return cutoff, removable


@app.get("/api/cache/preview", response_model=CachePreview)
def cache_preview(keep_days: int = 90):
    """
    预览清理结果：统计将被删除的文章数、封面图数、详情缓存数。
    不执行任何实际删除，只供前端展示确认弹窗。
    """
    if keep_days < 1:
        raise HTTPException(status_code=400, detail="keep_days 必须 >= 1")

    cutoff, removable_ids = _collect_removable_ids(keep_days)
    message_info = _read_message_info()
    total_articles = sum(len(v.get("blogs", [])) for v in message_info.values())

    # 统计可删除的封面图（按文件名匹配）
    removable_covers = 0
    if COVERS_DIR.exists():
        cover_files = {f.stem: f for f in COVERS_DIR.glob("*.jpg")}
        for rid in removable_ids:
            if rid.replace("/", "_") in cover_files:
                removable_covers += 1

    # 统计可删除的详情缓存（message_detail_text.json 中的键）
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
    执行缓存清理，删除早于 keep_days 天的数据：
      1. 从 message_info.json 删除旧文章记录
      2. 从 data/covers/ 删除对应封面图文件
      3. 从 message_detail_text.json 删除对应详情缓存
      4. 刷新 data_manager 内存，避免旧数据残留

    爬取任务运行期间禁止清理，以避免数据写入冲突。
    """
    if _crawl_state["running"]:
        raise HTTPException(status_code=409, detail="爬取任务正在进行中，请等待完成后再清理")
    if body.keep_days < 1:
        raise HTTPException(status_code=400, detail="keep_days 必须 >= 1")

    _, removable_ids = _collect_removable_ids(body.keep_days)
    if not removable_ids:
        return CacheClearResult(removed_articles=0, removed_covers=0, removed_detail_texts=0)

    # 1. 从 message_info.json 移除旧文章
    message_info = _read_message_info()
    for account in message_info.values():
        account["blogs"] = [b for b in account.get("blogs", []) if b["id"] not in removable_ids]
    with open(MESSAGE_INFO_FILE, "w", encoding="utf-8") as f:
        json.dump(message_info, f, ensure_ascii=False, indent=4)

    # 2. 删除封面图文件
    removed_covers = 0
    if COVERS_DIR.exists():
        for rid in removable_ids:
            cover_path = COVERS_DIR / (rid.replace("/", "_") + ".jpg")
            if cover_path.exists():
                cover_path.unlink()
                removed_covers += 1

    # 3. 从 message_detail_text.json 删除详情缓存
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

    # 4. 同步刷新 data_manager 内存，避免旧数据在本次进程中继续存在
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


# ── 扫码登录 ────────────────────────────────────────────────────────────────────
# 当凭证过期时，用户可以通过前端触发扫码登录流程：
#   1. 后端用无头 Chrome 打开微信公众平台登录页
#   2. 每 2 秒截图保存到 _login_state["qrcode_img"]
#   3. 前端轮询 /api/auth/qrcode 获取截图并展示
#   4. 用户扫码后，后端检测 URL 中出现 token，提取并保存凭证
#   5. 前端轮询 /api/auth/login/status 检测完成，关闭弹窗

_login_state: dict = {
    "running": False,    # 是否正在等待扫码
    "done": False,       # 本次登录流程是否已结束（成功或失败）
    "error": "",         # 失败时的错误信息
    "qrcode_img": "",    # 最新二维码截图（data:image/png;base64,...）
    "qrcode_at": "",     # 截图时间（"HH:MM:SS"）
    "started_at": "",    # 登录流程开始时间
    "finished_at": "",   # 登录流程结束时间
}
_login_lock = threading.Lock()  # 保护 _login_state 的多线程读写


def _run_login() -> None:
    """
    后台登录线程：
      - 用无头 Chrome 打开微信登录页面（不弹出可见窗口）
      - 循环截图，让前端可以展示二维码供用户扫描
      - 检测到 URL 含 token 后，提取 token + cookie 写入 id_info.json
      - 3 分钟内未扫码则超时退出
    """
    import time

    bro = None
    try:
        from DrissionPage import ChromiumPage, ChromiumOptions
        from src.utils.data_manager import data_manager

        # headless=True：不弹出可见窗口，在后台渲染页面
        # auto_port()：自动分配调试端口，避免与已有 Chrome 冲突
        co = ChromiumOptions().auto_port().headless(True)
        bro = ChromiumPage(co)
        bro.set.window.size(1280, 800)  # 设置虚拟窗口大小，影响截图分辨率
        bro.get("https://mp.weixin.qq.com/")

        # 首屏会先出现登录骨架/文案，二维码 img 晚几秒才出现；若此时截全页会误导用户。
        # 先等待二维码节点出现，再进入轮询；只推送「二维码元素」截图，不再用全页图当二维码。
        qr_wait_deadline = time.time() + 35
        qr_elem = None
        while time.time() < qr_wait_deadline and "token" not in bro.url:
            try:
                qr_elem = bro.ele("css:img[src*='qrcode']", timeout=2)
                if qr_elem:
                    break
            except Exception:
                pass
            time.sleep(0.35)
        if "token" not in bro.url and not qr_elem:
            raise Exception("页面未在预期时间内加载出登录二维码，请检查网络或稍后重试")

        # 二维码一出现就推送首帧，避免再等主循环一轮才写入 _login_state
        if qr_elem and "token" not in bro.url:
            try:
                _b64 = qr_elem.get_screenshot(as_base64=True)
                if _b64:
                    with _login_lock:
                        _login_state["qrcode_img"] = f"data:image/png;base64,{_b64}"
                        _login_state["qrcode_at"] = datetime.now().strftime("%H:%M:%S")
            except Exception:
                pass

        max_wait = 180  # 最多等待 3 分钟
        start = time.time()

        while "token" not in bro.url:
            if time.time() - start > max_wait:
                raise Exception("等待扫码超时（3 分钟），请重试")

            img_b64 = ""
            try:
                qr_elem = bro.ele("css:img[src*='qrcode']", timeout=3)
                if qr_elem:
                    img_b64 = qr_elem.get_screenshot(as_base64=True)
            except Exception:
                pass

            if img_b64:
                with _login_lock:
                    _login_state["qrcode_img"] = f"data:image/png;base64,{img_b64}"
                    _login_state["qrcode_at"] = datetime.now().strftime("%H:%M:%S")

            time.sleep(2)  # 每 2 秒刷新一次截图（二维码会过期刷新）

        # ── 扫码成功，从 URL 提取 token ──
        match = re.search(r"token=(\d+)", bro.url)
        if not match:
            raise ValueError("无法从 URL 中解析 token")
        token = match.group(1)

        # 将所有 cookie 拼接为字符串（"name=value; name2=value2; ..."）
        cookies = bro.cookies()
        cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in cookies)

        # 写入 id_info.json，同时更新内存中的 data_manager
        data_manager.id_info["token"] = token
        data_manager.id_info["cookie"] = cookie_str
        data_manager.write("id_info")

        _mark_auth_ok()
        with _login_lock:
            _login_state.update(running=False, done=True, error="",
                                qrcode_img="", qrcode_at="",
                                finished_at=datetime.now().strftime("%H:%M:%S"))
    except Exception as e:
        with _login_lock:
            _login_state.update(running=False, done=True, error=str(e),
                                qrcode_img="", qrcode_at="",
                                finished_at=datetime.now().strftime("%H:%M:%S"))
    finally:
        # 无论成功还是失败，都关闭浏览器，释放资源
        try:
            if bro:
                bro.quit()
        except Exception:
            pass


class LoginStatus(BaseModel):
    """扫码登录的进度状态。"""
    running: bool
    done: bool
    error: str
    started_at: str
    finished_at: str


@app.post("/api/auth/login")
def start_login():
    """
    启动扫码登录流程（后台线程），立即返回。
    同一时间只允许一个登录流程运行。
    """
    with _login_lock:
        if _login_state["running"]:
            return {"detail": "已有登录流程正在进行，请扫描当前二维码"}
        _login_state.update(running=True, done=False, error="",
                            qrcode_img="", qrcode_at="",
                            started_at=datetime.now().strftime("%H:%M:%S"),
                            finished_at="")
    threading.Thread(target=_run_login, daemon=True).start()
    return {"detail": "正在加载登录页面，请稍候..."}


@app.get("/api/auth/login/status", response_model=LoginStatus)
def get_login_status():
    """查询当前扫码登录流程的状态，前端每 2 秒轮询一次。"""
    with _login_lock:
        return LoginStatus(**{k: _login_state[k] for k in LoginStatus.model_fields})


@app.get("/api/auth/qrcode")
def get_qrcode():
    """
    返回最新的微信登录二维码截图（base64 编码的 PNG）。
    前端每 2 秒调用一次，刷新展示的二维码图片（二维码有有效期，会自动更新）。
    """
    with _login_lock:
        img = _login_state.get("qrcode_img", "")
        at = _login_state.get("qrcode_at", "")
    if not img:
        raise HTTPException(status_code=404, detail="暂无二维码，请先点击扫码登录")
    return {"img": img, "refreshed_at": at}
