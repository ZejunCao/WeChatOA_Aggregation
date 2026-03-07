# 微信公众号聚合 - 前端

基于 Vue 3 + TypeScript + Vite 构建的本地 Web 界面，用于浏览和筛选每日爬取的微信公众号文章。直接读取项目 `data/` 目录下的 JSON 文件，无需独立后端服务。

## 快速启动

```bash
# 安装依赖（首次）
npm install

# 启动开发服务器（自动映射 /data/ 到 ../data/）
npm run dev
# 浏览器访问 http://localhost:5173

# 生产构建
npm run build
# 构建产物在 dist/，将 ../data/*.json 复制到 dist/data/ 后即可部署
```

## 目录结构

```
frontend/
├── index.html                      # 入口 HTML，设置页面标题和字体
├── vite.config.ts                  # Vite 配置：Tailwind 插件 + /data/ 中间件
├── src/
│   ├── main.ts                     # 应用入口：挂载 Vue、Pinia、Router
│   ├── App.vue                     # 根组件：侧边栏 + 主内容区布局，移动端汉堡菜单
│   ├── style.css                   # 全局样式：Tailwind 导入、CSS 变量主题、滚动条
│   │
│   ├── types/
│   │   └── index.ts                # TypeScript 类型定义（见下方详解）
│   │
│   ├── stores/
│   │   ├── articles.ts             # 文章数据 store（见下方详解）
│   │   └── config.ts               # 用户配置 store（见下方详解）
│   │
│   ├── composables/
│   │   └── useFilters.ts           # 筛选/排序/分组逻辑的可复用函数
│   │
│   ├── router/
│   │   └── index.ts                # 路由：/ → FeedView，/config → ConfigView
│   │
│   ├── components/
│   │   ├── layout/
│   │   │   ├── AppSidebar.vue      # 左侧导航栏（折叠/展开、公众号快捷列表）
│   │   │   └── ThemeToggle.vue     # 主题切换按钮（浅色/深色/跟随系统）
│   │   │
│   │   ├── articles/
│   │   │   ├── ArticleCard.vue     # 文章卡片（网格视图，含封面图/标题/摘要/标签）
│   │   │   ├── ArticleRow.vue      # 文章行（列表视图，紧凑横向布局）
│   │   │   └── FilterBar.vue       # 顶部筛选栏（搜索框、日期、排序、分组、高级筛选）
│   │   │
│   │   └── ui/
│   │       ├── Dropdown.vue        # 通用浮层下拉菜单（替代原生 <select>）
│   │       └── DateRangePicker.vue # 日期范围选择器（预设区间 + 自定义输入）
│   │
│   └── views/
│       ├── FeedView.vue            # 文章流页面（主页）
│       └── ConfigView.vue          # 公众号配置页面
```

## 各模块详解

### `src/types/index.ts` — 类型定义

核心类型：

| 类型 | 说明 |
|------|------|
| `Article` | 单篇文章，对应 `message_info.json` 中 `blogs[]` 的一项；包含 `tags?` 和 `summary?` 两个**预留字段**，LLM 接入后填充 |
| `AccountData` | 单个公众号数据，含 `latest_update_time` 和 `blogs` 列表 |
| `MessageInfo` | `{ "公众号名": AccountData }` 的映射，对应整个 `message_info.json` |
| `AccountInfo` | 前端展示用的公众号信息，额外包含 `article_count` 和 `visible` 字段 |
| `FilterState` | 筛选条件快照：关键词、选中公众号、标签、日期范围、排序方式、分组方式 |

### `src/stores/articles.ts` — 文章数据

使用 Pinia 管理，应用启动时在 `App.vue` 的 `onMounted` 中调用 `loadData()` 加载数据。

| 状态/计算属性 | 说明 |
|-------------|------|
| `messageInfo` | 原始 JSON 数据 |
| `loading` / `error` | 加载状态，供视图展示 loading/error UI |
| `accounts` | 所有公众号列表（含文章数、最后更新时间） |
| `allArticles` | 所有未删除文章，按时间倒序，每条附带 `account` 字段 |
| `allTags` | 所有文章的标签去重列表（LLM 接入后有值） |
| `stats` | 总公众号数、总文章数、最新更新时间，供配置页展示 |

### `src/stores/config.ts` — 用户配置

使用 `pinia-plugin-persistedstate` 自动持久化到浏览器 `localStorage`，刷新页面后配置不丢失。

| 状态/方法 | 说明 |
|----------|------|
| `hiddenAccounts` | 隐藏的公众号名称列表 |
| `theme` | 当前主题：`'light'` / `'dark'` / `'system'` |
| `toggleAccount(name)` | 切换某公众号的显示/隐藏 |
| `isVisible(name)` | 判断某公众号是否在文章流中展示 |
| `showAll()` / `hideAll()` | 批量操作 |
| `setTheme(t)` / `initTheme()` | 主题切换，`initTheme()` 在应用启动时调用 |

### `src/composables/useFilters.ts` — 筛选逻辑

封装了筛选、排序、分组的全部计算逻辑，在 `FeedView.vue` 中调用。

- `filters` — 响应式筛选条件对象（reactive）
- `filteredArticles` — 经过关键词、公众号、标签、日期筛选后的文章列表
- `groupedArticles` — 在 `filteredArticles` 基础上按日期或公众号分组
- `resetFilters()` — 重置所有筛选条件
- `activeFilterCount` — 当前生效的筛选条件数量（用于筛选按钮上的角标）

### `src/components/ui/` — 基础 UI 组件

这两个组件是为了替代浏览器原生控件而自建的，与 Tailwind 主题系统完全兼容：

**`Dropdown.vue`**：通用弹出菜单
- Props: `options`（选项列表）、`modelValue`（当前值）
- 点击触发浮层，当前选中项显示 `✓`，点击外部自动关闭（`@vueuse/core` 的 `onClickOutside`）
- 用于 FilterBar 中的"排序"和"分组"控件

**`DateRangePicker.vue`**：日期范围选择器
- 内置预设区间：不限时间 / 今天 / 近 7 天 / 近 30 天 / 近 3 个月 / 今年
- 支持自定义输入（`YYYY-MM-DD` 格式文本框，无浏览器 OS 样式）
- Emits `update:dateFrom` 和 `update:dateTo`，与 `FilterState` 兼容

### `src/views/FeedView.vue` — 文章流页面

主页，路由 `/`。包含：
- 顶部固定 FilterBar，支持关键词搜索、日期范围、排序、分组、高级筛选面板
- 网格/列表视图切换（`ArticleCard` / `ArticleRow`）
- 加载中、加载失败、空结果三种状态的提示 UI
- 与侧边栏的 `selectedAccount` 双向同步（侧边栏点公众号 = FilterBar 公众号筛选联动）

### `src/views/ConfigView.vue` — 配置页

路由 `/config`。包含：
- 顶部统计看板（总公众号数、总文章数、最近更新）
- 公众号卡片网格，点击切换显示/隐藏状态
- 全选/全不选批量操作
- 公众号搜索框（公众号数量多时方便定位）

## 数据读取方案

开发环境下，`vite.config.ts` 注册了一个自定义中间件，将所有 `/data/*` 请求映射到项目根目录的 `../data/` 文件夹：

```
浏览器请求 GET /data/message_info.json
      ↓
Vite 中间件读取 ../data/message_info.json
      ↓
返回 JSON 内容
```

**生产部署**：`npm run build` 后，将 `data/*.json` 复制到 `dist/data/` 目录即可，任何静态文件服务器均可托管。

## 未来扩展：LLM 标签与摘要

`Article` 类型中已预留两个可选字段：

```typescript
interface Article {
  // ... 现有字段 ...
  tags?: string[]     // LLM 生成的标签列表
  summary?: string    // LLM 生成的文章摘要
}
```

Python 爬虫调用 LLM 处理后，只需在 `message_info.json` 中为每篇文章补充这两个字段，前端无需改动即可：
- `ArticleCard` / `ArticleRow` 自动显示标签 chip 和"AI 摘要"标记
- 摘要优先于 `digest` 展示
- FilterBar 的标签筛选（`allTags`）自动聚合所有出现过的标签
