// ─────────────────────────────────────────────────────────────────────────────
// 全局 TypeScript 类型定义
// 所有页面和组件共用的数据结构都在这里声明，保持类型一致性。
// ─────────────────────────────────────────────────────────────────────────────

// ── 文章数据（对应 message_info.json 中每篇博客的结构） ──────────────────────
export interface Article {
  id: string           // 唯一 ID：格式为 "{msgid}-{aid}-{create_time}"
  title: string        // 文章标题
  digest: string       // 文章摘要（微信原始摘要）
  link: string         // 微信原文链接（点击后跳转）
  cover: string        // 封面图原始 URL（微信 CDN，可能有防盗链）
  create_time: string  // 发布时间，格式 "YYYY-MM-DD HH:MM"
  is_deleted: boolean  // 是否已被公众号删除
  item_show_type: number  // 文章展示类型（0=普通图文，5=视频 等，非 0 一般跳过）

  // 预留 LLM 字段，目前为空，后续接入大模型打标签/摘要时填充
  tags?: string[]      // LLM 生成的标签列表
  summary?: string     // LLM 生成的文章摘要（比 digest 更精炼）
  word_count?: number  // 文章字数（中文按字、英文按词）

  /** SQLite：用户阅读/收藏状态（由 API 返回） */
  is_read?: boolean
  starred?: boolean

  /** SQLite：进库来源 crawl=订阅抓取，import=纯链接导入（不可变） */
  source?: 'crawl' | 'import'
  /** SQLite：是否出现在「导入」分栏 */
  import_listed?: boolean
}

// ── 单个公众号的文章集合（message_info.json 中每个 key 对应的 value） ────────
export interface AccountData {
  latest_update_time: string  // 最后一次成功爬取的时间
  blogs: Article[]            // 该公众号的所有文章列表
}

// message_info.json 的完整结构：{ "公众号名称": AccountData, ... }
export type MessageInfo = Record<string, AccountData>

// name2fakeid.json 的结构：{ "公众号名称": "fakeid字符串", ... }
export type Name2FakeId = Record<string, string>

// ── 公众号信息（前端展示用，合并了 name2fakeid 和 message_info 的数据） ──────
export interface AccountInfo {
  name: string               // 公众号名称
  fakeid: string             // 微信内部 ID
  latest_update_time: string // 最后爬取时间
  article_count: number      // 当前有效文章数
  visible: boolean           // 是否在文章流中显示（可通过配置隐藏）
}

// ── 筛选/排序/分组相关类型 ────────────────────────────────────────────────────

// 文章排序方式
export type SortOrder = 'newest' | 'oldest'  // 最新优先 / 最早优先

// 文章分组方式
export type GroupBy = 'date' | 'account' | 'none'  // 按日期 / 按公众号 / 不分组

// 已读/收藏筛选
export type ReadFilter = 'all' | 'unread' | 'bookmarked' | 'imported'  // 全部 / 未读 / 收藏 / 链接导入

// 标签筛选中的特殊值：表示“未打标签”的文章
export const TAG_UNTAGGED = '__untagged__'

// FilterBar 组件管理的所有筛选条件
export interface FilterState {
  keyword: string        // 关键词搜索（匹配标题、摘要、AI 摘要）
  accounts: string[]     // 只显示选中公众号的文章（空数组=显示全部）
  tags: string[]         // 标签过滤（多选按“命中任一标签”处理；支持特殊值 TAG_UNTAGGED）
  dateFrom: string       // 日期范围起始（格式 "YYYY-MM-DD"）
  dateTo: string         // 日期范围结束（格式 "YYYY-MM-DD"）
  sortOrder: SortOrder   // 排序方式
  groupBy: GroupBy       // 分组方式
  readFilter: ReadFilter // 已读状态筛选
}

// ── API 响应类型（与后端 api.py 中的 Pydantic 模型对应） ─────────────────────

// GET /api/auth/status 和 POST /api/auth/check 的响应
export interface AuthStatus {
  has_credentials: boolean  // id_info.json 中是否有 token 和 cookie
  valid: boolean            // 上次检测凭证是否有效
  checked_at: string        // 上次检测时间
  error: string             // 失败原因（正常时为空）
  token_hint: string        // token 前 8 位，供确认身份
  id_info_mtime: string     // id_info.json 最后修改时间
}

// GET /api/cache/preview 的响应（清理前预览）
export interface CachePreview {
  keep_days: number            // 保留天数
  cutoff_date: string          // 截止日期
  total_articles: number       // 当前文章总数
  removable_articles: number   // 将删除的文章数
  removable_covers: number     // 将删除的封面图数
  removable_detail_texts: number // 将删除的详情缓存数
}

// GET /api/crawl/status 的响应（爬取进度，前端轮询）
export interface CrawlStatus {
  running: boolean      // 是否正在爬取
  total: number         // 本次需爬取的公众号总数
  done: number          // 已完成的公众号数
  current: string       // 正在爬取的公众号名称
  errors: string[]      // 本次爬取错误列表
  started_at: string    // 开始时间
  finished_at: string   // 结束时间（未结束时为空）
  new_articles: number  // 本次新增文章数
  auth_error: boolean   // 是否因凭证失效而终止
  cancel_requested?: boolean // 是否已请求取消
  cancelled?: boolean   // 是否由用户取消
}
