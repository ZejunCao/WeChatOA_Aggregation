#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author      : Cao Zejun
# @Time        : 2024/7/31 23:43
# @File        : message2md.py
# @Software    : Pycharm
# @description : 将微信公众号聚合平台数据转换为markdown文件，上传博客平台

import datetime
import os
import re
from collections import defaultdict
from pathlib import Path

import requests
from PIL import Image
from tqdm import tqdm

from ..utils.helpers import check_text_ratio, nunjucks_escape
from ..utils.data_manager import data_manager, headers


def get_valid_message():
    is_deleted_set = set(data_manager.issues_message['is_delete'])

    delete_count = 0
    dup_count = 0
    md_dict_by_date = defaultdict(list)  # 按日期分割，key=时间，年月日，value=文章
    md_dict_by_blogger = defaultdict(list)  # 按博主分割，key=博主名，value=文章
    for k, v in data_manager.message_info.items():
        # 由name2fakeid决定哪些公众号需要展示，如果从name2fakeid中删除了公众号但历史的message_info中存在，则跳过
        if k not in data_manager.name2fakeid.keys():
            continue
        # 遍历所有文章
        for m in v['blogs']:
            # 去除已删除文章
            if m['id'] in is_deleted_set:
                delete_count += 1
                continue
            # 按博主展示，不需要文章去重
            md_dict_by_blogger[k].append(m)
            # 按日期展示，需要去掉重复率高的文章
            if m['id'] in data_manager.issues_message['dup_minhash'].keys():
                dup_count += 1
                continue
            t = datetime.datetime.strptime(m['create_time'],"%Y-%m-%d %H:%M").strftime("%Y-%m-%d")
            md_dict_by_date[t].append(m)

    print(f'{delete_count} messages have been deleted')
    print(f'{dup_count} messages have been deduplicated')
    return md_dict_by_date, md_dict_by_blogger


def message2md():
    md_dict_by_date, md_dict_by_blogger = get_valid_message()
    # 1. 写入按日期区分的md文件
    md_by_date = '''---
layout: post
title: "微信公众号聚合平台_按时间区分"
date: 2024-07-29 01:36
top: true
hide: true
tags: 
    - 开源项目
    - 微信公众号聚合平台
---
'''
    # 获取所有时间并逆序排列
    date_list = sorted(md_dict_by_date.keys(), reverse=True)
    now = datetime.datetime.now()
    for date in date_list:
        # 为方便查看，只保留近半年的
        if now - datetime.datetime.strptime(date, '%Y-%m-%d') > datetime.timedelta(days=6*30):
            continue
        md_by_date += f'## {date}\n'
        for m in md_dict_by_date[date]:
            md_by_date += f'* [{m["title"]}]({m["link"]})\n'

    md_path = Path(__file__).parent.parent / 'data' / '微信公众号聚合平台_按时间区分.md'
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md_by_date)

    # 2. 写入按公众号区分的md文件
    md_by_blogger = '''---
layout: post
title: "微信公众号聚合平台_按公众号区分"
date: 2024-08-31 02:16
top: true
hide: true
tags: 
    - 开源项目
    - 微信公众号聚合平台
---
'''
    md_dict_by_blogger = {k: sorted(v, key=lambda x: x['create_time'], reverse=True) for k, v in md_dict_by_blogger.items()}
    for k, v in md_dict_by_blogger.items():
        md_by_blogger += f'## {k}\n'
        for m in v:
            # 为方便查看，只保留近半年的
            if now - datetime.datetime.strptime(m['create_time'], '%Y-%m-%d %H:%M') > datetime.timedelta(days=6*30):
                continue
            md_by_blogger += f'* [{m["title"]}]({m["link"]})\n'

    md_path = Path(__file__).parent.parent / 'data' / '微信公众号聚合平台_按公众号区分.md'
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md_by_blogger)


def single_message2md():
    md_dict_by_date, _ = get_valid_message()
    # hexo路径
    img_path = r"D:\learning\zejun'blog\Hexo\themes\hexo-theme-matery\source\medias\frontcover"
    md_path = r"D:\learning\zejun'blog\Hexo\source\_posts"

    # 将近半月的文章单独写入md文件展示
    # 1. 先收集近半月的文章id
    # - 先获取每个id对应的博主名字
    id2oaname = {}
    for k, v in data_manager.message_info.items():
        for m in v['blogs']:
            id2oaname[m['id']] = k
    # - 获取每个id对应的文章信息
    id2message_info = {}
    now = datetime.datetime.now()
    for k, v in md_dict_by_date.items():
        if now - datetime.datetime.strptime(k, '%Y-%m-%d') > datetime.timedelta(days=15):
            continue
        for m in v:
            id2message_info[m['id']] = m
            id2message_info[m['id']]['oaname'] = id2oaname[m['id']]

    # 2. 下载文章封面图
    all_frontcover_img = os.listdir(img_path)
    for _id in tqdm(id2message_info.keys(), desc='downloading frontcover img', total=len(id2message_info)):
        if _id.replace('/', '_') + '.jpg' in all_frontcover_img:
            continue
        # 下载封面图
        img = requests.get(url=id2message_info[_id]['cover'], headers=headers).content
        single_img_path = os.path.join(img_path, f"{_id.replace('/', '_')}.jpg")
        # 写入到hexo展示目录
        with open(single_img_path, 'wb') as fp:
            fp.write(img)
        # 缩放图片，防止封面太大占用空间
        img = Image.open(single_img_path)
        # 获取图片尺寸
        width, height = img.size
        # 如果高度大于640,进行缩放
        if width > 640:
            # 计算缩放比例
            ratio = 640.0 / width
            new_height = int(height * ratio)
            new_width = 640
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            # 保存缩放后的图片
            img.save(single_img_path)

    # 3. 将近半月的文章写入成单个md文件
    for _id in id2message_info.keys():
        d = id2message_info[_id]
        d['title'] = d['title'].replace('"', "'")
        md = f'''---
layout: post
title: "{d['title']}"
date: {d['create_time']}
top: false
hide: false
img: /medias/frontcover/{_id.replace('/', '_')}.jpg
tags: 
    - {d['oaname']}
---
'''
        md += f'[{d["title"]}]({d["link"]})\n\n'
        md += '> 仅用于站内搜索，没有排版格式，具体信息请跳转上方微信公众号内链接\n\n'
        all_text = data_manager.message_detail_text[_id]
        all_text = [all_text] if isinstance(all_text, str) else all_text
        for i in range(len(all_text)):
            # 替换一些字符，防止 Nunjucks 转义失败
            all_text[i] = nunjucks_escape(all_text[i])
            # 去掉大段代码
            if len(all_text[i]) > 100 and sum(check_text_ratio(all_text[i])) > 0.5:
                all_text[i] = ""

        md += '\n'.join(all_text)

        single_md_path = os.path.join(md_path, f"{_id.replace('/', '_')}.md")
        with open(single_md_path, 'w', encoding='utf-8') as f:
            f.write(md)

    valid_id = [id for id in id2message_info.keys()]
    # 4. 删除多余的md文件
    for filename in os.listdir(md_path):
        if filename in ["微信公众号聚合平台.md", "微信公众号聚合平台_byname.md"]:
            continue
        if filename[:-3] not in valid_id:
            os.remove(os.path.join(md_path, filename))

    # 5. 删除多余的图片
    for filename in os.listdir(img_path):
        if filename[:-4] not in valid_id:
            os.remove(os.path.join(img_path, filename))