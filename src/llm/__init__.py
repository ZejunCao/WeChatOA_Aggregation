"""LLM 适配与文章打标。"""

from src.llm.article_tagging import tag_article
from src.llm.model_client import chat_qwen35_27b, qwen_endpoint_configured

__all__ = ["chat_qwen35_27b", "qwen_endpoint_configured", "tag_article"]
