"""
去重模块

使用MinHash和LSH算法对文章进行去重处理。
"""

import pickle
from pathlib import Path
from typing import Dict, List, Set, Optional, Any

from tqdm import tqdm

from .data_manager import DataManager
from ..utils.file_utils import url2text


def calc_duplicate_rate(text_list1: List[str], text_list2: List[str]) -> float:
    """计算重复率方法1：以提取文本方法1中的返回值为参数，比对列表1中的每个元素是否在列表2中
    
    Args:
        text_list1: 相同 title 下最早发布的文章
        text_list2: 其余相同 title 的文章
        
    Returns:
        重复字数比例
    """
    if len(''.join(text_list1)) == 0:
        return 0.0
    
    text_set2 = set(text_list2)
    co_word_count = 0
    for t in text_list1:
        if t in text_set2:
            co_word_count += len(t)
    
    co_rate = co_word_count / len(''.join(text_list1))
    return co_rate


def calc_duplicate_rate_max(text_list1: List[str], text_list2: List[str]) -> float:
    """重复字数判断，调换顺序计算两次"""
    dup_rate = max([calc_duplicate_rate(text_list1, text_list2), 
                    calc_duplicate_rate(text_list2, text_list1)])
    
    # 再次计算bleu值
    if dup_rate < 0.8:
        try:
            from nltk.translate.bleu_score import sentence_bleu
            bleu_score = sentence_bleu([list(''.join(text_list1))], list(''.join(text_list2)))
            if isinstance(bleu_score, (int, float)):
                dup_rate = max(dup_rate, float(bleu_score))
        except ImportError:
            print("NLTK库未安装，跳过BLEU评分")
    
    return dup_rate


class MinHashLSH:
    """MinHash LSH去重处理器"""
    
    def __init__(self, 
                 threshold: float = 0.8, 
                 num_perm: int = 128,
                 data_manager: Optional[DataManager] = None):
        """初始化MinHash LSH去重处理器
        
        Args:
            threshold: 相似度阈值
            num_perm: 哈希函数数量
            data_manager: 数据管理器实例
        """
        try:
            from datasketch import MinHash, MinHashLSH as LSH
            self.MinHash = MinHash
            self.LSH = LSH
        except ImportError:
            raise ImportError("需要安装datasketch库: pip install datasketch")
        
        self.lsh = self.LSH(threshold=threshold, num_perm=num_perm)
        self.threshold = threshold
        self.num_perm = num_perm
        
        # 数据管理器
        self.data_manager = data_manager or DataManager()
        
        # 加载问题消息
        self.issues_message = self.data_manager.issues_message
        self.is_deleted_set = set(self.data_manager.issues_message.get('is_delete', []))
        
        # 加载minhash签名缓存文件
        self.minhash_dict_path = self.data_manager.data_dir / 'cache' / 'minhash_dict.pickle'
        self.minhash_dict_path.parent.mkdir(parents=True, exist_ok=True)
        
        # minhash_dict 字典记录所有id的minhash签名，key: id, value: minhash签名
        if self.minhash_dict_path.exists():
            with open(self.minhash_dict_path, 'rb') as fp:
                self.minhash_dict = pickle.load(fp)  # 此时v是minhash签名的hash值(数组)
            # 将其转换为MinHash对象
            for k, v in self.minhash_dict.items():
                self.minhash_dict[k] = self.MinHash(hashvalues=v)
        else:
            self.minhash_dict = {}
    
    def write_vector(self, min_date: str = "2025-06-01"):
        """写入向量并进行去重检测
        
        Args:
            min_date: 最小日期，只处理此日期之后的文章
        """
        # 获取 {id: url} 的映射
        id2url = {m['id']: m['link'] for v in self.data_manager.message_info.values() 
                  for m in v['blogs']}
        
        # 获取所有文章，并过滤掉已删除和创建时间小于指定日期的
        message_total = [m for v in self.data_manager.message_info.values() 
                        for m in v['blogs']
                        if m['id'] not in self.is_deleted_set
                        and m['create_time'] > min_date]
        
        # 按照创建时间排序，去重时优先保留发布时间更早的
        message_total.sort(key=lambda x: x['create_time'])
        
        for i, m in tqdm(enumerate(message_total), total=len(message_total), desc="处理去重"):
            # 如果文章没有minhash编码，则进行minhash编码
            if m['id'] not in self.minhash_dict:
                # 如果没有爬取过详细文章内容，则在此进行爬取
                if m['id'] not in self.data_manager.message_detail_text:
                    self.data_manager.message_detail_text[m['id']] = url2text(m['link'])
                
                text_list = self.data_manager.message_detail_text[m['id']]
                
                # 如果文章已删除，则跳过
                if self.is_delete(text_list, m['id']):
                    continue
                
                # 对文章进行分词
                text_list = self.split_text(' '.join(text_list))
                min1 = self.MinHash(num_perm=self.num_perm)
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
                if m['id'] in self.data_manager.issues_message.get('dup_minhash', {}):
                    continue
                
                # 如果有相似的，先判断jaccard相似度，大于0.9直接通过，若在0.8-0.9之间则使用规则再次判断
                sim_m_res = []
                for s in sim_m:
                    jaccard_sim = self.minhash_dict[m['id']].jaccard(self.minhash_dict[s])
                    if jaccard_sim >= 0.9:  # .jaccard会和MinHashLSH计算的有点差异
                        sim_m_res.append(s)
                    else:
                        # 获取对比文章的文本
                        if s in id2url:
                            compare_text = url2text(id2url[s])
                            current_text = self.data_manager.message_detail_text.get(m['id'], [])
                            if isinstance(current_text, str):
                                current_text = [current_text]
                            
                            dup_rate = calc_duplicate_rate_max(current_text, compare_text)
                            # 规则大于0.7则认为是重复的
                            if dup_rate > 0.7:
                                sim_m_res.append(s)
                
                if sim_m_res:
                    if 'dup_minhash' not in self.data_manager.issues_message:
                        self.data_manager.issues_message['dup_minhash'] = {}
                    self.data_manager.issues_message['dup_minhash'][m['id']] = sim_m_res
            else:
                self.lsh.insert(m['id'], self.minhash_dict[m['id']])
        
        # 保存详细文本数据
        self.data_manager.write('message_detail_text')
    
    def is_delete(self, text_list: List[str], id_: str) -> bool:
        """检查文章是否已删除
        
        Args:
            text_list: 文章文本列表
            id_: 文章ID
            
        Returns:
            是否已删除
        """
        if text_list in [['已删除'], '已删除']:
            if 'is_delete' not in self.data_manager.issues_message:
                self.data_manager.issues_message['is_delete'] = []
            self.data_manager.issues_message['is_delete'].append(id_)
            self.data_manager.write('issues_message')
            return True
        return False
    
    def split_text(self, text: str) -> List[str]:
        """分词处理
        
        Args:
            text: 输入文本
            
        Returns:
            分词后的列表
        """
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
    
    def get_duplicate_stats(self) -> Dict[str, int]:
        """获取去重统计信息
        
        Returns:
            去重统计字典
        """
        stats = {
            'total_articles': 0,
            'deleted_articles': len(self.is_deleted_set),
            'duplicated_articles': len(self.data_manager.issues_message.get('dup_minhash', {})),
            'unique_articles': 0
        }
        
        # 计算总文章数
        for v in self.data_manager.message_info.values():
            stats['total_articles'] += len(v['blogs'])
        
        # 计算唯一文章数
        stats['unique_articles'] = (stats['total_articles'] - 
                                  stats['deleted_articles'] - 
                                  stats['duplicated_articles'])
        
        return stats
    
    def clear_cache(self):
        """清空缓存"""
        self.minhash_dict = {}
        if self.minhash_dict_path.exists():
            self.minhash_dict_path.unlink()
    
    def save_cache(self):
        """保存缓存"""
        hashvalues_dict = {}
        for k, v in self.minhash_dict.items():
            hashvalues_dict[k] = v.hashvalues
        
        with open(self.minhash_dict_path, 'wb') as fp:
            pickle.dump(hashvalues_dict, fp)
    
    # 为了正确调用with
    def __enter__(self):
        return self
    
    # 在debug停止或发生异常时能及时保存
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.save_cache()
        self.data_manager.write('issues_message')
        # 返回 True 表示异常已被处理，不会向外传播
        # return True