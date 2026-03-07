export interface Article {
  id: string
  title: string
  digest: string
  link: string
  cover: string
  create_time: string
  is_deleted: boolean
  item_show_type: number
  // LLM fields (reserved for future use)
  tags?: string[]
  summary?: string
}

export interface AccountData {
  latest_update_time: string
  blogs: Article[]
}

export type MessageInfo = Record<string, AccountData>

export type Name2FakeId = Record<string, string>

export interface AccountInfo {
  name: string
  fakeid: string
  latest_update_time: string
  article_count: number
  visible: boolean
}

export type SortOrder = 'newest' | 'oldest'
export type GroupBy = 'date' | 'account' | 'none'

export interface FilterState {
  keyword: string
  accounts: string[]
  tags: string[]
  dateFrom: string
  dateTo: string
  sortOrder: SortOrder
  groupBy: GroupBy
}

export interface CachePreview {
  keep_days: number
  cutoff_date: string
  total_articles: number
  removable_articles: number
  removable_covers: number
  removable_detail_texts: number
}

export interface CrawlStatus {
  running: boolean
  total: number
  done: number
  current: string
  errors: string[]
  started_at: string
  finished_at: string
  new_articles: number
}
