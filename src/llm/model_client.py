"""
通用 Chat Completions：配置来自 data/llm_config.json。

- ``provider=vllm``：OpenAI 官方 SDK（``base_url`` 为 ``…/v1``），``chat.completions.create`` + ``extra_body``。
- ``provider=http_requests``：``requests.post`` 到完整 Chat Completions URL，JSON 与内网网关一致。
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from urllib.parse import urlparse, urlunparse

import requests

from src.llm.llm_config import (
    PROVIDER_HTTP,
    PROVIDER_VLLM,
    read_llm_config,
    read_llm_config_for_summary,
    read_llm_config_for_tagging,
    llm_tagging_enabled,
)


def _path_parent_url(url: str) -> str | None:
    """去掉路径最后一层，例如 ``.../v2/models/llm`` → ``.../v2/models``。"""
    try:
        p = urlparse(url)
    except Exception:
        return None
    path = (p.path or "/").rstrip("/")
    if not path:
        return None
    parent_path = path.rsplit("/", 1)[0]
    if not parent_path:
        parent_path = "/"
    return urlunparse((p.scheme, p.netloc, parent_path, p.params, p.query, p.fragment))


def models_list_url_candidates(completions_url: str) -> list[str]:
    """
    由 Chat Completions URL 生成若干候选 ``GET`` 地址（兼容不同网关路径）。

    例如 ``.../v2/models/llm/chat/completions`` 会先试 ``.../llm/models``（常 404），
    再试上一级 ``.../v2/models``（不少内网网关在此列出模型）。
    """
    u = (completions_url or "").strip().rstrip("/")
    out: list[str] = []
    seen: set[str] = set()

    def add(x: str) -> None:
        x = (x or "").strip().rstrip("/")
        if not x or x in seen:
            return
        seen.add(x)
        out.append(x)

    if "/chat/completions" in u:
        base = u.split("/chat/completions", 1)[0].rstrip("/")
        if base:
            add(base + "/models")
            walk = base
            for _ in range(8):
                parent = _path_parent_url(walk)
                if not parent:
                    break
                parent = parent.rstrip("/")
                if not parent or parent == walk.rstrip("/"):
                    break
                add(parent)
                add(parent + "/models")
                walk = parent
        return out
    if u.endswith("/v1"):
        add(u + "/models")
        return out
    add(u + "/v1/models")
    return out


def chat_completions_url_to_models_url(completions_url: str) -> str:
    """返回首选候选（与 :func:`models_list_url_candidates` 第一项一致）。"""
    cands = models_list_url_candidates(completions_url)
    return cands[0] if cands else ""


def fetch_openai_compatible_model_ids(
    completions_url: str,
    *,
    api_key: str = "",
    timeout: float = 30.0,
) -> list[str]:
    """依次请求候选模型列表 URL，返回 ``id`` 列表（去重排序）。"""
    candidates = models_list_url_candidates(completions_url)
    if not candidates:
        raise ValueError("接口地址为空")
    headers: dict[str, str] = {"Content-Type": "application/json"}
    key = (api_key or "").strip()
    if key:
        headers["Authorization"] = f"Bearer {key}"

    last_detail = ""
    for models_url in candidates:
        try:
            resp = requests.get(models_url, headers=headers, timeout=timeout)
            if resp.status_code == 404:
                last_detail = f"404 {models_url}"
                continue
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, dict):
                last_detail = f"非 JSON 对象: {models_url}"
                continue
            items = data.get("data")
            if items is None:
                last_detail = f"响应无 data 字段: {models_url}"
                continue
            if not isinstance(items, list):
                last_detail = f"data 非列表: {models_url}"
                continue
            ids: list[str] = []
            for it in items:
                if not isinstance(it, dict):
                    continue
                mid = it.get("id")
                if mid:
                    ids.append(str(mid))
            return sorted(set(ids))
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                last_detail = f"404 {models_url}"
                continue
            last_detail = str(e)
            continue
        except Exception as e:
            last_detail = str(e)
            continue

    tried = ", ".join(candidates[:5]) + ("…" if len(candidates) > 5 else "")
    raise RuntimeError(
        "无法在常见路径下获取模型列表（已依次尝试多个候选地址）。"
        f"最后错误: {last_detail or 'unknown'}。已试 URL 示例: {tried}",
    )


def fetch_vllm_model_ids_sdk(
    base_v1_url: str,
    *,
    api_key: str = "",
    timeout: float = 30.0,
) -> list[str]:
    """vLLM OpenAI 兼容服务：使用 OpenAI SDK ``client.models.list()``。"""
    from openai import OpenAI

    base = (base_v1_url or "").strip().rstrip("/")
    if not base:
        raise ValueError("base_url 为空")
    key = (api_key or "").strip() or "EMPTY"
    to = max(5.0, min(float(timeout), 120.0))
    client = OpenAI(api_key=key, base_url=base, timeout=to)
    page = client.models.list()
    raw: list[Any] = []
    data_attr = getattr(page, "data", None)
    if isinstance(data_attr, list) and data_attr:
        raw = data_attr
    elif data_attr is not None:
        try:
            raw = list(data_attr)
        except (TypeError, ValueError):
            raw = []
    if not raw and page is not None:
        try:
            raw = list(page)
        except (TypeError, ValueError):
            raw = []
    ids: list[str] = []
    for m in raw:
        mid = getattr(m, "id", None)
        if mid is None and isinstance(m, dict):
            mid = m.get("id")
        if mid:
            ids.append(str(mid))
    return sorted(set(ids))


def _qwen_extra_body(cfg: dict[str, Any]) -> dict[str, Any]:
    """与 test.ipynb 中 Qwen3.5 / 内网网关一致的扩展字段（vLLM 走 extra_body，HTTP 走 JSON 根）。"""
    return {
        "top_k": int(cfg.get("top_k", 20)),
        "top_p": float(cfg.get("top_p", 0.8)),
        "min_p": float(cfg.get("min_p", 0.0)),
        "repetition_penalty": float(cfg.get("repetition_penalty", 1.0)),
        "presence_penalty": float(cfg.get("presence_penalty", 1.5)),
        "enable_thinking": bool(cfg.get("enable_thinking", False)),
    }


def merge_llm_config_for_ephemeral(
    overrides: dict[str, Any] | None,
) -> dict[str, Any]:
    """以当前已保存配置为底，仅应用 overrides 中出现的字段（用于未保存表单上的测试/发现）。"""
    cfg: dict[str, Any] = deepcopy(read_llm_config())
    if not overrides:
        return cfg
    allowed = frozenset({
        "provider",
        "base_url",
        "api_key",
        "model",
        "temperature",
        "max_tokens",
        "timeout_seconds",
        "top_k",
        "top_p",
        "min_p",
        "repetition_penalty",
        "presence_penalty",
        "enable_thinking",
    })
    for key, val in overrides.items():
        if key not in allowed or val is None:
            continue
        if key == "provider":
            s = str(val).strip()
            if s in (PROVIDER_VLLM, PROVIDER_HTTP):
                cfg[key] = s
        elif key in ("base_url", "api_key", "model"):
            cfg[key] = str(val).strip()
        elif key == "temperature":
            cfg[key] = float(val)
        elif key in ("max_tokens", "timeout_seconds", "top_k"):
            cfg[key] = int(val)
        elif key in ("top_p", "min_p", "repetition_penalty", "presence_penalty"):
            cfg[key] = float(val)
        elif key == "enable_thinking":
            cfg[key] = bool(val)
    return cfg


def is_llm_configured() -> bool:
    """是否启用打标且已填写接口地址与模型名。"""
    return llm_tagging_enabled()


def is_chat_test_ready(cfg: dict[str, Any]) -> bool:
    base_ok = bool(str(cfg.get("base_url") or "").strip())
    if not base_ok:
        return False
    prov = str(cfg.get("provider") or PROVIDER_HTTP)
    if prov == PROVIDER_VLLM:
        return bool(str(cfg.get("model") or "").strip())
    # HTTP 直连下 model 可选（部分网关会忽略或由服务端默认）
    return True


def _chat_http_requests_raw(
    cfg: dict[str, Any],
    messages: list[dict[str, Any]],
) -> str:
    """HTTP 直连：POST 完整 Chat Completions URL，JSON 与内网网关 / requests 示例一致。"""
    url = str(cfg["base_url"]).strip()
    model = str(cfg["model"]).strip()
    timeout = float(cfg.get("timeout_seconds") or 120)
    temperature = float(cfg.get("temperature") if cfg.get("temperature") is not None else 0.2)
    max_tokens = int(cfg.get("max_tokens") or 1024)
    api_key = str(cfg.get("api_key") or "").strip()

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        **_qwen_extra_body(cfg),
    }

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    choice0 = data.get("choices", [{}])[0] or {}
    msg = choice0.get("message") or {}
    content = msg.get("content")
    if content is None:
        raise RuntimeError(f"响应缺少 choices[0].message.content: {repr(data)[:500]}")
    return str(content)


def _chat_vllm_openai_sdk(
    cfg: dict[str, Any],
    messages: list[dict[str, Any]],
) -> str:
    """vLLM：OpenAI SDK，``base_url`` 为 ``http://host:port/v1``。"""
    from openai import OpenAI

    base = str(cfg["base_url"]).strip().rstrip("/")
    model = str(cfg["model"]).strip()
    timeout = float(cfg.get("timeout_seconds") or 120)
    temperature = float(cfg.get("temperature") if cfg.get("temperature") is not None else 0.2)
    max_tokens = int(cfg.get("max_tokens") or 1024)
    api_key = str(cfg.get("api_key") or "").strip() or "EMPTY"

    client = OpenAI(api_key=api_key, base_url=base, timeout=timeout)
    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        extra_body=_qwen_extra_body(cfg),
    )
    msg = completion.choices[0].message
    content = msg.content
    if content is None:
        raise RuntimeError("响应缺少 choices[0].message.content")
    return str(content).strip()


def chat_completions_with_config(
    cfg: dict[str, Any],
    messages: list[dict[str, Any]],
    *,
    require_enabled: bool = True,
    model_override: str | None = None,
) -> str:
    """使用给定配置调用模型：``provider=vllm`` 走 OpenAI SDK；``http_requests`` 走 requests 直连。

    ``model_override`` 非空时覆盖 ``cfg["model"]``（一般无需使用；多配置请用不同 profile）。
    """
    prov = str(cfg.get("provider") or PROVIDER_HTTP)
    use_model = (model_override or "").strip() or str(cfg.get("model") or "").strip()
    if require_enabled:
        if not str(cfg.get("base_url") or "").strip():
            raise RuntimeError("LLM 未启用或未配置 base_url / model")
        if prov == PROVIDER_VLLM and not use_model:
            raise RuntimeError("LLM 未启用或未配置 base_url / model")
    else:
        cfg_try = {**cfg, "model": use_model}
        if not is_chat_test_ready(cfg_try):
            raise RuntimeError("请先填写接口地址（vLLM 还需模型名）")

    cfg_call = {**cfg, "model": use_model}
    if prov == PROVIDER_VLLM:
        return _chat_vllm_openai_sdk(cfg_call, messages)
    return _chat_http_requests_raw(cfg_call, messages)


def chat_completions(messages: list[dict[str, Any]], *, require_enabled: bool = True) -> str:
    """
    POST Chat Completions，返回 assistant 的文本 content。

    :param messages: [{"role": "system"|"user"|"assistant", "content": "..."}, ...]
    :param require_enabled: True 时要求配置可用；False 时仅做最小字段校验
    :raises RuntimeError: 配置不完整，或 require_enabled=True 且未启用
    :raises requests.HTTPError: HTTP 非 2xx
    """
    cfg = read_llm_config()
    if require_enabled and not llm_tagging_enabled():
        raise RuntimeError("LLM 未启用或未配置 base_url / model")
    return chat_completions_with_config(cfg, messages, require_enabled=require_enabled)


def chat_completions_for_tagging(
    messages: list[dict[str, Any]],
    *,
    require_enabled: bool = True,
) -> str:
    """打标签：使用配置页中「打标签所用配置」指向的整套 profile（未选则当前默认配置）。"""
    cfg = read_llm_config_for_tagging()
    if require_enabled and not llm_tagging_enabled():
        raise RuntimeError("LLM 未启用或未配置 base_url / model")
    return chat_completions_with_config(cfg, messages, require_enabled=require_enabled)


def chat_completions_for_summary(
    messages: list[dict[str, Any]],
    *,
    require_enabled: bool = True,
) -> str:
    """文章总结：使用「文章总结所用配置」指向的整套 profile（未选则当前默认配置）。"""
    cfg = read_llm_config_for_summary()
    if require_enabled:
        if not str(cfg.get("base_url") or "").strip():
            raise RuntimeError("未配置 base_url")
        prov = str(cfg.get("provider") or PROVIDER_HTTP)
        if prov == PROVIDER_VLLM and not str(cfg.get("model") or "").strip():
            raise RuntimeError("未配置模型")
    return chat_completions_with_config(cfg, messages, require_enabled=require_enabled)
