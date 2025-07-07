#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author      : Cao Zejun
# @Time        : 2025/07/08
# @File        : message_converter.py
# @Software    : Pycharm
# @description : 消息数据转换和预处理

import datetime
from collections import defaultdict

from ..utils.data_manager import data_manager


def get_valid_message():
    """获取有效的消息数据，过滤已删除和重复的文章
    
    Returns:
        tuple: (md_dict_by_date, md_dict_by_blogger)
            - md_dict_by_date: 按日期分组的文章字典
            - md_dict_by_blogger: 按博主分组的文章字典
    """
    is_deleted_set = set(data_manager.issues_message['is_delete'])

    delete_count = 0
    dup_count = 0
    md_dict_by_date = defaultdict(list)  # 按日期分割，key=时间，年月日，value=文章
    md_dict_by_blogger = defaultdict(list)  # 按博主分割，key=博主名，value=文章
    
    for k, v in data_manager.message_info.items():
        # 由name2fakeid决定哪些公众号需要展示，如果从name2fakeid中删除了公众号但历史的message_info中存在，则跳过
        if k not in data_manager.name2fakeid.keys():
            continue
        # 遍历所有文章
        for m in v['blogs']:
            # 去除已删除文章
            if m['id'] in is_deleted_set:
                delete_count += 1
                continue
            # 按博主展示，不需要文章去重
            md_dict_by_blogger[k].append(m)
            # 按日期展示，需要去掉重复率高的文章
            if m['id'] in data_manager.issues_message['dup_minhash'].keys():
                dup_count += 1
                continue
            t = datetime.datetime.strptime(m['create_time'],"%Y-%m-%d %H:%M").strftime("%Y-%m-%d")
            md_dict_by_date[t].append(m)

    print(f'{delete_count} messages have been deleted')
    print(f'{dup_count} messages have been deduplicated')
    return md_dict_by_date, md_dict_by_blogger 