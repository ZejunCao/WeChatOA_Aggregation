// ─────────────────────────────────────────────────────────────────────────────
// useFilters — 文章筛选/排序/分组组合式函数（Composable）
//
// Vue 3 的 Composable 类似 React Hook：将相关的响应式逻辑封装成一个函数，
// 供多个组件复用，避免在组件中堆积大量逻辑。
//
// 使用方：FeedView.vue（负责将结果传给 FilterBar 和文章列表）
//
// 筛选流程：
//   allArticles（全部） → 公众号可见性过滤 → 关键词/账号/标签/日期过滤
//   → 已读状态过滤 → 排序 → 分组 → groupedArticles（最终结果）
// ─────────────────────────────────────────────────────────────────────────────

import { computed, reactive } from 'vue'
import { useArticlesStore } from '@/stores/articles'
import { useConfigStore } from '@/stores/config'
import { useReadingStore } from '@/stores/reading'
import { TAG_UNTAGGED, type FilterState, type GroupBy } from '@/types'

export function useFilters() {
  const articlesStore = useArticlesStore()
  const configStore = useConfigStore()
  const readingStore = useReadingStore()

  // ── 筛选条件（reactive 使整个对象响应式，子字段变化都会触发重新计算） ──────
  const filters = reactive<FilterState>({
    keyword: '',         // 关键词（空=不过滤）
    accounts: [],        // 选中的公众号（空数组=全部）
    tags: [],            // 选中的标签（空数组=全部）
    dateFrom: '',        // 开始日期（空=不限）
    dateTo: '',          // 结束日期（空=不限）
    sortOrder: 'newest', // 默认最新优先
    groupBy: 'date',     // 默认按日期分组（最新日期在最前）
    readFilter: 'all',   // 默认显示全部
  })

  // ── 筛选后的文章列表（核心计算属性） ─────────────────────────────────────────
  const filteredArticles = computed(() => {
    // 第一步：只保留配置中未被隐藏的公众号的文章
    let list = articlesStore.allArticles.filter((a) => configStore.isVisible(a.account))

    // 第二步：公众号筛选（FilterBar 中选中了具体公众号时生效）
    if (filters.accounts.length > 0) {
      list = list.filter((a) => filters.accounts.includes(a.account))
    }

    // 第三步：关键词（SQLite 由服务端 FTS 处理，避免对已加载分页数据二次过滤）
    if (filters.keyword.trim() && !articlesStore.isSqlite) {
      const kw = filters.keyword.trim().toLowerCase()
      list = list.filter(
        (a) =>
          a.title.toLowerCase().includes(kw) ||
          a.digest.toLowerCase().includes(kw) ||
          (a.summary || '').toLowerCase().includes(kw),
      )
    }

    // 第四步：标签筛选（多选按 OR；支持“未打标签”）
    if (filters.tags.length > 0) {
      list = list.filter((a) => {
        const tags = a.tags ?? []
        const hasUntagged = tags.length === 0
        return filters.tags.some((t) => (t === TAG_UNTAGGED ? hasUntagged : tags.includes(t)))
      })
    }

    // 第五步：日期范围过滤（create_time 格式为 "YYYY-MM-DD HH:MM"，字符串可直接比较）
    if (filters.dateFrom) {
      list = list.filter((a) => a.create_time >= filters.dateFrom)
    }
    if (filters.dateTo) {
      // dateTo 只有日期没有时间，补上 23:59 确保包含当天所有文章
      list = list.filter((a) => a.create_time <= filters.dateTo + ' 23:59')
    }

    // 第六步：已读/收藏（SQLite 已由 API 筛选；JSON 模式在客户端筛）
    if (!articlesStore.isSqlite) {
      if (filters.readFilter === 'unread') {
        list = list.filter((a) => !readingStore.isRead(a.id))
      } else if (filters.readFilter === 'bookmarked') {
        list = list.filter((a) => readingStore.isBookmarked(a.id))
      }
    }
    // 'all' 时不过滤

    // 第七步：排序（默认已按最新排序，只在"最早优先"时重新排）
    if (filters.sortOrder === 'oldest') {
      // 注意：不能直接 sort list（list 是 computed 的引用），需要先展开
      list = [...list].sort((a, b) => a.create_time.localeCompare(b.create_time))
    }

    return list
  })

  // ── 分组后的文章列表（用于文章流按日期或公众号分组展示） ──────────────────
  const groupedArticles = computed(() => {
    const list = filteredArticles.value
    const groupBy: GroupBy = filters.groupBy

    // 不分组时，包装成统一格式（key/label 为空，articles 是全部）
    if (groupBy === 'none') {
      return [{ key: '', label: '', articles: list }]
    }

    // 按 key 分组（date → 取日期前 10 位；account → 取公众号名）
    const groups: Record<string, typeof list> = {}
    for (const article of list) {
      const key =
        groupBy === 'date'
          ? article.create_time.slice(0, 10)  // "YYYY-MM-DD"
          : article.account                   // 公众号名称

      if (!groups[key]) groups[key] = []
      groups[key].push(article)
    }

    // 按日期分组时倒序（最新日期在前）；按公众号分组时正序（字母序）
    return Object.entries(groups)
      .sort((a, b) => (groupBy === 'date' ? b[0].localeCompare(a[0]) : a[0].localeCompare(b[0])))
      .map(([key, articles]) => ({ key, label: key, articles }))
  })

  // ── 重置所有筛选条件 ──────────────────────────────────────────────────────
  function resetFilters() {
    filters.keyword = ''
    filters.accounts = []
    filters.tags = []
    filters.dateFrom = ''
    filters.dateTo = ''
    filters.sortOrder = 'newest'
    filters.readFilter = 'all'
    // groupBy 不重置，用户通常希望保留分组偏好
  }

  /**
   * 当前激活的筛选条件数量（用于 FilterBar 上的"已筛选"徽标）。
   * readFilter 不计入（它有独立的 Tab 展示），groupBy 也不计入。
   * 日期范围在顶栏单独可见，因此不计入"高级筛选"徽标，避免误导。
   */
  const activeFilterCount = computed(() => {
    let count = 0
    if (filters.keyword) count++
    if (filters.accounts.length) count++
    if (filters.tags.length) count++
    return count
  })

  return { filters, filteredArticles, groupedArticles, resetFilters, activeFilterCount }
}
