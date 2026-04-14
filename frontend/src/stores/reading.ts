// ─────────────────────────────────────────────────────────────────────────────
// 已读 & 收藏 Store（Pinia）
//
// 职责：
//   - 记录用户已阅读过的文章 ID 列表（readIds）
//   - 记录用户收藏的文章 ID 列表（bookmarkIds）
//   - 提供已读数、收藏数的统计
//
// 持久化：
//   使用 pinia-plugin-persistedstate，自动将 readIds 和 bookmarkIds
//   保存到 localStorage（key: "wechat-reading"），刷新页面后不丢失。
//
// 性能优化：
//   ID 存为数组（方便序列化），但查询时通过 computed Set 加速（O(1) 查找）。
// ─────────────────────────────────────────────────────────────────────────────

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useArticlesStore } from './articles'

export const useReadingStore = defineStore(
  'reading',
  () => {
    // ── 状态：ID 数组（持久化到 localStorage） ────────────────────────────────
    // 用数组而非 Set，因为 JSON.stringify(Set) 会序列化为 {}
    const readIds = ref<string[]>([])
    const bookmarkIds = ref<string[]>([])

    // ── 计算 Set：用于 O(1) 查找（不直接持久化，每次从数组重建） ──────────────
    const readSet = computed(() => new Set(readIds.value))
    const bookmarkSet = computed(() => new Set(bookmarkIds.value))

    // ── 已读操作 ──────────────────────────────────────────────────────────────

    /** 判断某篇文章是否已读 */
    function isRead(id: string) {
      return readSet.value.has(id)
    }

    /** 标记为已读（幂等：已经已读则不重复添加） */
    function markRead(id: string) {
      if (!readSet.value.has(id)) readIds.value.push(id)
    }

    /** 标记为未读（从已读列表中移除） */
    function markUnread(id: string) {
      readIds.value = readIds.value.filter((i) => i !== id)
    }

    /** 切换已读/未读状态 */
    function toggleRead(id: string) {
      isRead(id) ? markUnread(id) : markRead(id)
    }

    // ── 收藏操作 ──────────────────────────────────────────────────────────────

    /** 判断某篇文章是否已收藏 */
    function isBookmarked(id: string) {
      return bookmarkSet.value.has(id)
    }

    /** 切换收藏/取消收藏状态 */
    function toggleBookmark(id: string) {
      if (bookmarkSet.value.has(id)) {
        bookmarkIds.value = bookmarkIds.value.filter((i) => i !== id)
      } else {
        bookmarkIds.value.push(id)
      }
    }

    /**
     * 将给定 ID 列表全部标为已读。
     * 用于 FeedView 的"全部已读"按钮——只标记当前筛选结果中的文章。
     */
    function markAllRead(ids: string[]) {
      const existing = readSet.value
      for (const id of ids) {
        if (!existing.has(id)) readIds.value.push(id)
      }
    }

    /** 文章从列表删除后，同步清除已读/收藏中的 id */
    function removeArticleTracking(id: string) {
      readIds.value = readIds.value.filter((i) => i !== id)
      bookmarkIds.value = bookmarkIds.value.filter((i) => i !== id)
    }

    // ── 统计 ──────────────────────────────────────────────────────────────────

    /**
     * 未读文章数：从 articlesStore 的全部文章中排除已读的。
     * 注意：在 store 内部使用另一个 store（articlesStore）是合法的，
     * 但必须在函数体内调用 useArticlesStore()，不能放在顶层（避免循环依赖）。
     */
    const unreadCount = computed(() => {
      const articlesStore = useArticlesStore()
      return articlesStore.allArticles.filter((a) => !readSet.value.has(a.id)).length
    })

    /** 收藏文章数（直接取数组长度） */
    const bookmarkCount = computed(() => bookmarkIds.value.length)

    return {
      readIds,
      bookmarkIds,
      isRead,
      markRead,
      markUnread,
      toggleRead,
      isBookmarked,
      toggleBookmark,
      markAllRead,
      removeArticleTracking,
      unreadCount,
      bookmarkCount,
    }
  },
  {
    // 持久化配置：指定 key 和存储方式（localStorage）
    persist: {
      key: 'wechat-reading',
      storage: localStorage,
    },
  },
)
