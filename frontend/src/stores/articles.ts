import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Article, MessageInfo, Name2FakeId, AccountInfo } from '@/types'

export const useArticlesStore = defineStore('articles', () => {
  const messageInfo = ref<MessageInfo>({})
  const name2fakeid = ref<Name2FakeId>({})
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function loadData() {
    loading.value = true
    error.value = null
    try {
      const [msgRes, nameRes] = await Promise.all([
        fetch('/data/message_info.json'),
        fetch('/data/name2fakeid.json'),
      ])
      if (!msgRes.ok) throw new Error('无法加载文章数据')
      if (!nameRes.ok) throw new Error('无法加载公众号数据')
      messageInfo.value = await msgRes.json()
      name2fakeid.value = await nameRes.json()
    } catch (e) {
      error.value = e instanceof Error ? e.message : '数据加载失败'
    } finally {
      loading.value = false
    }
  }

  // 以 name2fakeid 为主源：所有已添加的公众号都会出现，
  // 即使还没有爬取到文章（has_articles = false）
  const accounts = computed<AccountInfo[]>(() => {
    return Object.entries(name2fakeid.value).map(([name, fakeid]) => {
      const data = messageInfo.value[name]
      const activeBlogs = data?.blogs.filter((b) => !b.is_deleted) ?? []
      return {
        name,
        fakeid,
        latest_update_time: data?.latest_update_time ?? '',
        article_count: activeBlogs.length,
        visible: true,
      }
    })
  })

  const allArticles = computed<Array<Article & { account: string }>>(() => {
    const result: Array<Article & { account: string }> = []
    for (const [account, data] of Object.entries(messageInfo.value)) {
      for (const blog of data.blogs) {
        if (!blog.is_deleted) {
          result.push({ ...blog, account })
        }
      }
    }
    return result.sort((a, b) => b.create_time.localeCompare(a.create_time))
  })

  const allTags = computed<string[]>(() => {
    const tagSet = new Set<string>()
    for (const article of allArticles.value) {
      if (article.tags) {
        article.tags.forEach((t) => tagSet.add(t))
      }
    }
    return Array.from(tagSet).sort()
  })

  const stats = computed(() => {
    const totalArticles = allArticles.value.length
    // 使用 name2fakeid 计数，反映真实添加数量
    const totalAccounts = Object.keys(name2fakeid.value).length
    const latestTime = allArticles.value[0]?.create_time || ''
    return { totalArticles, totalAccounts, latestTime }
  })

  // 通过 API 添加公众号后，刷新本地数据
  async function reloadAccounts() {
    try {
      const nameRes = await fetch('/data/name2fakeid.json')
      if (nameRes.ok) name2fakeid.value = await nameRes.json()
    } catch {
      // 静默失败，不影响页面
    }
  }

  return {
    messageInfo,
    name2fakeid,
    loading,
    error,
    loadData,
    reloadAccounts,
    accounts,
    allArticles,
    allTags,
    stats,
  }
})
