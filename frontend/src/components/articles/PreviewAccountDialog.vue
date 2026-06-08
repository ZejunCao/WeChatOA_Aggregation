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

const props = defineProps<{
  open: boolean
  accountName: string
}>()

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
const articlesFetchHint = ref('')
const showOtherMatches = ref(false)
const avatarBroken = ref(false)

const ARTICLE_FETCH_LIMIT = 20

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
      return `最近 ${n} 篇 · 本地已收录 ${localArticleCount.value} 篇`
    }
    return `最近 ${n} 篇`
  }
  return `本地 ${n} 篇`
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
  articlesFetchHint.value = ''
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

async function loadPanelData(name: string) {
  panelLoading.value = true
  searchState.value = 'loading'
  searchError.value = ''
  articlesFetchHint.value = ''
  avatarBroken.value = false

  const configured = articlesStore.accounts.find((a) => a.name === name)
  const configuredFakeid = configured?.fakeid?.trim() || ''

  try {
    const localParams = new URLSearchParams({ limit: '100', account: name })
    const [searchData, localRes] = await Promise.all([
      fetchSearchResults(name).catch((e: Error) => {
        searchState.value = 'error'
        searchError.value = e.message || '搜索失败'
        return [] as SearchCandidate[]
      }),
      fetch(`/api/articles?${localParams.toString()}`),
    ])

    searchResults.value = searchData
    if (searchState.value !== 'error') {
      searchState.value = 'idle'
    }

    const localData = localRes.ok ? await localRes.json() : { items: [], total: 0 }
    const localItems: Article[] = localData.items || []
    localIdSet.value = new Set(localItems.map((a) => a.id))
    localArticleCount.value =
      typeof localData.total === 'number' ? localData.total : localIdSet.value.size

    const exact = searchData.find((item) => item.nickname.trim() === name)
    const candidate = exact || searchData[0] || null
    const fakeid =
      configuredFakeid ||
      candidate?.fakeid?.trim() ||
      ''

    if (fakeid && !fakeid.startsWith('import:')) {
      const params = new URLSearchParams({
        fakeid,
        account: name,
        limit: String(ARTICLE_FETCH_LIMIT),
      })
      const res = await fetch(`/api/accounts/preview-articles?${params.toString()}`)
      const data = await res.json()
      if (res.ok && Array.isArray(data.items) && data.items.length > 0) {
        localArticles.value = data.items.map((item: Article) => ({
          ...item,
          account: name,
        }))
        articleTotal.value = localArticles.value.length
        articleSource.value = 'wechat'
        if (typeof data.local_count === 'number') {
          localArticleCount.value = data.local_count
        }
        return
      }
      if (!res.ok) {
        articlesFetchHint.value = data.detail || '无法从微信拉取文章，以下为本地已收录'
      }
    } else if (!fakeid || fakeid.startsWith('import:')) {
      articlesFetchHint.value = '该公众号未加入配置，仅展示本地已收录文章'
    }

    localArticles.value = localItems.slice(0, ARTICLE_FETCH_LIMIT).map((item) => ({
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
  if (localIdSet.value.has(article.id)) {
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
              v-if="isConfigured"
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
            <p>已加入配置，可在配置页批量爬取。</p>
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
          </div>

          <p v-if="articlesFetchHint" class="wx-account-articles-hint-bar">{{ articlesFetchHint }}</p>

          <div class="wx-account-articles">
            <div v-if="panelLoading" class="wx-account-articles-empty">
              <Loader2 class="h-5 w-5 animate-spin opacity-50" />
              <span>加载中…</span>
            </div>

            <div v-else-if="!localArticles.length" class="wx-account-articles-empty">
              <span>暂无文章</span>
              <span v-if="!isConfigured" class="wx-account-articles-hint">加入配置后可在配置页批量爬取</span>
            </div>

            <button
              v-for="article in localArticles"
              :key="article.id"
              type="button"
              class="wx-account-article-row"
              @click="openArticle(article)"
            >
              <div class="wx-account-article-main">
                <p class="wx-account-article-title">{{ displayText(article.title) || '无标题' }}</p>
                <p class="wx-account-article-meta">
                  {{ formatArticleMeta(article.create_time) }}
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
  --wx-pad-x: 15%;
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
  gap: 24px;
  padding: 0 var(--wx-pad-x);
  background: #fff;
  border-bottom: 1px solid #eee;
  flex-shrink: 0;
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
  align-items: flex-start;
  gap: 10px;
  width: 100%;
  padding: 11px var(--wx-pad-x);
  border: none;
  border-bottom: 1px solid #f0f0f0;
  background: #fff;
  text-align: left;
  cursor: pointer;
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
}

.wx-account-article-cover {
  width: 56px;
  height: 56px;
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
