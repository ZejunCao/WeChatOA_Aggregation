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
from util.util import handle_json, headers

# 将js获取的时间id转化成真实时间，截止到分钟
def jstime2realtime(jstime):
    return (datetime.datetime.strptime("1970-01-01 08:00", "%Y-%m-%d %H:%M") + datetime.timedelta(
        minutes=jstime // 60)).strftime("%Y-%m-%d %H:%M")

# 计算时间差
def time_delta(time1, time2):
    return datetime.datetime.strptime(time1,"%Y-%m-%d %H:%M") - datetime.datetime.strptime(time2,"%Y-%m-%d %H:%M")
# 获取当前时间
def time_now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

class WechatRequest:
    def __init__(self):
        id_info = handle_json('id_info')
        self.headers = headers
        self.headers['Cookie'] = id_info['cookie']
        self.token = id_info['token']

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
            msgid_exist.add(int(m['id'].split('/')[0]))

        message_url = []
        url = "https://mp.weixin.qq.com/cgi-bin/appmsgpublish?"
        response = requests.get(url=url, params=params, headers=headers).json()
        if self.session_is_overdue(response):
            params['token'] = self.token
            response = requests.get(url=url, params=params, headers=headers).json()
            self.session_is_overdue(response)
        # if 'publish_page' not in response.keys():
        #     raise Exception('The number of requests is too fast, please try again later')
        messages = json.loads(response['publish_page'])['publish_list']
        for message_i in range(len(messages)):
            message = json.loads(messages[message_i]['publish_info'])
            if message['msgid'] in msgid_exist:
                continue
            for i in range(len(message['appmsgex'])):
                link = message['appmsgex'][i]['link']
                if not message['appmsgex'][i]['create_time']:
                    continue
                real_time = jstime2realtime(message['appmsgex'][i]['create_time'])
                message_url.append({
                    'title': message['appmsgex'][i]['title'],
                    'create_time': real_time,
                    'link': link,
                    'id': str(message['msgid']) + '/' + str(message['appmsgex'][i]['aid']),
                })
        message_url.sort(key=lambda x: x['create_time'])
        return message_url

    def login(self):
        import re
        from DrissionPage import ChromiumPage

        bro = ChromiumPage()
        bro.get('https://mp.weixin.qq.com/')
        bro.set.window.max()
        while 'token' not in bro.url:
            pass

        token = re.search(r'token=(.*)', bro.url).group(1)
        cookie = bro.cookies()
        cookie_str = ''
        for c in cookie:
            cookie_str += c['name'] + '=' + c['value'] + '; '

        self.token = token
        self.headers['Cookie'] = cookie_str
        id_info = {
            'token': token,
            'cookie': cookie_str,
        }
        handle_json('id_info', data=id_info)
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

    def sort_messages(self):
        message_info = handle_json('message_info')

        for k, v in message_info.items():
            v['blogs'].sort(key=lambda x: x['create_time'])

        handle_json('message_info', data=message_info)


if __name__ == '__main__':

    # with open('./data/message_info.json', 'r', encoding='utf-8') as fp:
    #     message_info = json.load(fp)
    #
    # fakeid2message_update('MzAxMjc3MjkyMg==', message_info['老刘说NLP']['blogs'])

    wechat_request = WechatRequest()
    # wechat_request.sort_messages()

    # 测试登录
    wechat_request.login()