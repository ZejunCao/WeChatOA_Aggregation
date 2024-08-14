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
from tqdm import tqdm

from .util import headers, message_is_delete


def url2text(url):
    '''
    提取文本方法1：直接获取对应div下的所有文本，未处理
    :param url:
    :return: 列表形式，每个元素对应 div 下的一个子标签内的文本
    '''
    response = requests.get(url, headers=headers).text
    tree = etree.HTML(response)
    # 不同文章存储字段的class标签名不同
    div = tree.xpath('//div[@class="rich_media_content js_underline_content\n                       autoTypeSetting24psection\n            "]')
    if not div:
        div = tree.xpath('//div[@class="rich_media_content js_underline_content\n                       defaultNoSetting\n            "]')
    # 点进去显示分享一篇文章，然后需要再点阅读原文跳转
    if not div:
        url = tree.xpath('//div[@class="original_panel_tool"]/span/@data-url')
        if url:
            response = requests.get(url[0], headers=headers).text
            tree = etree.HTML(response)
            # 不同文章存储字段的class标签名不同
            div = tree.xpath('//div[@class="rich_media_content js_underline_content\n                       autoTypeSetting24psection\n            "]')
            if not div:
                div = tree.xpath('//div[@class="rich_media_content js_underline_content\n                       defaultNoSetting\n            "]')

    # 判断是博文删除了还是请求错误
    if not div:
        if message_is_delete(response=response):
            return '已删除'
        else:
            # print(url)
            return '请求错误'

    s_p = [p for p in div[0].iter() if p.tag in ['section', 'p']]
    text_list = []
    tag = []
    for s in s_p:
        text = ''.join([i.replace('\xa0', '') for i in s.xpath('.//text()') if i != '\u200d'])
        if not text:
            continue
        if text_list and text in text_list[-1]:
            parent_tag = []
            tmp = s
            while tmp.tag != 'div':
                tmp = tmp.getparent()
                parent_tag.append(tmp)
            if tag[-1] in parent_tag:
                del text_list[-1]
        tag.append(s)
        text_list.append(text)
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
    with open('./data/delete_message.json', 'r', encoding='utf-8') as f:
        delete_messages = json.load(f)
    with open('./data/dup_message.json', 'r', encoding='utf-8') as f:
        duplicate_message = json.load(f)

    error_links = []
    for k, v in tqdm(title_head.items(), total=len(title_head)):
        if v['co_count'] == 1:
            continue

        # 从列表中找到一个没被删除的
        for i in range(v['co_count']):
            text_list1 = url2text(v['links'][i]['link'])
            if text_list1 == '已删除':
                delete_messages['is_delete'].append(v['links'][i]['link'])
            else:
                from_id = v['links'][i]['id']
                break

        for j in range(i, v['co_count']):
            # 已经计算过这两个之间的重复率
            if v['links'][j]['id'] in duplicate_message.keys() and duplicate_message[v['links'][j]['id']]['from_id'] == from_id:
                continue
            text_list2 = url2text(v['links'][j]['link'])
            if text_list2 == '请求错误':
                error_links.append(v['links'][j]['link'])
                continue
            elif text_list2 == '已删除':
                delete_messages['is_delete'].append(v['links'][j]['link'])
                continue

            score = calc_duplicate_rate1(text_list1, text_list2)
            duplicate_message[v['links'][j]['id']] = {
                'from_id': from_id,
                'duplicate_rate': score
            }

    for e in error_links:
        print(e)
    print(f'共有{len(error_links)}个链接读取失败')
    with open('./data/title_head.json', 'w', encoding='utf-8') as f:
        json.dump(title_head, f, indent=4, ensure_ascii=False)

    with open('./data/dup_message.json', 'w', encoding='utf-8') as f:
        json.dump(duplicate_message, f, indent=4, ensure_ascii=False)

    with open('./data/delete_message.json', 'w', encoding='utf-8') as f:
        json.dump(delete_messages, f, indent=4, ensure_ascii=False)

if __name__ == '__main__':
    # url1 = 'http://mp.weixin.qq.com/s?__biz=MzkxMzUxNzEzMQ==&mid=2247488093&idx=1&sn=4c61d43fd3e6e57f632f1fe2c29ab59e&chksm=c17d2d79f60aa46f13db4861aa9fd16eb9010759e2cd6a5887a574333badba95975f32e19e98#rd'
    # url2 = 'http://mp.weixin.qq.com/s?__biz=MzkzODY1MTQzOQ==&mid=2247485270&idx=3&sn=80f4ac6489b22f697de59f08fc1353a4&chksm=c2fdbd16f58a3400c4ec3269b308f317f53635def558a32bad516a5d6184a4aa641b7cdd516f#rd'
    # text_list1 = url2text1(url1)
    # text_list2 = url2text1(url2)
    # co_rate = calc_duplicate_rate1(text_list1, text_list2)
    # print(co_rate)


    get_filtered_message()