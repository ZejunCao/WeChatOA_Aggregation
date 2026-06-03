// ─────────────────────────────────────────────────────────────────────────────
// 文章数据 Store（Pinia）— SQLite 分页 API
// ─────────────────────────────────────────────────────────────────────────────

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Article, Name2FakeId, AccountInfo, FilterState } from '@/types'
import { TAG_UNTAGGED } from '@/types'
import { useReadingStore } from './reading'

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { cache: 'no-store', ...init })
  const contentType = res.headers.get('content-type') || ''
  if (!contentType.includes('application/json')) {
    const snippet = (await res.text()).slice(0, 160)
    throw new Error(
      `接口返回非 JSON（${contentType || 'unknown'}）。` +
        `请确认后端已在 8000 端口启动，并通过 http://127.0.0.1:5173 访问前端。` +
        ` 响应片段：${snippet}`,
    )
  }
  const data = (await res.json()) as T & { detail?: string }
  if (!res.ok) {
    throw new Error(data.detail || `请求失败 (${res.status})`)
  }
  return data
}

type FeedArticle = Article & {
  account: string
  is_read?: boolean
  starred?: boolean
  source?: 'crawl' | 'import'
}

const PAGE_SIZE = 40

export type ImportArticleResult = {
  status: 'created' | 'exists'
  article_id: string
  account: string
  title: string
  link: string
  message: string
}

export const useArticlesStore = defineStore('articles', () => {
  const name2fakeid = ref<Name2FakeId>({})
  const loading = ref(false)
  const error = ref<string | null>(null)

  const items = ref<FeedArticle[]>([])
  const nextCursor = ref<string | null>(null)
  const tags = ref<string[]>([])
  const loadingMore = ref(false)
  const globalTotalCount = ref(0)
  const filterTotalCount = ref(0)
  const importTotalCount = ref(0)
  const accountsList = ref<AccountInfo[]>([])

  const isSqlite = computed(() => true)
  const sqliteHasMore = computed(() => !!nextCursor.value)
  const sqliteGlobalTotalCount = globalTotalCount
  const sqliteFilterTotalCount = filterTotalCount
  const sqliteItems = items
  const sqliteNextCursor = nextCursor
  const sqliteLoadingMore = loadingMore
  const sqliteAccounts = accountsList
  const storageBackend = computed(() => 'sqlite' as const)

  async function loadTags() {
    try {
      const data = await fetchJson<{ tags: string[] }>('/api/articles/tags')
      tags.value = data.tags ?? []
    } catch {
      tags.value = []
    }
  }

  async function fetchGlobalTotal() {
    try {
      const data = await fetchJson<{ total?: number }>('/api/articles?limit=1')
      if (typeof data.total === 'number') {
        globalTotalCount.value = data.total
        return
      }
    } catch {
      /* 回退 */
    }
    globalTotalCount.value = accountsList.value.reduce(
      (s, a) => s + (a.article_count || 0),
      0,
    )
  }

  async function loadAccounts() {
    const rows = await fetchJson<
      Array<{
        name: string
        fakeid: string
        article_count: number
        latest_update_time: string
      }>
    >('/api/accounts')
    accountsList.value = rows.map((r) => ({
      name: r.name,
      fakeid: r.fakeid,
      latest_update_time: r.latest_update_time || '',
      article_count: r.article_count ?? 0,
      visible: true,
    }))
    const n2f: Name2FakeId = {}
    for (const a of accountsList.value) {
      n2f[a.name] = a.fakeid
    }
    name2fakeid.value = n2f
  }

  function buildArticlesQuery(
    filters: Partial<FilterState>,
    cursor: string | null,
    limit = PAGE_SIZE,
  ) {
    const params = new URLSearchParams()
    params.set('limit', String(limit))
    if (cursor) params.set('cursor', cursor)
    const account = filters.accounts?.[0]
    if (filters.accounts?.length === 1 && account) {
      params.set('account', account)
    }
    const tag = filters.tags?.[0]
    if (filters.tags?.length === 1 && tag && tag !== TAG_UNTAGGED) {
      params.set('tag', tag)
    }
    if (filters.dateFrom) params.set('date_from', filters.dateFrom)
    if (filters.dateTo) params.set('date_to', filters.dateTo)
    if (filters.readFilter === 'unread') params.set('read_filter', 'unread')
    if (filters.readFilter === 'bookmarked') params.set('starred_only', 'true')
    if (filters.readFilter === 'imported') params.set('import_only', 'true')
    if (filters.readFilter === 'noted') params.set('read_filter', 'noted')
    return params
  }

  async function fetchImportTotal() {
    try {
      const data = await fetchJson<{ total?: number }>(
        '/api/articles?limit=1&import_only=true',
      )
      if (typeof data.total === 'number') {
        importTotalCount.value = data.total
      }
    } catch {
      importTotalCount.value = 0
    }
  }

  async function loadArticlesPage(
    filters: Partial<FilterState>,
    options: { reset?: boolean } = {},
  ) {
    const reset = options.reset !== false
    if (reset) {
      loading.value = true
      nextCursor.value = null
    } else {
      if (!nextCursor.value || loadingMore.value) return
      loadingMore.value = true
    }
    error.value = null
    try {
      const kw = (filters.keyword || '').trim()
      let url: string
      if (kw) {
        const params = buildArticlesQuery(filters, reset ? null : nextCursor.value)
        params.set('q', kw)
        url = `/api/articles/search?${params}`
      } else {
        const params = buildArticlesQuery(filters, reset ? null : nextCursor.value)
        url = `/api/articles?${params}`
      }
      const data = await fetchJson<{
        items: FeedArticle[]
        next_cursor?: string | null
        total?: number
      }>(url)
      const pageItems = data.items || []
      if (typeof data.total === 'number') {
        filterTotalCount.value = data.total
      }
      if (reset) {
        items.value = pageItems
      } else {
        const seen = new Set(items.value.map((a) => a.id))
        for (const it of pageItems) {
          if (!seen.has(it.id)) items.value.push(it)
        }
      }
      nextCursor.value = data.next_cursor ?? null
      useReadingStore().mergeFeedStates(pageItems)
    } catch (e) {
      error.value = e instanceof Error ? e.message : '文章加载失败'
    } finally {
      loading.value = false
      loadingMore.value = false
    }
  }

  async function loadMoreArticles(filters: Partial<FilterState>) {
    await loadArticlesPage(filters, { reset: false })
  }

  async function loadData(filters?: Partial<FilterState>) {
    loading.value = true
    error.value = null
    try {
      await fetchJson<{ backend: string }>('/api/storage/backend')
      await Promise.all([loadAccounts(), loadTags(), fetchImportTotal()])
      await fetchGlobalTotal()
      await useReadingStore().syncFromServer()
      await loadArticlesPage(filters || {}, { reset: true })
    } catch (e) {
      error.value = e instanceof Error ? e.message : '数据加载失败'
    } finally {
      loading.value = false
    }
  }

  const accounts = computed(() => accountsList.value)

  const allArticles = computed<FeedArticle[]>(() =>
    isSqlite.value
      ? items.value
      : [...items.value].sort((a, b) => b.create_time.localeCompare(a.create_time)),
  )

  const allTags = computed(() => [...tags.value].sort())

  const stats = computed(() => ({
    totalArticles:
      globalTotalCount.value ||
      accountsList.value.reduce((s, a) => s + (a.article_count || 0), 0),
    totalAccounts: accountsList.value.length,
    latestTime: allArticles.value[0]?.create_time || '',
  }))

  async function reloadAccounts() {
    try {
      await loadAccounts()
    } catch {
      /* 静默 */
    }
  }

  function removeArticleLocally(_account: string, articleId: string) {
    items.value = items.value.filter((a) => a.id !== articleId)
  }

  async function importByUrl(url: string): Promise<ImportArticleResult> {
    const result = await fetchJson<ImportArticleResult>('/api/articles/import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    })
    await fetchImportTotal()
    return result
  }

  return {
    name2fakeid,
    loading,
    error,
    storageBackend,
    isSqlite,
    sqliteGlobalTotalCount,
    sqliteFilterTotalCount,
    importTotalCount,
    sqliteHasMore,
    sqliteLoadingMore,
    sqliteItems,
    sqliteNextCursor,
    sqliteAccounts,
    loadData,
    loadArticlesPage,
    loadMoreArticles,
    reloadAccounts,
    removeArticleLocally,
    fetchImportTotal,
    importByUrl,
    accounts,
    allArticles,
    allTags,
    stats,
  }
})
