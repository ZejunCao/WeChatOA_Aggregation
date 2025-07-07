# -*- coding:utf-8 -*-
# @Author      : Cao Zejun
# @Time        : 2025/07/08
# @File        : __init__.py
# @description : web模块初始化文件

from .blog_generator import generate_single_posts, generate_summary_markdown

__all__ = [
    'generate_summary_markdown',
    'generate_single_posts',
] 