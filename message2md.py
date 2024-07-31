#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author      : Cao Zejun
# @Time        : 2024/7/31 23:43
# @File        : message2md.py
# @Software    : Pycharm
# @description : 将微信公众号聚合平台数据转换为markdown文件，上传博客平台

import json
import datetime
from collections import defaultdict


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
        with open('./data/message_info.json', 'r', encoding='utf-8') as fp:
            message_info = json.load(fp)

    md_dict = defaultdict(list)
    for k, v in message_info.items():
        for m in v['blogs']:
            if not m['create_time']:
                continue
            t = datetime.datetime.strptime(m['create_time'],"%Y-%m-%d %H:%M").strftime("%Y-%m-%d")
            md_dict[t].append(m)

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