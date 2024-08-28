#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author      : Cao Zejun
# @Time        : 2024/8/5 22:06
# @File        : util.py
# @Software    : Pycharm
# @description : 工具函数，存储一些通用的函数

import os
import shutil

from tqdm import tqdm
os.chdir('D:\\learning\\python\\WeChatOA_Aggregation')
import json
import requests
from lxml import etree


headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36',
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
    message_info = handle_json('message_info')
    delete_messages = handle_json('delete_message')
    delete_messages_set = set(delete_messages['is_delete'])

    try:
        for k, v in tqdm(message_info.items(), total=len(message_info)):
            for m in v['blogs']:
                if m['id'] in delete_messages_set:
                    continue
                if message_is_delete(m['link']):
                    delete_messages['is_delete'].append(m['id'])
    except:
        pass

    handle_json('message_info', message_info)

def handle_json(file_name, data=None):
    if not file_name.endswith('.json'):
        file_name = './data/' + file_name + '.json'

    if not data:
        if not os.path.exists(file_name):
            return {}
        with open(file_name, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        # 安全写入，防止在写入过程中中断程序导致数据丢失
        with open('tmp.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        shutil.move('tmp.json', file_name)



if __name__ == '__main__':
    update_message_info()
    # delete_messages = {
    #     'is_delete': []
    # }
    # with open('./data/delete_message.json', 'w', encoding='utf-8') as f:
    #     json.dump(delete_messages, f, indent=4, ensure_ascii=False)