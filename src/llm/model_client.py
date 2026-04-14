"""
大模型调用适配：当前实现 Qwen3.5-27B 兼容接口（与自部署 / 网关 POST 体一致）。
通过环境变量配置 endpoint 与可选 API Key；未配置 endpoint 时上层应跳过打标。
"""

from __future__ import annotations

import os
from typing import Any

import requests

# 默认与业务侧约定一致；可通过环境变量覆盖模型名（自部署网关可能要求固定 id）
_DEFAULT_MODEL = "Qwen3.5-27B"
_DEFAULT_TIMEOUT = 120.0


def qwen_endpoint_configured() -> bool:
    """是否已配置 Qwen 接口地址（有值才启用爬取后打标）。"""
    return bool(os.environ.get("QWEN35_27B_ENDPOINT", "").strip())


def _endpoint() -> str:
    return os.environ.get("QWEN35_27B_ENDPOINT", "").strip()


def _api_key() -> str | None:
    k = (
        os.environ.get("QWEN35_27B_API_KEY", "").strip()
        or os.environ.get("LLM_API_KEY", "").strip()
    )
    return k or None


def _model_name() -> str:
    return os.environ.get("QWEN35_27B_MODEL", _DEFAULT_MODEL).strip() or _DEFAULT_MODEL


def chat_qwen35_27b(messages: list[dict[str, Any]]) -> str:
    """
    调用 Qwen3.5-27B 兼容接口，返回 assistant 文本内容。

    :param messages: OpenAI 风格 [{"role": "system"|"user"|"assistant", "content": "..."}, ...]
    :raises RuntimeError: 未配置 endpoint
    :raises requests.HTTPError: HTTP 非 2xx
    """
    url = _endpoint()
    if not url:
        raise RuntimeError("QWEN35_27B_ENDPOINT 未设置")

    payload = {
        "model": _model_name(),
        "messages": messages,
        "temperature": 0.1,
        "top_k": 20,
        "top_p": 0.8,
        "min_p": 0.0,
        "repetition_penalty": 1.0,
        "presence_penalty": 1.5,
        "enable_thinking": False,
    }
    headers: dict[str, str] = {"Content-Type": "application/json"}
    key = _api_key()
    if key:
        headers["Authorization"] = f"Bearer {key}"

    resp = requests.post(url, json=payload, headers=headers, timeout=_DEFAULT_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


# ---------------------------------------------------------------------------
# 预留：后续可在此增加 OpenAI 兼容、Ollama、本地 vLLM 等，统一入口例如：
#
#   class LLMProvider(Enum):
#       QWEN35_27B = "qwen35_27b"
#       OPENAI = "openai"
#
#   def chat(messages: list[dict], *, provider: LLMProvider = LLMProvider.QWEN35_27B) -> str:
#       ...
#
# 当前仅使用 chat_qwen35_27b，避免未使用的抽象。
# ---------------------------------------------------------------------------
