#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author      : Cao Zejun
# @Time        : 2024/8/5 22:06
# @File        : util.py
# @Software    : Pycharm
# @description : 工具函数，存储一些通用的函数

import os
os.chdir('..')
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
def check_message(url):
    r = requests.get(url=url, headers=headers).text
    tree = etree.HTML(r)
    warn = tree.xpath('//div[@class="weui-msg__title warn"]/text()')
    if len(warn) > 0 and warn[0] == '该内容已被发布者删除':
        return False
    return True

# 自检函数，更新message_info.json文件
def update_message_info():
    with open('./data/message_info.json', 'r', encoding='utf-8') as f:
        messages = json.load(f)

    for k, v in messages.items():
        print('当前自检中：', k)
        for m in v['blogs']:
            if not check_message(m['link']):
                m['is_delete'] = True

    for k, v in messages.items():
        v['blogs'] = [i for i in v['blogs'] if not i['is_delete']]

    with open('./data/message_info.json', 'w', encoding='utf-8') as f:
        json.dump(messages, f, indent=4, ensure_ascii=False)

    # 每次自检完默认重新生成title_head文件
    generate_title_head()


# 以message_info文件生成title_head文件
def generate_title_head():
    with open('./data/message_info.json', 'r', encoding='utf-8') as f:
        messages = json.load(f)
    # 以 title 为 key 写入 json 文件，记录有几个重复的title和它们的相关信息
    title_head = defaultdict(dict)
    for k, v in messages.items():
        for m in v['blogs']:
            title = m['title']
            if title not in title_head.keys():
                title_head[title] = {
                    'co_count': 1,
                    'this_link': {},
                    'other_link': [],
                }
            cur_m = {
                'id': str(m['msgid']) + '/' + str(m['aid']),
                'link': m['link'],
                'create_time': m['create_time'],
            }
            title_head[title]['other_link'].append(cur_m)

    for k, v in title_head.items():
        v['other_link'].sort(key=lambda x: x['create_time'])
        title_head[k]['co_count'] = len(v['other_link'])
        title_head[k]['this_link'] = v['other_link'][0]
        title_head[k]['other_link'] = v['other_link'][1:]
    with open('./data/title_head.json', 'w', encoding='utf-8') as f:
        json.dump(title_head, f, indent=4, ensure_ascii=False)


if __name__ == '__main__':
    # update_message_info()
    generate_title_head()