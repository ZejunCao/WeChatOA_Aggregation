# -*- coding:utf-8 -*-
# @Author      : Cao Zejun
# @Time        : 2025/07/08
# @File        : __init__.py
# @description : web模块初始化文件

from .blog_generator import (
    generate_summary_markdown,
    generate_single_posts,
    message2md,
    single_message2md
)

__all__ = [
    'generate_summary_markdown',
    'generate_single_posts',
    'message2md',
    'single_message2md',
] 