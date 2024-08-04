#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author      : Cao Zejun
# @Time        : 2024/8/3 0:11
# @File        : message_request.py
# @Software    : Pycharm
# @description : 爬取具体文章，并提取具体信息

import json
import requests
from lxml import etree

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36',
}

def url2text(url):
    response = requests.get(url, headers=headers).text
    tree = etree.HTML(response)
    text_list = tree.xpath('//div[@class="rich_media_content js_underline_content\n                       autoTypeSetting24psection\n            "]//text()')
    return text_list

# 计算两个存储文章句子的列表的重复率
def calc_duplicate_rate(text_list1, text_list2):
    text_set1 = set(text_list1)
    co_count = 0
    for t in text_list2:
        if t in text_set1:
            co_count += 1
    return co_count / len(text_list2)

# 将title_head写入json文件
def write_json(title_head, text_list):
    with open('data.json', 'a', encoding='utf-8') as f:
        json.dump(title_head, f, ensure_ascii=False)