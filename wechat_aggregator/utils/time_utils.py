"""
时间工具模块

提供时间转换、计算等工具函数。
"""

import datetime
from typing import Union


def jstime2realtime(jstime: int) -> str:
    """将js获取的时间id转化成真实时间，截止到分钟
    
    Args:
        jstime: JavaScript时间戳（分钟数）
        
    Returns:
        格式化的时间字符串，格式为"YYYY-MM-DD HH:MM"
    """
    base_time = datetime.datetime.strptime("1970-01-01 08:00", "%Y-%m-%d %H:%M")
    return (base_time + datetime.timedelta(minutes=jstime // 60)).strftime("%Y-%m-%d %H:%M")


def realtime2jstime(realtime: str) -> int:
    """将真实时间转化为js获取的时间（自1970-01-01 08:00起的分钟数）
    
    Args:
        realtime: 字符串，格式为"YYYY-MM-DD HH:MM"
        
    Returns:
        分钟数
    """
    base_time = datetime.datetime.strptime("1970-01-01 08:00", "%Y-%m-%d %H:%M")
    target_time = datetime.datetime.strptime(realtime, "%Y-%m-%d %H:%M")
    delta = target_time - base_time
    return int(delta.total_seconds() // 60)


def time_delta(time1: str, time2: str) -> datetime.timedelta:
    """计算时间差
    
    Args:
        time1: 第一个时间，格式为"YYYY-MM-DD HH:MM"
        time2: 第二个时间，格式为"YYYY-MM-DD HH:MM"
    
    Returns:
        返回时间差对象，可以通过：
        - result.days 获取天数
        - result.seconds 获取不满一天的秒数（0-86399）
        - result.total_seconds() 获取总的秒数
    """
    time1_dt = datetime.datetime.strptime(time1, "%Y-%m-%d %H:%M")
    time2_dt = datetime.datetime.strptime(time2, "%Y-%m-%d %H:%M")
    return time1_dt - time2_dt


def time_now() -> str:
    """获取当前时间
    
    Returns:
        格式化的当前时间字符串，格式为"YYYY-MM-DD HH:MM"
    """
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def time_now_full() -> str:
    """获取完整的当前时间
    
    Returns:
        格式化的当前时间字符串，格式为"YYYY-MM-DD HH:MM:SS"
    """
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_time(time_str: str, format_str: str = "%Y-%m-%d %H:%M") -> datetime.datetime:
    """解析时间字符串为datetime对象
    
    Args:
        time_str: 时间字符串
        format_str: 时间格式字符串，默认为"%Y-%m-%d %H:%M"
        
    Returns:
        datetime对象
    """
    return datetime.datetime.strptime(time_str, format_str)


def format_time(dt: datetime.datetime, format_str: str = "%Y-%m-%d %H:%M") -> str:
    """格式化datetime对象为字符串
    
    Args:
        dt: datetime对象
        format_str: 时间格式字符串，默认为"%Y-%m-%d %H:%M"
        
    Returns:
        格式化的时间字符串
    """
    return dt.strftime(format_str)


def is_time_in_range(check_time: str, start_time: str, end_time: str) -> bool:
    """检查时间是否在指定范围内
    
    Args:
        check_time: 要检查的时间，格式为"YYYY-MM-DD HH:MM"
        start_time: 起始时间，格式为"YYYY-MM-DD HH:MM"
        end_time: 结束时间，格式为"YYYY-MM-DD HH:MM"
        
    Returns:
        True如果在范围内，False否则
    """
    check_dt = parse_time(check_time)
    start_dt = parse_time(start_time)
    end_dt = parse_time(end_time)
    
    return start_dt <= check_dt <= end_dt


def get_time_range(days: int = 30) -> tuple[str, str]:
    """获取时间范围
    
    Args:
        days: 天数，默认30天
        
    Returns:
        (start_time, end_time) 元组，格式为"YYYY-MM-DD HH:MM"
    """
    now = datetime.datetime.now()
    start_time = now - datetime.timedelta(days=days)
    
    return format_time(start_time), format_time(now)