#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author      : Cao Zejun
# @Time        : 2024/7/31 0:54
# @File        : wechat_request.py
# @Software    : Pycharm
# @description : 微信公众号爬虫工具函数

import requests
import json
from lxml import etree
import time
import datetime
from util.util import token, headers, message_is_delete

# 将js获取的时间id转化成真实事件，截止到分钟
def jstime2realtime(jstime):
    return (datetime.datetime.strptime("1970-01-01 08:00", "%Y-%m-%d %H:%M") + datetime.timedelta(
        minutes=jstime // 60)).strftime("%Y-%m-%d %H:%M")

# 检查session和token是否过期
def session_is_overdue(response):
    if response['base_resp']['err_msg'] == 'invalid session':
        raise Exception('session expired')
    if response['base_resp']['err_msg'] == 'invalid csrf token':
        raise Exception('token expired')

# 计算时间差
def time_delta(time1, time2):
    return datetime.datetime.strptime(time1,"%Y-%m-%d %H:%M") - datetime.datetime.strptime(time2,"%Y-%m-%d %H:%M")
# 获取当前时间
def time_now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

# 使用公众号名字获取 id 值
def name2fakeid(name):
    params = {
        'action': 'search_biz',
        'begin': 0,
        'count': 5,
        'query': name,
        'token': token,
        'lang': 'zh_CN',
        'f': 'json',
        'ajax': 1,
    }

    nickname = {}
    url = 'https://mp.weixin.qq.com/cgi-bin/searchbiz?'
    # 避免请求频率过高
    while True:
        response = requests.get(url=url, params=params, headers=headers).json()
        if response['base_resp']['err_msg'] == 'ok':
            break
        else:
            time.sleep(0.1)
    for l in response['list']:
        nickname[l['nickname']] = l['fakeid']
    if name in nickname.keys():
        return nickname[name]
    else:
        return None

# 根据公众号 id 值获取所有文章
def fakeid2message(fakeid):
    params = {
        'sub': 'list',
        'search_field': 'null',
        'begin': 0,
        'count': 20,
        'query': '',
        'fakeid': fakeid,
        'type': '101_1',
        'free_publish_type': 1,
        'sub_action': 'list_ex',
        'token': token,
        'lang': 'zh_CN',
        'f': 'json',
        'ajax': 1,
    }

    message_url = []
    url = "https://mp.weixin.qq.com/cgi-bin/appmsgpublish?"
    response = requests.get(url=url, params=params, headers=headers).json()
    session_is_overdue(response)
    messages = json.loads(response['publish_page'])['publish_list']
    for message_i in range(len(messages)):
        message = json.loads(messages[message_i]['publish_info'])
        for i in range(len(message['appmsgex'])):
            link = message['appmsgex'][i]['link']
            # 检查博文是否已被博主删除
            r = requests.get(url=link, headers=headers).text
            tree = etree.HTML(r)
            warn = tree.xpath('//div[@class="weui-msg__title warn"]/text()')
            if len(warn) > 0 and warn[0] == '该内容已被发布者删除':
                continue
            real_time = jstime2realtime(message['appmsgex'][i]['create_time'])
            message_url.append({
                'title': message['appmsgex'][i]['title'],
                'create_time': real_time,
                'link': link,
                'msgid': message['msgid'],
                'appmsgid': message['appmsgex'][i]['appmsgid'],
                'aid': message['appmsgex'][i]['aid'],
            })
    # 返回存储该公众号的所有文章链接列表
    return message_url


# 请求次数限制，不是请求文章条数限制
def fakeid2message_update(fakeid, message_exist=[]):
    params = {
        'sub': 'list',
        'search_field': 'null',
        'begin': 0,
        'count': 20,
        'query': '',
        'fakeid': fakeid,
        'type': '101_1',
        'free_publish_type': 1,
        'sub_action': 'list_ex',
        'token': token,
        'lang': 'zh_CN',
        'f': 'json',
        'ajax': 1,
    }
    # 根据文章id判断新爬取的文章是否已存在
    msgid_exist = set()
    for m in message_exist:
        msgid_exist.add(m['msgid'])

    message_url = []
    url = "https://mp.weixin.qq.com/cgi-bin/appmsgpublish?"
    response = requests.get(url=url, params=params, headers=headers).json()
    session_is_overdue(response)
    if 'publish_page' not in response.keys():
        raise Exception('请求次数过快，请稍后重试')
    messages = json.loads(response['publish_page'])['publish_list']
    for message_i in range(len(messages)):
        message = json.loads(messages[message_i]['publish_info'])
        if message['msgid'] in msgid_exist:
            continue
        for i in range(len(message['appmsgex'])):
            link = message['appmsgex'][i]['link']
            # 检查博文是否正常运行(未被作者删除)
            if message_is_delete(link):
                continue
            # r = requests.get(url=link, headers=headers).text
            # tree = etree.HTML(r)
            # warn = tree.xpath('//div[@class="weui-msg__title warn"]/text()')
            # if len(warn) > 0 and warn[0] == '该内容已被发布者删除':
            #     continue

            real_time = jstime2realtime(message['appmsgex'][i]['create_time'])
            message_url.append({
                'title': message['appmsgex'][i]['title'],
                'create_time': real_time,
                'link': link,
                'msgid': message['msgid'],
                'appmsgid': message['appmsgex'][i]['appmsgid'],
                'aid': message['appmsgex'][i]['aid'],
            })
    return message_url