#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author      : Cao Zejun
# @Time        : 2024/8/5 22:06
# @File        : util.py
# @Software    : Pycharm
# @description : 工具函数，存储一些通用的函数

import os

from tqdm import tqdm

os.chdir('D:\\learning\\python\\WeChatOA_Aggregation')
import json
from collections import defaultdict

import requests
from lxml import etree


# token和Cookie定期更换
with open('./data/id_info.json', 'r', encoding='utf-8') as f:
    id_info = json.load(f)
token = id_info['token']
cookie = id_info['cookie']
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36',
    'Cookie': cookie
}


# 检查文章是否正常运行(未被作者删除)
def message_is_delete(url='', response=None):
    if not response:
        response = requests.get(url=url, headers=headers).text
    tree = etree.HTML(response)
    warn = tree.xpath('//div[@class="weui-msg__title warn"]/text()')
    if len(warn) > 0 and warn[0] == '该内容已被发布者删除':
        return True
    return False

# 自检函数，更新message_info.json文件
def update_message_info():
    with open('./data/message_info.json', 'r', encoding='utf-8') as f:
        messages = json.load(f)
    with open('./data/delete_message.json', 'r', encoding='utf-8') as f:
        delete_messages = json.load(f)
    delete_messages_set = set(delete_messages['is_delete'])

    try:
        for k, v in tqdm(messages.items(), total=len(messages)):
            for m in v['blogs']:
                if m['id'] in delete_messages_set:
                    continue
                if message_is_delete(m['link']):
                    delete_messages['is_delete'].append(m['id'])
    except:
        pass

    # 已被博主删除的文章，在message_info中添加is_delete字段，不进行删除
    # for k, v in messages.items():
    #     v['blogs'] = [i for i in v['blogs'] if not i['is_delete']]

    with open('./data/delete_message.json', 'w', encoding='utf-8') as f:
        json.dump(delete_messages, f, indent=4, ensure_ascii=False)


# 以message_info文件生成title_head文件
def generate_title_head():
    with open('./data/message_info.json', 'r', encoding='utf-8') as f:
        messages = json.load(f)
    with open('./data/delete_message.json', 'r', encoding='utf-8') as f:
        delete_messages = json.load(f)
    delete_messages_set = set(delete_messages['is_delete'])

    # 以 title 为 key 写入 json 文件，记录有几个重复的title和它们的相关信息
    title_head = defaultdict(dict)
    for k, v in messages.items():
        for m in v['blogs']:
            if m['id'] in delete_messages_set:
                continue
            title = m['title']
            if title not in title_head.keys():
                title_head[title] = {
                    'co_count': 1,
                    'links': [],
                }
            cur_m = {
                'id': m['id'],
                'link': m['link'],
                'create_time': m['create_time'],
            }
            title_head[title]['links'].append(cur_m)

    for k, v in title_head.items():
        v['links'].sort(key=lambda x: x['create_time'])
        title_head[k]['co_count'] = len(v['links'])
    with open('./data/title_head.json', 'w', encoding='utf-8') as f:
        json.dump(title_head, f, indent=4, ensure_ascii=False)

def sort_messages():
    with open('./data/message_info.json', 'r', encoding='utf-8') as fp:
        message_info = json.load(fp)

    for k, v in message_info.items():
        v['blogs'].sort(key=lambda x: x['create_time'])

    with open('./data/message_info.json', 'w', encoding='utf-8') as fp:
        json.dump(message_info, fp, ensure_ascii=False, indent=4)


if __name__ == '__main__':
    # update_message_info()
    generate_title_head()
    # delete_messages = {
    #     'is_delete': []
    # }
    # with open('./data/delete_message.json', 'w', encoding='utf-8') as f:
    #     json.dump(delete_messages, f, indent=4, ensure_ascii=False)