# WeChatOA_Aggregation

微信公众号聚合平台——爬取多个公众号的文章，在本地 Web 界面中进行筛选、过滤和阅读，可聚合多个公众号的优质文章统一阅读，AI 辅助分析。

![blog_preview.png](figures/blog_preview.png)

---

## 快速启动

### 1. 环境准备

```bash
# 推荐使用 uv 管理 Python 依赖
uv sync

# 前端依赖（首次或 package 变更后）
cd frontend && npm install && cd ..
```

### 2. 一键启动前后端（推荐）

在项目根目录执行：

```bash
./start_all.sh
```

脚本会并行启动：

- 后端 API：`http://127.0.0.1:8000`（`uv run uvicorn api:app --reload --port 8000`）
- 前端开发服：`http://127.0.0.1:5173`（`frontend` 内 `npm run dev`）

按 `Ctrl+C` 会结束前后端子进程。

可选：启动前设置大模型打标地址（见下文「大模型打标签」）；`start_all.sh` 内对 `QWEN35_27B_ENDPOINT` 带有默认值，可按需 `export` 覆盖。

### 3. 首次使用：微信凭证

1. 用上一节方式启动服务，浏览器打开 **http://127.0.0.1:5173**
2. 进入 **「配置」** 页
3. 点击 **「扫码登录」**，按提示用微信扫描公众平台登录页；成功后 **token / cookie 会自动写入** `data/id_info.json`

若凭证过期，配置页顶部会出现提示，同样通过 **扫码登录** 续期即可。

### 4. 大模型打标签（可选）

爬取到**新文章**时，若配置了 LLM 接口，会为每篇生成 `tags` 并写入 `message_info.json`，前端筛选栏与卡片可展示、过滤标签。

| 环境变量 | 说明 |
|----------|------|
| `QWEN35_27B_ENDPOINT` | 自部署或网关的 Chat Completions 兼容地址（POST JSON）。**未设置则跳过打标**，爬取与其它功能不受影响。 |
| `QWEN35_27B_API_KEY` 或 `LLM_API_KEY` | 可选；若设置则请求头携带 `Authorization: Bearer <密钥>`。 |
| `QWEN35_27B_MODEL` | 可选，默认 `Qwen3.5-27B`。 |

标签由一组**种子标签**（含 **「广告」**）与模型扩展组成；若正文明显为推广、带货、商务合作、营销软文，提示词要求模型必须打上「广告」。单次请求失败时该篇可能无标签，不影响爬取落盘。

### 5. 手动分启（备选）

```bash
# 终端 1
uv run uvicorn api:app --reload --port 8000

# 终端 2
cd frontend && npm run dev
# 浏览器访问 http://localhost:5173
```

---

## 功能说明

### 前端界面

| 页面 / 功能模块 | 说明 |
|----------------|------|
| **文章信息流** | 卡片 / 列表两种视图；默认按日期分组；关键词搜索、公众号筛选、日期范围、排序与分组；单篇删除（黑名单，再次爬取不入库）；**Feed 界面主题**（奶白磨砂网格 / 清蓝网格 / 粉紫渐变玻璃等）在侧栏底部切换并持久化 |
| **已读 / 收藏** | 点击文章标为已读；收藏与 FilterBar「全部 / 未读 / 收藏」；已读降低强调、未读圆点 |
| **公众号管理（配置页）** | 搜索添加、移除、显示/隐藏；**扫码登录** 写入微信凭证；立即爬取与进度；缓存清理；凭证状态 |
| **操作日志** | 爬取、账号、清理等记录（JSONL），时间轴与详情 |
| **主题** | 全局浅色 / 深色 / 跟随系统；Feed 区独立界面预设（与上表「界面主题」一致） |

### 爬虫与数据

- 支持按公众号 `fakeid` 批量拉取近一个月文章
- 基于 `msgid-aid-create_time` 组合 ID 增量去重
- 用户删除的文章 id 记入 `deleted_article_ids.json`，后续爬取跳过
- 封面图落地 `data/covers/`，大图等比缩放；规避 CDN 防盗链
- 爬取前凭证预检，失效时中止并提示
- 重要操作写入 `data/operation_logs.jsonl`
- MinHash+LSH 相似文检测（阈值 0.9 等，见文末实验表）
- 可选：配置 `QWEN35_27B_ENDPOINT` 后为新文章打 `tags`

### 技术栈

**前端：** Vue 3 · TypeScript · Vite · Tailwind CSS v4 · Pinia（持久化）· Vue Router · lucide-vue-next  

**后端：** FastAPI · uvicorn · Pillow · requests · DrissionPage  

**数据：** 本地 JSON（`data/`），无需数据库  

---

## 目录结构

```
WeChatOA_Aggregation/
├── start_all.sh             # 一键启动前后端（开发）
├── scripts/
│   └── daily_update.sh      # 个人环境用定时/发布脚本示例（路径需自行改）
├── api.py                   # FastAPI：账号、爬取、缓存、凭证、日志等
├── pyproject.toml           # Python 依赖（uv）
├── data/
│   ├── id_info.json         # 微信 token / cookie（配置页扫码写入，亦可手动）
│   ├── name2fakeid.json     # 已添加公众号
│   ├── message_info.json    # 文章主数据
│   ├── message_detail_text.json  # 正文缓存（若启用）
│   ├── deleted_article_ids.json
│   ├── covers/              # 封面图缓存
│   └── operation_logs.jsonl
├── src/
│   ├── crawler/
│   │   └── wechat_request.py
│   ├── llm/
│   │   ├── model_client.py
│   │   └── article_tagging.py
│   └── utils/
│       └── data_manager.py
├── demo/                    # 静态 UI 参考（index.html 等）
└── frontend/
    ├── package.json
    └── src/
        ├── themes/feed-themes.ts   # Feed 界面预设 id
        ├── styles/                 # 全局样式、主题预设 CSS
        ├── types/index.ts
        ├── stores/                 # articles / reading / config
        ├── composables/useFilters.ts
        ├── components/
        │   ├── articles/           # ArticleCard、ArticleRow、FilterBar
        │   ├── layout/             # AppSidebar、ThemeToggle、FeedThemePicker
        │   └── ui/
        └── views/
            ├── FeedView.vue
            ├── ConfigView.vue
            └── LogView.vue
```

---

## 生产构建

```bash
cd frontend
npm run build
# 部署 dist/，并按需把仓库根目录 data/*.json（及 covers）提供给静态托管或同域 API
```

---

## TODO

### 爬虫 / 数据

- [x] **重复文章识别（规则 + 正文）**：先通过标题做候选筛选，再拉正文计算相似度，降低同一内容多次入库。
- [x] **MinHash+LSH 去重**：已上线 0.9 阈值方案，见文末实验记录。
- [ ] **向量语义去重**：引入向量模型，覆盖“标题不同但正文几乎一致”的重复内容。
- [x] **爬取稳态能力**：已包含爬取频率控制、凭证失效扫码续期、删文检测、封面本地缓存、凭证预检、操作日志落盘。
- [ ] **广告内容过滤**：在去重之外，补充广告/软文识别策略，减少低价值内容。
- [x] **请求频率与代理兜底**：历史已验证，当前微信策略变化后该项默认弱化使用。
- [ ] **定时自动爬取**：接入 APScheduler，并在配置页提供开关、执行时间、最近一次执行状态。

### 前端 / 阅读体验

- [x] **配置页核心能力**：公众号管理、筛选、日志、已读/收藏、凭证状态横幅与扫码登录。
- [x] **Feed 主题系统**：奶白网格/清蓝网格/粉紫渐变玻璃，支持切换与本地持久化。
- [ ] **统计图表页**：展示公众号发文频率趋势、总文章增长曲线、近 7/30 天活跃度。
- [ ] **封面补全工具**：对历史缺失封面的文章批量补下载，并展示补全进度。
- [ ] **数据导出能力**：将当前筛选结果导出为 Markdown、CSV、JSON。
- [ ] **PWA 安装支持**：补齐 manifest 与离线缓存，支持桌面/手机添加到主屏。
- [ ] **添加公众号连续录入体验**：点击“添加公众号”后自动聚焦输入框，添加成功后停留在添加流程以便连续录入。
- [ ] **爬取进度文案优化**：每日爬取时，尽早展示当前账号名，避免“0/N”停留造成无响应错觉。

### LLM

- [x] **新文章自动打标签**：爬取后调用 `QWEN35_27B_*` 接口生成 `tags`。
- [ ] **文章摘要生成**：为新文章生成 `summary`，并在信息流中展示摘要内容。
- [ ] **语义搜索**：对文章向量化后支持自然语言检索与召回排序。

### 部署

- [ ] **静态部署验证**：已在 GitHub Pages 完成基础部署并支持站内搜索。
- [x] **凭证失效引导**：前端可提示并引导扫码重新授权。
- [ ] **Docker Compose 一键部署**：提供后端 + 前端统一编排，降低本地与服务器部署门槛。

---

## MinHash 实验记录

在 4005 条博文的测试集下的去重实验（`minhash_0.9` 代表 MinHashLSH 阈值为 0.9）：

| 方法 | 检测重复个数 | 错误个数 |
|------|------------|---------|
| minhash_0.9 | 528 | 0 |
| minhash_0.8 | 699 | 24 |
| minhash_0.8 + 规则 0.7 | 665 | 1（文字很少，主体为图片） |

---

## 类似项目参考

- [wechat-article-exporter](https://github.com/jooooock/wechat-article-exporter)
- [WeChat_Article](https://github.com/1061700625/WeChat_Article)
