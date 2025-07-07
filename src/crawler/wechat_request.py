#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author      : Cao Zejun
# @Time        : 2024/7/31 0:54
# @File        : wechat_request.py
# @Software    : Pycharm
# @description : 微信公众号爬虫工具函数

import json
import re
from dataclasses import asdict

import requests

from src.utils.data_manager import Message_Info, data_manager, headers
from src.utils.helpers import jstime2realtime, time_delta, time_now


class WechatRequest:
    def __init__(self):
        self.headers = headers
        self.headers['Cookie'] = data_manager.id_info['cookie']
        self.token = data_manager.id_info['token']

    # 使用公众号名字获取 id 值
    def name2fakeid(self, name):
        params = {
            'action': 'search_biz',
            'begin': 0,
            'count': 5,
            'query': name,
            'token': self.token,
            'lang': 'zh_CN',
            'f': 'json',
            'ajax': 1,
        }

        nickname = {}
        url = 'https://mp.weixin.qq.com/cgi-bin/searchbiz?'
        response = requests.get(url=url, params=params, headers=self.headers).json()
        if self.session_is_overdue(response):
            params['token'] = self.token
            response = requests.get(url=url, params=params, headers=headers).json()
            self.session_is_overdue(response)
        for l in response['list']:
            nickname[l['nickname']] = l['fakeid']
        if name in nickname.keys():
            return nickname[name]
        else:
            return ''

    # 请求次数限制，不是请求文章条数限制
    def fakeid2message_update(self, fakeid, message_exist=[]):
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
            'token': self.token,
            'lang': 'zh_CN',
            'f': 'json',
            'ajax': 1,
        }
        # 根据文章id判断新爬取的文章是否已存在
        msgid_exist = set()
        for m in message_exist:
            msgid_exist.add(m['id'])
        is_deleted_set = set(data_manager.issues_message['is_delete'])

        crawl_message_info = []
        url = "https://mp.weixin.qq.com/cgi-bin/appmsgpublish?"
        response = requests.get(url=url, params=params, headers=headers).json()
        if self.session_is_overdue(response):
            params['token'] = self.token
            response = requests.get(url=url, params=params, headers=headers).json()
            self.session_is_overdue(response)
        
        # 解析里面的每一个文章，并转换为Message_Info对象
        messages = json.loads(response['publish_page'])['publish_list']
        for message_i in range(len(messages)):
            message = json.loads(messages[message_i]['publish_info'])
            for i in range(len(message['appmsgex'])):
                unique_id = str(message['msgid']) + '-' + str(message['appmsgex'][i]['aid']) + '-' + str(message['appmsgex'][i]['create_time'])
                # 1. 如果当前id已经写入，则跳过
                if unique_id in msgid_exist:
                    continue
                # 2. 爬取时能够直接获取文章是否已被删除，如已删除，则记录id并跳过写入
                if message['appmsgex'][i]['is_deleted'] and unique_id not in is_deleted_set:
                    data_manager.issues_message['is_delete'].append(unique_id)
                    continue
                # 3. 特殊文章类型，跳过
                if message['appmsgex'][i]['item_show_type'] in [5, 8, 10]:
                    continue
                # 4. 重新刷新，只爬取一个月内的文章
                if time_delta(time_now(), jstime2realtime(message['appmsgex'][i]['create_time'])).days > 30:
                    continue
                message_info = Message_Info(
                    id=unique_id,
                    title=message['appmsgex'][i]['title'],
                    digest=message['appmsgex'][i]['digest'],
                    link=message['appmsgex'][i]['link'],
                    cover=message['appmsgex'][i]['cover'],
                    create_time=jstime2realtime(message['appmsgex'][i]['create_time']),
                    is_deleted=message['appmsgex'][i]['is_deleted'],
                    item_show_type=message['appmsgex'][i]['item_show_type'],
                )
                crawl_message_info.append(asdict(message_info))
        crawl_message_info.sort(key=lambda x: x['create_time'])
        return crawl_message_info

    def login(self):
        from DrissionPage import ChromiumPage

        bro = ChromiumPage()
        bro.get('https://mp.weixin.qq.com/')
        bro.set.window.max()
        while 'token' not in bro.url:
            pass

        match = re.search(r'token=(.*)', bro.url)
        if not match:
            raise ValueError("无法在URL中找到token")
        token = match.group(1)
        cookie = bro.cookies()
        cookie_str = ''
        for c in cookie:
            cookie_str += c['name'] + '=' + c['value'] + '; '

        self.token = token
        self.headers['Cookie'] = cookie_str
        data_manager.id_info['token'] = token
        data_manager.id_info['cookie'] = cookie_str
        data_manager.write('id_info')
        bro.close()

    # 检查session和token是否过期
    def session_is_overdue(self, response):
        err_msg = response['base_resp']['err_msg']
        if err_msg in ['invalid session', 'invalid csrf token']:
            self.login()
            return True
        if err_msg == 'freq control':
            raise Exception('The number of requests is too fast, please try again later')
        return False