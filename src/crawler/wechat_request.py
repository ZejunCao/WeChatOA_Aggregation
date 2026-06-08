#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author      : Cao Zejun
# @Time        : 2024/7/31 0:54
# @File        : wechat_request.py
# @Software    : Pycharm
# @description : 微信公众号爬虫核心类

import json
import re
import time
from dataclasses import asdict
from typing import Any

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
        # 独立副本，避免污染全局 headers；每次请求前 sync_credentials 对齐磁盘凭证
        self.headers = dict(headers)
        self.sync_credentials()

    def sync_credentials(self) -> None:
        """从 data_manager 同步 token / cookie（爬取循环中 id_info 可能被更新）。"""
        self.token = str(data_manager.id_info.get('token') or '')
        cookie = str(data_manager.id_info.get('cookie') or '').strip()
        if cookie:
            self.headers['Cookie'] = cookie
        elif 'Cookie' in self.headers:
            del self.headers['Cookie']

    def _mp_get_json(self, url: str, params: dict, *, retries: int = 4) -> dict[str, Any]:
        """
        请求微信公众平台 JSON 接口，带重试。
        空响应 / 非 JSON 多见于 freq control 或瞬时网络问题。
        """
        last_err = '微信接口无响应'
        params = dict(params)
        params['token'] = self.token

        for attempt in range(retries):
            self.sync_credentials()
            resp = requests.get(
                url=url,
                params=params,
                headers=self.headers,
                timeout=30,
            )
            text = (resp.text or '').strip()
            if not text:
                last_err = f'微信返回空内容（HTTP {resp.status_code}），可能被限流'
                time.sleep(1.5 * (attempt + 1))
                continue
            try:
                data = resp.json()
            except json.JSONDecodeError:
                preview = text[:120].replace('\n', ' ')
                last_err = f'微信返回非 JSON（HTTP {resp.status_code}）: {preview}'
                time.sleep(2.0 * (attempt + 1))
                continue

            if not isinstance(data, dict):
                last_err = f'微信返回异常结构: {type(data).__name__}'
                continue

            if self.session_is_overdue(data):
                params['token'] = self.token
                continue

            base = data.get('base_resp') or {}
            err_msg = str(base.get('err_msg') or '')
            ret = base.get('ret', 0)
            if err_msg == 'freq control' or ret in (200013, 200014):
                last_err = '请求过快，请稍后重试（freq control）'
                time.sleep(2.5 * (attempt + 1))
                continue
            if ret not in (0, None) and err_msg and err_msg not in ('ok', 'success'):
                last_err = f'微信接口错误: {err_msg} (ret={ret})'
                if ret in (-1, 200003):
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise RuntimeError(last_err)
            return data

        raise RuntimeError(last_err)

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
        response = self._mp_get_json(url, params)
        biz_list = response.get('list') or []
        for l in biz_list:
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

        # 用户在前端主动删除的文章 id，爬取时永久跳过
        from src.db.repository import ArticleRepository

        with ArticleRepository() as repo:
            rows = repo.conn.execute(
                "SELECT article_id FROM deleted_articles"
            ).fetchall()
            skipped_by_user = {r["article_id"] for r in rows}

        # 已知被删除的文章 id 集合（避免重复记录）
        is_deleted_set = set(data_manager.issues_message['is_delete'])

        crawl_message_info = []
        url = "https://mp.weixin.qq.com/cgi-bin/appmsgpublish?"
        response = self._mp_get_json(url, params)

        publish_page = response.get('publish_page')
        if not publish_page:
            base = response.get('base_resp') or {}
            raise RuntimeError(
                f"无 publish_page: {base.get('err_msg') or base} (ret={base.get('ret')})"
            )

        # 解析返回的 publish_page 字段（JSON 字符串中嵌套 JSON 字符串）
        try:
            messages = json.loads(publish_page)['publish_list']
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            raise RuntimeError(f"publish_page 解析失败: {e}") from e
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

    def fetch_appmsg_preview_list(
        self,
        fakeid: str,
        *,
        count: int = 20,
        begin: int = 0,
    ) -> list[dict[str, Any]]:
        """预览用：从微信拉取公众号文章列表（只读，不做入库去重/时间过滤）。"""
        count = max(1, min(int(count), 40))
        begin = max(0, int(begin))
        params = {
            'sub': 'list',
            'search_field': 'null',
            'begin': begin,
            'count': count,
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
        url = "https://mp.weixin.qq.com/cgi-bin/appmsgpublish?"
        response = self._mp_get_json(url, params)
        publish_page = response.get('publish_page')
        if not publish_page:
            base = response.get('base_resp') or {}
            raise RuntimeError(
                f"无 publish_page: {base.get('err_msg') or base} (ret={base.get('ret')})"
            )

        try:
            messages = json.loads(publish_page)['publish_list']
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            raise RuntimeError(f"publish_page 解析失败: {e}") from e

        articles: list[dict[str, Any]] = []
        for message_i in range(len(messages)):
            message = json.loads(messages[message_i]['publish_info'])
            for i in range(len(message['appmsgex'])):
                item = message['appmsgex'][i]
                unique_id = (
                    str(message['msgid']) + '-'
                    + str(item['aid']) + '-'
                    + str(item['create_time'])
                )
                articles.append(
                    {
                        'id': unique_id,
                        'title': item.get('title') or '',
                        'digest': item.get('digest') or '',
                        'link': item.get('link') or '',
                        'cover': item.get('cover') or '',
                        'create_time': jstime2realtime(item['create_time']),
                        'is_deleted': bool(item.get('is_deleted')),
                        'item_show_type': int(item.get('item_show_type') or 0),
                    }
                )

        articles.sort(key=lambda x: x['create_time'], reverse=True)
        return articles

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
        - api.py 扫码登录使用 HTTP 接口（见 src.auth.mp_scan_login）
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
        base = response.get('base_resp') if isinstance(response, dict) else None
        if not isinstance(base, dict):
            return False
        err_msg = base.get('err_msg') or ''
        if err_msg in ['invalid session', 'invalid csrf token']:
            # 凭证失效，自动登录后调用方应用新的 token 重试
            self.login()
            return True
        if err_msg == 'freq control':
            raise Exception('The number of requests is too fast, please try again later')
        return False
