"""
Markdown生成模块

将微信公众号聚合平台数据转换为markdown文件，支持按时间和按公众号分组。
"""

import datetime
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import requests
from tqdm import tqdm

from .data_manager import DataManager
from ..utils.file_utils import nunjucks_escape, check_text_ratio


class MarkdownGenerator:
    """Markdown文件生成器"""
    
    def __init__(self, data_manager: Optional[DataManager] = None):
        """初始化Markdown生成器
        
        Args:
            data_manager: 数据管理器实例，如果为None则使用默认实例
        """
        self.data_manager = data_manager or DataManager()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36',
        }
    
    def get_valid_messages(self) -> Tuple[Dict[str, List], Dict[str, List]]:
        """获取有效的消息数据
        
        Returns:
            (按日期分组的消息字典, 按博主分组的消息字典)
        """
        is_deleted_set = set(self.data_manager.issues_message.get('is_delete', []))
        
        delete_count = 0
        dup_count = 0
        md_dict_by_date = defaultdict(list)  # 按日期分割，key=时间，年月日，value=文章
        md_dict_by_blogger = defaultdict(list)  # 按博主分割，key=博主名，value=文章
        
        for k, v in self.data_manager.message_info.items():
            # 由name2fakeid决定哪些公众号需要展示，如果从name2fakeid中删除了公众号但历史的message_info中存在，则跳过
            if k not in self.data_manager.name2fakeid.keys():
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
                if m['id'] in self.data_manager.issues_message.get('dup_minhash', {}):
                    dup_count += 1
                    continue
                t = datetime.datetime.strptime(m['create_time'], "%Y-%m-%d %H:%M").strftime("%Y-%m-%d")
                md_dict_by_date[t].append(m)
        
        print(f'{delete_count} messages have been deleted')
        print(f'{dup_count} messages have been deduplicated')
        return md_dict_by_date, md_dict_by_blogger
    
    def generate_markdown_files(self, output_dir: Optional[str] = None) -> bool:
        """生成Markdown文件
        
        Args:
            output_dir: 输出目录，如果为None则使用默认目录
            
        Returns:
            是否生成成功
        """
        if output_dir is None:
            output_dir = Path(__file__).parent.parent.parent / 'output' / 'markdown'
        else:
            output_dir = Path(output_dir)
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            md_dict_by_date, md_dict_by_blogger = self.get_valid_messages()
            
            # 1. 生成按日期区分的md文件
            self._generate_date_based_markdown(md_dict_by_date, output_dir)
            
            # 2. 生成按公众号区分的md文件
            self._generate_blogger_based_markdown(md_dict_by_blogger, output_dir)
            
            return True
        except Exception as e:
            print(f"生成Markdown文件失败: {str(e)}")
            return False
    
    def _generate_date_based_markdown(self, md_dict_by_date: Dict[str, List], output_dir: Path):
        """生成按日期区分的Markdown文件"""
        md_content = '''---
layout: post
title: "微信公众号聚合平台_按时间区分"
date: 2024-07-29 01:36
top: true
hide: true
tags: 
    - 开源项目
    - 微信公众号聚合平台
---
'''
        
        # 获取所有时间并逆序排列
        date_list = sorted(md_dict_by_date.keys(), reverse=True)
        now = datetime.datetime.now()
        
        for date in date_list:
            # 为方便查看，只保留近半年的
            if now - datetime.datetime.strptime(date, '%Y-%m-%d') > datetime.timedelta(days=6*30):
                continue
            md_content += f'## {date}\n'
            for m in md_dict_by_date[date]:
                md_content += f'* [{m["title"]}]({m["link"]})\n'
        
        md_path = output_dir / '微信公众号聚合平台_按时间区分.md'
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
    
    def _generate_blogger_based_markdown(self, md_dict_by_blogger: Dict[str, List], output_dir: Path):
        """生成按公众号区分的Markdown文件"""
        md_content = '''---
layout: post
title: "微信公众号聚合平台_按公众号区分"
date: 2024-08-31 02:16
top: true
hide: true
tags: 
    - 开源项目
    - 微信公众号聚合平台
---
'''
        
        # 按时间排序
        md_dict_by_blogger = {k: sorted(v, key=lambda x: x['create_time'], reverse=True) 
                             for k, v in md_dict_by_blogger.items()}
        now = datetime.datetime.now()
        
        for k, v in md_dict_by_blogger.items():
            md_content += f'## {k}\n'
            for m in v:
                # 为方便查看，只保留近半年的
                if now - datetime.datetime.strptime(m['create_time'], '%Y-%m-%d %H:%M') > datetime.timedelta(days=6*30):
                    continue
                md_content += f'* [{m["title"]}]({m["link"]})\n'
        
        md_path = output_dir / '微信公众号聚合平台_按公众号区分.md'
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
    
    def generate_single_markdown_files(self, 
                                     hexo_md_path: str, 
                                     hexo_img_path: str,
                                     days_limit: int = 15) -> bool:
        """生成单个文章的Markdown文件
        
        Args:
            hexo_md_path: Hexo博客Markdown文件路径
            hexo_img_path: Hexo博客图片路径
            days_limit: 生成文章的天数限制
            
        Returns:
            是否生成成功
        """
        try:
            md_dict_by_date, _ = self.get_valid_messages()
            
            # 收集指定天数内的文章
            id2message_info = self._collect_recent_messages(md_dict_by_date, days_limit)
            
            # 下载封面图片
            self._download_cover_images(id2message_info, hexo_img_path)
            
            # 生成单个Markdown文件
            self._generate_individual_markdown_files(id2message_info, hexo_md_path)
            
            # 清理旧文件
            self._cleanup_old_files(id2message_info, hexo_md_path, hexo_img_path)
            
            return True
        except Exception as e:
            print(f"生成单个Markdown文件失败: {str(e)}")
            return False
    
    def _collect_recent_messages(self, md_dict_by_date: Dict[str, List], days_limit: int) -> Dict[str, Dict]:
        """收集最近的消息"""
        # 先获取每个id对应的博主名字
        id2oaname = {}
        for k, v in self.data_manager.message_info.items():
            for m in v['blogs']:
                id2oaname[m['id']] = k
        
        # 获取每个id对应的文章信息
        id2message_info = {}
        now = datetime.datetime.now()
        
        for k, v in md_dict_by_date.items():
            if now - datetime.datetime.strptime(k, '%Y-%m-%d') > datetime.timedelta(days=days_limit):
                continue
            for m in v:
                id2message_info[m['id']] = m
                id2message_info[m['id']]['oaname'] = id2oaname[m['id']]
        
        return id2message_info
    
    def _download_cover_images(self, id2message_info: Dict[str, Dict], img_path: str):
        """下载封面图片"""
        Path(img_path).mkdir(parents=True, exist_ok=True)
        all_frontcover_img = os.listdir(img_path)
        
        for _id in tqdm(id2message_info.keys(), desc='downloading frontcover img', total=len(id2message_info)):
            img_filename = f"{_id.replace('/', '_')}.jpg"
            if img_filename in all_frontcover_img:
                continue
            
            try:
                # 下载封面图
                img = requests.get(url=id2message_info[_id]['cover'], headers=self.headers).content
                single_img_path = os.path.join(img_path, img_filename)
                
                # 写入到hexo展示目录
                with open(single_img_path, 'wb') as fp:
                    fp.write(img)
                
                # 缩放图片，防止封面太大占用空间
                self._resize_image(single_img_path, max_width=640)
                
            except Exception as e:
                print(f"下载封面图片失败 {_id}: {str(e)}")
    
    def _resize_image(self, image_path: str, max_width: int = 640):
        """调整图片尺寸"""
        try:
            from PIL import Image
            
            img = Image.open(image_path)
            width, height = img.size
            
            # 如果宽度大于最大宽度，进行缩放
            if width > max_width:
                ratio = max_width / width
                new_height = int(height * ratio)
                new_width = max_width
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                img.save(image_path)
        except ImportError:
            print("需要安装PIL库: pip install Pillow")
        except Exception as e:
            print(f"调整图片尺寸失败 {image_path}: {str(e)}")
    
    def _generate_individual_markdown_files(self, id2message_info: Dict[str, Dict], md_path: str):
        """生成单个Markdown文件"""
        Path(md_path).mkdir(parents=True, exist_ok=True)
        
        for _id in id2message_info.keys():
            d = id2message_info[_id]
            d['title'] = d['title'].replace('"', "'")
            
            md_content = f'''---
layout: post
title: "{d['title']}"
date: {d['create_time']}
top: false
hide: false
img: /medias/frontcover/{_id.replace('/', '_')}.jpg
tags: 
    - {d['oaname']}
---
'''
            md_content += f'[{d["title"]}]({d["link"]})\n\n'
            md_content += '> 仅用于站内搜索，没有排版格式，具体信息请跳转上方微信公众号内链接\n\n'
            
            # 处理文章内容
            if _id in self.data_manager.message_detail_text:
                all_text = self.data_manager.message_detail_text[_id]
                all_text = [all_text] if isinstance(all_text, str) else all_text
                
                for i in range(len(all_text)):
                    # 替换一些字符，防止 Nunjucks 转义失败
                    all_text[i] = nunjucks_escape(all_text[i])
                    # 去掉大段代码
                    if len(all_text[i]) > 100 and sum(check_text_ratio(all_text[i])) > 0.5:
                        all_text[i] = ""
                
                md_content += '\n'.join(all_text)
            
            single_md_path = os.path.join(md_path, f"{_id.replace('/', '_')}.md")
            with open(single_md_path, 'w', encoding='utf-8') as f:
                f.write(md_content)
    
    def _cleanup_old_files(self, id2message_info: Dict[str, Dict], md_path: str, img_path: str):
        """清理旧文件"""
        valid_id = list(id2message_info.keys())
        
        # 删除多余的md文件
        for filename in os.listdir(md_path):
            if filename in ["微信公众号聚合平台_按时间区分.md", "微信公众号聚合平台_按公众号区分.md"]:
                continue
            if filename.endswith('.md') and filename[:-3] not in valid_id:
                try:
                    os.remove(os.path.join(md_path, filename))
                except Exception as e:
                    print(f"删除旧md文件失败 {filename}: {str(e)}")
        
        # 删除多余的图片
        for filename in os.listdir(img_path):
            if filename.endswith('.jpg') and filename[:-4] not in valid_id:
                try:
                    os.remove(os.path.join(img_path, filename))
                except Exception as e:
                    print(f"删除旧图片文件失败 {filename}: {str(e)}")
    
    def generate_all_markdown(self, 
                            output_dir: Optional[str] = None,
                            hexo_md_path: Optional[str] = None,
                            hexo_img_path: Optional[str] = None) -> bool:
        """生成所有类型的Markdown文件
        
        Args:
            output_dir: 聚合文件输出目录
            hexo_md_path: Hexo博客Markdown文件路径
            hexo_img_path: Hexo博客图片路径
            
        Returns:
            是否生成成功
        """
        success = True
        
        # 生成聚合Markdown文件
        if not self.generate_markdown_files(output_dir):
            success = False
        
        # 生成单个Markdown文件（如果提供了hexo路径）
        if hexo_md_path and hexo_img_path:
            if not self.generate_single_markdown_files(hexo_md_path, hexo_img_path):
                success = False
        
        return success