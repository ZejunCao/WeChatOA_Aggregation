"""
微信公众号请求处理模块

处理微信公众号的登录、文章爬取等功能。
"""

import json
import re
from dataclasses import asdict
from typing import Dict, List, Optional

import requests

from .data_manager import Message_Info, DataManager
from ..utils.time_utils import jstime2realtime, time_delta, time_now


class WechatRequest:
    """微信公众号请求处理器"""
    
    def __init__(self, data_manager: Optional[DataManager] = None):
        """初始化微信请求处理器
        
        Args:
            data_manager: 数据管理器实例，如果为None则使用默认实例
        """
        self.data_manager = data_manager or DataManager()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36',
        }
        self.headers['Cookie'] = self.data_manager.id_info.get('cookie', '')
        self.token = self.data_manager.id_info.get('token', '')

    def name2fakeid(self, name: str) -> str:
        """使用公众号名字获取fakeid
        
        Args:
            name: 公众号名称
            
        Returns:
            公众号的fakeid，如果未找到返回空字符串
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
        
        if self.session_is_overdue(response):
            params['token'] = self.token
            response = requests.get(url=url, params=params, headers=self.headers).json()
            self.session_is_overdue(response)
            
        for item in response['list']:
            nickname[item['nickname']] = item['fakeid']
            
        return nickname.get(name, '')

    def fakeid2message_update(self, fakeid: str, message_exist: List[Dict] = None) -> List[Dict]:
        """根据fakeid获取公众号文章更新
        
        Args:
            fakeid: 公众号的fakeid
            message_exist: 已存在的文章列表，用于去重
            
        Returns:
            新爬取的文章信息列表
        """
        if message_exist is None:
            message_exist = []
            
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
        is_deleted_set = set(self.data_manager.issues_message.get('is_delete', []))

        crawl_message_info = []
        url = "https://mp.weixin.qq.com/cgi-bin/appmsgpublish?"
        response = requests.get(url=url, params=params, headers=self.headers).json()
        
        if self.session_is_overdue(response):
            params['token'] = self.token
            response = requests.get(url=url, params=params, headers=self.headers).json()
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
                    if 'is_delete' not in self.data_manager.issues_message:
                        self.data_manager.issues_message['is_delete'] = []
                    self.data_manager.issues_message['is_delete'].append(unique_id)
                    continue
                    
                # 3. 特殊文章类型，跳过
                if message['appmsgex'][i]['item_show_type'] in [5, 8, 10]:
                    continue
                    
                if message['appmsgex'][i]['item_show_type'] != 0:
                    print(message['appmsgex'][i]['item_show_type'], message['appmsgex'][i]['link'])
                    
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
        """自动登录微信公众平台"""
        try:
            from DrissionPage import ChromiumPage
        except ImportError:
            raise ImportError("需要安装DrissionPage库: pip install DrissionPage")

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
        self.data_manager.id_info['token'] = token
        self.data_manager.id_info['cookie'] = cookie_str
        self.data_manager.write('id_info')
        bro.close()

    def session_is_overdue(self, response: Dict) -> bool:
        """检查session和token是否过期
        
        Args:
            response: 请求响应的JSON数据
            
        Returns:
            是否过期并已重新登录
        """
        err_msg = response['base_resp']['err_msg']
        if err_msg in ['invalid session', 'invalid csrf token']:
            self.login()
            return True
        if err_msg == 'freq control':
            raise Exception('The number of requests is too fast, please try again later')
        return False