// ─────────────────────────────────────────────────────────────────────────────
// 文章就地预览：服务端抓取微信 HTML → iframe srcdoc（同 wechat-article-exporter）
// ─────────────────────────────────────────────────────────────────────────────

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Article } from '@/types'
import { useReadingStore } from './reading'
import { useArticlesStore } from './articles'

export type FeedArticle = Article & { account: string }

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { cache: 'no-store', ...init })
  const data = (await res.json()) as T & { detail?: string }
  if (!res.ok) {
    throw new Error(data.detail || `请求失败 (${res.status})`)
  }
  return data
}

export const useArticlePreviewStore = defineStore('articlePreview', () => {
  const open = ref(false)
  const article = ref<FeedArticle | null>(null)
  const previewHtml = ref('')
  const loading = ref(false)
  const error = ref<string | null>(null)
  const navigationIds = ref<string[]>([])

  const display = computed(() => article.value)

  const navigationIndex = computed(() => {
    const id = article.value?.id
    if (!id) return -1
    return navigationIds.value.indexOf(id)
  })

  const canGoPrev = computed(() => navigationIndex.value > 0)
  const canGoNext = computed(
    () =>
      navigationIndex.value >= 0 &&
      navigationIndex.value < navigationIds.value.length - 1,
  )

  function setNavigationIds(ids: string[]) {
    navigationIds.value = ids
  }

  async function openPreview(item: FeedArticle) {
    article.value = item
    previewHtml.value = ''
    error.value = null
    loading.value = true
    open.value = true
    void useReadingStore().markRead(item.id)

    try {
      const data = await fetchJson<{ html: string }>(
        `/api/articles/${encodeURIComponent(item.id)}/preview`,
      )
      previewHtml.value = data.html || ''
      if (!previewHtml.value.trim()) {
        error.value = '预览内容为空'
      }
    } catch (e) {
      error.value = e instanceof Error ? e.message : '加载预览失败'
    } finally {
      loading.value = false
    }
  }

  function close() {
    open.value = false
    previewHtml.value = ''
    error.value = null
  }

  function openOriginal() {
    const link = article.value?.link
    if (link) {
      window.open(link, '_blank', 'noopener,noreferrer')
    }
  }

  async function copyOriginalLink(): Promise<boolean> {
    const link = article.value?.link?.trim()
    if (!link) return false
    try {
      await navigator.clipboard.writeText(link)
      return true
    } catch {
      try {
        const ta = document.createElement('textarea')
        ta.value = link
        ta.style.position = 'fixed'
        ta.style.left = '-9999px'
        document.body.appendChild(ta)
        ta.select()
        const ok = document.execCommand('copy')
        document.body.removeChild(ta)
        return ok
      } catch {
        return false
      }
    }
  }

  function openSibling(delta: number) {
    const idx = navigationIndex.value
    if (idx < 0) return
    const nextId = navigationIds.value[idx + delta]
    if (!nextId) return
    const next = useArticlesStore().allArticles.find((a) => a.id === nextId)
    if (next) void openPreview(next)
  }

  function goPrev() {
    if (canGoPrev.value) openSibling(-1)
  }

  function goNext() {
    if (canGoNext.value) openSibling(1)
  }

  return {
    open,
    article,
    display,
    previewHtml,
    loading,
    error,
    canGoPrev,
    canGoNext,
    navigationIndex,
    navigationTotal: computed(() => navigationIds.value.length),
    setNavigationIds,
    openPreview,
    close,
    openOriginal,
    copyOriginalLink,
    goPrev,
    goNext,
  }
})
