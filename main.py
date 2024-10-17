#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author      : Cao Zejun
# @Time        : 2024/7/31 1:11
# @File        : main.py
# @Software    : Pycharm
# @description : 主程序，爬取文章并存储

from tqdm import tqdm
from request_.wechat_request import WechatRequest, time_delta, time_now
from util.message2md import message2md, message2md_byname
from util.util import handle_json
from util.filter_duplication import minHashLSH


if __name__ == '__main__':
    # 获取必要信息
    name2fakeid_dict = handle_json('name2fakeid')
    message_info = handle_json('message_info')

    wechat_request = WechatRequest()
    try:
        for n, id in tqdm(name2fakeid_dict.items()):
            # 如果是新增加的公众号
            if not id:
                name2fakeid_dict[n] = wechat_request.name2fakeid(n)
                handle_json('name2fakeid', data=name2fakeid_dict)
                message_info[n] = {
                    'latest_time': "2000-01-01 00:00", # 默认一个很久远的时间
                    'blogs': [],
                }
            # 如果latest_time非空（之前太久不发文章的），或者今天已经爬取过，则跳过
            if message_info[n]['latest_time'] and time_delta(time_now(), message_info[n]['latest_time']).days < 1:
                continue
            message_info[n]['blogs'].extend(wechat_request.fakeid2message_update(id, message_info[n]['blogs']))
            message_info[n]['latest_time'] = time_now()
    except Exception as e:
        # 写入message_info，如果请求中间失败，及时写入
        handle_json('message_info', data=message_info)
        raise e

    # 写入message_info，如果请求顺利进行，则正常写入
    handle_json('message_info', data=message_info)

    # 每次更新时验证去重
    with minHashLSH() as minhash:
        minhash.write_vector()

    # 将message_info转换为md上传到个人博客系统
    message2md(message_info)
    message2md_byname(message_info)