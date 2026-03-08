<script setup lang="ts">
// ─────────────────────────────────────────────────────────────────────────────
// ConfigView — 公众号管理页面
//
// 包含以下功能模块（各自独立，通过注释分隔）：
//   1. 公众号列表展示 & 可见性切换
//   2. 搜索/添加公众号（两步流程：搜索候选 → 确认添加）
//   3. 删除公众号
//   4. 立即爬取（后台任务 + 进度轮询横幅）
//   5. 缓存清理（预览弹窗 + 确认删除）
//   6. 凭证状态检测（横幅提示 + 重新检测）
//   7. 扫码登录（无头 Chrome 截图 + 前端展示弹窗）
// ─────────────────────────────────────────────────────────────────────────────

import { computed, onUnmounted, ref } from 'vue'
import {
  Settings,
  Eye,
  EyeOff,
  CheckSquare,
  Square,
  Clock,
  FileText,
  Users,
  TrendingUp,
  Search,
  Plus,
  X,
  Loader2,
  AlertCircle,
  CheckCircle2,
  Trash2,
  ChevronLeft,
  BadgeCheck,
  RefreshCw,
  CircleCheck,
  CircleX,
  Eraser,
  TriangleAlert,
  ShieldCheck,
  ShieldAlert,
  ShieldOff,
  QrCode,
} from 'lucide-vue-next'
import type { CrawlStatus, CachePreview, AuthStatus } from '@/types'
import { useArticlesStore } from '@/stores/articles'
import { useConfigStore } from '@/stores/config'

const articlesStore = useArticlesStore()
const configStore = useConfigStore()

// ── 公众号搜索（本地过滤，不调用后端） ─────────────────────────────────────
const accountSearchQuery = ref('')

// 根据搜索词过滤已添加的公众号列表
const filteredAccounts = computed(() => {
  const q = accountSearchQuery.value.trim().toLowerCase()
  return articlesStore.accounts.filter((a) => !q || a.name.toLowerCase().includes(q))
})

// 当前在文章流中可见的公众号数量（未被隐藏的）
const visibleCount = computed(
  () => articlesStore.accounts.filter((a) => configStore.isVisible(a.name)).length,
)

// 当前被隐藏的公众号数量
const hiddenCount = computed(() => articlesStore.accounts.length - visibleCount.value)

/** 全选/全不选公众号可见性 */
function toggleAll(show: boolean) {
  if (show) {
    configStore.showAll()
  } else {
    configStore.hideAll(articlesStore.accounts.map((a) => a.name))
  }
}

/** 所有公众号中最近一次爬取时间（取最大值），用于统计卡片展示 */
const latestUpdateTime = computed(() => {
  const times = articlesStore.accounts.map((a) => a.latest_update_time).filter(Boolean)
  return times.sort().reverse()[0] || '—'
})

// 公众号头像背景色（由名称首字符 charCode 取模决定，同名同色）
const accountColors = [
  '#6366f1', '#8b5cf6', '#ec4899', '#f97316', '#14b8a6', '#3b82f6', '#10b981',
  '#f59e0b', '#ef4444', '#84cc16',
]

function getColor(name: string) {
  return accountColors[name.charCodeAt(0) % accountColors.length]
}

// ── 添加公众号弹窗（两步流程） ────────────────────────────────────────────────
// 第一步（'input'）：用户输入关键词 → 调用 POST /api/accounts/search → 展示候选列表
// 第二步（'results'）：用户点击选中 → 调用 POST /api/accounts 确认添加

interface SearchCandidate {
  fakeid: string
  nickname: string
  alias: string
  avatar: string
  signature: string
  service_type: number
  verify_status?: number
}

const showAddDialog = ref(false)
const addStep = ref<'input' | 'results'>('input')  // 当前所在步骤
const searchQuery = ref('')
const searchState = ref<'idle' | 'loading' | 'error'>('idle')
const searchError = ref('')
const searchResults = ref<SearchCandidate[]>([])    // 搜索结果候选列表
const selectedCandidate = ref<SearchCandidate | null>(null)  // 正在确认添加的候选
const confirmState = ref<'idle' | 'loading' | 'success' | 'error'>('idle')
const confirmError = ref('')

function openAddDialog() {
  showAddDialog.value = true
  addStep.value = 'input'
  searchQuery.value = ''
  searchState.value = 'idle'
  searchError.value = ''
  searchResults.value = []
  selectedCandidate.value = null
  confirmState.value = 'idle'
  confirmError.value = ''
}

function closeAddDialog() {
  showAddDialog.value = false
}

function backToSearch() {
  addStep.value = 'input'
  selectedCandidate.value = null
  confirmState.value = 'idle'
  confirmError.value = ''
}

async function doSearch() {
  const q = searchQuery.value.trim()
  if (!q) return
  searchState.value = 'loading'
  searchError.value = ''
  searchResults.value = []
  try {
    const res = await fetch('/api/accounts/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: q }),
    })
    const data = await res.json()
    if (!res.ok) {
      searchState.value = 'error'
      searchError.value = data.detail || '搜索失败'
      return
    }
    searchResults.value = data
    addStep.value = 'results'
    searchState.value = 'idle'
  } catch {
    searchState.value = 'error'
    searchError.value = '无法连接到后端服务，请确认 api.py 已启动（端口 8000）'
  }
}

async function confirmAdd(candidate: SearchCandidate) {
  selectedCandidate.value = candidate
  confirmState.value = 'loading'
  confirmError.value = ''
  try {
    const res = await fetch('/api/accounts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: candidate.nickname, fakeid: candidate.fakeid }),
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
    setTimeout(() => closeAddDialog(), 1000)
  } catch {
    confirmState.value = 'error'
    confirmError.value = '网络错误，请重试'
    selectedCandidate.value = null
  }
}

function serviceTypeLabel(t: number) {
  if (t === 0) return '订阅号'
  if (t === 1) return '服务号'
  return '公众号'
}

// ── 删除公众号 ────────────────────────────────────────────────────────────────

const deletingName = ref('')  // 正在删除中的公众号名，用于显示加载状态

async function removeAccount(name: string) {
  if (!confirm(`确认从追踪列表中移除「${name}」？\n（已爬取的文章数据不会删除）`)) return
  deletingName.value = name
  try {
    const res = await fetch(`/api/accounts/${encodeURIComponent(name)}`, { method: 'DELETE' })
    if (res.ok || res.status === 204) {
      await articlesStore.reloadAccounts()  // 刷新公众号列表
      configStore.showAll()                 // 重置可见性（避免已删除账号残留在隐藏列表）
    }
  } catch {
    alert('删除失败，请确认后端服务已启动')
  } finally {
    deletingName.value = ''
  }
}

// ── 爬取任务 ─────────────────────────────────────────────────────────────────
// 流程：点击"立即爬取" → POST /api/crawl → 后端启动后台线程
//       → 前端每 800ms 轮询 GET /api/crawl/status → 展示进度横幅
//       → 爬取完成后重新加载文章数据，停止轮询

const defaultCrawlStatus: CrawlStatus = {
  running: false,
  total: 0,
  done: 0,
  current: '',
  errors: [],
  started_at: '',
  finished_at: '',
  new_articles: 0,
  auth_error: false,
}

const crawlStatus = ref<CrawlStatus>({ ...defaultCrawlStatus })
const crawlStarting = ref(false)  // 点击按钮后到后端确认启动之间的短暂 loading 状态
const showCrawlBanner = ref(false) // 是否展示进度横幅
let _pollTimer: ReturnType<typeof setInterval> | null = null

/** 轮询爬取进度，爬取完成后自动停止并刷新数据 */
async function fetchCrawlStatus() {
  try {
    const res = await fetch('/api/crawl/status')
    if (res.ok) {
      const data: CrawlStatus = await res.json()
      crawlStatus.value = data
      // 爬取完成（running=false 且有结束时间）时自动收尾
      if (!data.running && showCrawlBanner.value && data.finished_at) {
        await articlesStore.loadData()  // 重新加载文章数据，展示新爬取的内容
        stopPolling()
        // 后端在爬取结束时已更新 _auth_state，直接读缓存同步前端显示
        await loadAuthStatus()
      }
    }
  } catch { /* 忽略轮询网络错误，下次轮询会自动重试 */ }
}

function startPolling() {
  stopPolling()
  // 800ms 轮询一次，既不太频繁，又能捕捉到每个账号的进度变化
  _pollTimer = setInterval(fetchCrawlStatus, 800)
}

function stopPolling() {
  if (_pollTimer !== null) {
    clearInterval(_pollTimer)
    _pollTimer = null
  }
}

async function startCrawl() {
  crawlStarting.value = true
  try {
    const res = await fetch('/api/crawl', { method: 'POST' })
    if (res.status === 409) {
      // 后端已有爬取任务在运行（比如之前没关页面），直接接上展示进度
      showCrawlBanner.value = true
      startPolling()
      return
    }
    if (!res.ok) {
      const data = await res.json()
      alert(data.detail || '启动爬取失败')
      return
    }
    showCrawlBanner.value = true
    crawlStatus.value = { ...defaultCrawlStatus, running: true, started_at: new Date().toLocaleString() }
    // 立即查询一次，尽快拿到后端写入的 total（账号总数），
    // 避免等第一个 800ms 轮询周期才显示进度分母
    await fetchCrawlStatus()
    startPolling()
  } catch {
    alert('无法连接到后端服务，请确认 api.py 已启动（端口 8000）')
  } finally {
    crawlStarting.value = false
  }
}

/** 用户手动关闭进度横幅（不影响后台爬取任务的继续运行） */
function dismissCrawlBanner() {
  stopPolling()
  showCrawlBanner.value = false
  crawlStatus.value = { ...defaultCrawlStatus }
}

// 组件卸载时清理所有轮询定时器，避免内存泄漏
onUnmounted(() => { stopPolling(); stopLoginPoll() })

// ── 凭证状态 ──────────────────────────────────────────────────────────────────

const authStatus = ref<AuthStatus | null>(null)

/** 仅读取缓存状态，不发起微信探测（页面加载时用） */
async function loadAuthStatus() {
  try {
    const res = await fetch('/api/auth/status')
    if (res.ok) authStatus.value = await res.json()
  } catch { /* 静默 */ }
}

// 计算凭证的综合状态
const authLevel = computed<'ok' | 'warn' | 'error' | 'unknown'>(() => {
  const s = authStatus.value
  if (!s) return 'unknown'
  if (!s.has_credentials) return 'error'
  if (!s.valid && s.checked_at) return 'warn'
  return 'ok'
})

// 页面载入时只读缓存，不主动探测（避免每次进页面都发微信请求）
loadAuthStatus()

// ---------- 扫码登录 ----------

const showLoginModal = ref(false)
const loginPending = ref(false)     // 正在等待扫码
const loginError = ref('')
const qrcodeImg = ref('')           // 最新二维码截图（base64）
const qrcodeAt = ref('')            // 截图时间
const qrcodeLoading = ref(true)     // 二维码尚未就绪

let _loginPollTimer: ReturnType<typeof setInterval> | null = null
let _qrcodePollTimer: ReturnType<typeof setInterval> | null = null

function stopLoginPoll() {
  if (_loginPollTimer !== null) { clearInterval(_loginPollTimer); _loginPollTimer = null }
  if (_qrcodePollTimer !== null) { clearInterval(_qrcodePollTimer); _qrcodePollTimer = null }
}

async function fetchQrcode() {
  try {
    const res = await fetch('/api/auth/qrcode')
    if (res.ok) {
      const data = await res.json()
      qrcodeImg.value = data.img
      qrcodeAt.value = data.refreshed_at
      qrcodeLoading.value = false
    }
  } catch { /* 忽略 */ }
}

async function pollLoginStatus() {
  try {
    const res = await fetch('/api/auth/login/status')
    if (!res.ok) return
    const data = await res.json()
    if (!data.running && data.done) {
      stopLoginPoll()
      loginPending.value = false
      if (data.error) {
        loginError.value = data.error
      } else {
        showLoginModal.value = false
        await loadAuthStatus()
      }
    }
  } catch { /* 忽略 */ }
}

async function startLogin() {
  if (loginPending.value) return
  loginPending.value = true
  loginError.value = ''
  qrcodeImg.value = ''
  qrcodeLoading.value = true
  showLoginModal.value = true
  try {
    const res = await fetch('/api/auth/login', { method: 'POST' })
    if (!res.ok) {
      loginPending.value = false
      showLoginModal.value = false
      return
    }
    // 每 2 秒刷新二维码截图
    _qrcodePollTimer = setInterval(fetchQrcode, 2000)
    // 每 2 秒检查是否扫码完成
    _loginPollTimer = setInterval(pollLoginStatus, 2000)
  } catch {
    loginPending.value = false
    showLoginModal.value = false
    alert('无法连接到后端服务')
  }
}

function closeLoginModal() {
  if (loginPending.value) return   // 扫码过程中不允许关闭
  showLoginModal.value = false
  stopLoginPoll()
}

// ---------- 缓存清理 ----------

const showCacheModal = ref(false)
const cacheKeepDays = ref(90)
const cachePreview = ref<CachePreview | null>(null)
const cachePreviewLoading = ref(false)
const cacheClearLoading = ref(false)
const cacheClearDone = ref(false)

const keepDaysOptions = [
  { label: '最近 30 天', value: 30 },
  { label: '最近 60 天', value: 60 },
  { label: '最近 90 天', value: 90 },
  { label: '最近 180 天', value: 180 },
]

async function openCacheModal() {
  showCacheModal.value = true
  cacheClearDone.value = false
  await fetchCachePreview()
}

function closeCacheModal() {
  showCacheModal.value = false
  cachePreview.value = null
  cacheClearDone.value = false
}

async function fetchCachePreview() {
  cachePreviewLoading.value = true
  cachePreview.value = null
  try {
    const res = await fetch(`/api/cache/preview?keep_days=${cacheKeepDays.value}`)
    if (res.ok) cachePreview.value = await res.json()
  } catch { /* 静默 */ } finally {
    cachePreviewLoading.value = false
  }
}

async function doCacheClear() {
  if (!cachePreview.value || cachePreview.value.removable_articles === 0) return
  cacheClearLoading.value = true
  try {
    const res = await fetch('/api/cache/clear', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ keep_days: cacheKeepDays.value }),
    })
    if (res.ok) {
      cacheClearDone.value = true
      await articlesStore.loadData()
      // 刷新预览数据
      await fetchCachePreview()
    } else {
      const data = await res.json()
      alert(data.detail || '清理失败')
    }
  } catch {
    alert('无法连接到后端服务')
  } finally {
    cacheClearLoading.value = false
  }
}
</script>

<template>
  <div class="flex h-full flex-col overflow-hidden">
    <!-- Header -->
    <div class="shrink-0 border-b border-[var(--color-border)] bg-[var(--color-background)]/80 backdrop-blur-sm px-6 py-5">
      <div class="flex items-center gap-3 mb-4">
        <div class="flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--color-primary)]/10">
          <Settings class="h-5 w-5 text-[var(--color-primary)]" />
        </div>
        <div>
          <h1 class="text-lg font-semibold text-[var(--color-foreground)]">公众号管理</h1>
          <p class="text-sm text-[var(--color-muted-foreground)]">管理爬取列表，控制文章流中的显示</p>
        </div>
      </div>

      <!-- Stats bar -->
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div class="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-3">
          <div class="flex items-center gap-2 mb-1">
            <Users class="h-4 w-4 text-[var(--color-primary)]" />
            <span class="text-xs text-[var(--color-muted-foreground)]">公众号总数</span>
          </div>
          <p class="text-2xl font-bold text-[var(--color-foreground)]">{{ articlesStore.stats.totalAccounts }}</p>
        </div>
        <div class="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-3">
          <div class="flex items-center gap-2 mb-1">
            <FileText class="h-4 w-4 text-[var(--color-primary)]" />
            <span class="text-xs text-[var(--color-muted-foreground)]">文章总数</span>
          </div>
          <p class="text-2xl font-bold text-[var(--color-foreground)]">{{ articlesStore.stats.totalArticles }}</p>
        </div>
        <div class="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-3">
          <div class="flex items-center gap-2 mb-1">
            <Eye class="h-4 w-4 text-emerald-500" />
            <span class="text-xs text-[var(--color-muted-foreground)]">已显示</span>
          </div>
          <p class="text-2xl font-bold text-[var(--color-foreground)]">{{ visibleCount }}</p>
        </div>
        <div class="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-3">
          <div class="flex items-center gap-2 mb-1">
            <Clock class="h-4 w-4 text-[var(--color-primary)]" />
            <span class="text-xs text-[var(--color-muted-foreground)]">最近更新</span>
          </div>
          <p class="text-sm font-semibold text-[var(--color-foreground)] truncate">
            {{ latestUpdateTime ? latestUpdateTime.slice(0, 10) : '—' }}
          </p>
        </div>
      </div>
    </div>

    <!-- Auth status banner -->
    <div
      v-if="authLevel !== 'ok'"
      class="shrink-0 flex items-center gap-3 px-6 py-2.5 text-sm border-b"
      :class="{
        'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800 text-red-700 dark:text-red-400': authLevel === 'error',
        'bg-orange-50 dark:bg-orange-900/20 border-orange-200 dark:border-orange-800 text-orange-700 dark:text-orange-400': authLevel === 'warn',
        'bg-[var(--color-muted)]/50 border-[var(--color-border)] text-[var(--color-muted-foreground)]': authLevel === 'unknown',
      }"
    >
      <ShieldOff v-if="authLevel === 'error'" class="h-4 w-4 shrink-0" />
      <ShieldAlert v-else-if="authLevel === 'warn'" class="h-4 w-4 shrink-0" />
      <Loader2 v-else class="h-4 w-4 shrink-0 animate-spin" />

      <span v-if="authLevel === 'error'" class="flex-1">
        <strong>凭证未配置</strong>：请在 <code class="rounded bg-red-100 dark:bg-red-800/40 px-1 py-0.5 text-xs">data/id_info.json</code> 中填入有效的 token 和 cookie，或点击右侧按钮扫码登录
      </span>
      <span v-else-if="authLevel === 'warn'" class="flex-1">
        <strong>凭证可能已过期</strong>：上次爬取时出现认证错误（{{ authStatus?.error }}），可更新 <code class="rounded bg-orange-100 dark:bg-orange-800/40 px-1 py-0.5 text-xs">data/id_info.json</code> 或点击右侧按钮扫码重新登录
      </span>
      <span v-else class="flex-1 text-xs">正在检测凭证状态...</span>

      <!-- 等待扫码时显示进度提示 -->
      <span v-if="loginPending" class="shrink-0 flex items-center gap-1.5 text-xs opacity-80">
        <Loader2 class="h-3.5 w-3.5 animate-spin" />
        等待扫码，请查看弹出的浏览器窗口...
      </span>

      <button
        @click="startLogin"
        :disabled="loginPending"
        class="shrink-0 rounded-lg border px-2.5 py-1 text-xs font-medium transition-colors hover:bg-white/50 dark:hover:bg-white/10 disabled:opacity-50 disabled:cursor-not-allowed"
        :class="{
          'border-red-300 dark:border-red-700': authLevel === 'error',
          'border-orange-300 dark:border-orange-700': authLevel === 'warn',
          'border-[var(--color-border)]': authLevel === 'unknown',
        }"
      >
        {{ loginPending ? '登录中...' : '扫码登录' }}
      </button>
    </div>

    <!-- Auth status OK indicator (compact, only in toolbar) -->
    <!-- Toolbar -->
    <div class="shrink-0 border-b border-[var(--color-border)] bg-[var(--color-background)] px-6 py-3 flex items-center gap-3">
      <div class="relative flex-1 max-w-sm">
        <Search class="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--color-muted-foreground)]" />
        <input
          v-model="accountSearchQuery"
          type="text"
          placeholder="搜索公众号..."
          class="h-8 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] pl-8 pr-3 text-sm text-[var(--color-foreground)] placeholder-[var(--color-muted-foreground)] outline-none focus:border-[var(--color-ring)] focus:ring-1 focus:ring-[var(--color-ring)]"
        />
      </div>
      <button
        @click="toggleAll(true)"
        class="flex items-center gap-1.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-3 py-1.5 text-xs font-medium text-[var(--color-foreground)] hover:bg-[var(--color-accent)] transition-colors"
      >
        <CheckSquare class="h-3.5 w-3.5" />
        全选
      </button>
      <button
        @click="toggleAll(false)"
        class="flex items-center gap-1.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-3 py-1.5 text-xs font-medium text-[var(--color-muted-foreground)] hover:bg-[var(--color-accent)] hover:text-[var(--color-foreground)] transition-colors"
      >
        <Square class="h-3.5 w-3.5" />
        全不选
      </button>
      <span class="text-xs text-[var(--color-muted-foreground)]">
        显示 {{ visibleCount }}/{{ articlesStore.accounts.length }}
        <span v-if="hiddenCount > 0" class="text-orange-500 ml-1">（隐藏 {{ hiddenCount }}）</span>
      </span>
      <!-- Right actions -->
      <div class="ml-auto flex items-center gap-2">
        <!-- Auth status pill -->
        <div
          v-if="authStatus"
          class="flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-medium"
          :class="{
            'border-emerald-200 bg-emerald-50 text-emerald-600 dark:border-emerald-800 dark:bg-emerald-900/20 dark:text-emerald-400': authLevel === 'ok',
            'border-orange-200 bg-orange-50 text-orange-600 dark:border-orange-800 dark:bg-orange-900/20 dark:text-orange-400': authLevel === 'warn',
            'border-red-200 bg-red-50 text-red-600 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400': authLevel === 'error',
          }"
          :title="authLevel === 'ok'
            ? `凭证有效，token: ${authStatus.token_hint}，文件更新于 ${authStatus.id_info_mtime}`
            : authStatus.error || '凭证状态异常'"
        >
          <ShieldCheck v-if="authLevel === 'ok'" class="h-3.5 w-3.5" />
          <ShieldAlert v-else-if="authLevel === 'warn'" class="h-3.5 w-3.5" />
          <ShieldOff v-else class="h-3.5 w-3.5" />
          <span>{{ authLevel === 'ok' ? '凭证有效' : authLevel === 'warn' ? '可能过期' : '未配置' }}</span>
        </div>

        <!-- Cache clear button -->
        <button
          @click="openCacheModal"
          class="flex items-center gap-1.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-3 py-1.5 text-xs font-medium text-[var(--color-muted-foreground)] hover:bg-[var(--color-accent)] hover:text-[var(--color-foreground)] transition-colors"
        >
          <Eraser class="h-3.5 w-3.5" />
          清理缓存
        </button>
        <!-- Crawl button -->
        <button
          @click="startCrawl"
          :disabled="crawlStatus.running || crawlStarting"
          class="flex items-center gap-1.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-3 py-1.5 text-xs font-medium text-[var(--color-foreground)] hover:bg-[var(--color-accent)] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Loader2 v-if="crawlStatus.running || crawlStarting" class="h-3.5 w-3.5 animate-spin" />
          <RefreshCw v-else class="h-3.5 w-3.5" />
          {{ crawlStatus.running ? '爬取中...' : '立即爬取' }}
        </button>
        <!-- Add account button -->
        <button
          @click="openAddDialog"
          class="flex items-center gap-1.5 rounded-lg bg-[var(--color-primary)] px-3 py-1.5 text-xs font-medium text-white hover:opacity-90 transition-opacity"
        >
          <Plus class="h-3.5 w-3.5" />
          添加公众号
        </button>
      </div>
    </div>

    <!-- Crawl progress banner -->
    <Transition name="slide-down">
      <div
        v-if="showCrawlBanner"
        class="shrink-0 border-b border-[var(--color-border)] bg-[var(--color-card)] px-6 py-3"
      >
        <div class="flex items-start gap-3">
          <!-- Icon -->
          <div class="mt-0.5 shrink-0">
            <Loader2 v-if="crawlStatus.running" class="h-4 w-4 animate-spin text-[var(--color-primary)]" />
            <ShieldAlert v-else-if="crawlStatus.auth_error" class="h-4 w-4 text-red-500" />
            <CircleCheck v-else-if="crawlStatus.errors.length === 0" class="h-4 w-4 text-emerald-500" />
            <CircleX v-else class="h-4 w-4 text-orange-500" />
          </div>

          <!-- Content -->
          <div class="flex-1 min-w-0">
            <!-- Title row -->
            <div class="flex items-center justify-between gap-2 mb-1.5">
              <p class="text-sm font-medium text-[var(--color-foreground)]">
                <template v-if="crawlStatus.running">
                  正在爬取
                  <span v-if="crawlStatus.current" class="text-[var(--color-primary)]">「{{ crawlStatus.current }}」</span>
                  <span class="text-[var(--color-muted-foreground)] font-normal ml-1">（{{ crawlStatus.done }}/{{ crawlStatus.total }}）</span>
                </template>
                <template v-else-if="crawlStatus.auth_error">
                  <span class="text-red-500">凭证已失效，爬取已终止</span>
                  <span class="text-[var(--color-muted-foreground)] font-normal ml-1 text-xs">请更新 data/id_info.json 中的 token 和 cookie</span>
                </template>
                <template v-else-if="crawlStatus.finished_at">
                  爬取完成 — 新增 <span class="text-emerald-500">{{ crawlStatus.new_articles }}</span> 篇文章
                  <span v-if="crawlStatus.errors.length > 0" class="text-orange-500 ml-1">，{{ crawlStatus.errors.length }} 个账号失败</span>
                </template>
              </p>
              <button
                v-if="!crawlStatus.running"
                @click="dismissCrawlBanner"
                class="shrink-0 flex h-5 w-5 items-center justify-center rounded-md text-[var(--color-muted-foreground)] hover:bg-[var(--color-accent)] hover:text-[var(--color-foreground)] transition-colors"
              >
                <X class="h-3.5 w-3.5" />
              </button>
            </div>

            <!-- Progress bar -->
            <div v-if="crawlStatus.total > 0" class="h-1.5 w-full rounded-full bg-[var(--color-muted)] overflow-hidden">
              <div
                class="h-full rounded-full transition-all duration-500"
                :class="crawlStatus.running ? 'bg-[var(--color-primary)]' : crawlStatus.errors.length === 0 ? 'bg-emerald-500' : 'bg-orange-400'"
                :style="{ width: `${Math.round((crawlStatus.done / crawlStatus.total) * 100)}%` }"
              />
            </div>

            <!-- Error list (collapsed) -->
            <div v-if="!crawlStatus.running && crawlStatus.errors.length > 0" class="mt-2 space-y-0.5">
              <p
                v-for="err in crawlStatus.errors"
                :key="err"
                class="text-xs text-orange-500 truncate"
              >{{ err }}</p>
            </div>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Account grid -->
    <div class="flex-1 overflow-y-auto px-6 py-6">
      <div v-if="articlesStore.loading" class="flex items-center justify-center py-24 gap-3">
        <div class="h-6 w-6 animate-spin rounded-full border-2 border-[var(--color-primary)] border-t-transparent" />
        <span class="text-sm text-[var(--color-muted-foreground)]">加载中...</span>
      </div>

      <div
        v-else-if="filteredAccounts.length === 0"
        class="flex flex-col items-center justify-center py-24 gap-3"
      >
        <Users class="h-10 w-10 text-[var(--color-muted-foreground)]" />
        <p class="text-sm text-[var(--color-muted-foreground)]">还没有公众号</p>
        <button
          @click="openAddDialog"
          class="flex items-center gap-1.5 rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 transition-opacity"
        >
          <Plus class="h-4 w-4" />
          添加第一个公众号
        </button>
      </div>

      <div v-else class="grid gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        <div
          v-for="acc in filteredAccounts"
          :key="acc.name"
          class="group relative flex flex-col rounded-xl border bg-[var(--color-card)] p-4 transition-all duration-200"
          :class="
            configStore.isVisible(acc.name)
              ? 'border-[var(--color-border)] opacity-100 hover:shadow-md cursor-pointer'
              : 'border-[var(--color-border)] opacity-50 hover:shadow-md cursor-pointer'
          "
          @click="configStore.toggleAccount(acc.name)"
        >
          <!-- Visibility toggle badge -->
          <div class="absolute top-3 right-3">
            <div
              class="flex h-5 w-5 items-center justify-center rounded-full transition-colors"
              :class="
                configStore.isVisible(acc.name)
                  ? 'bg-emerald-500 text-white'
                  : 'bg-[var(--color-muted)] text-[var(--color-muted-foreground)]'
              "
            >
              <Eye v-if="configStore.isVisible(acc.name)" class="h-3 w-3" />
              <EyeOff v-else class="h-3 w-3" />
            </div>
          </div>

          <!-- Avatar -->
          <div
            class="mb-3 flex h-12 w-12 items-center justify-center rounded-xl text-white font-bold text-lg"
            :style="{ backgroundColor: getColor(acc.name) }"
          >
            {{ acc.name.slice(0, 2) }}
          </div>

          <!-- Name -->
          <h3 class="text-sm font-semibold text-[var(--color-foreground)] mb-1 pr-6 line-clamp-2">
            {{ acc.name }}
          </h3>

          <!-- "Pending" hint for newly added accounts -->
          <p
            v-if="acc.article_count === 0"
            class="text-[11px] text-[var(--color-muted-foreground)] italic"
          >待首次爬取</p>

          <!-- Meta + delete -->
          <div class="mt-auto pt-3 border-t border-[var(--color-border)]">
            <div class="flex items-center justify-between text-xs text-[var(--color-muted-foreground)]">
              <div class="flex items-center gap-1">
                <FileText class="h-3 w-3" />
                <span>{{ acc.article_count }} 篇文章</span>
              </div>
              <div v-if="acc.latest_update_time" class="flex items-center gap-1">
                <TrendingUp class="h-3 w-3" />
                <span>{{ acc.latest_update_time.slice(0, 10) }}</span>
              </div>
            </div>

            <!-- Delete button: shown on hover, in footer -->
            <button
              class="mt-2 w-full flex items-center justify-center gap-1.5 rounded-lg py-1.5 text-xs text-[var(--color-muted-foreground)] opacity-0 group-hover:opacity-100 hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-900/20 transition-all"
              :class="deletingName === acc.name ? '!opacity-100 !text-red-500' : ''"
              @click.stop="removeAccount(acc.name)"
              title="从追踪列表中移除"
            >
              <Loader2 v-if="deletingName === acc.name" class="h-3 w-3 animate-spin" />
              <Trash2 v-else class="h-3 w-3" />
              <span>{{ deletingName === acc.name ? '移除中...' : '移除' }}</span>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Add account dialog -->
    <Teleport to="body">
      <Transition
        enter-active-class="transition duration-150 ease-out"
        enter-from-class="opacity-0"
        enter-to-class="opacity-100"
        leave-active-class="transition duration-100 ease-in"
        leave-from-class="opacity-100"
        leave-to-class="opacity-0"
      >
        <div
          v-if="showAddDialog"
          class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
          @click.self="closeAddDialog"
        >
          <div class="w-full max-w-md rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] shadow-2xl overflow-hidden">

            <!-- ── Step 1: 搜索输入 ── -->
            <div v-if="addStep === 'input'" class="p-6">
              <div class="flex items-center justify-between mb-5">
                <div>
                  <h2 class="text-base font-semibold text-[var(--color-foreground)]">添加公众号</h2>
                  <p class="text-xs text-[var(--color-muted-foreground)] mt-0.5">搜索公众号名称，从结果中选择</p>
                </div>
                <button @click="closeAddDialog" class="flex h-7 w-7 items-center justify-center rounded-lg text-[var(--color-muted-foreground)] hover:bg-[var(--color-accent)] transition-colors">
                  <X class="h-4 w-4" />
                </button>
              </div>

              <div class="space-y-3">
                <div class="flex gap-2">
                  <input
                    v-model="searchQuery"
                    type="text"
                    placeholder="输入公众号名称关键词..."
                    :disabled="searchState === 'loading'"
                    class="h-10 flex-1 rounded-xl border border-[var(--color-border)] bg-[var(--color-background)] px-3 text-sm text-[var(--color-foreground)] placeholder-[var(--color-muted-foreground)] outline-none transition-colors focus:border-[var(--color-ring)] focus:ring-1 focus:ring-[var(--color-ring)] disabled:opacity-50"
                    @keydown.enter="doSearch"
                  />
                  <button
                    @click="doSearch"
                    :disabled="!searchQuery.trim() || searchState === 'loading'"
                    class="h-10 px-4 rounded-xl bg-[var(--color-primary)] text-sm font-medium text-white hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
                  >
                    <Loader2 v-if="searchState === 'loading'" class="h-4 w-4 animate-spin" />
                    <Search v-else class="h-4 w-4" />
                    <span>{{ searchState === 'loading' ? '搜索中' : '搜索' }}</span>
                  </button>
                </div>

                <div v-if="searchState === 'error'" class="flex items-start gap-2 rounded-xl bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 p-3">
                  <AlertCircle class="h-4 w-4 text-red-500 shrink-0 mt-0.5" />
                  <p class="text-xs text-red-600 dark:text-red-400">{{ searchError }}</p>
                </div>

                <p class="text-[11px] text-[var(--color-muted-foreground)] leading-relaxed">
                  需要后端服务运行中（<code class="bg-[var(--color-muted)] px-1 py-0.5 rounded">uvicorn api:app --reload</code>）且微信 token/cookie 有效。
                </p>
              </div>
            </div>

            <!-- ── Step 2: 搜索结果选择 ── -->
            <div v-else class="flex flex-col max-h-[80vh]">
              <!-- Header -->
              <div class="flex items-center gap-2 px-4 py-3 border-b border-[var(--color-border)] shrink-0">
                <button @click="backToSearch" class="flex h-7 w-7 items-center justify-center rounded-lg text-[var(--color-muted-foreground)] hover:bg-[var(--color-accent)] transition-colors">
                  <ChevronLeft class="h-4 w-4" />
                </button>
                <div class="flex-1 min-w-0">
                  <p class="text-sm font-medium text-[var(--color-foreground)] truncate">
                    "{{ searchQuery }}" 的搜索结果
                  </p>
                  <p class="text-xs text-[var(--color-muted-foreground)]">找到 {{ searchResults.length }} 个公众号，点击选择</p>
                </div>
                <button @click="closeAddDialog" class="flex h-7 w-7 items-center justify-center rounded-lg text-[var(--color-muted-foreground)] hover:bg-[var(--color-accent)] transition-colors">
                  <X class="h-4 w-4" />
                </button>
              </div>

              <!-- Success banner -->
              <div v-if="confirmState === 'success'" class="flex items-center gap-2 bg-emerald-50 dark:bg-emerald-900/20 border-b border-emerald-200 dark:border-emerald-800 px-4 py-2.5">
                <CheckCircle2 class="h-4 w-4 text-emerald-500 shrink-0" />
                <p class="text-xs text-emerald-600 dark:text-emerald-400">添加成功！下次爬取时将同步文章。</p>
              </div>

              <!-- Error banner -->
              <div v-if="confirmState === 'error'" class="flex items-start gap-2 bg-red-50 dark:bg-red-900/20 border-b border-red-200 dark:border-red-800 px-4 py-2.5">
                <AlertCircle class="h-4 w-4 text-red-500 shrink-0 mt-0.5" />
                <p class="text-xs text-red-600 dark:text-red-400">{{ confirmError }}</p>
              </div>

              <!-- Results list -->
              <div class="overflow-y-auto flex-1">
                <div
                  v-if="searchResults.length === 0"
                  class="flex flex-col items-center justify-center py-12 gap-2"
                >
                  <Search class="h-8 w-8 text-[var(--color-muted-foreground)]" />
                  <p class="text-sm text-[var(--color-muted-foreground)]">未找到相关公众号</p>
                </div>

                <button
                  v-for="item in searchResults"
                  :key="item.fakeid"
                  @click="confirmAdd(item)"
                  :disabled="confirmState === 'loading' || confirmState === 'success'"
                  class="w-full flex items-start gap-3 px-4 py-3.5 border-b border-[var(--color-border)] last:border-0 text-left transition-colors hover:bg-[var(--color-accent)] disabled:opacity-60 disabled:cursor-not-allowed"
                  :class="selectedCandidate?.fakeid === item.fakeid && confirmState === 'loading' ? 'bg-[var(--color-accent)]' : ''"
                >
                  <!-- Avatar -->
                  <div class="relative shrink-0">
                    <img
                      v-if="item.avatar"
                      :src="item.avatar"
                      :alt="item.nickname"
                      class="h-11 w-11 rounded-xl object-cover bg-[var(--color-muted)]"
                      @error="($event.target as HTMLImageElement).style.display = 'none'"
                    />
                    <div
                      v-else
                      class="h-11 w-11 rounded-xl flex items-center justify-center text-white font-bold text-base"
                      :style="{ backgroundColor: getColor(item.nickname) }"
                    >
                      {{ item.nickname.slice(0, 2) }}
                    </div>
                    <!-- Loading spinner overlay -->
                    <div
                      v-if="selectedCandidate?.fakeid === item.fakeid && confirmState === 'loading'"
                      class="absolute inset-0 flex items-center justify-center rounded-xl bg-black/30"
                    >
                      <Loader2 class="h-5 w-5 animate-spin text-white" />
                    </div>
                  </div>

                  <!-- Info -->
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-1.5 mb-0.5">
                      <span class="text-sm font-semibold text-[var(--color-foreground)] truncate">{{ item.nickname }}</span>
                      <BadgeCheck v-if="item.verify_status !== undefined" class="h-3.5 w-3.5 shrink-0 text-[var(--color-primary)]" />
                      <span class="shrink-0 rounded-full bg-[var(--color-muted)] px-1.5 py-0.5 text-[10px] text-[var(--color-muted-foreground)]">
                        {{ serviceTypeLabel(item.service_type) }}
                      </span>
                    </div>
                    <p v-if="item.alias" class="text-[11px] text-[var(--color-muted-foreground)] mb-0.5">微信号：{{ item.alias }}</p>
                    <p v-if="item.signature" class="text-xs text-[var(--color-muted-foreground)] line-clamp-2 leading-relaxed">{{ item.signature }}</p>
                  </div>

                  <!-- Already added badge -->
                  <div
                    v-if="articlesStore.name2fakeid[item.nickname]"
                    class="shrink-0 self-center text-[10px] text-emerald-500 font-medium"
                  >已添加</div>
                </button>
              </div>
            </div>

          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- ===== 清理缓存 Modal ===== -->
    <Teleport to="body">
      <Transition name="fade">
        <div
          v-if="showCacheModal"
          class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
          @click.self="closeCacheModal"
        >
          <div class="w-full max-w-md rounded-2xl bg-[var(--color-card)] border border-[var(--color-border)] shadow-2xl overflow-hidden">
            <!-- Header -->
            <div class="flex items-center justify-between px-6 py-4 border-b border-[var(--color-border)]">
              <div class="flex items-center gap-2.5">
                <Eraser class="h-5 w-5 text-[var(--color-muted-foreground)]" />
                <h2 class="text-base font-semibold text-[var(--color-foreground)]">清理历史文章缓存</h2>
              </div>
              <button @click="closeCacheModal" class="flex h-7 w-7 items-center justify-center rounded-lg text-[var(--color-muted-foreground)] hover:bg-[var(--color-accent)] transition-colors">
                <X class="h-4 w-4" />
              </button>
            </div>

            <!-- Body -->
            <div class="px-6 py-5 space-y-5">

              <!-- 保留天数选择 -->
              <div>
                <p class="text-sm font-medium text-[var(--color-foreground)] mb-3">保留最近多少天的文章？</p>
                <div class="grid grid-cols-2 gap-2">
                  <button
                    v-for="opt in keepDaysOptions"
                    :key="opt.value"
                    @click="cacheKeepDays = opt.value; fetchCachePreview()"
                    class="rounded-lg border py-2 text-sm font-medium transition-colors"
                    :class="cacheKeepDays === opt.value
                      ? 'border-[var(--color-primary)] bg-[var(--color-primary)]/10 text-[var(--color-primary)]'
                      : 'border-[var(--color-border)] bg-[var(--color-card)] text-[var(--color-muted-foreground)] hover:bg-[var(--color-accent)]'"
                  >
                    {{ opt.label }}
                  </button>
                </div>
              </div>

              <!-- 预览结果 -->
              <div class="rounded-xl border border-[var(--color-border)] bg-[var(--color-muted)]/40 p-4">
                <div v-if="cachePreviewLoading" class="flex items-center justify-center gap-2 py-2">
                  <Loader2 class="h-4 w-4 animate-spin text-[var(--color-muted-foreground)]" />
                  <span class="text-sm text-[var(--color-muted-foreground)]">计算中...</span>
                </div>
                <div v-else-if="cachePreview" class="space-y-2.5">
                  <div class="flex items-center justify-between text-sm">
                    <span class="text-[var(--color-muted-foreground)]">当前文章总数</span>
                    <span class="font-semibold text-[var(--color-foreground)]">{{ cachePreview.total_articles }} 篇</span>
                  </div>
                  <div class="flex items-center justify-between text-sm">
                    <span class="text-[var(--color-muted-foreground)]">截止日期（含）</span>
                    <span class="font-semibold text-[var(--color-foreground)]">{{ cachePreview.cutoff_date }}</span>
                  </div>
                  <div class="border-t border-[var(--color-border)] pt-2.5 space-y-2">
                    <div class="flex items-center justify-between text-sm">
                      <span class="text-[var(--color-muted-foreground)]">将删除文章记录</span>
                      <span class="font-semibold" :class="cachePreview.removable_articles > 0 ? 'text-red-500' : 'text-emerald-500'">
                        {{ cachePreview.removable_articles }} 篇
                      </span>
                    </div>
                    <div class="flex items-center justify-between text-sm">
                      <span class="text-[var(--color-muted-foreground)]">将删除封面图</span>
                      <span class="font-medium text-[var(--color-muted-foreground)]">{{ cachePreview.removable_covers }} 张</span>
                    </div>
                    <div class="flex items-center justify-between text-sm">
                      <span class="text-[var(--color-muted-foreground)]">将删除详情缓存</span>
                      <span class="font-medium text-[var(--color-muted-foreground)]">{{ cachePreview.removable_detail_texts }} 条</span>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 成功提示 -->
              <div v-if="cacheClearDone" class="flex items-center gap-2 rounded-xl bg-emerald-50 dark:bg-emerald-900/20 px-4 py-3 text-sm text-emerald-600 dark:text-emerald-400">
                <CircleCheck class="h-4 w-4 shrink-0" />
                清理完成，文章列表已刷新
              </div>

              <!-- 警告 -->
              <div v-if="cachePreview && cachePreview.removable_articles > 0 && !cacheClearDone" class="flex items-start gap-2 rounded-xl bg-orange-50 dark:bg-orange-900/20 px-4 py-3 text-xs text-orange-600 dark:text-orange-400">
                <TriangleAlert class="h-3.5 w-3.5 shrink-0 mt-0.5" />
                <span>此操作不可撤销，删除后文章需重新爬取才能恢复</span>
              </div>
            </div>

            <!-- Footer -->
            <div class="flex items-center justify-end gap-3 px-6 py-4 border-t border-[var(--color-border)]">
              <button
                @click="closeCacheModal"
                class="rounded-lg border border-[var(--color-border)] px-4 py-2 text-sm font-medium text-[var(--color-foreground)] hover:bg-[var(--color-accent)] transition-colors"
              >
                {{ cacheClearDone ? '关闭' : '取消' }}
              </button>
              <button
                v-if="!cacheClearDone"
                @click="doCacheClear"
                :disabled="cacheClearLoading || !cachePreview || cachePreview.removable_articles === 0"
                class="flex items-center gap-1.5 rounded-lg bg-red-500 px-4 py-2 text-sm font-medium text-white hover:bg-red-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Loader2 v-if="cacheClearLoading" class="h-3.5 w-3.5 animate-spin" />
                <Eraser v-else class="h-3.5 w-3.5" />
                {{ cacheClearLoading ? '清理中...' : `确认删除 ${cachePreview?.removable_articles ?? 0} 篇` }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- 扫码登录弹窗 -->
    <Teleport to="body">
      <Transition name="fade">
        <div
          v-if="showLoginModal"
          class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
          @click.self="closeLoginModal"
        >
          <div class="w-full max-w-sm rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] shadow-2xl overflow-hidden">
            <!-- 标题 -->
            <div class="flex items-center justify-between px-5 py-4 border-b border-[var(--color-border)]">
              <div class="flex items-center gap-2">
                <QrCode class="h-4 w-4 text-[var(--color-primary)]" />
                <h3 class="text-sm font-semibold text-[var(--color-foreground)]">扫码登录微信公众平台</h3>
              </div>
              <button
                v-if="!loginPending"
                @click="closeLoginModal"
                class="rounded-md p-1 text-[var(--color-muted-foreground)] hover:bg-[var(--color-muted)] transition-colors"
              >
                <X class="h-4 w-4" />
              </button>
            </div>

            <!-- 二维码区域 -->
            <div class="flex flex-col items-center gap-4 p-6">
              <!-- 加载中 -->
              <div
                v-if="qrcodeLoading"
                class="h-56 w-56 flex flex-col items-center justify-center gap-3 rounded-xl bg-[var(--color-muted)]/30 text-[var(--color-muted-foreground)]"
              >
                <Loader2 class="h-8 w-8 animate-spin" />
                <span class="text-xs">正在加载二维码...</span>
              </div>

              <!-- 二维码图片 -->
              <img
                v-else-if="qrcodeImg"
                :src="qrcodeImg"
                alt="微信登录二维码"
                class="h-56 w-56 rounded-xl object-cover border border-[var(--color-border)]"
              />

              <!-- 失败提示 -->
              <div
                v-if="loginError"
                class="w-full rounded-xl bg-red-50 dark:bg-red-900/20 px-4 py-3 text-xs text-red-600 dark:text-red-400"
              >
                {{ loginError }}
              </div>

              <div v-if="!loginError" class="text-center space-y-1">
                <p class="text-sm text-[var(--color-foreground)]">用微信扫一扫登录</p>
                <p class="text-xs text-[var(--color-muted-foreground)]">登录后 token 和 cookie 将自动保存</p>
                <p v-if="qrcodeAt" class="text-xs text-[var(--color-muted-foreground)] opacity-60">截图更新于 {{ qrcodeAt }}</p>
              </div>

              <!-- 出错后可重试 -->
              <button
                v-if="loginError"
                @click="startLogin"
                class="rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 transition-opacity"
              >
                重新尝试
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>
