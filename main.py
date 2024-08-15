#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author      : Cao Zejun
# @Time        : 2024/7/31 1:11
# @File        : main.py
# @Software    : Pycharm
# @description : 主程序，爬取文章并存储

from tqdm import tqdm
import json
from request_.wechat_request import fakeid2message_update, time_delta, time_now
from util.message2md import message2md


if __name__ == '__main__':
    # 获取必要信息
    # name2fakeid_dict = {}
    # message_info = {}
    with open('./data/name2fakeid.json', 'r', encoding='utf-8') as fp:
        name2fakeid_dict = json.load(fp)
    with open('./data/message_info.json', 'r', encoding='utf-8') as fp:
        message_info = json.load(fp)

    try:
        for n, id in tqdm(name2fakeid_dict.items()):
            # 如果latest_time非空（之前太久不发文章的），或者今天已经爬取过，则跳过
            if message_info[n]['latest_time'] and time_delta(time_now(), message_info[n]['latest_time']).days < 1:
                continue
            message_info[n]['blogs'].extend(fakeid2message_update(id, message_info[n]['blogs']))
            message_info[n]['latest_time'] = time_now()
    except Exception as e:
        # 写入message_info，如果请求中间失败，及时写入
        with open('./data/message_info.json', 'w', encoding='utf-8') as fp:
            json.dump(message_info, fp, ensure_ascii=False, indent=4)
        raise e

    # 写入message_info，如果请求顺利进行，则正常写入
    with open('./data/message_info.json', 'w', encoding='utf-8') as fp:
        json.dump(message_info, fp, ensure_ascii=False, indent=4)

    # 将message_info转换为md上传到个人博客系统
    message2md(message_info)