#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author      : Cao Zejun
# @Time        : 2024/7/31 23:43
# @File        : message2md.py
# @Software    : Pycharm
# @description : 将微信公众号聚合平台数据转换为markdown文件，上传博客平台

import os
os.chdir('D:\\learning\\python\\WeChatOA_Aggregation')
import datetime
from collections import defaultdict
from .util import handle_json


def message2md(message_info=None):
    md = '''---
layout: post
title: "微信公众号聚合平台"
date: 2024-07-29 01:36
comments: true
tags: 
    - 开源项目
---
'''
    if not message_info:
        message_info = handle_json('message_info')
    dup_message = handle_json('dup_message')
    delete_messages = handle_json('delete_message')
    delete_messages_set = set(delete_messages['is_delete'])

    delete_count = 0
    dup_count = 0
    md_dict = defaultdict(list)
    for k, v in message_info.items():
        for m in v['blogs']:
            # 历史遗留，有些文章没有创建时间，疑似已删除，待验证
            if not m['create_time']:
                continue
            # 去除已删除文章
            if m['id'] in delete_messages_set:
                delete_count += 1
                continue
            # 去掉重复率高的文章
            if m['id'] in dup_message.keys() and dup_message[m['id']]['duplicate_rate'] > 0.5:
                dup_count += 1
                continue

            t = datetime.datetime.strptime(m['create_time'],"%Y-%m-%d %H:%M").strftime("%Y-%m-%d")
            md_dict[t].append(m)

    print(f'{delete_count} messages have been deleted')
    print(f'{dup_count} messages have been deduplicated')
    date_list = sorted(md_dict.keys(), reverse=True)
    for date in date_list:
        if date < '2024-07-01':
            continue
        md += f'## {date}\n'
        for m in md_dict[date]:
            md += f'* [{m["title"]}]({m["link"]})\n'

    with open('./data/微信公众号聚合平台.md', 'w', encoding='utf-8') as f:
        f.write(md)

if __name__ == '__main__':
    message2md()