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
  - 存在问题：存在标题相同内容不同，例如“今日Github最火的10个Python项目”，该公众号每天都用这个标题，但是内容每日更新
  - [ ] 解决方案1：增加白名单，保留该标题所有博文（不需要）
  - [x] 解决方案2：获取文章具体内容，使用`tree.xpath`提取对应`div`下的所有`//text()`，以列表形式返回，计算两个文本列表的重叠个数占比
    - 存在问题：取`//text()`的方式是按照标签分割，一些加粗的文本会单独列出，导致文章结尾多出很多无意义文本，但在列表长度上占比很大
    - [x] 解决方案1：以重叠字数计算占比，而不是重叠列表长度
    - [x] 解决方案2：改进`tree.xpath`取文本策略，获取所有section和p标签，取此标签下的所有文本并还原顺序
'''
import os.path
import re
import pickle
import sys
from collections import defaultdict
import requests
from lxml import etree
from tqdm import tqdm
from upstash_vector import Index

# 调试用，执行当前文件时防止路径导入错误
if sys.argv[0] == __file__:
    from util import headers, message_is_delete, handle_json
else:
    from .util import headers, message_is_delete, handle_json


def url2text(url):
    '''
    提取文本方法1：直接获取对应div下的所有文本，未处理
    :param url:
    :return: 列表形式，每个元素对应 div 下的一个子标签内的文本
    '''
    response = requests.get(url, headers=headers).text
    tree = etree.HTML(response)
    # 不同文章存储字段的class标签名不同
    div = tree.xpath('//div[@class="rich_media_content js_underline_content\n                       autoTypeSetting24psection\n            "]')
    if not div:
        div = tree.xpath('//div[@class="rich_media_content js_underline_content\n                       defaultNoSetting\n            "]')
    # 点进去显示分享一篇文章，然后需要再点阅读原文跳转
    if not div:
        url = tree.xpath('//div[@class="original_panel_tool"]/span/@data-url')
        if url:
            response = requests.get(url[0], headers=headers).text
            tree = etree.HTML(response)
            # 不同文章存储字段的class标签名不同
            div = tree.xpath('//div[@class="rich_media_content js_underline_content\n                       autoTypeSetting24psection\n            "]')
            if not div:
                div = tree.xpath('//div[@class="rich_media_content js_underline_content\n                       defaultNoSetting\n            "]')

    # 判断是博文删除了还是请求错误
    if not div:
        if message_is_delete(response=response):
            return '已删除'
        else:
            # print(url)
            return '请求错误'

    s_p = [p for p in div[0].iter() if p.tag in ['section', 'p']]
    text_list = []
    tag = []
    for s in s_p:
        text = ''.join([i.replace('\xa0', '') for i in s.xpath('.//text()') if i != '\u200d'])
        if not text:
            continue
        if text_list and text in text_list[-1]:
            parent_tag = []
            tmp = s
            while tmp.tag != 'div':
                tmp = tmp.getparent()
                parent_tag.append(tmp)
            if tag[-1] in parent_tag:
                del text_list[-1]
        tag.append(s)
        text_list.append(text)
    return text_list

def calc_duplicate_rate1(text_list1, text_list2):
    '''
    计算重复率方法1：以提取文本方法1中的返回值为参数，比对列表1中的每个元素是否在列表2中，若在计入重复字数，最后统计重复字数比例
    :param text_list1: 相同 title 下最早发布的文章
    :param text_list2: 其余相同 title 的文章
    :return:
    '''
    text_set2 = set(text_list2)
    co_word_count = 0
    for t in text_list1:
        if t in text_set2:
            co_word_count += len(t)
    co_rate = co_word_count / len(''.join(text_list1))
    return co_rate


def get_filtered_message():
    generate_title_head()
    title_head = handle_json('title_head')
    delete_messages = handle_json('delete_message')
    duplicate_message = handle_json('dup_message')

    error_links = []
    for k, v in tqdm(title_head.items(), total=len(title_head)):
        if v['co_count'] == 1:
            continue

        # 从列表中找到一个没被删除的
        for i in range(v['co_count']):
            text_list1 = url2text(v['links'][i]['link'])
            if text_list1 == '已删除':
                delete_messages['is_delete'].append(v['links'][i]['id'])
            else:
                from_id = v['links'][i]['id']
                break

        for j in range(i+1, v['co_count']):
            # 已经计算过这两个之间的重复率
            if v['links'][j]['id'] in duplicate_message.keys() and duplicate_message[v['links'][j]['id']]['from_id'] == from_id:
                continue
            text_list2 = url2text(v['links'][j]['link'])
            if text_list2 == '请求错误':
                error_links.append(v['links'][j]['link'])
                delete_messages['is_delete'].append(v['links'][j]['id'])
                continue
            elif text_list2 == '已删除':
                delete_messages['is_delete'].append(v['links'][j]['id'])
                continue

            score = calc_duplicate_rate1(text_list1, text_list2)
            duplicate_message[v['links'][j]['id']] = {
                'from_id': from_id,
                'duplicate_rate': score
            }

    for e in error_links:
        print(e)
    print(f'共有{len(error_links)}个链接读取失败')
    handle_json('title_head', data=title_head)
    handle_json('dup_message', data=duplicate_message)
    handle_json('delete_message', data=delete_messages)


# 以message_info文件生成title_head文件
def generate_title_head():
    message_info = handle_json('message_info')
    delete_messages = handle_json('delete_message')
    delete_messages_set = set(delete_messages['is_delete'])

    # 以 title 为 key 写入 json 文件，记录有几个重复的title和它们的相关信息
    title_head = defaultdict(dict)
    for k, v in message_info.items():
        for m in v['blogs']:
            if m['id'] in delete_messages_set:
                continue
            title = m['title']
            if title not in title_head.keys():
                title_head[title] = {
                    'co_count': 1,
                    'links': [],
                }
            cur_m = {
                'id': m['id'],
                'link': m['link'],
                'create_time': m['create_time'],
            }
            title_head[title]['links'].append(cur_m)

    for k, v in title_head.items():
        v['links'].sort(key=lambda x: x['create_time'])
        title_head[k]['co_count'] = len(v['links'])
    handle_json('title_head', data=title_head)


class UpstashVector:
    def __init__(self):
        id_info = handle_json('id_info')
        self.delete_messages = handle_json('delete_message')
        self.delete_messages_set = set(self.delete_messages['is_delete'])
        self.index = Index(url=id_info['upstash_url'],
                      token=id_info['upstash_token'])
        self.dup_vector_message = {}
        self.writed_upstash_id = handle_json('writed_upstash_id')

    def upsert(self, text_list, m):
        self.index.upsert(
            vectors=[
                (m['id'], '\n'.join(text_list),
                 {
                     "title": m['title'],
                     "create_time": m['create_time'],
                     "link": m['link'],
                  }
                 ),
            ]
        )

    def query_vector(self, text_list, top_k=1):
        query_result = self.index.query(
            data='\n'.join(text_list),
            top_k=top_k,
            include_vectors=True,
            include_metadata=True,
            include_data=True,
        )
        return query_result

    def write_vector(self):
        dup_num = len(self.dup_vector_message)
        message_info = handle_json('message_info')

        message_total = [m for v in message_info.values() for m in v['blogs']
                         if m['id'] not in self.delete_messages_set
                         and m['create_time'] > "2024-07-01"]
        message_total.sort(key=lambda x: x['create_time'])
        for i, m in tqdm(enumerate(message_total), total=len(message_total)):
            if m['id'] in self.writed_upstash_id['writed_upstash_id']:
                continue
            # fetch_result = self.index.fetch(
            #     ids=m['id'],
            #     include_vectors=True,
            #     include_metadata=True,
            #     include_data=True,
            # )
            # if fetch_result[0]:
            #     continue
            # index.delete("id2")

            text_list = url2text(m['link'])
            self.is_delete(text_list, m['id'])

            query_result = self.query_vector(text_list)
            # 如果库中有相似的文章就不再写入
            if query_result and query_result[0].score > 0.9:
                if query_result[0].score != 1:
                    self.dup_vector_message[m['id']] = {
                            'from_id': query_result[0].id,
                            'duplicate_rate': query_result[0].score
                    }
            else:
                self.upsert(text_list, m)
            self.writed_upstash_id['writed_upstash_id'].append(m['id'])
            if i % 300 == 0:
                handle_json('writed_upstash_id', data=self.writed_upstash_id)
                if dup_num != len(self.dup_vector_message):
                    handle_json('dup_vector_message', data=self.dup_vector_message)
                    dup_num = len(self.dup_vector_message)

    def is_delete(self, text_list, id_):
        if text_list in ['请求错误', '已删除']:
            self.delete_messages['is_delete'].append(id_)
            handle_json('delete_message', data=self.delete_messages)

    # 为了正确调用with
    def __enter__(self):
        return self
    # 在debug停止或发生异常时能及时保存
    def __exit__(self, exc_type, exc_val, exc_tb):
        handle_json('writed_upstash_id', data=self.writed_upstash_id)
        handle_json('dup_vector_message', data=self.dup_vector_message)
        # 返回 True 表示异常已被处理，不会向外传播
        return True

class minHashLSH:
    def __init__(self):
        from datasketch import MinHash, MinHashLSH
        self.lsh = MinHashLSH(threshold=0.9, num_perm=128)

        self.delete_messages = handle_json('delete_message')
        self.delete_messages_set = set(self.delete_messages['is_delete'])

        # 加载minhash签名缓存文件
        self.minhash_dict_path = './data/minhash_dict.pickle'
        if os.path.exists(self.minhash_dict_path):
            with open(self.minhash_dict_path, 'rb') as fp:
                self.minhash_dict = pickle.load(fp)

            for k, v in self.minhash_dict.items():
                self.minhash_dict[k] = MinHash(hashvalues=v)
        else:
            self.minhash_dict = {}

        # 加载minhash重复文件
        self.issues_message = handle_json('issues_message')
        if 'dup_minhash' not in self.issues_message.keys():
            self.issues_message['dup_minhash'] = {}

    def write_vector(self):
        from datasketch import MinHash, MinHashLSH
        message_info = handle_json('message_info')

        message_total = [m for v in message_info.values() for m in v['blogs']
                         if m['id'] not in self.delete_messages_set
                         and m['create_time'] > "2024-07-01"]
        message_total.sort(key=lambda x: x['create_time'])
        for i, m in tqdm(enumerate(message_total), total=len(message_total)):
            if m['id'] not in self.minhash_dict.keys():
                text_list = url2text(m['link'])
                if self.is_delete(text_list, m['id']): continue
                text_list = ' '.join(text_list)
                text_list = self.split_text(text_list)
                min1 = MinHash(num_perm=128)
                for d in text_list:
                    min1.update(d.encode('utf8'))
                self.minhash_dict[m['id']] = min1

            sim_m = self.lsh.query(self.minhash_dict[m['id']])
            if sim_m:
                if m['id'] not in self.issues_message['dup_minhash'].keys():
                    self.issues_message['dup_minhash'][m['id']] = {
                        'from_id': sim_m,
                    }
            else:
                self.lsh.insert(m['id'], self.minhash_dict[m['id']])

    def is_delete(self, text_list, id_):
        if text_list in ['请求错误', '已删除']:
            self.delete_messages['is_delete'].append(id_)
            handle_json('delete_message', data=self.delete_messages)
            return True
        return False

    def split_text(self, text):
        # words = re.findall(r'\w| |[\u4e00-\u9fff]', text)
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
        handle_json('issues_message', data=self.issues_message)
        # 返回 True 表示异常已被处理，不会向外传播
        # return True


if __name__ == '__main__':
    # url1 = 'http://mp.weixin.qq.com/s?__biz=MzkxMzUxNzEzMQ==&mid=2247488093&idx=1&sn=4c61d43fd3e6e57f632f1fe2c29ab59e&chksm=c17d2d79f60aa46f13db4861aa9fd16eb9010759e2cd6a5887a574333badba95975f32e19e98#rd'
    # url2 = 'http://mp.weixin.qq.com/s?__biz=MzkzODY1MTQzOQ==&mid=2247485270&idx=3&sn=80f4ac6489b22f697de59f08fc1353a4&chksm=c2fdbd16f58a3400c4ec3269b308f317f53635def558a32bad516a5d6184a4aa641b7cdd516f#rd'
    # text_list1 = url2text1(url1)
    # text_list2 = url2text1(url2)
    # co_rate = calc_duplicate_rate1(text_list1, text_list2)
    # print(co_rate)
    # url = 'https://mp.weixin.qq.com/s?__biz=MzA3MzI4MjgzMw==&mid=2650930329&idx=1&sn=1418416efe70fd2a965ac259fac81c3d&chksm=84e438e7b393b1f17389649e3aa6287871633b4063b184cdaf32ce70715dc041e1eb0cbab216#rd'
    # text_list1 = url2text(url)
    # url2 = 'https://mp.weixin.qq.com/s?__biz=MzIwOTc2MTUyMg==&mid=2247564131&idx=2&sn=7ac4c81349e53d0709803e1ce24a68a9&chksm=976d5efea01ad7e8c353354ea58ef0ff35b258e5307b78636b4c86251e9619a78469744f92a7#rd'
    # text_list2 = url2text(url2)
    # co_rate = calc_duplicate_rate1(text_list1, text_list2)
    #
    # from nltk.translate.bleu_score import corpus_bleu, sentence_bleu
    # score = sentence_bleu([list(''.join(text_list1))], list(''.join(text_list2)), weights=(0.25, 0.25, 0.25, 0.25))
    # print(score)
    #
    # get_filtered_message()
    # message_info = handle_json('message_info')
    # message_total = [m for v in message_info.values() for m in v['blogs']]

    # upstash_vector = UpstashVector()
    # url = 'https://mp.weixin.qq.com/s?__biz=MzIwOTc2MTUyMg==&mid=2247564131&idx=2&sn=7ac4c81349e53d0709803e1ce24a68a9&chksm=976d5efea01ad7e8c353354ea58ef0ff35b258e5307b78636b4c86251e9619a78469744f92a7#rd'

    # text_list = url2text(url)
    # query_result = upstash_vector.query_vector(text_list, top_k=3)
    # upstash_vector.write_vector()

    # with UpstashVector() as upstash_vector:
    #     upstash_vector.write_vector()
    with minHashLSH() as minhash:
        minhash.write_vector()
