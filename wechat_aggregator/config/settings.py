"""
默认配置设置

定义项目的默认配置参数。
"""

from typing import Dict, Any


DEFAULT_CONFIG: Dict[str, Any] = {
    # 微信相关配置
    'wechat': {
        'token': '',  # 微信公众平台token
        'cookie': '',  # 微信公众平台cookie
        'request_delay': 1,  # 请求延迟(秒)
        'retry_times': 3,  # 重试次数
        'max_articles_per_request': 20,  # 每次请求最大文章数
    },
    
    # 去重配置
    'deduplication': {
        'minhash_threshold': 0.8,  # MinHash阈值
        'text_similarity_threshold': 0.7,  # 文本相似度阈值
        'num_perm': 128,  # MinHash排列数
        'min_date': '2025-06-01',  # 处理文章的最小日期
    },
    
    # 输出配置
    'output': {
        'markdown_path': 'output/markdown/',  # Markdown输出路径
        'assets_path': 'output/assets/',  # 资源文件路径
        'blog_path': '',  # Hexo博客路径
        'single_articles_days': 15,  # 单个文章生成的天数限制
        'archive_months': 6,  # 归档文章的月份限制
    },
    
    # 数据配置
    'data': {
        'directory': 'data/',  # 数据目录
        'cache_directory': 'data/cache/',  # 缓存目录
        'raw_directory': 'data/raw/',  # 原始数据目录
        'processed_directory': 'data/processed/',  # 处理后数据目录
    },
    
    # 日志配置
    'logging': {
        'level': 'INFO',  # 日志级别
        'file': 'logs/wechat_aggregator.log',  # 日志文件
        'max_size': '10MB',  # 日志文件最大大小
        'backup_count': 5,  # 备份文件数量
        'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    },
    
    # 网络配置
    'network': {
        'timeout': 30,  # 请求超时时间
        'max_retries': 3,  # 最大重试次数
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36',
    },
    
    # 图片处理配置
    'image': {
        'max_width': 640,  # 图片最大宽度
        'quality': 85,  # 图片质量
        'format': 'JPEG',  # 图片格式
    },
}


def get_default_config() -> Dict[str, Any]:
    """获取默认配置的副本
    
    Returns:
        默认配置字典的深拷贝
    """
    import copy
    return copy.deepcopy(DEFAULT_CONFIG)


def get_config_value(key_path: str, default: Any = None) -> Any:
    """从默认配置中获取值
    
    Args:
        key_path: 配置键路径，用点分隔
        default: 默认值
        
    Returns:
        配置值
    """
    keys = key_path.split('.')
    value = DEFAULT_CONFIG
    
    try:
        for key in keys:
            value = value[key]
        return value
    except (KeyError, TypeError):
        return default


def validate_config(config: Dict[str, Any]) -> bool:
    """验证配置的有效性
    
    Args:
        config: 配置字典
        
    Returns:
        配置是否有效
    """
    required_sections = [
        'wechat',
        'deduplication', 
        'output',
        'data',
        'logging',
        'network'
    ]
    
    for section in required_sections:
        if section not in config:
            print(f"缺少必需的配置节: {section}")
            return False
    
    # 验证关键配置项
    critical_configs = [
        'deduplication.minhash_threshold',
        'deduplication.num_perm',
        'output.markdown_path',
        'data.directory',
    ]
    
    for config_path in critical_configs:
        if get_config_value_from_dict(config, config_path) is None:
            print(f"缺少关键配置项: {config_path}")
            return False
    
    return True


def get_config_value_from_dict(config: Dict[str, Any], key_path: str, default: Any = None) -> Any:
    """从指定配置字典中获取值
    
    Args:
        config: 配置字典
        key_path: 配置键路径，用点分隔
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