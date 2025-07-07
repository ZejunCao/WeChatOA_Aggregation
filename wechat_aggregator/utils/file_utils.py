"""
文件工具模块

提供文件操作、网络请求、文本处理等工具函数。
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from lxml import etree


def ensure_dir(path: str) -> Path:
    """确保目录存在，如果不存在则创建
    
    Args:
        path: 目录路径
        
    Returns:
        Path对象
    """
    path_obj = Path(path)
    path_obj.mkdir(parents=True, exist_ok=True)
    return path_obj


def read_json(file_path: str) -> Dict[str, Any]:
    """读取JSON文件
    
    Args:
        file_path: 文件路径
        
    Returns:
        JSON数据字典
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def write_json(file_path: str, data: Dict[str, Any], indent: int = 4) -> bool:
    """写入JSON文件
    
    Args:
        file_path: 文件路径
        data: 要写入的数据
        indent: 缩进层次，默认4
        
    Returns:
        是否写入成功
    """
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
        return True
    except Exception as e:
        print(f"Error writing JSON file {file_path}: {str(e)}")
        return False


def url2text(url: str, num: int = 0) -> List[str]:
    """从微信公众号文章URL提取文本内容
    
    Args:
        url: 文章URL
        num: 重试次数，默认0
        
    Returns:
        文章文本内容列表，每个元素对应一个段落
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36',
    }
    
    try:
        response = requests.get(url, headers=headers).text
        tree = etree.HTML(response, parser=etree.HTMLParser(encoding='utf-8'))
        
        # 不同文章存储字段的class标签名不同
        div = tree.xpath('//div[@class="rich_media_content js_underline_content\n                       autoTypeSetting24psection\n            "]')
        if not div:
            div = tree.xpath('//div[@class="rich_media_content js_underline_content\n                       defaultNoSetting\n            "]')
        
        # 点进去显示分享一篇文章，然后需要再点阅读原文跳转
        if not div:
            data_url = tree.xpath('//div[@class="original_panel_tool"]/span/@data-url')
            if data_url:
                response = requests.get(data_url[0], headers=headers).text
                tree = etree.HTML(response, parser=etree.HTMLParser(encoding='utf-8'))
                # 不同文章存储字段的class标签名不同
                div = tree.xpath('//div[@class="rich_media_content js_underline_content\n                       autoTypeSetting24psection\n            "]')
                if not div:
                    div = tree.xpath('//div[@class="rich_media_content js_underline_content\n                       defaultNoSetting\n            "]')

        # 判断是博文删除了还是请求错误
        if not div:
            if message_is_delete(response=response):
                return ['已删除']
            else:
                # '请求错误'则再次重新请求，最多3次
                if num >= 3:
                    return ['请求错误']
                return url2text(url, num=num+1)

        s_p = [p for p in div[0].iter() if p.tag in ['section', 'p']]
        text_list = []
        tag = []
        filter_char = ['\xa0', '\u200d', '&nbsp;', '■', ' ']
        pattern = '|'.join(filter_char)
        
        for s in s_p:
            text = ''.join([re.sub(pattern, '', i) for i in s.xpath('.//text()') if i != '\u200d'])
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
    except Exception as e:
        print(f"Error extracting text from URL {url}: {str(e)}")
        return ['请求错误']


def message_is_delete(url: str = '', response: Optional[str] = None) -> bool:
    """检查文章是否被删除
    
    Args:
        url: 文章URL
        response: 响应内容，如果提供则不再请求
        
    Returns:
        True如果文章被删除，False否则
    """
    if not response:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36',
        }
        try:
            response = requests.get(url=url, headers=headers).text
        except Exception:
            return False
    
    tree = etree.HTML(response, parser=etree.HTMLParser(encoding='utf-8'))
    warn = tree.xpath('//div[@class="weui-msg__title warn"]/text()')
    if len(warn) > 0 and warn[0] == '该内容已被发布者删除':
        return True
    return False


def check_text_ratio(text: str) -> Tuple[float, float]:
    """检测文本中英文和符号的占比
    
    Args:
        text: 输入文本字符串
        
    Returns:
        (英文字符占比, 符号占比) 元组
    """
    # 统计字符数
    total_chars = len(text)
    if total_chars == 0:
        return 0.0, 0.0

    # 统计英文字符
    english_chars = sum(1 for c in text if c.isascii() and c.isalpha())

    # 统计符号 (不包括空格)
    symbols = sum(1 for c in text if not c.isalnum() and not c.isspace())

    # 计算占比
    english_ratio = english_chars / total_chars
    symbol_ratio = symbols / total_chars

    return english_ratio, symbol_ratio


def nunjucks_escape(text: str) -> str:
    """替换 Nunjucks 转义字符
    
    Args:
        text: 输入文本
        
    Returns:
        转义后的文本
    """
    text = text.replace('{{', '{ {')
    text = text.replace('}}', '} }')  # 补充右大括号
    text = text.replace('{%', '{ %')  # 补充 Nunjucks 标签
    text = text.replace('%}', '% }')  # 补充 Nunjucks 标签
    text = text.replace('{#', '{ #')
    text = text.replace('#}', '# }')  # 补充注释标签
    text = text.replace('https:', 'https :')
    text = text.replace('http:', 'http :')
    
    # 新增：处理可能引起解析错误的特殊字符组合
    text = text.replace('{-', '{ -')
    text = text.replace('-}', '- }')
    text = text.replace('{{-', '{ { -')
    text = text.replace('-}}', '- } }')
    text = text.replace('{%-', '{ % -')
    text = text.replace('-%}', '- % }')
    
    # 处理可能的变量访问语法
    text = re.sub(r'(\w+)\.(\w+)', r'\1\. \2', text)  # 处理点号访问
    text = re.sub(r'(\w+)\[(\w+)\]', r'\1\[ \2\]', text)  # 处理方括号访问
    
    # 处理管道符（Nunjucks 过滤器语法）
    text = text.replace('|', '\\|')
    
    # 处理反引号和特殊引号
    text = text.replace('`', '\\`')
    text = text.replace('"', '\\"')
    text = text.replace('"', '\\"')
    
    # 处理可能的数学表达式或特殊符号
    text = text.replace('&lt;', '< ')
    text = text.replace('&gt;', '> ')
    text = text.replace('&amp;', '& ')
    text = text.replace('&quot;', '\\" ')
    
    # 处理HTML实体编码中的特殊字符
    text = re.sub(r'&#x([0-9A-Fa-f]+);', r'&# x\1;', text)
    text = re.sub(r'&#(\d+);', r'&# \1;', text)
    
    # 处理可能被误认为是 Nunjucks 语法的其他字符组合
    text = text.replace('\\n\\n\\n', '\\n \\n \\n')  # 根据你的错误可能相关
    
    for ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
        text = text.replace(ext, '')
    
    # 去掉html标签，防止转义失败
    text = re.sub(r'<[^>]*>', '', text)
    
    return text


def clean_filename(filename: str) -> str:
    """清理文件名，移除不合法字符
    
    Args:
        filename: 原始文件名
        
    Returns:
        清理后的文件名
    """
    # 移除或替换不合法字符
    illegal_chars = r'[<>:"/\\|?*]'
    cleaned = re.sub(illegal_chars, '_', filename)
    
    # 移除多余的空格和点
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    cleaned = cleaned.strip('.')
    
    return cleaned


def get_file_size(file_path: str) -> int:
    """获取文件大小
    
    Args:
        file_path: 文件路径
        
    Returns:
        文件大小（字节）
    """
    try:
        return Path(file_path).stat().st_size
    except Exception:
        return 0


def copy_file(src: str, dst: str) -> bool:
    """复制文件
    
    Args:
        src: 源文件路径
        dst: 目标文件路径
        
    Returns:
        是否复制成功
    """
    try:
        import shutil
        shutil.copy2(src, dst)
        return True
    except Exception as e:
        print(f"Error copying file from {src} to {dst}: {str(e)}")
        return False