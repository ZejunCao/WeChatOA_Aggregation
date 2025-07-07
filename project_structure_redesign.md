# WeChatOA_Aggregation 项目重构设计

## 当前项目结构问题分析

### 1. 目录命名问题
- `request_/` - 包含下划线，不符合Python包命名规范
- `util/` - 过于泛化，功能不够明确

### 2. 文件组织混乱
- 根目录文件过多，缺乏层次感
- `data/` 目录混合了配置文件、数据文件、输出文件
- 缺少明确的功能模块分离

### 3. 缺少标准开源项目元素
- 缺少 LICENSE 文件
- 缺少 .gitignore 文件
- 缺少 setup.py 或 pyproject.toml
- 缺少测试目录和文档目录

## 新目录结构设计

```
WeChatOA_Aggregation/
├── README.md                    # 项目说明文档
├── LICENSE                      # 开源许可证
├── .gitignore                   # Git忽略文件配置
├── pyproject.toml              # 项目配置和依赖管理
├── requirements.txt            # 依赖包列表
├── setup.py                    # 安装脚本(可选)
├── 
├── wechat_aggregator/          # 主要源代码包
│   ├── __init__.py
│   ├── main.py                 # 主入口文件
│   ├── 
│   ├── core/                   # 核心功能模块
│   │   ├── __init__.py
│   │   ├── request_handler.py  # 微信请求处理
│   │   ├── data_manager.py     # 数据管理
│   │   ├── deduplication.py    # 去重算法
│   │   └── markdown_generator.py # Markdown生成
│   │   
│   ├── utils/                  # 工具函数
│   │   ├── __init__.py
│   │   ├── time_utils.py       # 时间相关工具
│   │   ├── file_utils.py       # 文件操作工具
│   │   └── config_utils.py     # 配置相关工具
│   │   
│   └── config/                 # 配置文件
│       ├── __init__.py
│       ├── settings.py         # 默认配置
│       └── logging.conf        # 日志配置
│
├── config/                     # 用户配置文件
│   ├── config.yaml             # 主配置文件
│   └── accounts.json           # 账号配置
│
├── data/                       # 数据文件目录
│   ├── cache/                  # 缓存文件
│   │   ├── minhash_dict.pickle
│   │   └── name2fakeid.json
│   ├── raw/                    # 原始数据
│   │   ├── message_info.json
│   │   ├── message_detail_text.json
│   │   └── issues_message.json
│   └── processed/              # 处理后数据
│       └── id_info.json
│
├── output/                     # 输出文件目录
│   ├── markdown/               # 生成的Markdown文件
│   │   ├── 微信公众号聚合平台_按时间区分.md
│   │   └── 微信公众号聚合平台_按公众号区分.md
│   └── assets/                 # 静态资源
│       └── blog_preview.png
│
├── scripts/                    # 脚本文件
│   ├── daily_update.sh         # 每日更新脚本
│   ├── setup_env.sh            # 环境设置脚本
│   └── deploy.sh               # 部署脚本
│
├── tests/                      # 测试文件
│   ├── __init__.py
│   ├── test_request_handler.py
│   ├── test_deduplication.py
│   └── test_markdown_generator.py
│
├── docs/                       # 文档目录
│   ├── installation.md         # 安装指南
│   ├── usage.md               # 使用指南
│   ├── configuration.md       # 配置说明
│   └── api.md                 # API文档
│
└── examples/                   # 示例文件
    ├── basic_usage.py          # 基础使用示例
    └── advanced_config.py      # 高级配置示例
```

## 文件重构映射

### 当前文件 -> 新位置

1. **核心代码重构**
   - `main.py` → `wechat_aggregator/main.py`
   - `request_/wechat_request.py` → `wechat_aggregator/core/request_handler.py`
   - `util/util.py` → `wechat_aggregator/utils/time_utils.py` + `wechat_aggregator/utils/file_utils.py`
   - `util/data_config.py` → `wechat_aggregator/core/data_manager.py`
   - `util/filter_duplication.py` → `wechat_aggregator/core/deduplication.py`
   - `util/message2md.py` → `wechat_aggregator/core/markdown_generator.py`

2. **配置文件重构**
   - `data/name2fakeid.json` → `config/accounts.json`
   - 创建 `config/config.yaml` 统一配置

3. **数据文件重新组织**
   - `data/minhash_dict.pickle` → `data/cache/minhash_dict.pickle`
   - `data/message_info.json` → `data/raw/message_info.json`
   - `data/message_detail_text.json` → `data/raw/message_detail_text.json`
   - `data/issues_message.json` → `data/raw/issues_message.json`
   - `data/id_info.json` → `data/processed/id_info.json`

4. **输出文件重新组织**
   - `data/微信公众号聚合平台_*.md` → `output/markdown/`
   - `figures/blog_preview.png` → `output/assets/blog_preview.png`

5. **脚本文件重新组织**
   - `daily_update.sh` → `scripts/daily_update.sh`

## 新增必要文件

### 1. `.gitignore`
```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Data files
data/cache/
data/raw/
data/processed/
config/accounts.json

# Output files
output/

# Environment
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db
```

### 2. `pyproject.toml`
```toml
[build-system]
requires = ["setuptools>=45", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "wechat-aggregator"
version = "1.0.0"
description = "微信公众号聚合平台，获取多个公众号的博文进行筛选、过滤"
authors = [
    {name = "Cao Zejun", email = "your-email@example.com"}
]
license = {text = "MIT"}
readme = "README.md"
requires-python = ">=3.8"
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
]
dependencies = [
    "DrissionPage",
    "lxml",
    "requests",
    "tqdm",
    "datasketch",
    "pyyaml",
]

[project.optional-dependencies]
dev = [
    "pytest",
    "pytest-cov",
    "black",
    "flake8",
    "mypy",
]

[project.urls]
Homepage = "https://github.com/yourusername/WeChatOA_Aggregation"
Repository = "https://github.com/yourusername/WeChatOA_Aggregation"
Documentation = "https://github.com/yourusername/WeChatOA_Aggregation/docs"
```

### 3. `config/config.yaml`
```yaml
# 微信公众号聚合平台配置文件

# 微信相关配置
wechat:
  token: ""  # 微信公众平台token
  cookie: ""  # 微信公众平台cookie
  request_delay: 1  # 请求延迟(秒)
  retry_times: 3  # 重试次数

# 去重配置
deduplication:
  minhash_threshold: 0.9  # MinHash阈值
  text_similarity_threshold: 0.7  # 文本相似度阈值

# 输出配置
output:
  markdown_path: "output/markdown/"
  assets_path: "output/assets/"
  blog_path: ""  # Hexo博客路径

# 日志配置
logging:
  level: "INFO"
  file: "logs/wechat_aggregator.log"
  max_size: "10MB"
  backup_count: 5
```

## 重构的优势

1. **模块化设计**: 清晰的功能模块分离，便于维护和扩展
2. **标准化结构**: 符合Python项目和开源项目的标准规范
3. **配置统一**: 统一的配置管理，便于部署和定制
4. **数据分层**: 明确的数据分层存储，便于管理和备份
5. **可测试性**: 完整的测试框架支持
6. **文档完善**: 完整的文档体系，便于用户使用
7. **部署友好**: 标准的Python包结构，支持pip安装

## 实施建议

1. 创建新的目录结构
2. 重构核心代码，拆分功能模块
3. 统一配置管理
4. 添加单元测试
5. 完善文档
6. 优化部署脚本

这个新结构将使项目更加专业、易于维护和扩展，同时也便于其他开发者理解和贡献代码。