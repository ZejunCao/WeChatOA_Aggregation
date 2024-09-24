#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author      : Cao Zejun
# @Time        : 2024/7/31 23:43
# @File        : message2md.py
# @Software    : Pycharm
# @description : 将微信公众号聚合平台数据转换为markdown文件，上传博客平台

import sys
from pathlib import Path
import datetime
from collections import defaultdict

# 调试用，执行当前文件时防止路径导入错误
if sys.argv[0] == __file__:
    from util import handle_json
else:
    from .util import handle_json


def message2md(message_info=None):
    md = '''---
layout: post
title: "微信公众号聚合平台"
date: 2024-07-29 01:36
comments: true
tags: 
    - 开源项目
    - 微信公众号聚合平台
---
'''
    if not message_info:
        message_info = handle_json('message_info')

    name2fakeid = handle_json('name2fakeid')
    issues_message = handle_json('issues_message')
    delete_messages_set = set(issues_message['is_delete'])

    delete_count = 0
    dup_count = 0
    md_dict = defaultdict(list)  # key=时间，年月日，value=文章
    for k, v in message_info.items():
        if k not in name2fakeid.keys():
            continue
        for m in v['blogs']:
            # 历史遗留，有些文章没有创建时间，疑似已删除，待验证
            if not m['create_time']:
                continue
            # 去除已删除文章
            if m['id'] in delete_messages_set:
                delete_count += 1
                continue
            if m['title'] == '一文看尽LLM对齐技术：RLHF、RLAIF、PPO、DPO……':
                print()
            # 去掉重复率高的文章
            if m['id'] in issues_message['dup_minhash'].keys():
                dup_count += 1
                continue

            t = datetime.datetime.strptime(m['create_time'],"%Y-%m-%d %H:%M").strftime("%Y-%m-%d")
            md_dict[t].append(m)

    print(f'{delete_count} messages have been deleted')
    print(f'{dup_count} messages have been deduplicated')
    # 获取所有时间并逆序排列
    date_list = sorted(md_dict.keys(), reverse=True)
    for date in date_list:
        if date < '2024-07-01':
            continue
        md += f'## {date}\n'
        for m in md_dict[date]:
            md += f'* [{m["title"]}]({m["link"]})\n'

    md_path = Path(__file__).parent.parent / 'data' / '微信公众号聚合平台.md'
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md)


# 按微信公众号名字区分
def message2md_byname(message_info=None):
    md = '''---
layout: post
title: "微信公众号聚合平台_按公众号区分"
date: 2024-08-31 02:16
comments: true
tags: 
    - 开源项目
    - 微信公众号聚合平台
---
'''
    if not message_info:
        message_info = handle_json('message_info')

    name2fakeid = handle_json('name2fakeid')
    issues_message = handle_json('issues_message')
    delete_messages_set = set(issues_message['is_delete'])

    delete_count = 0
    dup_count = 0
    md_dict = defaultdict(list)
    for k, v in message_info.items():
        if k not in name2fakeid.keys():
            continue
        for m in v['blogs']:
            # 历史遗留，有些文章没有创建时间，疑似已删除，待验证
            if not m['create_time']:
                continue
            # 去除已删除文章
            if m['id'] in delete_messages_set:
                delete_count += 1
                continue
            # 去掉重复率高的文章
            # if m['id'] in issues_message['dup_minhash'].keys():
            #     dup_count += 1
            #     continue

            md_dict[k].append(m)

    # print(f'{delete_count} messages have been deleted')
    # print(f'{dup_count} messages have been deduplicated')
    md_dict = {k: sorted(v, key=lambda x: x['create_time'], reverse=True) for k, v in md_dict.items()}
    for k, v in md_dict.items():
        md += f'## {k}\n'
        for m in v:
            if m['create_time'] < '2024-07-01':
                continue
            md += f'* [{m["title"]}]({m["link"]})\n'

    md_path = Path(__file__).parent.parent / 'data' / '微信公众号聚合平台_byname.md'
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md)


if __name__ == '__main__':
    message2md()
    message2md_byname()