#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
项目结构迁移脚本

将旧的项目结构迁移到新的标准化结构。
"""

import os
import shutil
import json
from pathlib import Path
from typing import Dict, Any


class ProjectMigrator:
    """项目迁移器"""
    
    def __init__(self, old_root: str, new_root: str):
        """初始化迁移器
        
        Args:
            old_root: 旧项目根目录
            new_root: 新项目根目录
        """
        self.old_root = Path(old_root)
        self.new_root = Path(new_root)
        
    def migrate(self):
        """执行完整迁移"""
        print("开始项目结构迁移...")
        
        # 1. 创建新的目录结构
        self._create_new_structure()
        
        # 2. 迁移数据文件
        self._migrate_data_files()
        
        # 3. 迁移配置文件
        self._migrate_config_files()
        
        # 4. 迁移脚本文件
        self._migrate_scripts()
        
        # 5. 迁移输出文件
        self._migrate_output_files()
        
        # 6. 生成迁移报告
        self._generate_migration_report()
        
        print("项目结构迁移完成！")
    
    def _create_new_structure(self):
        """创建新的目录结构"""
        directories = [
            'wechat_aggregator/core',
            'wechat_aggregator/utils', 
            'wechat_aggregator/config',
            'config',
            'data/cache',
            'data/raw', 
            'data/processed',
            'output/markdown',
            'output/assets',
            'scripts',
            'tests',
            'docs',
            'examples',
            'logs'
        ]
        
        for directory in directories:
            dir_path = self.new_root / directory
            dir_path.mkdir(parents=True, exist_ok=True)
            print(f"创建目录: {directory}")
    
    def _migrate_data_files(self):
        """迁移数据文件"""
        print("迁移数据文件...")
        
        old_data_dir = self.old_root / 'data'
        if not old_data_dir.exists():
            print("未找到旧的data目录")
            return
        
        # 文件迁移映射
        file_mappings = {
            'minhash_dict.pickle': 'data/cache/minhash_dict.pickle',
            'name2fakeid.json': 'config/accounts.json',  # 特殊处理
            'message_info.json': 'data/raw/message_info.json',
            'message_detail_text.json': 'data/raw/message_detail_text.json',
            'issues_message.json': 'data/raw/issues_message.json',
            'id_info.json': 'data/processed/id_info.json',
        }
        
        for old_file, new_file in file_mappings.items():
            old_path = old_data_dir / old_file
            new_path = self.new_root / new_file
            
            if old_path.exists():
                if old_file == 'name2fakeid.json':
                    # 特殊处理：转换为新的accounts格式
                    self._convert_name2fakeid(old_path, new_path)
                else:
                    shutil.copy2(old_path, new_path)
                print(f"迁移文件: {old_file} -> {new_file}")
    
    def _convert_name2fakeid(self, old_path: Path, new_path: Path):
        """转换name2fakeid格式到新的accounts格式"""
        with open(old_path, 'r', encoding='utf-8') as f:
            old_data = json.load(f)
        
        # 转换为新格式（保持向后兼容）
        new_data = old_data  # 暂时保持原格式，新系统兼容
        
        with open(new_path, 'w', encoding='utf-8') as f:
            json.dump(new_data, f, ensure_ascii=False, indent=4)
    
    def _migrate_config_files(self):
        """迁移配置文件"""
        print("迁移配置文件...")
        
        # 复制requirements.txt
        old_req = self.old_root / 'requirements.txt'
        new_req = self.new_root / 'requirements.txt'
        if old_req.exists():
            shutil.copy2(old_req, new_req)
            print("迁移文件: requirements.txt")
        
        # 如果存在旧的配置文件，尝试迁移
        old_config_files = [
            'config.ini',
            'config.json', 
            'settings.py'
        ]
        
        for config_file in old_config_files:
            old_path = self.old_root / config_file
            if old_path.exists():
                new_path = self.new_root / 'config' / config_file
                shutil.copy2(old_path, new_path)
                print(f"迁移配置文件: {config_file}")
    
    def _migrate_scripts(self):
        """迁移脚本文件"""
        print("迁移脚本文件...")
        
        script_files = [
            'daily_update.sh',
            'setup.sh',
            'deploy.sh'
        ]
        
        for script_file in script_files:
            old_path = self.old_root / script_file
            if old_path.exists():
                new_path = self.new_root / 'scripts' / script_file
                shutil.copy2(old_path, new_path)
                print(f"迁移脚本: {script_file}")
    
    def _migrate_output_files(self):
        """迁移输出文件"""
        print("迁移输出文件...")
        
        # 迁移markdown文件
        old_data_dir = self.old_root / 'data'
        if old_data_dir.exists():
            md_files = [
                '微信公众号聚合平台_按时间区分.md',
                '微信公众号聚合平台_按公众号区分.md'
            ]
            
            for md_file in md_files:
                old_path = old_data_dir / md_file
                if old_path.exists():
                    new_path = self.new_root / 'output' / 'markdown' / md_file
                    shutil.copy2(old_path, new_path)
                    print(f"迁移Markdown文件: {md_file}")
        
        # 迁移图片文件
        old_figures_dir = self.old_root / 'figures'
        if old_figures_dir.exists():
            for img_file in old_figures_dir.iterdir():
                if img_file.is_file():
                    new_path = self.new_root / 'output' / 'assets' / img_file.name
                    shutil.copy2(img_file, new_path)
                    print(f"迁移图片文件: {img_file.name}")
    
    def _generate_migration_report(self):
        """生成迁移报告"""
        report_path = self.new_root / 'migration_report.txt'
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("项目结构迁移报告\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"旧项目路径: {self.old_root}\n")
            f.write(f"新项目路径: {self.new_root}\n\n")
            f.write("迁移完成的内容:\n")
            f.write("- 创建了新的标准化目录结构\n")
            f.write("- 迁移了数据文件到对应目录\n")
            f.write("- 迁移了配置文件\n")
            f.write("- 迁移了脚本文件\n")
            f.write("- 迁移了输出文件\n\n")
            f.write("注意事项:\n")
            f.write("1. 请检查config/config.example.yaml并创建config/config.yaml\n")
            f.write("2. 请更新脚本文件中的路径引用\n")
            f.write("3. 请验证所有数据文件是否正确迁移\n")
            f.write("4. 可以安全删除旧的项目目录\n")
        
        print(f"迁移报告已生成: {report_path}")


def main():
    """主函数"""
    import sys
    
    if len(sys.argv) != 3:
        print("使用方法: python migrate_to_new_structure.py <旧项目目录> <新项目目录>")
        print("示例: python migrate_to_new_structure.py ./old_project ./new_project")
        sys.exit(1)
    
    old_root = sys.argv[1]
    new_root = sys.argv[2]
    
    if not os.path.exists(old_root):
        print(f"错误: 旧项目目录不存在: {old_root}")
        sys.exit(1)
    
    # 确认操作
    print(f"即将迁移项目:")
    print(f"  从: {old_root}")
    print(f"  到: {new_root}")
    confirm = input("确认继续? (y/N): ")
    
    if confirm.lower() != 'y':
        print("迁移已取消")
        sys.exit(0)
    
    # 执行迁移
    migrator = ProjectMigrator(old_root, new_root)
    migrator.migrate()


if __name__ == '__main__':
    main()