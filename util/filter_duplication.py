#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author      : Cao Zejun
# @Time        : 2024/8/5 23:20
# @File        : filter_duplication.py
# @Software    : Pycharm
# @description : 去重操作

import requests
from lxml import etree

from util import headers

def url2text(url):
    response = requests.get(url, headers=headers).text
    tree = etree.HTML(response)
    text_list = tree.xpath(
        '//div[@class="rich_media_content js_underline_content\n                       autoTypeSetting24psection\n            "]//text()')
    # 判断是博文删除了还是请求错误
    if not text_list:
        warn = tree.xpath('//div[@class="weui-msg__title warn"]/text()')
        if len(warn) > 0 and warn[0] == '该内容已被发布者删除':
            return '已删除'
        else:
            text_list = url2text(url)
    return text_list

def calc_duplicate_rate(text_list1, text_list2):
    text_set2 = set(text_list2)
    co_word_count = 0
    for t in text_list1:
        if t in text_set2:
            co_word_count += len(t)
    co_rate = co_word_count / len(''.join(text_list1))
    return co_rate
