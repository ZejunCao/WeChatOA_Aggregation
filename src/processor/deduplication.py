#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author      : Cao Zejun
# @Time        : 2024/8/5 23:20
# @File        : filter_duplication.py
# @Software    : Pycharm
# @description : 去重操作
'''
## 实验过程
- 根据标题去重
  - 存在问题：存在标题相同内容不同，例如"今日Github最火的10个Python项目"，该公众号每天都用这个标题，但是内容每日更新
  - [ ] 解决方案1：增加白名单，保留该标题所有博文（不需要）
  - [x] 解决方案2：获取文章具体内容，使用`tree.xpath`提取对应`div`下的所有`//text()`，以列表形式返回，计算两个文本列表的重叠个数占比
    - 存在问题：取`//text()`的方式是按照标签分割，一些加粗的文本会单独列出，导致文章结尾多出很多无意义文本，但在列表长度上占比很大
    - [x] 解决方案1：以重叠字数计算占比，而不是重叠列表长度
    - [x] 解决方案2：改进`tree.xpath`取文本策略，获取所有section和p标签，取此标签下的所有文本并还原顺序

- datasketch官方文档：https://ekzhu.com/datasketch/lsh.html
'''
import pickle
from pathlib import Path

from nltk.translate.bleu_score import corpus_bleu, sentence_bleu
from tqdm import tqdm

from ..utils.helpers import url2text
from ..utils.data_manager import data_manager


def calc_duplicate_rate(text_list1, text_list2) -> float:
    '''
    计算重复率方法1：以提取文本方法1中的返回值为参数，比对列表1中的每个元素是否在列表2中，若在计入重复字数，最后统计重复字数比例
    :param text_list1: 相同 title 下最早发布的文章
    :param text_list2: 其余相同 title 的文章
    :return: 重复字数比例
    '''
    if len(''.join(text_list1)) == 0:
        return 0
    text_set2 = set(text_list2)
    co_word_count = 0
    for t in text_list1:
        if t in text_set2:
            co_word_count += len(t)
    co_rate = co_word_count / len(''.join(text_list1))
    return co_rate


def calc_duplicate_rate_max(text_list1, text_list2) -> float:
    '''重复字数判断，调换顺序计算两次'''
    dup_rate = max([calc_duplicate_rate(text_list1, text_list2), calc_duplicate_rate(text_list2, text_list1)])
    # 再次计算bleu值
    if dup_rate < 0.8:
        bleu_score = sentence_bleu([list(''.join(text_list1))], list(''.join(text_list2)))
        if isinstance(bleu_score, (int, float)):
            dup_rate = max(dup_rate, float(bleu_score))
    return dup_rate


class minHashLSH:
    def __init__(self):
        from datasketch import MinHash, MinHashLSH
        self.lsh = MinHashLSH(threshold=0.8, num_perm=128)

        # 加载minhash重复文件
        self.issues_message = data_manager.issues_message
        self.is_deleted_set = set(data_manager.issues_message['is_delete'])

        # 加载minhash签名缓存文件
        self.minhash_dict_path = Path(__file__).parent.parent / 'data' / 'minhash_dict.pickle'
        # minhash_dict 字典记录所有id的minhash签名，key: id, value: minhash签名
        if self.minhash_dict_path.exists():
            with open(self.minhash_dict_path, 'rb') as fp:
                self.minhash_dict = pickle.load(fp)  # 此时v是minhash签名的hash值(数组)
            for k, v in self.minhash_dict.items():
                self.minhash_dict[k] = MinHash(hashvalues=v)  # 将其转换为MinHash对象
        else:
            self.minhash_dict = {}

    def write_vector(self):
        from datasketch import MinHash
        # 获取 {id: url} 的映射
        id2url = {m['id']: m['link'] for v in data_manager.message_info.values() for m in v['blogs']}

        # 获取所有文章，并过滤掉已删除和创建时间小于2025-06-01的
        message_total = [m for v in data_manager.message_info.values() for m in v['blogs']
                         if m['id'] not in self.is_deleted_set
                         and m['create_time'] > "2025-06-01"]
        # 按照创建时间排序，去重时优先保留发布时间更早的
        message_total.sort(key=lambda x: x['create_time'])

        for i, m in tqdm(enumerate(message_total), total=len(message_total)):
            # 如果文章没有minhash编码，则进行minhash编码
            if m['id'] not in self.minhash_dict.keys():
                # 如果没有爬取过详细文章内容，则在此进行爬取
                if m['id'] not in data_manager.message_detail_text:
                    data_manager.message_detail_text[m['id']] = url2text(m['link'])
                text_list = data_manager.message_detail_text[m['id']]
                # 如果文章已删除，则跳过
                if self.is_delete(text_list, m['id']):
                    continue
                # 对文章进行分词
                text_list = self.split_text(' '.join(text_list))
                min1 = MinHash(num_perm=128)
                for d in text_list:
                    min1.update(d.encode('utf8'))
                self.minhash_dict[m['id']] = min1
            else:
                # 已 minhash 编码的文章也已去过重
                continue

            sim_m = self.lsh.query(self.minhash_dict[m['id']])
            # sim_m 不为空，说明有相似的文章
            if sim_m:
                # 如果文章已去重，则跳过
                if m['id'] in data_manager.issues_message['dup_minhash'].keys():
                    continue
                # 如果有相似的，先判断jaccard相似度，大于0.9直接通过，若在0.8-0.9之间则使用规则再次判断
                sim_m_res = []
                for s in sim_m:
                    if self.minhash_dict[m['id']].jaccard(self.minhash_dict[s]) >= 0.9:  # .jaccard会和MinHashLSH计算的有点差异
                        sim_m_res.append(s)
                    else:
                        dup_rate = calc_duplicate_rate_max(text_list, url2text(id2url[s]))
                        # 规则大于0.7则认为是重复的
                        if dup_rate > 0.7:
                            sim_m_res.append(s)
                if sim_m_res:
                    data_manager.issues_message['dup_minhash'][m['id']] = sim_m
            else:
                self.lsh.insert(m['id'], self.minhash_dict[m['id']])
        data_manager.write('message_detail_text')

    def is_delete(self, text_list, id_):
        if text_list in ['已删除']:
            data_manager.issues_message['is_delete'].append(id_)
            data_manager.write('issues_message')
            return True
        return False

    def split_text(self, text):
        words = list(text)

        # 结果列表
        result = []
        last_word = 0  # 0：中文，1：英文

        for word in words:
            if '\u4e00' <= word <= '\u9fff':  # 如果是中文字符
                result.append(word)
                last_word = 0
            else:  # 如果是英文单词
                if not result:
                    if word != ' ':
                        result.append(word)
                        last_word = 1
                else:
                    if last_word == 1:
                        if word != ' ':
                            result[-1] += word
                            last_word = 1
                        else:
                            last_word = 0
                    else:
                        if word != ' ':
                            result.append(word)
                            last_word = 1

        return result

    # 为了正确调用with
    def __enter__(self):
        return self

    # 在debug停止或发生异常时能及时保存
    def __exit__(self, exc_type, exc_val, exc_tb):
        hashvalues_dict = {}
        for k, v in self.minhash_dict.items():
            hashvalues_dict[k] = v.hashvalues
        with open(self.minhash_dict_path, 'wb') as fp:
            pickle.dump(hashvalues_dict, fp)
        data_manager.write('issues_message')
        # 返回 True 表示异常已被处理，不会向外传播
        # return True