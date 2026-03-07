# WeChatOA_Aggregation

微信公众号聚合平台——爬取多个公众号的文章，在本地 Web 界面中进行筛选、过滤和阅读，可聚合多个公众号的优质文章统一阅读，AI辅助分析。

![blog_preview.png](figures/blog_preview.png)

---

## 快速启动

### 1. 环境准备

```bash
# 推荐使用 uv 管理环境
uv sync
```

### 2. 配置 token 与 cookie

在 `data/id_info.json` 中填入微信公众平台的 `token` 和 `cookie`：

```json
{
    "token": "xxxxxxxxx",
    "cookie": "xxxxxxxxx"
}
```

**获取方式：** 进入 [微信公众平台](https://mp.weixin.qq.com)，扫码登录后地址栏末尾可看到 `token=xxxxxxxxx`；按 F12 → Network → Fetch/XHR，刷新页面，随意点开一个请求即可找到 `Cookie` 字段。

> **自动续期：** token 或 cookie 过期时，程序会自动打开浏览器弹出公众号页面，扫码后自动获取新的 token/cookie 并写回文件。

### 3. 启动后端 API 服务

```bash
uvicorn api:app --reload --port 8000
```

### 4. 启动前端

```bash
cd frontend
npm install
npm run dev
# 浏览器访问 http://localhost:5173
```

---

## 功能说明

### 前端界面

| 页面 | 功能 |
|------|------|
| **文章流** | 卡片 / 列表两种视图；关键词搜索、公众号筛选、日期范围过滤、排序与分组 |
| **公众号管理** | 搜索并添加公众号、移除公众号、控制各账号在文章流中的显示/隐藏 |
| **立即爬取** | 一键触发后端爬取任务，实时进度条展示当前爬取账号与数量 |
| **清理缓存** | 按保留天数（30/60/90/180 天）预览并删除过期文章、封面图和详情缓存 |
| **操作日志** | 时间轴展示爬取、账号管理、缓存清理的历史记录 |
| **主题切换** | 浅色 / 深色 / 跟随系统 |

### 爬虫与数据

- 支持按公众号 `fakeid` 批量拉取近一个月文章
- 基于 `msgid-aid-create_time` 组合 ID 增量去重，已爬取的文章不会重复写入
- 下载封面图到本地 `data/covers/`，规避微信 CDN 防盗链
- 使用 MinHash+LSH 算法对文章内容编码，识别并标记相似/重复文章（阈值 0.9，4005 条测试集准确率 100%）

### 技术栈

**前端：** Vue 3 · TypeScript · Vite · Tailwind CSS v4 · Pinia · Vue Router

**后端：** FastAPI · uvicorn · Pillow · requests

**数据：** 本地 JSON 文件（`data/`），无需数据库

---

## 生产构建

```bash
cd frontend
npm run build
# 将 dist/ 目录部署，并把 ../data/*.json 复制到 dist/data/ 下
```

---

## TODO

### 爬虫 / 数据

- [x] 根据标题筛选可能相似博文，再获取具体内容计算重复率去重，去除大量转载文章
- [x] 使用 MinHash+LSH 算法对文章编码，去除重复文章
  - 0.9 阈值检测 528 篇重复文章，准确率 100%，召回率待测
- [ ] 使用向量编码模型对文章编码，进一步覆盖标题不同但内容相同的情况
  - 长文本准确率较低，待探索
- [x] 爬取次数限制：记录最新爬取时间，一天内已爬取则跳过，反复执行直到全部完成
- [x] cookie/token 过期自动模拟登录获取
- [x] 已爬取的文章定期检测是否已被删除
- [ ] 去除广告等无用博文
- [x] 请求频率限制时，切换代理 IP（免费代理不稳定，微信现已取消次数限制，暂搁置）
- [ ] **定时自动爬取**：在后端接入 APScheduler，配置每天固定时间自动触发，配置页提供开关和时间设置

### 前端 / 阅读体验

- [x] 现代化 Web 界面，支持公众号管理、文章筛选与预览
- [x] 封面图本地缓存，解决微信 CDN 防盗链问题
- [x] 操作日志页面
- [ ] **已读 / 未读标记 + 收藏功能**：localStorage 存储已读 ID，支持收藏单独筛选
- [ ] **统计图表**：各公众号发文频率趋势、全局文章增长曲线（ECharts / Chart.js）
- [ ] **批量补下载封面**：对历史文章中缺失本地封面的条目一键补全下载
- [ ] **数据导出**：将筛选结果导出为 Markdown / CSV / JSON
- [ ] **PWA 支持**：添加 manifest.json，可安装到手机主屏幕作为轻量阅读器使用

### LLM 集成（前端占位符已预留）

- [ ] **自动打标签 + 摘要**：爬取后调用 Ollama 本地模型或 OpenAI API，为新文章生成 `tags` 和 `summary`，写回 `message_info.json`
- [ ] **语义搜索**：对文章内容做向量化，支持自然语言检索（已有 `增加搜索功能，关键词粗召回，再向量重排` 规划）

### 部署

- [x] GitHub Pages 搭建个人博客，将公众号聚合平台部署上去（简易版）：https://zejuncao.github.io/
- [x] 支持站内搜索
- [ ] **Token/Cookie 过期前端提醒**：爬取失败时检测是否为 session 失效，在 UI 上显示醒目提示并引导用户刷新凭证

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
