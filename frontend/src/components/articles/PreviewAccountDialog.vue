<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  X,
  Loader2,
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  RefreshCw,
} from 'lucide-vue-next'
import type { Article } from '@/types'
import { useArticlesStore } from '@/stores/articles'
import { useArticlePreviewStore } from '@/stores/articlePreview'
import { accountColor } from '@/lib/accountColor'
import { displayText } from '@/lib/displayText'
import { proxyWechatImageUrl } from '@/lib/wechatImage'

interface SearchCandidate {
  fakeid: string
  nickname: string
  alias: string
  avatar: string
  signature: string
  service_type: number
}

type LocalArticle = Article & { account: string }

const props = withDefaults(
  defineProps<{
    open: boolean
    accountName: string
    /** preview：文章预览内打开；config：配置页公众号卡片 */
    context?: 'preview' | 'config'
  }>(),
  { context: 'preview' },
)

const emit = defineEmits<{
  close: []
}>()

const router = useRouter()
const articlesStore = useArticlesStore()
const previewStore = useArticlePreviewStore()

const searchState = ref<'idle' | 'loading' | 'error'>('idle')
const searchError = ref('')
const searchResults = ref<SearchCandidate[]>([])
const selectedCandidate = ref<SearchCandidate | null>(null)
const confirmState = ref<'idle' | 'loading' | 'success' | 'error'>('idle')
const confirmError = ref('')
const panelLoading = ref(false)
const localArticles = ref<LocalArticle[]>([])
const articleTotal = ref(0)
const articleSource = ref<'wechat' | 'local'>('local')
const localArticleCount = ref(0)
const localIdSet = ref<Set<string>>(new Set())
const localLinkSet = ref<Set<string>>(new Set())
const localIndexVersion = ref(0)
const articlesFetchHint = ref('')
const articlesRefreshing = ref(false)
const pullRunning = ref(false)
const showOtherMatches = ref(false)
const avatarBroken = ref(false)

type IngestStatus = 'idle' | 'pulling' | 'done' | 'failed'
const articleIngestStatus = ref<Record<string, IngestStatus>>({})
const articleIngestError = ref<Record<string, string>>({})

const PREVIEW_DAYS = 30

const displayName = computed(() => displayText(props.accountName))
const dotColor = computed(() => accountColor(displayName.value))

const configuredAccount = computed(() =>
  articlesStore.accounts.find((a) => a.name === props.accountName.trim()),
)

const isConfigured = computed(() => !!configuredAccount.value)

const primaryCandidate = computed(() => {
  const q = props.accountName.trim()
  if (!q) return null
  const exact = searchResults.value.find((item) => item.nickname.trim() === q)
  return exact || searchResults.value[0] || null
})

const profileAvatar = computed(() => {
  if (avatarBroken.value) return ''
  const raw = primaryCandidate.value?.avatar || ''
  return proxyWechatImageUrl(raw)
})

watch(
  () => primaryCandidate.value?.avatar,
  () => {
    avatarBroken.value = false
  },
)

const profileSignature = computed(() => primaryCandidate.value?.signature?.trim() || '')

const articleCountLabel = computed(() => {
  if (panelLoading.value) return '加载中…'
  const n = articleTotal.value || localArticles.value.length
  if (n <= 0) return '暂无文章'
  if (articleSource.value === 'wechat') {
    if (localArticleCount.value > 0) {
      return `近一月 ${n} 篇 · 本地已收录 ${localArticleCount.value} 篇`
    }
    return `近一月 ${n} 篇`
  }
  return `本地已收录 ${n} 篇`
})

const followBtnLabel = computed(() => {
  if (confirmState.value === 'loading') {
    return isConfigured.value ? '移除中…' : '加入中…'
  }
  if (isConfigured.value) return '移除配置'
  return '加入配置'
})

const followBtnDisabled = computed(
  () =>
    panelLoading.value ||
    confirmState.value === 'loading' ||
    (!isConfigured.value && !primaryCandidate.value),
)

/** 多个候选且无同名精确匹配时才展示「其他匹配」 */
const showAlternateMatches = computed(() => {
  if (isConfigured.value) return false
  if (searchResults.value.length <= 1) return false
  const q = props.accountName.trim()
  if (!q) return false
  const hasExact = searchResults.value.some((item) => item.nickname.trim() === q)
  return !hasExact
})

const alternateMatchCount = computed(() => {
  if (!showAlternateMatches.value) return 0
  return searchResults.value.filter((i) => i.fakeid !== primaryCandidate.value?.fakeid).length
})

const unindexedCount = computed(() =>
  localArticles.value.filter(
    (a) => !isArticleIndexed(a) && articleIngestStatus.value[a.id] !== 'done',
  ).length,
)

const showArticleActionColumn = computed(() => articleSource.value === 'wechat')

type ArticleActionState = 'ingest' | 'retry' | 'pulling' | 'done' | 'pending'

function articleActionState(article: LocalArticle): ArticleActionState {
  const st = articleIngestStatus.value[article.id]
  if (st === 'pulling') return 'pulling'
  if (st === 'done' || isArticleIndexed(article)) return 'done'
  if (!isConfigured.value) return 'pending'
  if (st === 'failed') return 'retry'
  return 'ingest'
}

function normalizeArticleLink(url: string): string {
  const raw = (url || '').trim().split('#')[0]
  if (!raw) return ''
  try {
    const u = new URL(/^https?:\/\//i.test(raw) ? raw : `https://${raw}`)
    const host = u.hostname.replace(/^www\./, '').toLowerCase()
    if (host === 'mp.weixin.qq.com') {
      const path = u.pathname.replace(/\/$/, '') || '/'
      if (path.includes('/s/')) {
        return `https://mp.weixin.qq.com${path}`
      }
    }
    return u.toString()
  } catch {
    return raw
  }
}

function isArticleIndexed(article: { id: string; link?: string }): boolean {
  void localIndexVersion.value
  if (localIdSet.value.has(article.id)) return true
  const link = normalizeArticleLink(article.link || '')
  return !!link && localLinkSet.value.has(link)
}

function applyLocalIndexPayload(data: {
  local_ids?: string[]
  local_links?: string[]
  local_count?: number
}) {
  if (Array.isArray(data.local_ids)) {
    localIdSet.value = new Set(data.local_ids.filter(Boolean))
  }
  if (Array.isArray(data.local_links)) {
    localLinkSet.value = new Set(data.local_links.filter(Boolean))
  }
  if (typeof data.local_count === 'number') {
    localArticleCount.value = data.local_count
  }
  localIndexVersion.value++
}

function markArticleIndexed(article: { id: string; link?: string }) {
  const link = normalizeArticleLink(article.link || '')
  localIdSet.value = new Set([...localIdSet.value, article.id])
  if (link) {
    localLinkSet.value = new Set([...localLinkSet.value, link])
  }
  localIndexVersion.value++
}

function articleStatusBadge(article: { id: string; link?: string }): { text: string; cls: string; title?: string } | null {
  const st = articleIngestStatus.value[article.id]
  if (st === 'pulling') return { text: '拉取中', cls: 'is-pulling' }
  if (st === 'failed') {
    return {
      text: '失败',
      cls: 'is-failed',
      title: articleIngestError.value[article.id] || '收录失败',
    }
  }
  if (st === 'done' || isArticleIndexed(article)) {
    return { text: '已收录', cls: 'is-done' }
  }
  return null
}

const articleBadges = computed(() => {
  void localIndexVersion.value
  const out: Record<string, { text: string; cls: string; title?: string }> = {}
  for (const a of localArticles.value) {
    const badge = articleStatusBadge(a)
    if (badge) out[a.id] = badge
  }
  return out
})

function resetState() {
  searchState.value = 'idle'
  searchError.value = ''
  searchResults.value = []
  selectedCandidate.value = null
  confirmState.value = 'idle'
  confirmError.value = ''
  localArticles.value = []
  articleTotal.value = 0
  articleSource.value = 'local'
  localArticleCount.value = 0
  localIdSet.value = new Set()
  localLinkSet.value = new Set()
  localIndexVersion.value = 0
  articlesFetchHint.value = ''
  articlesRefreshing.value = false
  pullRunning.value = false
  articleIngestStatus.value = {}
  articleIngestError.value = {}
  showOtherMatches.value = false
  avatarBroken.value = false
  panelLoading.value = false
}

function close() {
  emit('close')
}

function goConfig() {
  close()
  void router.push('/config')
}

function candidateAvatar(item: SearchCandidate) {
  return proxyWechatImageUrl(item.avatar || '')
}

function articleCoverSrc(article: LocalArticle) {
  const url = (article.cover || '').trim()
  if (/^https?:\/\//i.test(url)) return proxyWechatImageUrl(url)
  return `/data/covers/${article.id.replace(/\//g, '_')}.jpg`
}

function formatArticleMeta(createTime: string) {
  const raw = (createTime || '').trim()
  if (!raw) return ''
  const d = new Date(raw.replace(' ', 'T'))
  if (Number.isNaN(d.getTime())) return raw.slice(0, 10)
  const now = new Date()
  const sameYear = d.getFullYear() === now.getFullYear()
  if (sameYear) {
    return `${d.getMonth() + 1}月${d.getDate()}日`
  }
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`
}

function articleWithinPreviewWindow(createTime: string): boolean {
  const raw = (createTime || '').trim()
  if (!raw) return true
  const d = new Date(raw.replace(' ', 'T'))
  if (Number.isNaN(d.getTime())) return true
  const cutoff = new Date()
  cutoff.setDate(cutoff.getDate() - PREVIEW_DAYS)
  cutoff.setHours(0, 0, 0, 0)
  return d >= cutoff
}

function buildAccountQuery(name: string): URLSearchParams {
  const configured = configuredAccount.value
  const fakeid =
    configured?.fakeid?.trim() ||
    primaryCandidate.value?.fakeid?.trim() ||
    ''
  const params = new URLSearchParams({ account: name })
  if (fakeid) params.set('fakeid', fakeid)
  return params
}

function canIngestArticle(article: LocalArticle): boolean {
  if (!isConfigured.value) return false
  if (isArticleIndexed(article)) return false
  const st = articleIngestStatus.value[article.id]
  return !st || st === 'failed'
}

async function fetchSearchResults(name: string): Promise<SearchCandidate[]> {
  const res = await fetch('/api/accounts/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query: name }),
  })
  const data = await res.json()
  if (!res.ok) {
    throw new Error(data.detail || '搜索失败')
  }
  return data as SearchCandidate[]
}

async function loadLocalIndex(name: string): Promise<Article[]> {
  const allItems: Article[] = []
  let cursor: string | null = null
  const ids: string[] = []
  const links: string[] = []

  for (;;) {
    const params = new URLSearchParams({ limit: '100', account: name })
    if (cursor) params.set('cursor', cursor)
    const localRes = await fetch(`/api/articles?${params.toString()}`)
    const localData = localRes.ok ? await localRes.json() : { items: [], total: 0 }
    const batch: Article[] = localData.items || []
    allItems.push(...batch)
    for (const a of batch) {
      if (a.id) ids.push(a.id)
      const link = normalizeArticleLink(a.link || '')
      if (link) links.push(link)
    }
    if (typeof localData.total === 'number') {
      localArticleCount.value = localData.total
    }
    cursor = (localData.next_cursor as string | null) || null
    if (!cursor) break
  }

  if (ids.length) localIdSet.value = new Set(ids)
  if (links.length) localLinkSet.value = new Set(links)
  localIndexVersion.value++
  return allItems
}

async function loadWechatArticles(name: string, fakeid: string): Promise<boolean> {
  const params = new URLSearchParams({
    fakeid,
    account: name,
    days: String(PREVIEW_DAYS),
  })
  const res = await fetch(`/api/accounts/preview-articles?${params.toString()}`)
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    articlesFetchHint.value =
      (data as { detail?: string }).detail || '无法从微信平台拉取最新文章，请检查凭证后重试'
    return false
  }
  const items = Array.isArray((data as { items?: Article[] }).items)
    ? (data as { items: Article[] }).items
    : []
  if (items.length === 0) {
    articlesFetchHint.value = '微信平台暂无文章'
    return false
  }
  localArticles.value = items.map((item) => ({
    ...item,
    account: name,
  }))
  articleTotal.value = localArticles.value.length
  articleSource.value = 'wechat'
  applyLocalIndexPayload(data as {
    local_ids?: string[]
    local_links?: string[]
    local_count?: number
  })
  articlesFetchHint.value = ''
  return true
}

async function refreshWechatArticles() {
  const name = props.accountName.trim()
  if (!name || articlesRefreshing.value || panelLoading.value) return

  const configured = articlesStore.accounts.find((a) => a.name === name)
  const fakeid =
    configured?.fakeid?.trim() ||
    primaryCandidate.value?.fakeid?.trim() ||
    ''
  if (!fakeid || fakeid.startsWith('import:')) return

  articlesRefreshing.value = true
  articlesFetchHint.value = ''
  try {
    await loadLocalIndex(name)
    const ok = await loadWechatArticles(name, fakeid)
    if (!ok) {
      localArticles.value = []
      articleTotal.value = 0
      articleSource.value = 'local'
    }
  } finally {
    articlesRefreshing.value = false
  }
}

async function ingestSingleArticle(
  article: LocalArticle,
  opts?: { reload?: boolean },
): Promise<boolean> {
  const name = props.accountName.trim()
  if (!name || !canIngestArticle(article)) return false
  if (articleIngestStatus.value[article.id] === 'pulling') return false

  const accountQuery = buildAccountQuery(name)
  articleIngestStatus.value[article.id] = 'pulling'
  delete articleIngestError.value[article.id]
  try {
    const ing = await fetch(`/api/accounts/ingest-article?${accountQuery}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(article),
    })
    const ingData = await ing.json().catch(() => ({}))
    if (!ing.ok) {
      articleIngestStatus.value[article.id] = 'failed'
      articleIngestError.value[article.id] =
        (ingData as { detail?: string }).detail || '收录失败'
      return false
    }
    articleIngestStatus.value[article.id] = 'done'
    markArticleIndexed(article)
    if (opts?.reload !== false) {
      await articlesStore.reloadAccounts()
    }
    return true
  } catch (e) {
    articleIngestStatus.value[article.id] = 'failed'
    articleIngestError.value[article.id] =
      e instanceof Error ? e.message : '收录失败'
    return false
  }
}

async function pullNewArticles() {
  const name = props.accountName.trim()
  if (!name || pullRunning.value || !isConfigured.value) return

  const accountQuery = buildAccountQuery(name)

  pullRunning.value = true
  articlesFetchHint.value = '正在获取待收录列表…'
  try {
    const res = await fetch(`/api/accounts/pull-candidates?${accountQuery}`)
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      articlesFetchHint.value =
        (data as { detail?: string }).detail || '获取待收录列表失败'
      return
    }

    const items = ((data as { items?: Article[] }).items || []) as Article[]
    applyLocalIndexPayload(data as {
      local_ids?: string[]
      local_links?: string[]
      local_count?: number
    })
    if (items.length === 0) {
      articlesFetchHint.value = '近一月内没有新的未收录文章'
      return
    }

    const merged = new Map<string, LocalArticle>()
    for (const a of localArticles.value) merged.set(a.id, a)
    for (const item of items) {
      merged.set(item.id, { ...item, account: name })
    }
    localArticles.value = [...merged.values()].sort((a, b) =>
      (b.create_time || '').localeCompare(a.create_time || ''),
    )
    articleTotal.value = localArticles.value.length
    articleSource.value = 'wechat'

    let okCount = 0
    for (const item of items) {
      if (isArticleIndexed(item)) continue
      articlesFetchHint.value = `正在收录：${okCount + 1} / ${items.length} 篇…`
      const ok = await ingestSingleArticle({ ...item, account: name }, { reload: false })
      if (ok) okCount++
    }

    const failCount = items.length - okCount
    articlesFetchHint.value =
      failCount > 0
        ? `拉取完成：成功 ${okCount} 篇，失败 ${failCount} 篇`
        : `拉取完成：成功收录 ${okCount} 篇`
    await articlesStore.reloadAccounts()
  } finally {
    pullRunning.value = false
  }
}

async function loadPanelData(name: string) {
  panelLoading.value = true
  searchState.value = 'loading'
  searchError.value = ''
  articlesFetchHint.value = ''
  avatarBroken.value = false

  const configured = articlesStore.accounts.find((a) => a.name === name)
  const configuredFakeid = configured?.fakeid?.trim() || ''

  try {
    let searchFailed = false
    const [searchData, localItems] = await Promise.all([
      fetchSearchResults(name).catch((e: Error) => {
        searchFailed = true
        searchError.value = e.message || '搜索失败'
        return [] as SearchCandidate[]
      }),
      loadLocalIndex(name),
    ])

    searchResults.value = searchData
    searchState.value = searchFailed ? 'error' : 'idle'

    const exact = searchData.find((item) => item.nickname.trim() === name)
    const candidate = exact || searchData[0] || null
    const fakeid =
      configuredFakeid ||
      candidate?.fakeid?.trim() ||
      ''

    if (fakeid && !fakeid.startsWith('import:')) {
      const ok = await loadWechatArticles(name, fakeid)
      if (ok) return
      // 已配置公众号：微信拉取失败时不回退本地列表，避免与「最新」混淆
      localArticles.value = []
      articleTotal.value = 0
      articleSource.value = 'local'
      return
    }

    if (!fakeid || fakeid.startsWith('import:')) {
      articlesFetchHint.value = '该公众号未加入配置，仅展示本地已收录文章'
    }

    localArticles.value = localItems
      .filter((item) => articleWithinPreviewWindow(item.create_time))
      .map((item) => ({
        ...item,
        account: name,
      }))
    articleTotal.value = localArticleCount.value
    articleSource.value = 'local'
  } catch {
    localArticles.value = []
    articleTotal.value = 0
    articleSource.value = 'local'
    articlesFetchHint.value = '文章加载失败'
  } finally {
    panelLoading.value = false
  }
}

async function confirmAdd(candidate?: SearchCandidate) {
  const target = candidate || primaryCandidate.value
  if (!target) return
  selectedCandidate.value = target
  confirmState.value = 'loading'
  confirmError.value = ''
  try {
    const res = await fetch('/api/accounts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: target.nickname, fakeid: target.fakeid }),
    })
    const data = await res.json()
    if (!res.ok) {
      confirmState.value = 'error'
      confirmError.value = data.detail || '添加失败'
      selectedCandidate.value = null
      return
    }
    confirmState.value = 'success'
    await articlesStore.reloadAccounts()
  } catch {
    confirmState.value = 'error'
    confirmError.value = '网络错误，请重试'
    selectedCandidate.value = null
  }
}

async function removeFromConfig() {
  const name = configuredAccount.value?.name || props.accountName.trim()
  if (!name) return
  confirmState.value = 'loading'
  confirmError.value = ''
  try {
    const res = await fetch(`/api/accounts/${encodeURIComponent(name)}`, {
      method: 'DELETE',
    })
    if (!res.ok && res.status !== 204) {
      const data = await res.json().catch(() => ({}))
      confirmState.value = 'error'
      confirmError.value = (data as { detail?: string }).detail || '移除失败'
      return
    }
    confirmState.value = 'idle'
    await articlesStore.reloadAccounts()
    if (props.context === 'config') {
      close()
    }
  } catch {
    confirmState.value = 'error'
    confirmError.value = '网络错误，请重试'
  }
}

function onConfigToggle() {
  if (isConfigured.value) {
    void removeFromConfig()
  } else {
    void confirmAdd()
  }
}

function openArticle(article: LocalArticle) {
  close()
  if (isArticleIndexed(article)) {
    void previewStore.openPreview(article)
    return
  }
  const link = article.link?.trim()
  if (link) {
    window.open(link, '_blank', 'noopener,noreferrer')
  }
}

watch(
  () => [props.open, props.accountName] as const,
  async ([open, name]) => {
    if (!open || !name.trim()) return
    resetState()
    panelLoading.value = true
    await loadPanelData(name.trim())
  },
)
</script>

<template>
  <Teleport to="body">
    <Transition name="preview-account-fade">
      <div
        v-if="open && accountName.trim()"
        class="wx-account-backdrop"
        @click.self="close"
      >
        <div
          class="wx-account-sheet"
          role="dialog"
          aria-modal="true"
          :aria-label="`公众号 ${displayName}`"
        >
          <header class="wx-account-topbar">
            <span class="wx-account-topbar-title">公众号</span>
            <button type="button" class="wx-account-close" aria-label="关闭" @click="close">
              <X class="h-5 w-5" />
            </button>
          </header>

          <div class="wx-account-profile">
            <div class="wx-account-profile-row">
              <div
                v-if="panelLoading"
                class="wx-account-avatar wx-account-avatar--skeleton"
                aria-hidden="true"
              />
              <img
                v-else-if="profileAvatar"
                :key="profileAvatar"
                :src="profileAvatar"
                :alt="displayName"
                class="wx-account-avatar"
                referrerpolicy="no-referrer"
                @error="avatarBroken = true"
              />
              <div
                v-else
                class="wx-account-avatar wx-account-avatar--fallback"
                :style="{ backgroundColor: dotColor }"
              >
                {{ displayName.slice(0, 2) }}
              </div>
              <div class="wx-account-profile-meta">
                <h2 class="wx-account-name">{{ displayName }}</h2>
                <p class="wx-account-count">{{ articleCountLabel }}</p>
              </div>
            </div>
            <p v-if="profileSignature" class="wx-account-signature">{{ profileSignature }}</p>
          </div>

          <div class="wx-account-action-wrap">
            <button
              type="button"
              class="wx-account-follow"
              :class="{
                'is-remove': isConfigured,
                'is-loading': confirmState === 'loading',
              }"
              :disabled="followBtnDisabled"
              @click="onConfigToggle()"
            >
              <Loader2 v-if="confirmState === 'loading'" class="h-4 w-4 animate-spin" />
              <span>{{ followBtnLabel }}</span>
            </button>
            <button
              v-if="isConfigured && context !== 'config'"
              type="button"
              class="wx-account-config-link"
              @click="goConfig"
            >
              前往配置页爬取
            </button>
          </div>

          <div
            v-if="confirmState === 'success'"
            class="wx-account-banner wx-account-banner--ok"
          >
            <CheckCircle2 class="h-4 w-4 shrink-0" />
            <p>{{ context === 'config' ? '已加入配置。' : '已加入配置，可在配置页批量爬取。' }}</p>
          </div>

          <div
            v-else-if="confirmState === 'error'"
            class="wx-account-banner wx-account-banner--err"
          >
            <AlertCircle class="h-4 w-4 shrink-0" />
            <p>{{ confirmError }}</p>
          </div>

          <div
            v-else-if="searchState === 'error' && !isConfigured"
            class="wx-account-banner wx-account-banner--err"
          >
            <AlertCircle class="h-4 w-4 shrink-0" />
            <p>{{ searchError }}</p>
          </div>

          <div
            v-if="showAlternateMatches && alternateMatchCount > 0 && !panelLoading"
            class="wx-account-other-matches"
          >
            <button
              type="button"
              class="wx-account-other-toggle"
              @click="showOtherMatches = !showOtherMatches"
            >
              <span>不是这个公众号？查看其他 {{ alternateMatchCount }} 个匹配</span>
              <ChevronUp v-if="showOtherMatches" class="h-4 w-4" />
              <ChevronDown v-else class="h-4 w-4" />
            </button>
            <div v-if="showOtherMatches" class="wx-account-other-list">
              <button
                v-for="item in searchResults.filter((i) => i.fakeid !== primaryCandidate?.fakeid)"
                :key="item.fakeid"
                type="button"
                class="wx-account-other-item"
                :disabled="confirmState === 'loading'"
                @click="confirmAdd(item)"
              >
                <img
                  v-if="candidateAvatar(item)"
                  :src="candidateAvatar(item)"
                  :alt="item.nickname"
                  class="wx-account-other-avatar"
                  referrerpolicy="no-referrer"
                />
                <span class="truncate">{{ item.nickname }}</span>
              </button>
            </div>
          </div>

          <div class="wx-account-tabs">
            <span class="wx-account-tab is-active">文章</span>
            <div class="wx-account-tab-actions">
              <button
                v-if="isConfigured && !panelLoading && (unindexedCount > 0 || pullRunning)"
                type="button"
                class="wx-account-pull-btn"
                :disabled="pullRunning || articlesRefreshing"
                title="收录近一月内尚未入库的文章（从上次已收录处增量）"
                @click="pullNewArticles"
              >
                <Loader2 v-if="pullRunning" class="h-3.5 w-3.5 animate-spin" />
                <span>{{ pullRunning ? '拉取中…' : `拉取未收录 (${unindexedCount})` }}</span>
              </button>
              <button
                v-if="isConfigured && !panelLoading"
                type="button"
                class="wx-account-refresh-btn"
                :disabled="articlesRefreshing || pullRunning"
                title="从微信平台重新拉取最新文章列表"
                @click="refreshWechatArticles"
              >
                <RefreshCw class="h-3.5 w-3.5" :class="{ 'animate-spin': articlesRefreshing }" />
                <span>{{ articlesRefreshing ? '刷新中…' : '刷新' }}</span>
              </button>
            </div>
          </div>

          <p v-if="articlesFetchHint" class="wx-account-articles-hint-bar">{{ articlesFetchHint }}</p>

          <div class="wx-account-articles">
            <div v-if="panelLoading" class="wx-account-articles-empty">
              <Loader2 class="h-5 w-5 animate-spin opacity-50" />
              <span>加载中…</span>
            </div>

            <div v-else-if="!localArticles.length" class="wx-account-articles-empty">
              <span>{{ articlesFetchHint || '暂无文章' }}</span>
              <button
                v-if="isConfigured && articlesFetchHint"
                type="button"
                class="wx-account-refresh-inline"
                :disabled="articlesRefreshing"
                @click="refreshWechatArticles"
              >
                重试拉取
              </button>
              <span v-else-if="!isConfigured" class="wx-account-articles-hint">加入配置后可在配置页批量爬取</span>
            </div>

            <div
              v-for="article in localArticles"
              :key="article.id"
              class="wx-account-article-row"
            >
              <button
                type="button"
                class="wx-account-article-open"
                @click="openArticle(article)"
              >
                <div class="wx-account-article-main">
                  <p class="wx-account-article-title">{{ displayText(article.title) || '无标题' }}</p>
                  <p class="wx-account-article-meta">
                    {{ formatArticleMeta(article.create_time) }}
                    <span
                      v-if="articleBadges[article.id]"
                      class="wx-account-article-badge"
                      :class="articleBadges[article.id]?.cls"
                      :title="articleBadges[article.id]?.title"
                    >{{ articleBadges[article.id]?.text }}</span>
                  </p>
                </div>
                <div class="wx-account-article-cover">
                  <img
                    :src="articleCoverSrc(article)"
                    :alt="article.title"
                    loading="lazy"
                    referrerpolicy="no-referrer"
                    @error="($event.target as HTMLImageElement).style.visibility = 'hidden'"
                  />
                </div>
              </button>
              <div
                v-if="showArticleActionColumn"
                class="wx-account-article-action"
              >
                <button
                  v-if="articleActionState(article) === 'ingest' || articleActionState(article) === 'retry'"
                  type="button"
                  class="wx-account-article-cache-btn"
                  :disabled="articleIngestStatus[article.id] === 'pulling' || pullRunning"
                  :title="articleActionState(article) === 'retry' ? '重试收录' : '收录到本地'"
                  @click="ingestSingleArticle(article)"
                >
                  <Loader2
                    v-if="articleIngestStatus[article.id] === 'pulling'"
                    class="h-3.5 w-3.5 animate-spin"
                  />
                  <span v-else>{{ articleActionState(article) === 'retry' ? '重试' : '收录' }}</span>
                </button>
                <span
                  v-else-if="articleActionState(article) === 'pulling'"
                  class="wx-account-article-action-status is-pulling"
                >
                  <Loader2 class="h-3.5 w-3.5 animate-spin" />
                </span>
                <span
                  v-else-if="articleActionState(article) === 'done'"
                  class="wx-account-article-action-status is-done"
                >已收录</span>
                <span
                  v-else
                  class="wx-account-article-action-status is-pending"
                >未收录</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.wx-account-backdrop {
  position: fixed;
  inset: 0;
  z-index: 350;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  background: rgba(0, 0, 0, 0.45);
  backdrop-filter: blur(4px);
}

.wx-account-sheet {
  width: 100%;
  max-width: 540px;
  height: min(88vh, 816px);
  min-height: min(88vh, 816px);
  display: flex;
  flex-direction: column;
  background: #f7f7f7;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 24px 48px rgba(0, 0, 0, 0.2);
  --wx-pad-x: 12%;
}

.dark .wx-account-sheet {
  background: #1a1a1a;
}

.wx-account-topbar {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  height: 48px;
  background: #ededed;
  flex-shrink: 0;
}

.dark .wx-account-topbar {
  background: #2c2c2c;
}

.wx-account-topbar-title {
  font-size: 15px;
  font-weight: 500;
  color: #111;
}

.dark .wx-account-topbar-title {
  color: #f5f5f5;
}

.wx-account-close {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: none;
  background: transparent;
  color: #666;
  cursor: pointer;
  border-radius: 8px;
}

.wx-account-close:hover {
  background: rgba(0, 0, 0, 0.06);
}

.wx-account-profile {
  padding: 18px var(--wx-pad-x) 10px;
  background: #fff;
}

.dark .wx-account-profile {
  background: #222;
}

.wx-account-profile-row {
  display: flex;
  align-items: center;
  gap: 14px;
}

.wx-account-avatar {
  width: 56px;
  height: 56px;
  border-radius: 8px;
  object-fit: cover;
  flex-shrink: 0;
}

.wx-account-avatar--fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 18px;
  font-weight: 700;
}

.wx-account-avatar--skeleton {
  background: linear-gradient(90deg, #ececec 25%, #f5f5f5 50%, #ececec 75%);
  background-size: 200% 100%;
  animation: wx-account-avatar-shimmer 1.1s ease-in-out infinite;
}

@keyframes wx-account-avatar-shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}

.dark .wx-account-avatar--skeleton {
  background: linear-gradient(90deg, #333 25%, #3a3a3a 50%, #333 75%);
  background-size: 200% 100%;
}

.wx-account-profile-meta {
  min-width: 0;
}

.wx-account-name {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #111;
  line-height: 1.3;
  word-break: break-all;
}

.dark .wx-account-name {
  color: #f5f5f5;
}

.wx-account-count {
  margin: 4px 0 0;
  font-size: 12px;
  color: #888;
}

.wx-account-signature {
  margin: 10px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: #666;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.dark .wx-account-signature {
  color: #aaa;
}

.wx-account-action-wrap {
  padding: 0 var(--wx-pad-x) 14px;
  background: #fff;
  border-bottom: 8px solid #f7f7f7;
}

.dark .wx-account-action-wrap {
  background: #222;
  border-bottom-color: #1a1a1a;
}

.wx-account-follow {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
  height: 40px;
  border: none;
  border-radius: 6px;
  background: #07c160;
  color: #fff;
  font-size: 15px;
  font-weight: 500;
  cursor: pointer;
  transition: opacity 0.15s;
}

.wx-account-follow:hover:not(:disabled) {
  opacity: 0.92;
}

.wx-account-follow.is-remove {
  background: #fff;
  color: #576b95;
  border: 1px solid #d9d9d9;
}

.wx-account-follow.is-remove:hover:not(:disabled) {
  opacity: 1;
  color: #fa5151;
  border-color: #fa5151;
  background: #fff;
}

.dark .wx-account-follow.is-remove {
  background: #2a2a2a;
  border-color: #444;
  color: #aaa;
}

.dark .wx-account-follow.is-remove:hover:not(:disabled) {
  color: #fa5151;
  border-color: #fa5151;
}

.wx-account-follow:disabled {
  cursor: not-allowed;
  opacity: 0.65;
}

.wx-account-config-link {
  display: block;
  width: 100%;
  margin-top: 10px;
  padding: 0;
  border: none;
  background: transparent;
  color: #576b95;
  font-size: 13px;
  cursor: pointer;
  text-align: center;
}

.wx-account-banner {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin: 0 var(--wx-pad-x) 8px;
  padding: 10px 12px;
  border-radius: 8px;
  font-size: 12px;
  line-height: 1.5;
}

.wx-account-banner--ok {
  background: rgba(7, 193, 96, 0.12);
  color: #047857;
}

.wx-account-banner--err {
  background: rgba(239, 68, 68, 0.1);
  color: #b91c1c;
}

.wx-account-other-matches {
  padding: 0 var(--wx-pad-x) 8px;
  background: #fff;
  border-bottom: 8px solid #f7f7f7;
}

.dark .wx-account-other-matches {
  background: #222;
  border-bottom-color: #1a1a1a;
}

.wx-account-other-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 8px 0;
  border: none;
  background: transparent;
  color: #576b95;
  font-size: 13px;
  cursor: pointer;
}

.wx-account-other-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-bottom: 8px;
}

.wx-account-other-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid #eee;
  background: #fafafa;
  font-size: 13px;
  color: #111;
  cursor: pointer;
}

.dark .wx-account-other-item {
  border-color: #333;
  background: #2a2a2a;
  color: #f5f5f5;
}

.wx-account-other-avatar {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  object-fit: cover;
  flex-shrink: 0;
}

.wx-account-tabs {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 0 var(--wx-pad-x);
  background: #fff;
  border-bottom: 1px solid #eee;
  flex-shrink: 0;
}

.wx-account-tab-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.wx-account-pull-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 12px;
  color: #07c160;
  transition: background-color 0.15s ease;
}

.wx-account-pull-btn:hover:not(:disabled) {
  background: rgba(7, 193, 96, 0.12);
}

.wx-account-pull-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.wx-account-refresh-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 12px;
  color: #576b95;
  transition: background-color 0.15s ease;
}

.wx-account-refresh-btn:hover:not(:disabled) {
  background: rgba(87, 107, 149, 0.1);
}

.wx-account-refresh-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.wx-account-refresh-inline {
  margin-top: 6px;
  font-size: 12px;
  color: #576b95;
  text-decoration: underline;
  text-underline-offset: 2px;
}

.wx-account-refresh-inline:disabled {
  opacity: 0.6;
}

.dark .wx-account-tabs {
  background: #222;
  border-bottom-color: #333;
}

.wx-account-tab {
  position: relative;
  padding: 10px 0;
  font-size: 14px;
  color: #888;
}

.wx-account-tab.is-active {
  color: #111;
  font-weight: 600;
}

.dark .wx-account-tab.is-active {
  color: #f5f5f5;
}

.wx-account-tab.is-active::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 2px;
  background: #111;
  border-radius: 1px;
}

.dark .wx-account-tab.is-active::after {
  background: #f5f5f5;
}

.wx-account-articles {
  flex: 1;
  min-height: 456px;
  overflow-y: auto;
  overflow-x: hidden;
  background: #fff;
  -webkit-overflow-scrolling: touch;
}

.dark .wx-account-articles {
  background: #222;
}

.wx-account-articles-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 456px;
  padding: 48px 16px;
  font-size: 14px;
  color: #999;
}

.wx-account-articles-hint {
  font-size: 12px;
  color: #bbb;
}

.wx-account-articles-hint-bar {
  margin: 0;
  padding: 8px var(--wx-pad-x) 0;
  font-size: 11px;
  line-height: 1.4;
  color: #999;
  background: #fff;
}

.dark .wx-account-articles-hint-bar {
  background: #222;
  color: #888;
}

.wx-account-article-row {
  display: flex;
  align-items: stretch;
  gap: 8px;
  width: 100%;
  padding: 10px var(--wx-pad-x);
  border-bottom: 1px solid #f0f0f0;
  background: #fff;
  transition: background 0.12s;
}

.dark .wx-account-article-row {
  background: #222;
  border-bottom-color: #333;
}

.wx-account-article-row:hover {
  background: #fafafa;
}

.dark .wx-account-article-row:hover {
  background: #2a2a2a;
}

.wx-account-article-row:last-child {
  border-bottom: none;
}

.wx-account-article-open {
  flex: 1;
  display: flex;
  align-items: flex-start;
  gap: 10px;
  min-width: 0;
  padding: 0;
  border: none;
  background: transparent;
  text-align: left;
  cursor: pointer;
}

.wx-account-article-action {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
}

.wx-account-article-action-status {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  line-height: 1.2;
  text-align: center;
  white-space: nowrap;
}

.wx-account-article-action-status.is-done {
  color: #07a050;
}

.wx-account-article-action-status.is-pending {
  color: #576b95;
}

.wx-account-article-action-status.is-pulling {
  color: #07c160;
}

.dark .wx-account-article-action-status.is-done {
  color: #2fd07a;
}

.dark .wx-account-article-action-status.is-pending {
  color: #8fa3c8;
}

.wx-account-article-cache-btn {
  flex-shrink: 0;
  padding: 3px 6px;
  border: 1px solid rgba(7, 193, 96, 0.45);
  border-radius: 4px;
  background: rgba(7, 193, 96, 0.08);
  color: #07a050;
  font-size: 11px;
  line-height: 1.2;
  cursor: pointer;
  transition: background 0.12s, border-color 0.12s;
}

.wx-account-article-cache-btn:hover:not(:disabled) {
  background: rgba(7, 193, 96, 0.16);
  border-color: rgba(7, 193, 96, 0.65);
}

.wx-account-article-cache-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.dark .wx-account-article-cache-btn {
  color: #2fd07a;
  border-color: rgba(47, 208, 122, 0.4);
  background: rgba(47, 208, 122, 0.1);
}

.wx-account-article-main {
  flex: 1;
  min-width: 0;
}

.wx-account-article-title {
  margin: 0;
  font-size: 14px;
  font-weight: 400;
  line-height: 1.45;
  color: #111;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.dark .wx-account-article-title {
  color: #f0f0f0;
}

.wx-account-article-meta {
  margin: 6px 0 0;
  font-size: 12px;
  color: #b2b2b2;
  display: flex;
  align-items: center;
  gap: 6px;
}

.wx-account-article-badge {
  display: inline-block;
  padding: 0 4px;
  border-radius: 3px;
  font-size: 10px;
  line-height: 1.5;
}

.wx-account-article-badge.is-pending {
  color: #576b95;
  background: rgba(87, 107, 149, 0.12);
}

.wx-account-article-badge.is-pulling {
  color: #07c160;
  background: rgba(7, 193, 96, 0.12);
}

.wx-account-article-badge.is-done {
  color: #07c160;
  background: rgba(7, 193, 96, 0.08);
}

.wx-account-article-badge.is-failed {
  color: #e54d42;
  background: rgba(229, 77, 66, 0.12);
  cursor: help;
}

.wx-account-article-cover {
  width: 52px;
  height: 52px;
  border-radius: 4px;
  overflow: hidden;
  flex-shrink: 0;
  background: #eee;
}

.dark .wx-account-article-cover {
  background: #333;
}

.wx-account-article-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.preview-account-fade-enter-active,
.preview-account-fade-leave-active {
  transition: opacity 0.18s ease;
}

.preview-account-fade-enter-from,
.preview-account-fade-leave-to {
  opacity: 0;
}
</style>
