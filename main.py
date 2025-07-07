#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author      : Cao Zejun
# @Time        : 2024/7/31 1:11
# @File        : main.py
# @Software    : Pycharm
# @description : 主程序，爬取文章并存储

import time

from tqdm import tqdm

from src.crawler.wechat_request import WechatRequest
from src.utils.data_manager import data_manager
from src.processor.deduplication import minHashLSH
from src.processor.message2md import message2md, single_message2md
from src.utils.helpers import time_delta, time_now

if __name__ == '__main__':
    # 获取必要信息
    wechat_request = WechatRequest()

    # 爬取公众号文章
    finished_name = set()
    while len(finished_name) != len(data_manager.name2fakeid):
        try:
            for oa_name, fakeid in tqdm(data_manager.name2fakeid.items(), total=len(data_manager.name2fakeid)):
                # 如果已经爬取过，则跳过
                if oa_name in finished_name:
                    continue
                # 如果是新增加的公众号
                if not fakeid:
                    data_manager.name2fakeid[oa_name] = wechat_request.name2fakeid(oa_name)
                    data_manager.write('name2fakeid')
                # 如果message_info中没有该公众号，则初始化
                if oa_name not in data_manager.message_info.keys():
                    data_manager.message_info[oa_name] = {
                        'latest_update_time': "2000-01-01 00:00", # 默认一个很久远的时间
                        'blogs': [],
                    }
                # 如果latest_update_time非空（之前太久不发文章的），或者今天已经爬取过，则跳过
                if data_manager.message_info[oa_name]['latest_update_time'] and time_delta(time_now(), data_manager.message_info[oa_name]['latest_update_time']).days < 1:
                    finished_name.add(oa_name)
                    continue
                data_manager.message_info[oa_name]['blogs'].extend(wechat_request.fakeid2message_update(fakeid, data_manager.message_info[oa_name]['blogs']))
                data_manager.message_info[oa_name]['latest_update_time'] = time_now()
                finished_name.add(oa_name)
        except Exception as e:
            # 写入message_info，如果请求中间失败，及时写入
            data_manager.write('message_info')
            print(e)
            time.sleep(30)  # 若请求失败（通常为请求频率限制），则等待30秒后重试
            continue

    # 写入message_info，如果请求顺利进行，则正常写入
    data_manager.write('message_info')

    # 每次更新时验证去重
    with minHashLSH() as minhash:
        minhash.write_vector()

    # 将message_info转换为md上传到个人博客系统
    message2md()
    single_message2md()