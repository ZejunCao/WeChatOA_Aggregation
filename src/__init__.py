# -*- coding:utf-8 -*-
# @Author      : Cao Zejun
# @Time        : 2025/07/08
# @File        : __init__.py
# @description : src包初始化文件

# 从各个子模块导入公共接口
from .crawler import WechatRequest
from .processor import minHashLSH, get_valid_message
from .utils import (
    data_manager, Message_Info, headers,
    time_now, time_delta, jstime2realtime, realtime2jstime,
    url2text, message_is_delete, check_text_ratio, nunjucks_escape
)
from .web import (
    generate_summary_markdown, generate_single_posts,
    message2md, single_message2md
)

__all__ = [
    # 从crawler模块导入
    'WechatRequest',
    # 从processor模块导入
    'minHashLSH',
    'get_valid_message',
    # 从utils模块导入
    'data_manager',
    'Message_Info',
    'headers',
    'time_now',
    'time_delta',
    'jstime2realtime',
    'realtime2jstime',
    'url2text',
    'message_is_delete',
    'check_text_ratio',
    'nunjucks_escape',
    # 从web模块导入
    'generate_summary_markdown',
    'generate_single_posts',
    'message2md',
    'single_message2md',
] 