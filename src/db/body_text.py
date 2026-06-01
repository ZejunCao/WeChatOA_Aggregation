# -*- coding: utf-8 -*-
"""正文规范化（JSON list/str → 单段 TEXT）。"""

from __future__ import annotations

from typing import Any


def normalize_body_text(raw: Any) -> str:
    if raw is None:
        return ""
    if isinstance(raw, list):
        return "\n".join(str(x) for x in raw)
    return str(raw)
