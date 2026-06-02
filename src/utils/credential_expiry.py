# -*- coding: utf-8 -*-
"""微信公众号凭证有效期（对齐 wechat-article-exporter：扫码登录后约 4 天）。"""

from __future__ import annotations

from datetime import datetime, timedelta

# 与 wechat-article-exporter server/api/web/login/bizlogin.post 一致
CREDENTIAL_TTL_DAYS = 4


def _parse_saved_at(raw: str) -> datetime | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def credential_expiry_from_id_info(
    id_info: dict | None,
    *,
    file_mtime: float | None = None,
) -> dict[str, str | float | bool | None]:
    """
    返回 saved_at、expires_at（字符串）、days_remaining（可小数）、expired、expires_soon。
    """
    info = id_info or {}
    saved_at = _parse_saved_at(str(info.get("saved_at") or ""))
    if saved_at is None and file_mtime:
        saved_at = datetime.fromtimestamp(file_mtime)

    if saved_at is None:
        return {
            "saved_at": "",
            "expires_at": "",
            "days_remaining": None,
            "expired": False,
            "expires_soon": False,
            "ttl_days": CREDENTIAL_TTL_DAYS,
        }

    expires_at = saved_at + timedelta(days=CREDENTIAL_TTL_DAYS)
    remaining = expires_at - datetime.now()
    days_remaining = remaining.total_seconds() / 86400.0
    expired = days_remaining <= 0
    expires_soon = not expired and days_remaining < 1.0

    return {
        "saved_at": saved_at.strftime("%Y-%m-%d %H:%M:%S"),
        "expires_at": expires_at.strftime("%Y-%m-%d %H:%M:%S"),
        "days_remaining": round(days_remaining, 2),
        "expired": expired,
        "expires_soon": expires_soon,
        "ttl_days": CREDENTIAL_TTL_DAYS,
    }


def format_days_remaining_label(days_remaining: float | None) -> str:
    if days_remaining is None:
        return ""
    if days_remaining <= 0:
        return "已过期"
    if days_remaining < 1:
        hours = max(1, int(days_remaining * 24))
        return f"约 {hours} 小时后过期"
    d = int(days_remaining) if days_remaining >= 1 else 1
    return f"还剩 {d} 天过期"
