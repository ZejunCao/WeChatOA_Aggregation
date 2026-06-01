// ─────────────────────────────────────────────────────────────────────────────
// 已读 & 收藏 Store（Pinia）
//
// 已读/收藏存于 SQLite article_annotations，经 API 读写
// ─────────────────────────────────────────────────────────────────────────────

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const READING_STORAGE_KEY = 'wechat-reading'

type FeedReadingSlice = { id: string; is_read?: boolean; starred?: boolean }

function loadJsonReadingFromStorage(): { readIds: string[]; bookmarkIds: string[] } {
  try {
    const raw = localStorage.getItem(READING_STORAGE_KEY)
    if (!raw) return { readIds: [], bookmarkIds: [] }
    const data = JSON.parse(raw) as { readIds?: string[]; bookmarkIds?: string[] }
    return {
      readIds: Array.isArray(data.readIds) ? data.readIds : [],
      bookmarkIds: Array.isArray(data.bookmarkIds) ? data.bookmarkIds : [],
    }
  } catch {
    return { readIds: [], bookmarkIds: [] }
  }
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { cache: 'no-store', ...init })
  const data = (await res.json()) as T & { detail?: string }
  if (!res.ok) {
    throw new Error(data.detail || `请求失败 (${res.status})`)
  }
  return data
}

export const useReadingStore = defineStore('reading', () => {
  const readIds = ref<string[]>([])
  const bookmarkIds = ref<string[]>([])
  const serverUnreadCount = ref(0)
  const serverStarredCount = ref(0)
  const synced = ref(false)

  const readSet = computed(() => new Set(readIds.value))
  const bookmarkSet = computed(() => new Set(bookmarkIds.value))

  /** 将列表接口返回的 is_read / starred 同步到内存 */
  function mergeFeedStates(items: FeedReadingSlice[]) {
    const read = new Set(readIds.value)
    const starred = new Set(bookmarkIds.value)
    for (const it of items) {
      if (it.is_read) read.add(it.id)
      else read.delete(it.id)
      if (it.starred) starred.add(it.id)
      else starred.delete(it.id)
    }
    readIds.value = [...read]
    bookmarkIds.value = [...starred]
  }

  async function syncFromServer() {
    let state = await fetchJson<{
      read_ids: string[]
      starred_ids: string[]
      unread_count: number
      starred_count: number
    }>('/api/reading/state')

    const local = loadJsonReadingFromStorage()
    const hasLocal =
      local.readIds.length > 0 || local.bookmarkIds.length > 0
    const dbEmpty =
      state.read_ids.length === 0 && state.starred_ids.length === 0
    if (hasLocal && dbEmpty) {
      await fetchJson('/api/reading/import-local', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          read_ids: local.readIds,
          starred_ids: local.bookmarkIds,
        }),
      })
      localStorage.removeItem(READING_STORAGE_KEY)
      state = await fetchJson('/api/reading/state')
    }

    readIds.value = state.read_ids ?? []
    bookmarkIds.value = state.starred_ids ?? []
    serverUnreadCount.value = state.unread_count ?? 0
    serverStarredCount.value = state.starred_count ?? 0
    synced.value = true
  }

  function isRead(id: string) {
    return readSet.value.has(id)
  }

  async function markRead(id: string) {
    if (!readSet.value.has(id)) readIds.value.push(id)
    serverUnreadCount.value = Math.max(0, serverUnreadCount.value - 1)
    try {
      await fetchJson(`/api/articles/${encodeURIComponent(id)}/reading`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_read: true }),
      })
    } catch {
      /* 本地已更新，失败时下次 sync 纠正 */
    }
  }

  async function markUnread(id: string) {
    readIds.value = readIds.value.filter((i) => i !== id)
    serverUnreadCount.value += 1
    try {
      await fetchJson(`/api/articles/${encodeURIComponent(id)}/reading`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_read: false }),
      })
    } catch {
      /* 静默 */
    }
  }

  async function toggleRead(id: string) {
    if (isRead(id)) await markUnread(id)
    else await markRead(id)
  }

  function isBookmarked(id: string) {
    return bookmarkSet.value.has(id)
  }

  async function toggleBookmark(id: string) {
    const was = bookmarkSet.value.has(id)
    if (was) {
      bookmarkIds.value = bookmarkIds.value.filter((i) => i !== id)
      serverStarredCount.value = Math.max(0, serverStarredCount.value - 1)
    } else {
      bookmarkIds.value.push(id)
      serverStarredCount.value += 1
    }
    try {
      await fetchJson(`/api/articles/${encodeURIComponent(id)}/reading`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ starred: !was }),
      })
    } catch {
      /* 静默 */
    }
  }

  async function markAllRead(ids: string[]) {
    const existing = readSet.value
    for (const id of ids) {
      if (!existing.has(id)) readIds.value.push(id)
    }
    try {
      await fetchJson('/api/reading/mark-all-read', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ article_ids: ids }),
      })
      serverUnreadCount.value = Math.max(
        0,
        serverUnreadCount.value - ids.filter((id) => !existing.has(id)).length,
      )
    } catch {
      /* 静默 */
    }
  }

  function removeArticleTracking(id: string) {
    const wasRead = readSet.value.has(id)
    const wasStar = bookmarkSet.value.has(id)
    readIds.value = readIds.value.filter((i) => i !== id)
    bookmarkIds.value = bookmarkIds.value.filter((i) => i !== id)
    if (wasRead) serverUnreadCount.value += 1
    if (wasStar) serverStarredCount.value = Math.max(0, serverStarredCount.value - 1)
  }

  const unreadCount = computed(() =>
    synced.value ? serverUnreadCount.value : 0,
  )

  const bookmarkCount = computed(() =>
    synced.value ? serverStarredCount.value : bookmarkIds.value.length,
  )

  return {
    readIds,
    bookmarkIds,
    synced,
    isRead,
    markRead,
    markUnread,
    toggleRead,
    isBookmarked,
    toggleBookmark,
    markAllRead,
    removeArticleTracking,
    syncFromServer,
    mergeFeedStates,
    unreadCount,
    bookmarkCount,
  }
})
