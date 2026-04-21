"""
爬取后为新文章生成「阅读筛选分析」：
- summary: 覆盖式摘要（<=200字）
- tags: 3~6 个具体标签
"""

from __future__ import annotations

import json
import re
from typing import Any

from src.llm.model_client import chat_completions_for_tagging, is_llm_configured

MIN_TAGS = 3  # 标签最少数量
MAX_TAGS = 6  # 标签最多数量
MAX_SUMMARY_CHARS = 200  # 覆盖摘要最大长度（字符）
MAX_BODY_CHARS = 10000  # 送入模型的正文片段最大长度（字符）

_SYSTEM_PROMPT = """你是“阅读筛选分析助手”。请严格按要求输出摘要与标签：

【一、主题覆盖摘要】
分为两部分输出：
1）一句话总结（可选）
- 用一句话概括文章主线（不超过30字）
- 可以省略，如果不好概括就不写
2）内容块拆分（核心）
- 按“文章讲了哪些内容块”分点列出（3~6点）
- 只说“做了什么”，不展开细节，某些技术名词注意体现
- 必须覆盖所有主要内容块（不能遗漏，包括推广）

要求：
- 总字数不超过100字
- 表达自然，适当口语化，不要过于书面化，不要模板化（不要固定句式）
- 避免技术细节（性能、实现等），统一用概括表达
目标：像“目录+简述”，一眼扫清文章结构

【二、内容标签】
1. 核心主题标签（必须1个）：
   - 选择最具体的技术点（如：协程 / RAG / Redis缓存）
   - 禁止使用宽泛词（如：Python / 编程）
2. 内容类型标签（必须1个）：
   - 教程 / 原理解析 / 实战案例 / 资讯 / 论文解读 / 工具推荐
3. 技术范围标签（1~2个）：
   - 如：Python / 后端 / LLM / 数据库 等
4. 特殊标签（可选）：
   - 推广（只要出现广告/卖课/引流必须标记）
   - 开源项目 / 官方文档 / 博主经验
要求：
- 标签必须具体、有区分度
- 禁止评价类标签（如：信息密度高/低）

【输出格式（必须是 JSON，不要 Markdown）】
{{
  "summary": "不超过200字的逐块覆盖摘要",
  "tags": ["标签1","标签2","标签3"]
}}"""


def _body_excerpt(detail: Any) -> str:
    if detail is None:
        return ""
    if isinstance(detail, list):
        text = "\n".join(str(p) for p in detail)
    else:
        text = str(detail)
    return text[:MAX_BODY_CHARS]


def _clean_json_candidate(content: str) -> str:
    s = content.strip()
    block = re.search(r"```(?:json)?\s*([\s\S]*?)```", s)
    if block:
        s = block.group(1).strip()
    return s


def _normalize_tags(raw_tags: Any) -> list[str]:
    if not isinstance(raw_tags, list):
        return []
    seen: set[str] = set()
    out: list[str] = []
    for x in raw_tags:
        t = str(x).strip()
        if not t or t in seen:
            continue
        seen.add(t)
        out.append(t)
        if len(out) >= MAX_TAGS:
            break
    return out


def _parse_analysis_json(content: str) -> tuple[str, list[str]]:
    """从模型输出中解析 {"summary": "...", "tags": [...]}。"""
    s = _clean_json_candidate(content)
    try:
        data = json.loads(s)
        if isinstance(data, dict):
            summary = str(data.get("summary") or "").strip()
            tags = _normalize_tags(data.get("tags"))
            return summary[:MAX_SUMMARY_CHARS], tags
    except json.JSONDecodeError:
        pass
    obj = re.search(r"\{[\s\S]*\}", s)
    if obj:
        try:
            data = json.loads(obj.group(0))
            if isinstance(data, dict):
                summary = str(data.get("summary") or "").strip()
                tags = _normalize_tags(data.get("tags"))
                return summary[:MAX_SUMMARY_CHARS], tags
        except json.JSONDecodeError:
            pass
    print(f"[tag] 无法解析为分析 JSON，原始片段: {content[:200]!r}...")
    return "", []


def tag_article(article: dict[str, Any], data_manager: Any) -> dict[str, Any]:
    """
    为单篇文章生成摘要+标签。未配置 LLM endpoint 时返回空结果。

    :param article: message_info 中 blogs 的一项（含 id/title/digest）
    :param data_manager: JsonFileManager 单例，用于读取 message_detail_text
    """
    if not is_llm_configured():
        return {"summary": "", "tags": []}

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
        raw = chat_completions_for_tagging(messages)
        summary, tags = _parse_analysis_json(raw)
        if len(tags) < MIN_TAGS:
            # 标签不足时保留已有（允许模型给少量高质量标签）
            tags = tags[:MAX_TAGS]
        return {"summary": summary, "tags": tags}
    except Exception as e:
        print(f"[tag] LLM 调用失败 article_id={aid!r}: {e}")
        return {"summary": "", "tags": []}
