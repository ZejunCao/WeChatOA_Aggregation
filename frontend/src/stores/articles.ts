// ─────────────────────────────────────────────────────────────────────────────
// 文章数据 Store（Pinia）
//
// 职责：
//   - 从本地 JSON 文件加载文章数据和公众号列表
//   - 提供计算属性（所有文章、账号列表、标签、统计）
//   - 不做持久化：数据来源是文件，刷新/重载即可获取最新
//
// 数据来源（通过 Vite 中间件从本地文件系统提供）：
//   /data/message_info.json  → 各公众号的文章列表
//   /data/name2fakeid.json   → 已跟踪的公众号名称和 fakeid
// ─────────────────────────────────────────────────────────────────────────────

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Article, MessageInfo, Name2FakeId, AccountInfo } from '@/types'

export const useArticlesStore = defineStore('articles', () => {
  // ── 原始数据（直接对应 JSON 文件结构） ──────────────────────────────────────
  const messageInfo = ref<MessageInfo>({})    // 各公众号的文章数据
  const name2fakeid = ref<Name2FakeId>({})    // 公众号名称 → fakeid 映射
  const loading = ref(false)                  // 加载中标志，供 UI 展示骨架屏
  const error = ref<string | null>(null)      // 加载失败的错误信息

  // ── 数据加载 ─────────────────────────────────────────────────────────────────
  async function loadData() {
    loading.value = true
    error.value = null
    try {
      // 并发请求两个文件，减少等待时间
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

  // ── 计算属性 ─────────────────────────────────────────────────────────────────

  /**
   * 所有已添加的公众号列表，以 name2fakeid 为主源。
   * 即使某个公众号还没有爬取到文章，也会出现在这里（article_count=0）。
   * 这保证了配置页能看到全部公众号，而不是只看到有文章的。
   */
  const accounts = computed<AccountInfo[]>(() => {
    return Object.entries(name2fakeid.value).map(([name, fakeid]) => {
      const data = messageInfo.value[name]
      // 过滤掉已被微信删除的文章，不计入有效文章数
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

  /**
   * 全部有效文章的扁平列表（跨公众号合并），附带所属公众号名称。
   * 已删除的文章不包含在内，默认按发布时间倒序排列（最新在前）。
   */
  const allArticles = computed<Array<Article & { account: string }>>(() => {
    const result: Array<Article & { account: string }> = []
    for (const [account, data] of Object.entries(messageInfo.value)) {
      for (const blog of data.blogs) {
        if (!blog.is_deleted) {
          result.push({ ...blog, account })
        }
      }
    }
    // 按发布时间倒序（字符串格式 "YYYY-MM-DD HH:MM" 可直接比较）
    return result.sort((a, b) => b.create_time.localeCompare(a.create_time))
  })

  /**
   * 所有文章中出现过的标签去重后的列表（按字母排序）。
   * 目前标签由 LLM 生成，字段为可选，暂时为空。
   */
  const allTags = computed<string[]>(() => {
    const tagSet = new Set<string>()
    for (const article of allArticles.value) {
      if (article.tags) {
        article.tags.forEach((t) => tagSet.add(t))
      }
    }
    return Array.from(tagSet).sort()
  })

  /**
   * 统计摘要数据，供配置页顶部的数据卡片展示。
   */
  const stats = computed(() => {
    const totalArticles = allArticles.value.length
    // 以 name2fakeid 计数，反映真实添加数量（而非有文章的数量）
    const totalAccounts = Object.keys(name2fakeid.value).length
    const latestTime = allArticles.value[0]?.create_time || ''
    return { totalArticles, totalAccounts, latestTime }
  })

  /**
   * 仅重新加载公众号列表（name2fakeid.json），不重新加载文章。
   * 在后端添加/删除公众号后调用，快速同步列表，不影响已加载的文章数据。
   */
  async function reloadAccounts() {
    try {
      const nameRes = await fetch('/data/name2fakeid.json')
      if (nameRes.ok) name2fakeid.value = await nameRes.json()
    } catch {
      // 静默失败，不影响页面正常显示
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
