import { computed, reactive } from 'vue'
import { useArticlesStore } from '@/stores/articles'
import { useConfigStore } from '@/stores/config'
import type { FilterState, GroupBy } from '@/types'

export function useFilters() {
  const articlesStore = useArticlesStore()
  const configStore = useConfigStore()

  const filters = reactive<FilterState>({
    keyword: '',
    accounts: [],
    tags: [],
    dateFrom: '',
    dateTo: '',
    sortOrder: 'newest',
    groupBy: 'none',
  })

  const filteredArticles = computed(() => {
    let list = articlesStore.allArticles.filter((a) => configStore.isVisible(a.account))

    if (filters.accounts.length > 0) {
      list = list.filter((a) => filters.accounts.includes(a.account))
    }

    if (filters.keyword.trim()) {
      const kw = filters.keyword.trim().toLowerCase()
      list = list.filter(
        (a) =>
          a.title.toLowerCase().includes(kw) ||
          a.digest.toLowerCase().includes(kw) ||
          (a.summary || '').toLowerCase().includes(kw),
      )
    }

    if (filters.tags.length > 0) {
      list = list.filter((a) => filters.tags.every((t) => a.tags?.includes(t)))
    }

    if (filters.dateFrom) {
      list = list.filter((a) => a.create_time >= filters.dateFrom)
    }
    if (filters.dateTo) {
      list = list.filter((a) => a.create_time <= filters.dateTo + ' 23:59')
    }

    if (filters.sortOrder === 'oldest') {
      list = [...list].sort((a, b) => a.create_time.localeCompare(b.create_time))
    }

    return list
  })

  const groupedArticles = computed(() => {
    const list = filteredArticles.value
    const groupBy: GroupBy = filters.groupBy

    if (groupBy === 'none') {
      return [{ key: '', label: '', articles: list }]
    }

    const groups: Record<string, typeof list> = {}
    for (const article of list) {
      const key =
        groupBy === 'date'
          ? article.create_time.slice(0, 10)
          : article.account

      if (!groups[key]) groups[key] = []
      groups[key].push(article)
    }

    return Object.entries(groups)
      .sort((a, b) => (groupBy === 'date' ? b[0].localeCompare(a[0]) : a[0].localeCompare(b[0])))
      .map(([key, articles]) => ({ key, label: key, articles }))
  })

  function resetFilters() {
    filters.keyword = ''
    filters.accounts = []
    filters.tags = []
    filters.dateFrom = ''
    filters.dateTo = ''
    filters.sortOrder = 'newest'
  }

  const activeFilterCount = computed(() => {
    let count = 0
    if (filters.keyword) count++
    if (filters.accounts.length) count++
    if (filters.tags.length) count++
    if (filters.dateFrom || filters.dateTo) count++
    return count
  })

  return { filters, filteredArticles, groupedArticles, resetFilters, activeFilterCount }
}
