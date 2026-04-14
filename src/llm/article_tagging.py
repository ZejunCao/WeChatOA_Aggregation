"""
爬取后为新文章生成中文标签：种子标签 + 模型扩展；推广类内容须含「广告」。
"""

from __future__ import annotations

import json
import re
from typing import Any

from src.llm.model_client import chat_qwen35_27b, qwen_endpoint_configured

# 种子标签（模型可从中选取，也可新增不在列表中的短标签）
SEED_TAGS: tuple[str, ...] = (
    "技术",
    "产品",
    "行业",
    "教程",
    "新闻",
    "观点",
    "工具",
    "科研",
    "广告",
)

MAX_TAGS = 5
MAX_BODY_CHARS = 3000

_SYSTEM_PROMPT = f"""你是微信公众号文章的标签分类助手。请根据标题、摘要与正文片段，输出 1～{MAX_TAGS} 个中文标签。

【种子标签】（可从中选择合适项，也可补充列表中没有的短标签，2～6 字为宜）：
{", ".join(SEED_TAGS)}

规则：
- 只输出一个 JSON 数组，例如：["技术","教程"]，不要其它说明文字。
- 标签应概括主题；允许从种子标签中选多个，也允许新增更贴切的中文标签。
- 若内容明显为推广、带货、商务合作、优惠券、引流加群、营销导向软文，必须包含标签「广告」。
- 不要重复；不要英文（除非专有名词极短且必要）。"""


def _body_excerpt(detail: Any) -> str:
    if detail is None:
        return ""
    if isinstance(detail, list):
        text = "\n".join(str(p) for p in detail)
    else:
        text = str(detail)
    return text[:MAX_BODY_CHARS]


def _parse_tags_json(content: str) -> list[str]:
    """从模型输出中解析 JSON 字符串数组。"""
    s = content.strip()
    block = re.search(r"```(?:json)?\s*([\s\S]*?)```", s)
    if block:
        s = block.group(1).strip()
    try:
        data = json.loads(s)
        if isinstance(data, list):
            out = [str(x).strip() for x in data if str(x).strip()]
            return out[:MAX_TAGS]
    except json.JSONDecodeError:
        pass
    bracket = re.search(r"\[[\s\S]*\]", s)
    if bracket:
        try:
            data = json.loads(bracket.group(0))
            if isinstance(data, list):
                out = [str(x).strip() for x in data if str(x).strip()]
                return out[:MAX_TAGS]
        except json.JSONDecodeError:
            pass
    print(f"[tag] 无法解析为 JSON 数组，原始片段: {content[:200]!r}...")
    return []


def tag_article(article: dict[str, Any], data_manager: Any) -> list[str]:
    """
    为单篇文章生成标签。未配置 LLM endpoint 时返回 []（调用方勿写字段）。

    :param article: message_info 中 blogs 的一项（含 id/title/digest）
    :param data_manager: JsonFileManager 单例，用于读取 message_detail_text
    """
    if not qwen_endpoint_configured():
        return []

    aid = article.get("id") or ""
    title = (article.get("title") or "").strip()
    digest = (article.get("digest") or "").strip()
    detail = None
    if aid and hasattr(data_manager, "message_detail_text"):
        detail = data_manager.message_detail_text.get(aid)
    excerpt = _body_excerpt(detail)

    user = f"""标题：{title}
摘要：{digest}
正文片段（可能不完整或为空）：
{excerpt}
"""
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]
    try:
        raw = chat_qwen35_27b(messages)
        return _parse_tags_json(raw)
    except Exception as e:
        print(f"[tag] LLM 调用失败 article_id={aid!r}: {e}")
        return []
