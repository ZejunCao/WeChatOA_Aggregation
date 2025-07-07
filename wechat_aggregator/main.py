"""
微信公众号聚合平台主程序

主要功能：
1. 爬取多个公众号的文章
2. 去重处理
3. 生成Markdown文件
"""

import time
from typing import Optional

from tqdm import tqdm

from .core.request_handler import WechatRequest
from .core.data_manager import DataManager
from .core.deduplication import MinHashLSH
from .core.markdown_generator import MarkdownGenerator
from .utils.time_utils import time_delta, time_now


def main(data_manager: Optional[DataManager] = None):
    """主程序入口
    
    Args:
        data_manager: 数据管理器实例，如果为None则使用默认实例
    """
    # 初始化组件
    if data_manager is None:
        data_manager = DataManager()
    
    wechat_request = WechatRequest(data_manager)
    
    print("开始爬取公众号文章...")
    
    # 爬取公众号文章
    finished_name = set()
    while len(finished_name) != len(data_manager.name2fakeid):
        try:
            for oa_name, fakeid in tqdm(data_manager.name2fakeid.items(), 
                                       total=len(data_manager.name2fakeid),
                                       desc="爬取公众号"):
                # 如果已经爬取过，则跳过
                if oa_name in finished_name:
                    continue
                
                # 如果是新增加的公众号
                if not fakeid:
                    data_manager.name2fakeid[oa_name] = wechat_request.name2fakeid(oa_name)
                    data_manager.write('name2fakeid')
                
                # 如果message_info中没有该公众号，则初始化
                if oa_name not in data_manager.message_info.keys():
                    data_manager.message_info[oa_name] = {
                        'latest_update_time': "2000-01-01 00:00",  # 默认一个很久远的时间
                        'blogs': [],
                    }
                
                # 如果latest_update_time非空（之前太久不发文章的），或者今天已经爬取过，则跳过
                if (data_manager.message_info[oa_name]['latest_update_time'] and 
                    time_delta(time_now(), data_manager.message_info[oa_name]['latest_update_time']).days < 1):
                    finished_name.add(oa_name)
                    continue
                
                # 爬取文章
                new_articles = wechat_request.fakeid2message_update(
                    data_manager.name2fakeid[oa_name], 
                    data_manager.message_info[oa_name]['blogs']
                )
                
                data_manager.message_info[oa_name]['blogs'].extend(new_articles)
                data_manager.message_info[oa_name]['latest_update_time'] = time_now()
                finished_name.add(oa_name)
                
                print(f"完成爬取 {oa_name}: {len(new_articles)} 篇新文章")
                
        except Exception as e:
            # 写入message_info，如果请求中间失败，及时写入
            data_manager.write('message_info')
            print(f"爬取过程中出现错误: {e}")
            time.sleep(30)  # 若请求失败（通常为请求频率限制），则等待30秒后重试
            continue
    
    # 写入message_info，如果请求顺利进行，则正常写入
    data_manager.write('message_info')
    print("文章爬取完成")
    
    # 每次更新时验证去重
    print("开始去重处理...")
    try:
        with MinHashLSH(data_manager=data_manager) as minhash:
            minhash.write_vector()
        print("去重处理完成")
    except Exception as e:
        print(f"去重处理失败: {e}")
    
    # 将message_info转换为md上传到个人博客系统
    print("开始生成Markdown文件...")
    try:
        markdown_generator = MarkdownGenerator(data_manager)
        markdown_generator.generate_markdown_files()
        print("Markdown文件生成完成")
    except Exception as e:
        print(f"Markdown文件生成失败: {e}")
    
    print("所有任务完成！")


def run_with_config(config_path: str):
    """使用配置文件运行程序
    
    Args:
        config_path: 配置文件路径
    """
    try:
        from .utils.config_utils import ConfigManager
        
        config_manager = ConfigManager(config_path)
        
        # 根据配置创建数据管理器
        data_dir = config_manager.get('data.directory')
        data_manager = DataManager(data_dir) if data_dir else DataManager()
        
        # 设置微信配置
        if config_manager.get('wechat.token'):
            data_manager.id_info['token'] = config_manager.get('wechat.token')
        if config_manager.get('wechat.cookie'):
            data_manager.id_info['cookie'] = config_manager.get('wechat.cookie')
        
        # 运行主程序
        main(data_manager)
        
    except ImportError:
        print("配置管理器不可用，使用默认配置")
        main()
    except Exception as e:
        print(f"配置文件加载失败: {e}")
        main()


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        # 如果提供了配置文件路径
        config_path = sys.argv[1]
        run_with_config(config_path)
    else:
        # 使用默认配置
        main()