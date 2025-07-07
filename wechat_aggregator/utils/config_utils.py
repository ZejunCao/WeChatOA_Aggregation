"""
配置工具模块

提供配置文件的读取、解析和管理功能。
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


def load_config(config_path: str, config_type: str = 'auto') -> Dict[str, Any]:
    """加载配置文件
    
    Args:
        config_path: 配置文件路径
        config_type: 配置文件类型，支持 'json', 'yaml', 'auto'
        
    Returns:
        配置字典
    """
    path = Path(config_path)
    
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    
    # 自动检测文件类型
    if config_type == 'auto':
        if path.suffix.lower() in ['.yaml', '.yml']:
            config_type = 'yaml'
        elif path.suffix.lower() == '.json':
            config_type = 'json'
        else:
            raise ValueError(f"无法自动检测配置文件类型: {config_path}")
    
    # 加载配置文件
    if config_type == 'json':
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    elif config_type == 'yaml':
        if not HAS_YAML:
            raise ImportError("需要安装pyyaml库: pip install pyyaml")
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    else:
        raise ValueError(f"不支持的配置文件类型: {config_type}")


def save_config(config: Dict[str, Any], config_path: str, config_type: str = 'auto') -> bool:
    """保存配置文件
    
    Args:
        config: 配置字典
        config_path: 配置文件路径
        config_type: 配置文件类型，支持 'json', 'yaml', 'auto'
        
    Returns:
        是否保存成功
    """
    path = Path(config_path)
    
    # 自动检测文件类型
    if config_type == 'auto':
        if path.suffix.lower() in ['.yaml', '.yml']:
            config_type = 'yaml'
        elif path.suffix.lower() == '.json':
            config_type = 'json'
        else:
            raise ValueError(f"无法自动检测配置文件类型: {config_path}")
    
    # 确保目录存在
    path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        # 保存配置文件
        if config_type == 'json':
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
        elif config_type == 'yaml':
            if not HAS_YAML:
                raise ImportError("需要安装pyyaml库: pip install pyyaml")
            with open(path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        else:
            raise ValueError(f"不支持的配置文件类型: {config_type}")
        
        return True
    except Exception as e:
        print(f"保存配置文件失败 {config_path}: {str(e)}")
        return False


def get_config_value(config: Dict[str, Any], key_path: str, default: Any = None) -> Any:
    """获取嵌套配置值
    
    Args:
        config: 配置字典
        key_path: 键路径，用点分隔，如 'database.host'
        default: 默认值
        
    Returns:
        配置值
    """
    keys = key_path.split('.')
    value = config
    
    try:
        for key in keys:
            value = value[key]
        return value
    except (KeyError, TypeError):
        return default


def set_config_value(config: Dict[str, Any], key_path: str, value: Any) -> Dict[str, Any]:
    """设置嵌套配置值
    
    Args:
        config: 配置字典
        key_path: 键路径，用点分隔，如 'database.host'
        value: 配置值
        
    Returns:
        更新后的配置字典
    """
    keys = key_path.split('.')
    current = config
    
    # 创建嵌套字典
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]
    
    # 设置最终值
    current[keys[-1]] = value
    
    return config


def merge_configs(base_config: Dict[str, Any], override_config: Dict[str, Any]) -> Dict[str, Any]:
    """合并配置字典
    
    Args:
        base_config: 基础配置
        override_config: 覆盖配置
        
    Returns:
        合并后的配置字典
    """
    merged = base_config.copy()
    
    for key, value in override_config.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = merge_configs(merged[key], value)
        else:
            merged[key] = value
    
    return merged


def get_env_config(prefix: str = 'WECHAT_AGGREGATOR') -> Dict[str, Any]:
    """从环境变量中获取配置
    
    Args:
        prefix: 环境变量前缀
        
    Returns:
        环境变量配置字典
    """
    config = {}
    prefix_len = len(prefix) + 1  # +1 for the underscore
    
    for key, value in os.environ.items():
        if key.startswith(prefix + '_'):
            config_key = key[prefix_len:].lower()
            config[config_key] = value
    
    return config


def validate_config(config: Dict[str, Any], required_keys: list) -> bool:
    """验证配置完整性
    
    Args:
        config: 配置字典
        required_keys: 必需的键列表
        
    Returns:
        是否通过验证
    """
    for key in required_keys:
        if get_config_value(config, key) is None:
            print(f"缺少必需的配置项: {key}")
            return False
    
    return True


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_path: Optional[str] = None):
        """初始化配置管理器
        
        Args:
            config_path: 配置文件路径，如果为None则使用默认路径
        """
        self.config_path = config_path
        self.config = {}
        
        if config_path:
            self.load()
    
    def load(self, config_path: Optional[str] = None) -> bool:
        """加载配置文件
        
        Args:
            config_path: 配置文件路径，如果为None则使用初始化时的路径
            
        Returns:
            是否加载成功
        """
        path = config_path or self.config_path
        if not path:
            return False
        
        try:
            self.config = load_config(path)
            return True
        except Exception as e:
            print(f"加载配置文件失败: {str(e)}")
            return False
    
    def save(self, config_path: Optional[str] = None) -> bool:
        """保存配置文件
        
        Args:
            config_path: 配置文件路径，如果为None则使用初始化时的路径
            
        Returns:
            是否保存成功
        """
        path = config_path or self.config_path
        if not path:
            return False
        
        return save_config(self.config, path)
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """获取配置值
        
        Args:
            key_path: 键路径
            default: 默认值
            
        Returns:
            配置值
        """
        return get_config_value(self.config, key_path, default)
    
    def set(self, key_path: str, value: Any) -> None:
        """设置配置值
        
        Args:
            key_path: 键路径
            value: 配置值
        """
        set_config_value(self.config, key_path, value)
    
    def merge(self, other_config: Dict[str, Any]) -> None:
        """合并其他配置
        
        Args:
            other_config: 其他配置字典
        """
        self.config = merge_configs(self.config, other_config)
    
    def validate(self, required_keys: list) -> bool:
        """验证配置完整性
        
        Args:
            required_keys: 必需的键列表
            
        Returns:
            是否通过验证
        """
        return validate_config(self.config, required_keys)