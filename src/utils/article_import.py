# -*- coding: utf-8 -*-
"""通过微信公众号文章链接导入单篇内容（参考 wechat-article-exporter 单篇模式）。"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import requests
from lxml import etree

from src.utils.helpers import message_is_delete, time_now
from src.utils.wechat_body import fetch_article_body
from src.utils.wechat_preview import _request_headers

_MP_HOST = "mp.weixin.qq.com"


class ArticleImportError(ValueError):
    """链接导入失败（可展示给用户）。"""


def normalize_mp_article_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        raise ArticleImportError("链接不能为空")
    if not re.match(r"^https?://", raw, re.I):
        raw = f"https://{raw}"
    parsed = urlparse(raw)
    if parsed.hostname not in (_MP_HOST, f"www.{_MP_HOST}"):
        raise ArticleImportError("请输入有效的微信公众号文章链接（mp.weixin.qq.com）")
    path = parsed.path or ""
    if "/s/" not in path and "appmsg" not in path:
        raise ArticleImportError("该链接不是公众号文章页")
    return raw


def _fetch_article_html(url: str) -> tuple[str, str]:
    """返回 (最终 URL, HTML)。"""
    h = _request_headers()
    try:
        resp = requests.get(url, headers=h, timeout=25, allow_redirects=True)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise ArticleImportError(f"无法访问该链接：{e}") from e
    final_url = resp.url.split("#")[0]
    html = resp.text
    if message_is_delete(response=html):
        raise ArticleImportError("该文章已被发布者删除")
    return final_url, html


def _re_first(pattern: str, text: str, group: int = 1) -> str:
    m = re.search(pattern, text, re.I | re.S)
    return (m.group(group) if m else "").strip()


def _parse_ids_and_time(html: str, final_url: str) -> tuple[str, str, str]:
    """解析 msgid、aid、create_time（与爬虫 id 格式一致）。"""
    qs = parse_qs(urlparse(final_url).query)
    mid = (
        (qs.get("mid") or [""])[0]
        or (qs.get("appmsgid") or [""])[0]
        or _re_first(r'var\s+mid\s*=\s*["\'](\d+)["\']', html)
        or _re_first(r'var\s+appmsgid\s*=\s*["\'](\d+)["\']', html)
    )
    idx = (qs.get("idx") or [""])[0] or _re_first(r'var\s+idx\s*=\s*["\'](\d+)["\']', html) or "1"
    if not mid:
        raise ArticleImportError("无法从页面解析文章编号，请确认链接有效")

    aid = _re_first(r'var\s+aid\s*=\s*["\']([^"\']+)["\']', html)
    if not aid:
        aid = f"{mid}_{idx}"

    ct_raw = (
        _re_first(r'var\s+ct\s*=\s*["\'](\d+)["\']', html)
        or _re_first(r"var\s+create_time\s*=\s*['\"](\d+)['\"]", html)
        or _re_first(r"var\s+oriCreateTime\s*=\s*['\"](\d+)['\"]", html)
    )
    if ct_raw:
        try:
            ts = int(ct_raw)
            create_time = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
        except (ValueError, OSError, OverflowError):
            create_time = time_now()
    else:
        create_time = time_now()
        ts = int(datetime.strptime(create_time, "%Y-%m-%d %H:%M").timestamp())

    msgid = _re_first(r'var\s+msgid\s*=\s*["\'](\d+)["\']', html) or mid
    article_id = f"{msgid}-{aid}-{ts}"
    return article_id, aid, create_time


def _parse_metadata(html: str, final_url: str) -> dict[str, str]:
    tree = etree.HTML(html, parser=etree.HTMLParser(encoding="utf-8"))
    if tree is None:
        raise ArticleImportError("页面解析失败")

    title = ""
    for node in tree.xpath('//*[@id="activity-name"]'):
        title = "".join(node.itertext()).strip()
        if title:
            break
    if not title:
        title = _re_first(r'property="og:title"\s+content="([^"]+)"', html)
    if not title:
        title = _re_first(r"var\s+msg_title\s*=\s*'([^']+)'", html)
    title = unquote(title).strip() or "未命名文章"

    account = ""
    for node in tree.xpath('//*[@id="js_name"]'):
        account = "".join(node.itertext()).strip()
        if account:
            break
    if not account:
        nick = _re_first(r'var\s+nickname\s*=\s*htmlDecode\("([^"]+)"\)', html)
        account = nick or "链接导入"

    digest = _re_first(r'property="og:description"\s+content="([^"]+)"', html)
    if not digest:
        digest = _re_first(r'var\s+msg_desc\s*=\s*htmlDecode\("([^"]*)"\)', html)
    digest = unquote(digest).strip()

    cover = _re_first(r'var\s+msg_cdn_url\s*=\s*"([^"]+)"', html)
    if not cover:
        cover = _re_first(r'property="og:image"\s+content="([^"]+)"', html)
    cover = unquote(cover).replace("&amp;", "&")

    biz = _re_first(r'var\s+biz\s*=\s*"([^"]+)"', html)
    if not biz:
        biz = (parse_qs(urlparse(final_url).query).get("__biz") or [""])[0]

    return {
        "title": title,
        "account": account,
        "digest": digest,
        "cover": cover,
        "biz": biz,
    }


def build_blog_from_url(url: str) -> dict[str, Any]:
    """
    抓取链接并构造与爬虫一致的 blog 字典。
    参考 wechat-article-exporter：normalizeUrl → 拉 HTML → 解析元数据。
    """
    normalized = normalize_mp_article_url(url)
    final_url, html = _fetch_article_html(normalized)
    meta = _parse_metadata(html, final_url)
    article_id, _aid, create_time = _parse_ids_and_time(html, final_url)

    text, _body_html = fetch_article_body(final_url)
    if text == "已删除":
        raise ArticleImportError("该文章已被发布者删除")
    if text == "请求错误":
        raise ArticleImportError("抓取正文失败，请检查网络或 data/id_info.json 凭证")

    if not meta["digest"] and isinstance(text, list):
        joined = "\n".join(str(x) for x in text if str(x).strip())
        meta["digest"] = joined[:160].replace("\n", " ")

    blog = {
        "id": article_id,
        "title": meta["title"],
        "digest": meta["digest"],
        "link": final_url,
        "cover": meta["cover"],
        "create_time": create_time,
        "is_deleted": False,
        "item_show_type": 0,
        "_import_biz": meta["biz"],
        "_import_account": meta["account"],
    }
    return blog


def import_article_by_link(url: str) -> dict[str, Any]:
    """
    导入文章并写入 SQLite（由 API 层调用 repository）。
    返回 { status, article_id, account, title, link, message }。
    """
    blog = build_blog_from_url(url)
    return blog
