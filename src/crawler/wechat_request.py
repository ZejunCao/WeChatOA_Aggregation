#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author      : Cao Zejun
# @Time        : 2024/7/31 0:54
# @File        : wechat_request.py
# @Software    : Pycharm
# @description : 微信公众号爬虫核心类

import json
import re
from dataclasses import asdict

import requests

from src.utils.data_manager import Message_Info, data_manager, headers
from src.utils.helpers import jstime2realtime, time_delta, time_now


class WechatRequest:
    """
    微信公众平台的请求封装类。

    负责：
    1. 用公众号名称查询 fakeid（name2fakeid）
    2. 用 fakeid 获取近一月的文章列表（fakeid2message_update）
    3. 在 token/cookie 过期时自动触发扫码登录（session_is_overdue → login）

    初始化时从 data_manager（即 data/id_info.json）读取 token 和 cookie，
    因此每次使用前应确保 id_info.json 是最新的。
    """

    def __init__(self):
        # 复用全局 headers，再注入当前的 Cookie
        self.headers = headers
        self.headers['Cookie'] = data_manager.id_info['cookie']
        self.token = data_manager.id_info['token']

    def name2fakeid(self, name):
        """
        根据公众号名称搜索并返回其 fakeid。

        微信搜索接口会返回多个模糊匹配结果，这里只返回名称精确匹配的那个。
        如果没有精确匹配，返回空字符串。

        注意：如果 session 过期，会自动触发 login() 重新获取凭证后重试。
        """
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

        # 如果检测到 session 过期，login() 会更新 self.token，然后用新 token 重试
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

    def fakeid2message_update(self, fakeid, message_exist=[]):
        """
        获取指定公众号近一月内的新文章。

        去重逻辑：
          - 通过 unique_id（msgid + aid + create_time 的组合）判断文章是否已存在
          - 已存在的文章直接跳过，不重复写入

        过滤逻辑（以下情况跳过）：
          0. article_id 在 deleted_article_ids 中（用户在前端已删除，永久跳过）
          1. article_id 已在 message_exist 中（已爬取过）
          2. 文章已被微信删除（is_deleted=True），记录到 issues_message 并跳过
          3. 特殊文章类型：item_show_type 为 5、8、10（非普通图文）
          4. 发布时间超过 30 天

        返回按发布时间排序的新文章列表（dataclass → dict 格式）。
        """
        params = {
            'sub': 'list',
            'search_field': 'null',
            'begin': 0,
            'count': 20,       # 每次最多取 20 篇
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

        # 将已有文章的 id 存入 set，方便 O(1) 查重
        msgid_exist = set()
        for m in message_exist:
            msgid_exist.add(m['id'])

        # 用户在前端主动删除的文章 id，爬取时永久跳过（见 data/deleted_article_ids.json）
        _raw_del = data_manager.deleted_article_ids
        skipped_by_user = set(_raw_del.get('ids', [])) if isinstance(_raw_del, dict) else set()

        # 已知被删除的文章 id 集合（避免重复记录）
        is_deleted_set = set(data_manager.issues_message['is_delete'])

        crawl_message_info = []
        url = "https://mp.weixin.qq.com/cgi-bin/appmsgpublish?"
        response = requests.get(url=url, params=params, headers=headers).json()

        # session 过期时自动登录后重试
        if self.session_is_overdue(response):
            params['token'] = self.token
            response = requests.get(url=url, params=params, headers=headers).json()
            self.session_is_overdue(response)

        # 解析返回的 publish_page 字段（JSON 字符串中嵌套 JSON 字符串）
        messages = json.loads(response['publish_page'])['publish_list']
        for message_i in range(len(messages)):
            message = json.loads(messages[message_i]['publish_info'])
            for i in range(len(message['appmsgex'])):
                # unique_id 格式："{msgid}-{aid}-{create_time}"，唯一标识一篇文章
                unique_id = (
                    str(message['msgid']) + '-'
                    + str(message['appmsgex'][i]['aid']) + '-'
                    + str(message['appmsgex'][i]['create_time'])
                )

                # 用户主动删除过的文章，不再入库
                if unique_id in skipped_by_user:
                    continue

                # 1. 已爬取过，跳过
                if unique_id in msgid_exist:
                    continue

                # 2. 文章已被删除，记录并跳过
                if message['appmsgex'][i]['is_deleted'] and unique_id not in is_deleted_set:
                    data_manager.issues_message['is_delete'].append(unique_id)
                    continue

                # 3. 非普通图文类型，跳过（5=视频, 8=?, 10=?）
                if message['appmsgex'][i]['item_show_type'] in [5, 8, 10]:
                    continue

                # 4. 超过 30 天的文章跳过（只保留近一月）
                if time_delta(time_now(), jstime2realtime(message['appmsgex'][i]['create_time'])).days > 30:
                    continue

                # 构造文章信息对象
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

        # 按发布时间升序排列，保持时间顺序
        crawl_message_info.sort(key=lambda x: x['create_time'])
        return crawl_message_info

    def login(self):
        """
        打开浏览器，跳转到微信公众平台登录页，等待用户扫码登录。

        登录成功后：
        - 从 URL 中解析 token
        - 从浏览器 cookies 中提取 cookie 字符串
        - 将新的 token/cookie 写回 data/id_info.json 持久化

        注意事项：
        - 此方法会阻塞，直到用户完成扫码或手动关闭浏览器
        - 在 api.py 的后台爬取流程中不会调用此方法（避免在服务进程中打开浏览器）
        - api.py 的 _run_login() 直接用 DrissionPage 实现了类似逻辑，并支持截图
        """
        from DrissionPage import ChromiumPage, ChromiumOptions

        # auto_port()：自动分配调试端口启动新 Chrome，不连接已有实例
        co = ChromiumOptions().auto_port()
        bro = ChromiumPage(co)
        bro.get('https://mp.weixin.qq.com/')
        bro.set.window.max()  # 最大化窗口，方便用户操作

        # 轮询等待 URL 中出现 token（说明用户已完成扫码登录）
        while 'token' not in bro.url:
            pass

        # 从 URL 参数中提取 token（形如 ?token=123456789）
        match = re.search(r'token=(.*)', bro.url)
        if not match:
            raise ValueError("无法在URL中找到token")
        token = match.group(1)

        # 将浏览器 cookies 拼接为字符串格式（"name=value; name2=value2; ..."）
        cookie = bro.cookies()
        cookie_str = ''
        for c in cookie:
            cookie_str += c['name'] + '=' + c['value'] + '; '

        # 更新内存和磁盘中的凭证
        self.token = token
        self.headers['Cookie'] = cookie_str
        data_manager.id_info['token'] = token
        data_manager.id_info['cookie'] = cookie_str
        data_manager.write('id_info')

        bro.close()

    def session_is_overdue(self, response):
        """
        检查微信 API 响应是否表明 session/token 已过期。

        返回 True：凭证已过期（并已自动触发 login() 重新登录）
        返回 False：凭证正常

        触发条件：
        - "invalid session"    → Cookie 中的 session 失效
        - "invalid csrf token" → token 参数失效

        特殊情况：
        - "freq control"：请求频率过快，抛出异常提示等待
        """
        err_msg = response['base_resp']['err_msg']
        if err_msg in ['invalid session', 'invalid csrf token']:
            # 凭证失效，自动登录后调用方应用新的 token 重试
            self.login()
            return True
        if err_msg == 'freq control':
            raise Exception('The number of requests is too fast, please try again later')
        return False
