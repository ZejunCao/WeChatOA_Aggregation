"""
LLM 打标签配置：读写 data/llm_config.json，与前端配置页同步。

支持多配置（profiles）+ 当前生效配置（active_profile）。
可指定“任务模型配置”（task_profile）：打标签/总结等任务统一使用同一套已保存配置。
兼容旧版单配置结构：自动迁移为默认 profile。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# 与 api.py 中 DATA_DIR 一致：项目根目录下的 data/
_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_CONFIG_PATH = _DATA_DIR / "llm_config.json"

# vllm：OpenAI SDK，base_url 为根地址（如 http://host:8055/v1），可拉取模型列表
# http_requests：requests 直连完整 Chat Completions URL，与内网网关 JSON 一致，不拉列表
PROVIDER_VLLM = "vllm"
PROVIDER_HTTP = "http_requests"
# 旧版 openai_compatible 读入时迁移为 http_requests
VALID_PROVIDERS = frozenset({PROVIDER_VLLM, PROVIDER_HTTP})
DEFAULT_PROFILE_NAME = "默认配置"

# 爬取补总结/打标：多线程并发上限（与配置页一致）
CRAWL_LLM_MULTITHREAD_WORKERS_MIN = 1
CRAWL_LLM_MULTITHREAD_WORKERS_MAX = 32
CRAWL_LLM_MULTITHREAD_WORKERS_DEFAULT = 4

_PROFILE_DEFAULTS: dict[str, Any] = {
    "provider": PROVIDER_HTTP,
    "base_url": "",
    "api_key": "",
    "model": "",
    "temperature": 0.2,
    "max_tokens": 1024,
    "timeout_seconds": 120,
    "top_k": 20,
    "top_p": 0.8,
    "min_p": 0.0,
    "repetition_penalty": 1.0,
    "presence_penalty": 1.5,
    "enable_thinking": False,
}


def llm_config_path() -> Path:
    return _CONFIG_PATH


def _merge_profile(raw: dict[str, Any]) -> dict[str, Any]:
    out = {**_PROFILE_DEFAULTS}
    for k, v in raw.items():
        if k in _PROFILE_DEFAULTS:
            out[k] = v
    prov = str(out.get("provider") or "").strip()
    if prov == "openai_compatible":
        prov = PROVIDER_HTTP
    if prov == PROVIDER_VLLM and "/chat/completions" in str(out.get("base_url") or ""):
        prov = PROVIDER_HTTP
    if prov not in VALID_PROVIDERS:
        prov = PROVIDER_HTTP
    out["provider"] = prov
    out["base_url"] = str(out.get("base_url") or "").strip()
    out["api_key"] = str(out.get("api_key") or "").strip()
    out["model"] = str(out.get("model") or "").strip()
    try:
        out["temperature"] = float(out["temperature"])
    except (TypeError, ValueError):
        out["temperature"] = _PROFILE_DEFAULTS["temperature"]
    try:
        out["max_tokens"] = int(out["max_tokens"])
    except (TypeError, ValueError):
        out["max_tokens"] = _PROFILE_DEFAULTS["max_tokens"]
    try:
        out["timeout_seconds"] = int(out["timeout_seconds"])
    except (TypeError, ValueError):
        out["timeout_seconds"] = _PROFILE_DEFAULTS["timeout_seconds"]
    try:
        out["top_k"] = int(out["top_k"])
    except (TypeError, ValueError):
        out["top_k"] = _PROFILE_DEFAULTS["top_k"]
    try:
        out["top_p"] = float(out["top_p"])
    except (TypeError, ValueError):
        out["top_p"] = _PROFILE_DEFAULTS["top_p"]
    try:
        out["min_p"] = float(out["min_p"])
    except (TypeError, ValueError):
        out["min_p"] = _PROFILE_DEFAULTS["min_p"]
    try:
        out["repetition_penalty"] = float(out["repetition_penalty"])
    except (TypeError, ValueError):
        out["repetition_penalty"] = _PROFILE_DEFAULTS["repetition_penalty"]
    try:
        out["presence_penalty"] = float(out["presence_penalty"])
    except (TypeError, ValueError):
        out["presence_penalty"] = _PROFILE_DEFAULTS["presence_penalty"]
    out["enable_thinking"] = bool(out.get("enable_thinking"))
    out["max_tokens"] = max(1, min(out["max_tokens"], 128_000))
    out["timeout_seconds"] = max(5, min(out["timeout_seconds"], 600))
    return out


def _clamp_crawl_llm_multithread_workers(raw: Any) -> int:
    try:
        n = int(raw)
    except (TypeError, ValueError):
        n = CRAWL_LLM_MULTITHREAD_WORKERS_DEFAULT
    return max(CRAWL_LLM_MULTITHREAD_WORKERS_MIN, min(n, CRAWL_LLM_MULTITHREAD_WORKERS_MAX))


def _normalize_store(raw: dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw.get("profiles"), list):
        profiles: list[dict[str, Any]] = []
        for item in raw["profiles"]:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            merged = _merge_profile(item)
            profiles.append({"name": name, **merged})
        if not profiles:
            profiles = [{"name": DEFAULT_PROFILE_NAME, **_merge_profile({})}]
        names = {p["name"] for p in profiles}
        active = str(raw.get("active_profile") or "").strip()
        if not active or active not in names:
            active = profiles[0]["name"]
        task_profile = str(raw.get("task_profile") or "").strip()
        if not task_profile:
            task_profile = str(raw.get("tagging_profile") or "").strip() or str(raw.get("summary_profile") or "").strip()
        if task_profile and task_profile not in names:
            task_profile = ""
        if "crawl_llm_enabled" in raw:
            crawl_llm_enabled = bool(raw.get("crawl_llm_enabled"))
        else:
            active_enabled = False
            raw_profiles = raw.get("profiles")
            if isinstance(raw_profiles, list):
                for p in raw_profiles:
                    if not isinstance(p, dict):
                        continue
                    if str(p.get("name") or "").strip() != active:
                        continue
                    active_enabled = bool(p.get("enabled"))
                    break
            crawl_llm_enabled = active_enabled
        crawl_llm_multithread_enabled = bool(raw.get("crawl_llm_multithread_enabled", False))
        crawl_llm_multithread_workers = _clamp_crawl_llm_multithread_workers(
            raw.get("crawl_llm_multithread_workers", CRAWL_LLM_MULTITHREAD_WORKERS_DEFAULT)
        )
        return {
            "active_profile": active,
            "task_profile": task_profile,
            "crawl_llm_enabled": crawl_llm_enabled,
            "crawl_llm_multithread_enabled": crawl_llm_multithread_enabled,
            "crawl_llm_multithread_workers": crawl_llm_multithread_workers,
            "profiles": profiles,
        }

    single = _merge_profile(raw if isinstance(raw, dict) else {})
    legacy_workers = (
        raw.get("crawl_llm_multithread_workers", CRAWL_LLM_MULTITHREAD_WORKERS_DEFAULT)
        if isinstance(raw, dict)
        else CRAWL_LLM_MULTITHREAD_WORKERS_DEFAULT
    )
    return {
        "active_profile": DEFAULT_PROFILE_NAME,
        "task_profile": "",
        "crawl_llm_enabled": False,
        "crawl_llm_multithread_enabled": False,
        "crawl_llm_multithread_workers": _clamp_crawl_llm_multithread_workers(legacy_workers),
        "profiles": [{"name": DEFAULT_PROFILE_NAME, **single}],
    }


def read_crawl_llm_enabled() -> bool:
    store = read_llm_store()
    return bool(store.get("crawl_llm_enabled"))


def write_crawl_llm_enabled(enabled: bool) -> None:
    store = read_llm_store()
    store["crawl_llm_enabled"] = bool(enabled)
    write_llm_store(store)


def read_crawl_llm_multithread_enabled() -> bool:
    store = read_llm_store()
    return bool(store.get("crawl_llm_multithread_enabled"))


def write_crawl_llm_multithread_enabled(enabled: bool) -> None:
    store = read_llm_store()
    store["crawl_llm_multithread_enabled"] = bool(enabled)
    write_llm_store(store)


def read_crawl_llm_multithread_workers() -> int:
    store = read_llm_store()
    return _clamp_crawl_llm_multithread_workers(
        store.get("crawl_llm_multithread_workers", CRAWL_LLM_MULTITHREAD_WORKERS_DEFAULT)
    )


def write_crawl_llm_multithread_workers(workers: int) -> None:
    store = read_llm_store()
    store["crawl_llm_multithread_workers"] = _clamp_crawl_llm_multithread_workers(workers)
    write_llm_store(store)


def read_llm_store() -> dict[str, Any]:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not _CONFIG_PATH.exists():
        return _normalize_store({})
    try:
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, dict):
            return _normalize_store({})
        return _normalize_store(raw)
    except (json.JSONDecodeError, OSError):
        return _normalize_store({})


def write_llm_store(store: dict[str, Any]) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    normalized = _normalize_store(store if isinstance(store, dict) else {})
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2)


def read_llm_config() -> dict[str, Any]:
    store = read_llm_store()
    return read_llm_config_for_named_profile(store, store["active_profile"])


def read_llm_config_for_named_profile(store: dict[str, Any], profile_name: str) -> dict[str, Any]:
    names = {p["name"] for p in store.get("profiles", [])}
    name = str(profile_name or "").strip()
    if not name or name not in names:
        name = str(store.get("active_profile") or "").strip()
    for p in store.get("profiles", []):
        if p.get("name") == name:
            patch = {k: p[k] for k in _PROFILE_DEFAULTS if k in p}
            return _merge_profile(patch)
    return {**_PROFILE_DEFAULTS}


def read_llm_config_for_task() -> dict[str, Any]:
    store = read_llm_store()
    key = str(store.get("task_profile") or "").strip()
    return read_llm_config_for_named_profile(store, key)


def read_llm_config_for_tagging() -> dict[str, Any]:
    return read_llm_config_for_task()


def read_llm_config_for_summary() -> dict[str, Any]:
    return read_llm_config_for_task()


def write_llm_config(
    cfg: dict[str, Any],
    profile_name: str | None = None,
    set_active: bool = True,
    source_profile_name: str | None = None,
) -> str:
    store = read_llm_store()
    name = str(profile_name or store.get("active_profile") or DEFAULT_PROFILE_NAME).strip() or DEFAULT_PROFILE_NAME
    source_name = str(source_profile_name or "").strip()
    merged = _merge_profile(cfg if isinstance(cfg, dict) else {})
    profiles = store["profiles"]
    source_idx = -1
    if source_name:
        for i, p in enumerate(profiles):
            if p["name"] == source_name:
                source_idx = i
                break
    if source_idx >= 0:
        if source_name != name:
            for i, p in enumerate(profiles):
                if i != source_idx and p["name"] == name:
                    raise ValueError(f"配置名称「{name}」已存在")
        profiles[source_idx] = {"name": name, **merged}
    else:
        replaced = False
        for i, p in enumerate(profiles):
            if p["name"] == name:
                profiles[i] = {"name": name, **merged}
                replaced = True
                break
        if not replaced:
            profiles.append({"name": name, **merged})
    if set_active:
        store["active_profile"] = name
    write_llm_store(store)
    return name


def set_llm_task_profile(task_profile: str) -> None:
    store = read_llm_store()
    names = {p["name"] for p in store["profiles"]}
    t = (task_profile or "").strip()
    if t and t not in names:
        raise ValueError(f"任务模型配置「{t}」不存在")
    store["task_profile"] = t
    write_llm_store(store)


def set_active_profile(profile_name: str) -> bool:
    store = read_llm_store()
    target = str(profile_name or "").strip()
    if not target:
        return False
    names = {p["name"] for p in store["profiles"]}
    if target not in names:
        return False
    store["active_profile"] = target
    write_llm_store(store)
    return True


def delete_profile(profile_name: str) -> tuple[bool, str]:
    store = read_llm_store()
    target = str(profile_name or "").strip()
    if not target:
        return False, "not_found"
    names = [p["name"] for p in store["profiles"]]
    if target not in names:
        return False, "not_found"
    if len(store["profiles"]) <= 1:
        return False, "last_profile"
    remain = [p for p in store["profiles"] if p["name"] != target]
    store["profiles"] = remain
    if store.get("active_profile") == target:
        store["active_profile"] = remain[0]["name"]
    if store.get("task_profile") == target:
        store["task_profile"] = ""
    write_llm_store(store)
    return True, ""


def reset_all_profiles() -> dict[str, Any]:
    store = read_llm_store()
    profiles = store.get("profiles", [])
    if not profiles:
        store = _normalize_store({})
        write_llm_store(store)
        return store
    store["profiles"] = [
        {"name": str(p.get("name") or DEFAULT_PROFILE_NAME), **_merge_profile({})}
        for p in profiles
        if isinstance(p, dict)
    ]
    if not store["profiles"]:
        store = _normalize_store({})
    names = {p["name"] for p in store["profiles"]}
    if store.get("active_profile") not in names:
        store["active_profile"] = store["profiles"][0]["name"]
    write_llm_store(store)
    return store


def reset_profile(profile_name: str | None = None) -> tuple[bool, str]:
    store = read_llm_store()
    target = str(profile_name or store.get("active_profile") or "").strip()
    if not target:
        return False, "not_found"
    for i, p in enumerate(store["profiles"]):
        if p["name"] == target:
            store["profiles"][i] = {"name": target, **_merge_profile({})}
            write_llm_store(store)
            return True, ""
    return False, "not_found"


def llm_tagging_enabled() -> bool:
    if not read_crawl_llm_enabled():
        return False
    c = read_llm_config_for_tagging()
    if not str(c.get("base_url") or "").strip():
        return False
    prov = str(c.get("provider") or PROVIDER_HTTP)
    if prov == PROVIDER_VLLM:
        return bool(str(c.get("model") or "").strip())
    return True
