#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""微信公众平台扫码登录（HTTP 调 scanloginqrcode / bizlogin，无需浏览器截图）。"""

from __future__ import annotations

import base64
import random
import re
import time
from typing import Callable
from urllib.parse import urlencode, urlparse, parse_qs

import requests

from src.utils.data_manager import headers as MP_HEADERS

MP_ORIGIN = "https://mp.weixin.qq.com"
SCAN_QR_URL = f"{MP_ORIGIN}/cgi-bin/scanloginqrcode"
BIZ_LOGIN_URL = f"{MP_ORIGIN}/cgi-bin/bizlogin"

_QR_CONTENT_TYPES = ("image/png", "image/jpeg", "image/jpg", "image/gif")

# 与 wechat-article-exporter Login.vue 中 ask 的 status 含义一致
SCAN_STATUS_WAITING = 0
SCAN_STATUS_CONFIRMED = 1
SCAN_STATUS_EXPIRED = (2, 3)
SCAN_STATUS_SCANNED = (4, 6)


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


def _session_headers() -> dict[str, str]:
    return {
        "User-Agent": MP_HEADERS["User-Agent"],
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
    """仿 wechat-article-exporter：startlogin → getqrcode → ask 轮询 → bizlogin。"""

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(_session_headers())
        self.sid = f"{int(time.time() * 1000)}{random.randint(0, 99)}"

    def start_session(self) -> None:
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

    def fetch_qrcode_bytes(self) -> bytes:
        resp = self.session.get(
            SCAN_QR_URL,
            params={"action": "getqrcode", "random": int(time.time() * 1000)},
            timeout=30,
        )
        resp.raise_for_status()
        ct = (resp.headers.get("Content-Type") or "").lower()
        if "image" in ct:
            return resp.content
        # 少数情况下为 JSON，尝试解析内嵌图片
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
        raw = self.fetch_qrcode_bytes()
        return _qrcode_data_url(raw, "image/png")

    def ask_once(self) -> dict:
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

    def wait_for_scan(
        self,
        *,
        timeout: float = 180,
        poll_interval: float = 2,
        on_qrcode: Callable[[str], None] | None = None,
        on_status: Callable[[int, str], None] | None = None,
    ) -> None:
        """轮询 ask，直到 status=1（可执行 bizlogin）。"""
        deadline = time.time() + timeout
        last_qr_at = 0.0

        def emit_status(status: int, data: dict | None = None) -> None:
            if on_status:
                on_status(status, scan_status_message(status, data))

        def push_qr(force: bool = False) -> None:
            nonlocal last_qr_at
            if not on_qrcode:
                return
            now = time.time()
            if not force and now - last_qr_at < poll_interval:
                return
            data_url = self.fetch_qrcode_data_url()
            on_qrcode(data_url)
            last_qr_at = now

        push_qr(force=True)
        emit_status(SCAN_STATUS_WAITING)

        while time.time() < deadline:
            data = self.ask_once()
            base = data.get("base_resp") or {}
            if base.get("ret", 0) != 0:
                if "status" in data:
                    status = int(data["status"])
                    emit_status(status, data)
                    if status == SCAN_STATUS_CONFIRMED:
                        return
                else:
                    emit_status(-1)
                time.sleep(poll_interval)
                continue

            status = int(data.get("status", 0))
            emit_status(status, data)

            if status == SCAN_STATUS_WAITING:
                time.sleep(poll_interval)
                continue
            if status == SCAN_STATUS_CONFIRMED:
                if on_status:
                    on_status(status, scan_status_message(status, data))
                return
            if status in SCAN_STATUS_EXPIRED:
                push_qr(force=True)
                time.sleep(poll_interval)
                continue
            if status in SCAN_STATUS_SCANNED:
                if data.get("acct_size", 0) < 1:
                    raise RuntimeError("没有可登录账号")
                time.sleep(poll_interval)
                continue
            if status == 5:
                raise RuntimeError("该账号尚未绑定邮箱，无法扫码登录")
            time.sleep(poll_interval)

        raise TimeoutError("等待扫码超时（3 分钟），请重试")

    def complete_login(self) -> tuple[str, str]:
        """执行 bizlogin login，返回 (token, cookie 字符串)。"""
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

        cookie_str = "; ".join(
            f"{c.name}={c.value}" for c in self.session.cookies
        )
        if not cookie_str:
            raise RuntimeError("登录成功但未获得 Cookie")

        return token, cookie_str

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
