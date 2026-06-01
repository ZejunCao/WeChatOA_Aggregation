#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
微信公众平台扫码登录（HTTP 四步：startlogin → getqrcode → ask → bizlogin）。

流程与 wechat-article-exporter 一致，同一会话须共用 requests.Session（自动维护 uuid Cookie）。
"""

from __future__ import annotations

import base64
import random
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import requests

MP_ORIGIN = "https://mp.weixin.qq.com"
SCAN_QR_URL = f"{MP_ORIGIN}/cgi-bin/scanloginqrcode"
BIZ_LOGIN_URL = f"{MP_ORIGIN}/cgi-bin/bizlogin"

# 与 wechat-article-exporter config/index.ts USER_AGENT 一致
MP_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/117.0.0.0 Safari/537.36 WAE/1.0"
)

_QR_CONTENT_TYPES = ("image/png", "image/jpeg", "image/jpg", "image/gif")

# ask 接口 status（与 exporter Login.vue 一致）
SCAN_STATUS_WAITING = 0
SCAN_STATUS_CONFIRMED = 1
SCAN_STATUS_EXPIRED = (2, 3)
SCAN_STATUS_SCANNED = (4, 6)


@dataclass
class ScanAskResult:
    """解析后的 ask 轮询结果。"""

    ret: int
    err_msg: str
    status: int
    acct_size: int
    message: str
    raw: dict[str, Any]


def scan_status_message(status: int, data: dict | None = None) -> str:
    data = data or {}
    if status == SCAN_STATUS_WAITING:
        return "请使用微信扫一扫登录"
    if status == SCAN_STATUS_CONFIRMED:
        return "已确认，正在登录…"
    if status in SCAN_STATUS_EXPIRED:
        return "二维码已过期，正在刷新…"
    if status in SCAN_STATUS_SCANNED:
        if data.get("acct_size", 0) >= 1:
            return "扫码成功，请在手机上确认登录"
        return "没有可登录账号"
    if status == 5:
        return "该账号尚未绑定邮箱，无法扫码登录"
    return "等待扫码…"


def parse_ask_response(data: dict[str, Any]) -> ScanAskResult:
    base = data.get("base_resp") or {}
    ret = int(base.get("ret", 0))
    err_msg = str(base.get("err_msg") or "")
    status = int(data.get("status", 0)) if "status" in data else -1
    acct_size = int(data.get("acct_size", 0) or 0)
    if ret != 0 and status < 0:
        return ScanAskResult(
            ret=ret,
            err_msg=err_msg or "扫码状态查询失败",
            status=-1,
            acct_size=acct_size,
            message=err_msg or "扫码状态查询失败",
            raw=data,
        )
    if status < 0:
        status = SCAN_STATUS_WAITING
    return ScanAskResult(
        ret=ret,
        err_msg=err_msg,
        status=status,
        acct_size=acct_size,
        message=scan_status_message(status, data),
        raw=data,
    )


def _session_headers() -> dict[str, str]:
    return {
        "User-Agent": MP_USER_AGENT,
        "Referer": f"{MP_ORIGIN}/",
        "Origin": MP_ORIGIN,
        "Accept-Encoding": "identity",
    }


def _form_body(data: dict) -> str:
    return urlencode({k: str(v) for k, v in data.items()})


def _qrcode_data_url(raw: bytes, content_type: str) -> str:
    mime = "image/png"
    if content_type:
        ct = content_type.split(";")[0].strip().lower()
        if ct in _QR_CONTENT_TYPES:
            mime = ct
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{b64}"


class MpScanLogin:
    """扫码登录会话：startlogin → getqrcode → ask 轮询 → bizlogin。"""

    def __init__(self, session_id: str | None = None) -> None:
        self.session = requests.Session()
        self.session.headers.update(_session_headers())
        self.sid = session_id or f"{int(time.time() * 1000)}{random.randint(0, 99)}"

    def start_session(self) -> None:
        """① bizlogin?action=startlogin — 获得 uuid Cookie。"""
        body = {
            "userlang": "zh_CN",
            "redirect_url": "",
            "login_type": 3,
            "sessionid": self.sid,
            "token": "",
            "lang": "zh_CN",
            "f": "json",
            "ajax": 1,
        }
        resp = self.session.post(
            BIZ_LOGIN_URL,
            params={"action": "startlogin"},
            data=_form_body(body),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        base = data.get("base_resp") or {}
        if base.get("ret", 0) != 0:
            raise RuntimeError(base.get("err_msg") or "创建登录会话失败")
        if not self.session.cookies.get("uuid"):
            raise RuntimeError("startlogin 未返回 uuid Cookie，无法继续扫码")

    def fetch_qrcode_bytes(self) -> bytes:
        """② scanloginqrcode?action=getqrcode — 须携带 uuid。"""
        resp = self.session.get(
            SCAN_QR_URL,
            params={"action": "getqrcode", "random": int(time.time() * 1000)},
            timeout=30,
        )
        resp.raise_for_status()
        ct = (resp.headers.get("Content-Type") or "").lower()
        if "image" in ct:
            return resp.content
        try:
            payload = resp.json()
        except ValueError as e:
            raise RuntimeError("getqrcode 响应既不是图片也不是 JSON") from e
        for key in ("qrcode", "qrcode_url", "qrcode_base64", "img"):
            val = payload.get(key)
            if not val:
                continue
            if isinstance(val, str) and val.startswith("data:image"):
                return base64.b64decode(val.split(",", 1)[1])
            if isinstance(val, str) and len(val) > 100:
                try:
                    return base64.b64decode(val)
                except Exception:
                    pass
        raise RuntimeError(f"getqrcode 无法解析二维码: {payload!r}")

    def fetch_qrcode_data_url(self) -> str:
        resp = self.session.get(
            SCAN_QR_URL,
            params={"action": "getqrcode", "random": int(time.time() * 1000)},
            timeout=30,
        )
        resp.raise_for_status()
        ct = resp.headers.get("Content-Type") or ""
        if "image" in ct.lower():
            return _qrcode_data_url(resp.content, ct)
        return _qrcode_data_url(self.fetch_qrcode_bytes(), "image/png")

    def ask_once(self) -> dict[str, Any]:
        """③ scanloginqrcode?action=ask — 单次轮询。"""
        resp = self.session.get(
            SCAN_QR_URL,
            params={
                "action": "ask",
                "token": "",
                "lang": "zh_CN",
                "f": "json",
                "ajax": 1,
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def poll_scan(self) -> ScanAskResult:
        return parse_ask_response(self.ask_once())

    def complete_login(self) -> tuple[str, str]:
        """④ bizlogin?action=login — 返回 (token, cookie 字符串)。"""
        body = {
            "userlang": "zh_CN",
            "redirect_url": "",
            "cookie_forbidden": 0,
            "cookie_cleaned": 0,
            "plugin_used": 0,
            "login_type": 3,
            "token": "",
            "lang": "zh_CN",
            "f": "json",
            "ajax": 1,
        }
        resp = self.session.post(
            BIZ_LOGIN_URL,
            params={"action": "login"},
            data=_form_body(body),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        base = data.get("base_resp") or {}
        if base.get("ret", 0) != 0:
            raise RuntimeError(base.get("err_msg") or "登录失败")

        redirect_url = data.get("redirect_url") or ""
        if not redirect_url:
            raise RuntimeError("登录响应中未找到 redirect_url")

        token = self._token_from_redirect(redirect_url)
        if not token:
            raise RuntimeError(f"无法从 redirect_url 解析 token: {redirect_url}")

        cookie_str = self._cookie_header_string(resp)
        if not cookie_str:
            raise RuntimeError("登录成功但未获得 Cookie")

        return token, cookie_str

    def _cookie_header_string(self, _login_resp: requests.Response) -> str:
        """登录后的 Cookie 串（排除扫码阶段的 uuid）。"""
        pairs: dict[str, str] = {}
        for c in self.session.cookies:
            if c.name.lower() == "uuid":
                continue
            pairs[c.name] = c.value
        return "; ".join(f"{k}={v}" for k, v in pairs.items())

    @staticmethod
    def _token_from_redirect(redirect_url: str) -> str:
        if redirect_url.startswith("http"):
            parsed = urlparse(redirect_url)
        else:
            parsed = urlparse(f"http://local{redirect_url}")
        qs = parse_qs(parsed.query)
        if qs.get("token"):
            return qs["token"][0]
        m = re.search(r"token=(\d+)", redirect_url)
        return m.group(1) if m else ""
