#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author      : Cao Zejun
# @Time        : 2024/8/5 23:20
# @File        : filter_duplication.py
# @Software    : Pycharm
# @description : 去重操作

import json
import requests
from lxml import etree

from util import headers


# 提取文章中的文字
def url2text1(url):
    '''
    提取文本方法1：直接获取对应div下的所有文本，未处理
    :param url:
    :return: 列表形式，每个元素对应 div 下的一个子标签内的文本
    '''
    response = requests.get(url, headers=headers).text
    tree = etree.HTML(response)
    text_list = tree.xpath('//div[@class="rich_media_content js_underline_content\n                       autoTypeSetting24psection\n            "]//text()')
    # 判断是博文删除了还是请求错误
    if not text_list:
        warn = tree.xpath('//div[@class="weui-msg__title warn"]/text()')
        if len(warn) > 0 and warn[0] == '该内容已被发布者删除':
            return '已删除'
        else:
            text_list = url2text1(url)
    return text_list


def calc_duplicate_rate1(text_list1, text_list2):
    '''
    计算重复率方法1：以提取文本方法1中的返回值为参数，比对列表1中的每个元素是否在列表2中，若在计入重复字数，最后统计重复字数比例
    :param text_list1: 相同 title 下最早发布的文章
    :param text_list2: 其余相同 title 的文章
    :return:
    '''
    text_set2 = set(text_list2)
    co_word_count = 0
    for t in text_list1:
        if t in text_set2:
            co_word_count += len(t)
    co_rate = co_word_count / len(''.join(text_list1))
    return co_rate


def get_filtered_message():
    with open('./data/title_head.json', 'r', encoding='utf-8') as f:
        title_head = json.load(f)

    duplicate_message = {}
    for k, v in title_head.items():
        if v['co_count'] == 1:
            continue

        have_duplicate = False
        text_list1 = url2text1(v['this_link']['link'])
        for i in range(len(v['other_link'])):
            text_list2 = url2text1(v['other_link'][i]['link'])
            score = calc_duplicate_rate1(text_list1, text_list2)
            v['other_link'][i]['duplicate_rate'] = score
            if score > 0.5:
                have_duplicate = True
        if have_duplicate:
            duplicate_message[k] = {
                'link': [i for i in v['other_link'] if i['duplicate_rate'] > 0.5]
            }
        v['other_link'] = [i for i in v['other_link'] if i['duplicate_rate'] <= 0.5]
        v['co_count'] = len(v['other_link']) + 1

    with open('./data/title_head.json', 'w', encoding='utf-8') as f:
        json.dump(title_head, f, indent=4, ensure_ascii=False)

    with open('./data/dup_message.json', 'w', encoding='utf-8') as f:
        json.dump(duplicate_message, f, indent=4, ensure_ascii=False)


if __name__ == '__main__':
    # url1 = 'http://mp.weixin.qq.com/s?__biz=MzkxMzUxNzEzMQ==&mid=2247488093&idx=1&sn=4c61d43fd3e6e57f632f1fe2c29ab59e&chksm=c17d2d79f60aa46f13db4861aa9fd16eb9010759e2cd6a5887a574333badba95975f32e19e98#rd'
    # url2 = 'http://mp.weixin.qq.com/s?__biz=MzkzODY1MTQzOQ==&mid=2247485270&idx=3&sn=80f4ac6489b22f697de59f08fc1353a4&chksm=c2fdbd16f58a3400c4ec3269b308f317f53635def558a32bad516a5d6184a4aa641b7cdd516f#rd'
    # text_list1 = url2text1(url1)
    # text_list2 = url2text1(url2)
    # co_rate = calc_duplicate_rate1(text_list1, text_list2)
    # print(co_rate)

    get_filtered_message()