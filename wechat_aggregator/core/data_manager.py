"""
数据管理模块

管理JSON文件的读写、数据缓存等功能。
"""

import json
import os
import shutil
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional


@dataclass
class Message_Info:
    """微信公众号文章信息数据类"""
    id: str  # 唯一id，形式为 msgid-aid-create_time
    title: str  # 标题
    digest: str  # 文章摘要
    link: str  # 文章链接
    cover: str  # 封面图片链接
    create_time: str  # 创建时间
    is_deleted: bool  # 是否删除
    item_show_type: int  # 文章类型，目前已知5(视频)、8(左右结构)、10是特殊结构，0为正常，11暂时未知


class DataManager:
    """数据管理器，使用单例模式处理JSON文件的读写"""
    
    _instance = None
    _lock = threading.Lock()
    
    # 预定义文件名
    FILES = [
        'name2fakeid',  # 需要爬取的公众号名字，以及对应的id
        'message_info',  # 公众号的博文元信息，包括url、id、创建时间、标题等
        'message_detail_text',  # 公众号的博文详情信息，key=id，value=博文详情
        'id_info',  # 微信公众号的cookie和token
        'issues_message',  # 存在问题的文章，包括重复文章、文章已删除等
    ]
    
    def __new__(cls, data_dir: Optional[str] = None):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_manager(data_dir)
            return cls._instance
    
    def _init_manager(self, data_dir: Optional[str] = None):
        """初始化管理器，创建数据目录并加载文件"""
        if data_dir is None:
            # 默认数据目录为项目根目录下的data目录
            self.data_dir = Path(__file__).parent.parent.parent / 'data'
        else:
            self.data_dir = Path(data_dir)
            
        # 确保数据目录存在
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化文件数据和锁
        self._data = {}
        self._file_locks = {}
        
        # 加载或初始化预定义文件
        for file_name in self.FILES:
            self._load_file(file_name)
    
    def _load_file(self, file_name: str):
        """加载或初始化单个文件"""
        file_path = self.data_dir / f"{file_name}.json"
        lock = threading.Lock()
        self._file_locks[file_name] = lock
        
        with lock:
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        self._data[file_name] = json.load(f)
                except (json.JSONDecodeError, IOError):
                    # 文件损坏时弹出异常提示
                    raise Exception(f"File '{file_name}' is corrupted")
            else:
                # 文件不存在时初始化为空字典
                self._data[file_name] = {}
                # 个性化，如果是issues_message，则增加一些字段
                if file_name == 'issues_message':
                    self._data[file_name] = {
                        'is_delete': [],
                        'dup_minhash': {},
                    }
    
    def __getattr__(self, name: str) -> Any:
        """通过属性名直接访问文件数据"""
        if name in self._data:
            return self._data[name]
        raise AttributeError(f"'{self.__class__.__name__}' has no attribute '{name}'")
    
    def write(self, file_name: str) -> bool:
        """安全写入指定文件"""
        if file_name not in self._data:
            raise ValueError(f"File '{file_name}' not managed by this instance")
        
        lock = self._file_locks[file_name]
        file_path = self.data_dir / f"{file_name}.json"
        temp_path = self.data_dir / f".{file_name}.tmp"
        
        with lock:
            try:
                # 先写入临时文件
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(
                        self._data[file_name], 
                        f, 
                        ensure_ascii=False, 
                        indent=4
                    )
                
                # 原子替换操作
                shutil.move(temp_path, file_path)
                return True
            except Exception as e:
                # 清理临时文件
                if temp_path.exists():
                    try:
                        os.remove(temp_path)
                    except:
                        pass
                print(f"Error writing {file_name}: {str(e)}")
                return False
    
    def write_all(self) -> Dict[str, bool]:
        """写入所有文件"""
        results = {}
        for file_name in self._data:
            results[file_name] = self.write(file_name)
        return results
    
    def reload(self, file_name: str) -> bool:
        """重新加载文件（丢弃内存中的修改）"""
        if file_name in self._data:
            self._load_file(file_name)
            return True
        return False
    
    def reload_all(self) -> bool:
        """重新加载所有文件"""
        for file_name in self._data:
            self.reload(file_name)
        return True
    
    def get_data_path(self, file_name: str) -> Path:
        """获取数据文件路径"""
        return self.data_dir / f"{file_name}.json"
    
    def set_data_dir(self, data_dir: str):
        """设置数据目录"""
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        # 重新加载所有文件
        for file_name in self.FILES:
            self._load_file(file_name)


# 默认数据管理器实例
default_data_manager = DataManager()