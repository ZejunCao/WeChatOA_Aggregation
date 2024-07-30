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

# token和Cookie定期更换
token = 2125306121
cookie = 'ua_id=KAfRPZPRS2CqGIwQAAAAAOxEmPdP6Vk1H5bwISXzYUk=; wxuin=22183570217006; uuid=be01a727e82e2df87b0ce0b08caa6b25; _clck=betmb9|1|fnu|0; rand_info=CAESINMW9JU5OGYDKeV6vw3RxRp3tlUI9eSnAkPPCE5b0/Er; slave_bizuin=3931536317; data_bizuin=3931536317; bizuin=3931536317; data_ticket=/zKums45viYyDkC9XsGIsO+EC+lt/K+9Sasjo1yepKobaBNt0fu6EX41vtWD87Ct; slave_sid=Z0gycGNBRDk5WVJoMnRrVVFTM0NyT09QT2x6SGVZazk4cFpKcDl2MzhTZmpRekU5eEluWW9aNlF2QlM5eHFiRERTekFBeVVCNFpFdHdyX3k1bDFvalZ2cURfdkgzMjRSZVZXeGFWVjJmRERIUWJBRkNKc045azFIVm1zcndsVzhYcmVkcG1BWTZjaDYybU5x; slave_user=gh_bfe9a82e08da; xid=53179ffd3a528f00cbfbbe93f6abf430; mm_lang=zh_CN; _clsk=5yyxro|1722183661168|2|1|mp.weixin.qq.com/weheat-agent/payload/record'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36',
    'Cookie': cookie
}

# 将js获取的时间id转化成真实事件，截止到分钟
def jstime2realtime(jstime):
    return (datetime.datetime.strptime("1970-01-01 08:00", "%Y-%m-%d %H:%M") + datetime.timedelta(
        minutes=jstime // 60)).strftime("%Y-%m-%d %H:%M")

# 检查session和token是否过期
def session_is_overdue(response):
    if response['base_resp']['err_msg'] == 'invalid session':
        raise Exception('session 过期了')
    if response['base_resp']['err_msg'] == 'invalid csrf token':
        raise Exception('token 过期了')

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
    messages = json.loads(response['publish_page'])['publish_list']
    for message_i in range(len(messages)):
        message = json.loads(messages[message_i]['publish_info'])
        if message['msgid'] in msgid_exist:
            continue
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
    return message_url