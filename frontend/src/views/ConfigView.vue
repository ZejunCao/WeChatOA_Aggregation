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

import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
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
  ChevronDown,
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
  Sparkles,
  Info,
  ExternalLink,
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
  cancel_requested: false,
  cancelled: false,
}

const crawlStatus = ref<CrawlStatus>({ ...defaultCrawlStatus })
const crawlStarting = ref(false)  // 点击按钮后到后端确认启动之间的短暂 loading 状态
const crawlCancelling = ref(false)
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
        crawlCancelling.value = false
        // 后端在爬取结束时已更新 _auth_state，直接读缓存同步前端显示
        await loadAuthStatus()
      }
    }
  } catch { /* 忽略轮询网络错误，下次轮询会自动重试 */ }
}

/** 进入配置页时恢复爬取横幅：若后台仍在跑，自动接回进度展示 */
async function resumeCrawlBannerIfRunning() {
  await fetchCrawlStatus()
  if (crawlStatus.value.running) {
    showCrawlBanner.value = true
    startPolling()
  }
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

async function cancelCrawl() {
  if (!crawlStatus.value.running || crawlStatus.value.cancel_requested || crawlCancelling.value) return
  crawlCancelling.value = true
  try {
    const res = await fetch('/api/crawl/cancel', { method: 'POST' })
    if (!res.ok) {
      llmSaveResult.value = { ok: false, message: '取消爬取失败' }
      return
    }
    crawlStatus.value.cancel_requested = true
  } catch {
    llmSaveResult.value = { ok: false, message: '取消爬取失败' }
  } finally {
    crawlCancelling.value = false
  }
}

/** 用户手动关闭进度横幅（不影响后台爬取任务的继续运行） */
function dismissCrawlBanner() {
  stopPolling()
  showCrawlBanner.value = false
  crawlStatus.value = { ...defaultCrawlStatus }
}

// 组件卸载时清理所有轮询定时器，避免内存泄漏
onUnmounted(() => {
  stopPolling()
  stopLoginPoll()
  if (typeof window !== 'undefined') {
    window.removeEventListener('mousedown', handleGlobalMouseDown)
  }
})

// ── 凭证状态 ──────────────────────────────────────────────────────────────────

const authStatus = ref<AuthStatus | null>(null)
const AUTH_STATUS_CACHE_KEY = 'wechatoa:last_auth_status'

function restoreAuthStatusFromCache() {
  if (typeof window === 'undefined') return
  try {
    const raw = localStorage.getItem(AUTH_STATUS_CACHE_KEY)
    if (!raw) return
    authStatus.value = JSON.parse(raw) as AuthStatus
  } catch { /* 静默 */ }
}

function saveAuthStatusToCache(next: AuthStatus | null) {
  if (typeof window === 'undefined') return
  try {
    if (!next) {
      localStorage.removeItem(AUTH_STATUS_CACHE_KEY)
      return
    }
    localStorage.setItem(AUTH_STATUS_CACHE_KEY, JSON.stringify(next))
  } catch { /* 静默 */ }
}

watch(authStatus, (next) => saveAuthStatusToCache(next), { deep: true })

/** 仅读取缓存状态，不发起微信探测（页面加载时用） */
async function loadAuthStatus() {
  try {
    const res = await fetch('/api/auth/status')
    if (res.ok) authStatus.value = await res.json()
  } catch { /* 静默 */ }
}

/** 主动探测凭证有效性（会请求微信接口） */
async function checkAuthStatus() {
  try {
    const res = await fetch('/api/auth/check', { method: 'POST' })
    if (res.ok) {
      authStatus.value = await res.json()
      return
    }
  } catch { /* 静默降级 */ }
  // 探测失败时回退到缓存状态，至少展示已有提示
  await loadAuthStatus()
}

// 计算凭证的综合状态
const authLevel = computed<'ok' | 'warn' | 'error' | 'unknown'>(() => {
  const s = authStatus.value
  if (!s) return 'unknown'
  if (!s.has_credentials) return 'error'
  if (!s.valid && s.checked_at) return 'warn'
  return 'ok'
})

// ── 模型配置（data/llm_config.json）──────────────────────────────────────────
const configTab = ref<'accounts' | 'ai' | 'about'>('accounts')
const viteMode = import.meta.env.MODE

const llmProviderOptions = [
  { value: 'vllm' as const, label: 'vLLM' },
  { value: 'http_requests' as const, label: 'HTTP直连' },
]
const llmProviderMenuOpen = ref(false)
const llmTaskProfileMenuOpen = ref(false)
const llmProviderDropdownRef = ref<HTMLElement | null>(null)
const llmTaskDropdownRef = ref<HTMLElement | null>(null)

type LlmProfileItem = {
  name: string
  provider: string
  base_url: string
  model: string
  has_api_key: boolean
  api_key_hint: string
}

function normalizeLlmProvider(p: string): 'vllm' | 'http_requests' {
  return p === 'vllm' ? 'vllm' : 'http_requests'
}

function defaultLlmForm(): {
  provider: 'vllm' | 'http_requests'
  base_url: string
  model: string
  temperature: number
  max_tokens: number
  timeout_seconds: number
  top_k: number
  top_p: number
  min_p: number
  repetition_penalty: number
  presence_penalty: number
  enable_thinking: boolean
  api_key_input: string
  has_api_key: boolean
  api_key_hint: string
} {
  return {
    provider: 'http_requests',
    base_url: '',
    model: '',
    temperature: 0.2,
    max_tokens: 1024,
    timeout_seconds: 120,
    top_k: 20,
    top_p: 0.8,
    min_p: 0.0,
    repetition_penalty: 1.0,
    presence_penalty: 1.5,
    enable_thinking: false,
    api_key_input: '',
    has_api_key: false,
    api_key_hint: '',
  }
}

const llmForm = ref(defaultLlmForm())
/** 全局任务绑定（与正在编辑的 profile 无关）；仅当 API 显式返回字段时同步，避免切换配置时被误清空 */
const llmTaskProfile = ref('')
const llmCrawlLlmEnabled = ref(false)
const llmCrawlLlmMultithreadEnabled = ref(false)
const llmCrawlLlmMultithreadWorkers = ref(4)
const llmTaskBindSaving = ref(false)
let llmTaskBindPersistTimer: ReturnType<typeof setTimeout> | null = null
const llmMultithreadWorkersPersisting = ref(false)
const llmLoading = ref(false)
const llmProfileSwitching = ref(false)
const llmSaving = ref(false)
const llmTestLoading = ref(false)
const llmDiscoverLoading = ref(false)
const llmModelSuggestions = ref<string[]>([])
const llmTestResult = ref<{ ok: boolean; message: string } | null>(null)
const llmSaveResult = ref<{ ok: boolean; message: string } | null>(null)
const llmProfiles = ref<LlmProfileItem[]>([])
const llmProfileName = ref('默认配置')
const llmSelectedProfileName = ref('默认配置')
const llmCreatingNewProfile = ref(false)
const llmDeleting = ref(false)
// 保存/拉取模型 与 测试连通 并列展示时，优先显示「保存类」反馈，避免测通成功后拉列表看起来像「没反应」
const llmNotice = computed<null | { message: string; kind: 'ok' | 'error' | 'info' }>(() => {
  if (llmSaveResult.value) {
    return { message: llmSaveResult.value.message, kind: llmSaveResult.value.ok ? 'info' : 'error' }
  }
  if (llmTestResult.value) {
    return { message: llmTestResult.value.message, kind: llmTestResult.value.ok ? 'ok' : 'error' }
  }
  return null
})

const llmBaseUrlLabel = computed(() =>
  llmForm.value.provider === 'vllm'
    ? '根地址（OpenAI SDK base_url，以 /v1 结尾）'
    : '接口地址（完整 Chat Completions URL，requests POST）',
)

const llmProviderLabel = computed(() => {
  const cur = llmProviderOptions.find((x) => x.value === llmForm.value.provider)
  return cur?.label || '请选择'
})

const llmTaskProfileLabel = computed(() => {
  const cur = llmProfiles.value.find((x) => x.name === llmTaskProfile.value)
  return cur?.name || '请选择'
})

function chooseLlmProvider(v: 'vllm' | 'http_requests') {
  llmForm.value.provider = v
  llmProviderMenuOpen.value = false
}

function chooseTaskProfile(name: string) {
  llmTaskProfile.value = name
  llmTaskProfileMenuOpen.value = false
  schedulePersistLlmTaskProfiles()
}

function closeLlmDropdownMenus() {
  llmProviderMenuOpen.value = false
  llmTaskProfileMenuOpen.value = false
}

function toggleLlmProviderMenu() {
  const next = !llmProviderMenuOpen.value
  closeLlmDropdownMenus()
  llmProviderMenuOpen.value = next
}

function toggleTaskProfileMenu() {
  const next = !llmTaskProfileMenuOpen.value
  closeLlmDropdownMenus()
  llmTaskProfileMenuOpen.value = next
}

function handleGlobalMouseDown(e: MouseEvent) {
  const target = e.target as Node | null
  if (!target) return
  if (
    llmProviderDropdownRef.value?.contains(target)
    || llmTaskDropdownRef.value?.contains(target)
  ) {
    return
  }
  closeLlmDropdownMenus()
}

const llmBaseUrlPlaceholder = computed(() =>
  llmForm.value.provider === 'vllm'
    ? '例如 http://10.136.0.65:8055/v1'
    : '例如 …/v1/chat/completions 或内网 …/v2/models/llm/chat/completions',
)

const CRAWL_LLM_MULTITHREAD_PRESETS = [
  { value: 4, label: '轻量', desc: '更省资源，适合低压场景。' },
  { value: 8, label: '均衡', desc: '适合大多数场景，兼顾速度与服务器友好度。' },
  { value: 16, label: '高速', desc: '吞吐更高，建议在高性能机器使用。' },
  { value: 32, label: '极限', desc: '并发最高，仅建议在服务端余量充足时启用。' },
] as const

function normalizeCrawlLlmMultithreadWorkers(n: number): number {
  if (!Number.isFinite(n)) return CRAWL_LLM_MULTITHREAD_PRESETS[0].value
  return CRAWL_LLM_MULTITHREAD_PRESETS.reduce((best, cur) => {
    return Math.abs(cur.value - n) < Math.abs(best.value - n) ? cur : best
  }, CRAWL_LLM_MULTITHREAD_PRESETS[0]).value
}

const activeCrawlLlmMultithreadPreset = computed(() =>
  CRAWL_LLM_MULTITHREAD_PRESETS.find((p) => p.value === llmCrawlLlmMultithreadWorkers.value)
  ?? CRAWL_LLM_MULTITHREAD_PRESETS[0],
)

function syncLlmTaskBindingsFromApi(d: Record<string, unknown>) {
  if ('task_profile' in d) {
    llmTaskProfile.value = String(d.task_profile ?? '')
  }
  if ('crawl_llm_enabled' in d) {
    llmCrawlLlmEnabled.value = !!d.crawl_llm_enabled
  }
  if ('crawl_llm_multithread_enabled' in d) {
    llmCrawlLlmMultithreadEnabled.value = !!d.crawl_llm_multithread_enabled
  }
  if ('crawl_llm_multithread_workers' in d) {
    llmCrawlLlmMultithreadWorkers.value = normalizeCrawlLlmMultithreadWorkers(Number(d.crawl_llm_multithread_workers))
  }
  if (ensureLlmTaskBindingsDefaultToFirstProfile()) {
    schedulePersistLlmTaskProfiles()
  }
}

/**
 * 不再提供“与默认相同”选项：
 * 当绑定为空时，自动回填为第一个已保存配置，并触发持久化。
 */
function ensureLlmTaskBindingsDefaultToFirstProfile(): boolean {
  const first = String(llmProfiles.value[0]?.name || '').trim()
  if (!first) return false
  if (String(llmTaskProfile.value || '').trim()) return false
  llmTaskProfile.value = first
  return true
}

/** 任务模型绑定：下拉变更后防抖写入 llm_config.json（不经过右侧「保存」） */
function schedulePersistLlmTaskProfiles() {
  if (llmTaskBindPersistTimer != null) {
    clearTimeout(llmTaskBindPersistTimer)
  }
  llmTaskBindPersistTimer = window.setTimeout(() => {
    llmTaskBindPersistTimer = null
    void persistLlmTaskProfilesNow()
  }, 280)
}

async function persistLlmTaskProfilesNow() {
  llmTaskBindSaving.value = true
  llmTestResult.value = null
  try {
    const res = await fetch('/api/llm/config/task-profile', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        task_profile: llmTaskProfile.value.trim(),
      }),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      llmSaveResult.value = {
        ok: false,
        message: (data as { detail?: string }).detail || '任务模型配置保存失败',
      }
      return
    }
    syncLlmTaskBindingsFromApi(data as Record<string, unknown>)
    if (Array.isArray((data as { profiles?: unknown[] }).profiles)) {
      llmProfiles.value = (data as { profiles: LlmProfileItem[] }).profiles
    }
    llmSaveResult.value = { ok: true, message: '任务模型配置已写入文件' }
  } catch {
    llmSaveResult.value = { ok: false, message: '无法连接到后端' }
  } finally {
    llmTaskBindSaving.value = false
  }
}

function applyApiToLlmForm(d: Record<string, unknown>) {
  const b = defaultLlmForm()
  llmForm.value = {
    ...b,
    provider: normalizeLlmProvider(String(d.provider || '')),
    base_url: String(d.base_url || ''),
    model: String(d.model || ''),
    temperature: Number(d.temperature) || 0.2,
    max_tokens: Number(d.max_tokens) || 1024,
    timeout_seconds: Number(d.timeout_seconds) || 120,
    top_k: Number(d.top_k) || 20,
    top_p: Number(d.top_p) || 0.8,
    min_p: Number(d.min_p) || 0,
    repetition_penalty: Number(d.repetition_penalty) || 1,
    presence_penalty: Number(d.presence_penalty) || 1.5,
    enable_thinking: !!d.enable_thinking,
    api_key_input: '',
    has_api_key: !!d.has_api_key,
    api_key_hint: String(d.api_key_hint || ''),
  }
}

async function loadLlmConfig() {
  llmLoading.value = true
  llmTestResult.value = null
  try {
    const res = await fetch('/api/llm/config')
    if (!res.ok) return
    const d = await res.json() as Record<string, unknown>
    llmProfiles.value = Array.isArray(d.profiles) ? d.profiles as LlmProfileItem[] : []
    llmProfileName.value = String(d.profile_name || d.active_profile || '默认配置')
    llmSelectedProfileName.value = llmProfileName.value
    llmCreatingNewProfile.value = false
    applyApiToLlmForm(d)
    syncLlmTaskBindingsFromApi(d)
  } catch {
    /* 静默 */
  } finally {
    llmLoading.value = false
  }
}

watch(
  () => llmForm.value.provider,
  (p) => {
    if (p === 'http_requests') {
      llmModelSuggestions.value = []
    }
  },
)

async function saveLlmConfig(showFeedback = true): Promise<boolean> {
  llmSaving.value = true
  if (showFeedback) {
    llmSaveResult.value = null
    llmTestResult.value = null
  }
  try {
    const profileName = llmProfileName.value.trim() || '默认配置'
    const sourceProfileName = llmCreatingNewProfile.value
      ? ''
      : (llmSelectedProfileName.value.trim() || profileName)
    const body: Record<string, unknown> = {
      profile_name: profileName,
      source_profile_name: sourceProfileName || null,
      set_active: true,
      provider: llmForm.value.provider,
      base_url: llmForm.value.base_url.trim(),
      model: llmForm.value.model.trim(),
      task_profile: llmTaskProfile.value.trim(),
      crawl_llm_enabled: llmCrawlLlmEnabled.value,
      crawl_llm_multithread_enabled: llmCrawlLlmMultithreadEnabled.value,
      crawl_llm_multithread_workers: normalizeCrawlLlmMultithreadWorkers(llmCrawlLlmMultithreadWorkers.value),
      temperature: llmForm.value.temperature,
      max_tokens: llmForm.value.max_tokens,
      timeout_seconds: llmForm.value.timeout_seconds,
      top_k: llmForm.value.top_k,
      top_p: llmForm.value.top_p,
      min_p: llmForm.value.min_p,
      repetition_penalty: llmForm.value.repetition_penalty,
      presence_penalty: llmForm.value.presence_penalty,
      enable_thinking: llmForm.value.enable_thinking,
    }
    if (llmForm.value.api_key_input.trim()) {
      body.api_key = llmForm.value.api_key_input.trim()
    } else {
      body.api_key = null
    }
    const res = await fetch('/api/llm/config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      if (showFeedback) llmSaveResult.value = { ok: false, message: (data as { detail?: string }).detail || '保存失败' }
      return false
    }
    llmForm.value.api_key_input = ''
    llmProfiles.value = Array.isArray((data as { profiles?: unknown[] }).profiles)
      ? ((data as { profiles: LlmProfileItem[] }).profiles)
      : llmProfiles.value
    llmProfileName.value = String((data as { profile_name?: string }).profile_name || profileName)
    llmSelectedProfileName.value = llmProfileName.value
    llmCreatingNewProfile.value = false
    llmForm.value.has_api_key = !!data.has_api_key
    llmForm.value.api_key_hint = data.api_key_hint || ''
    syncLlmTaskBindingsFromApi(data as Record<string, unknown>)
    if (showFeedback) llmSaveResult.value = { ok: true, message: 'LLM 配置已保存' }
    return true
  } catch {
    if (showFeedback) llmSaveResult.value = { ok: false, message: '无法连接到后端' }
    return false
  } finally {
    llmSaving.value = false
  }
}

async function toggleLlmEnabledForCrawl() {
  llmSaveResult.value = null
  llmTestResult.value = null
  llmSaving.value = true
  try {
    const res = await fetch('/api/llm/config/crawl-llm-enabled', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ crawl_llm_enabled: llmCrawlLlmEnabled.value }),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      llmSaveResult.value = {
        ok: false,
        message: (data as { detail?: string }).detail || '爬取模型开关保存失败',
      }
      return
    }
    syncLlmTaskBindingsFromApi(data as Record<string, unknown>)
    llmSaveResult.value = { ok: true, message: '爬取模型开关已保存' }
  } catch {
    llmSaveResult.value = { ok: false, message: '爬取模型开关保存失败' }
  } finally {
    llmSaving.value = false
  }
}

function selectCrawlLlmMultithreadPreset(value: number) {
  if (!llmCrawlLlmEnabled.value || !llmCrawlLlmMultithreadEnabled.value) return
  const next = normalizeCrawlLlmMultithreadWorkers(value)
  if (next === llmCrawlLlmMultithreadWorkers.value) return
  llmCrawlLlmMultithreadWorkers.value = next
  void persistCrawlLlmMultithreadWorkersNow()
}

async function persistCrawlLlmMultithreadWorkersNow() {
  if (!llmCrawlLlmEnabled.value || !llmCrawlLlmMultithreadEnabled.value) return
  const w = normalizeCrawlLlmMultithreadWorkers(llmCrawlLlmMultithreadWorkers.value)
  llmCrawlLlmMultithreadWorkers.value = w
  llmMultithreadWorkersPersisting.value = true
  llmTestResult.value = null
  try {
    const res = await fetch('/api/llm/config/crawl-llm-multithread-enabled', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ crawl_llm_multithread_workers: w }),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      llmSaveResult.value = {
        ok: false,
        message: (data as { detail?: string }).detail || '多线程并发数保存失败',
      }
      return
    }
    syncLlmTaskBindingsFromApi(data as Record<string, unknown>)
    llmSaveResult.value = { ok: true, message: '多线程并发数已保存' }
  } catch {
    llmSaveResult.value = { ok: false, message: '多线程并发数保存失败' }
  } finally {
    llmMultithreadWorkersPersisting.value = false
  }
}

async function toggleLlmMultithreadForCrawl() {
  llmSaveResult.value = null
  llmTestResult.value = null
  llmSaving.value = true
  try {
    const res = await fetch('/api/llm/config/crawl-llm-multithread-enabled', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        crawl_llm_multithread_enabled: llmCrawlLlmMultithreadEnabled.value,
        crawl_llm_multithread_workers: normalizeCrawlLlmMultithreadWorkers(llmCrawlLlmMultithreadWorkers.value),
      }),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      llmSaveResult.value = {
        ok: false,
        message: (data as { detail?: string }).detail || '多线程开关保存失败',
      }
      return
    }
    syncLlmTaskBindingsFromApi(data as Record<string, unknown>)
    llmSaveResult.value = { ok: true, message: '多线程开关已保存' }
  } catch {
    llmSaveResult.value = { ok: false, message: '多线程开关保存失败' }
  } finally {
    llmSaving.value = false
  }
}

async function resetCurrentLlmConfig() {
  const selectedName = llmSelectedProfileName.value.trim() || llmProfileName.value.trim() || '默认配置'
  llmSaving.value = true
  llmSaveResult.value = null
  llmTestResult.value = null
  try {
    const res = await fetch('/api/llm/config/reset', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ profile_name: selectedName }),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      llmSaveResult.value = { ok: false, message: (data as { detail?: string }).detail || '重置失败' }
      return
    }
    llmForm.value.api_key_input = ''
    llmProfiles.value = Array.isArray((data as { profiles?: unknown[] }).profiles)
      ? ((data as { profiles: LlmProfileItem[] }).profiles)
      : llmProfiles.value
    llmProfileName.value = String((data as { profile_name?: string; active_profile?: string }).profile_name || (data as { active_profile?: string }).active_profile || '默认配置')
    llmSelectedProfileName.value = llmProfileName.value
    llmCreatingNewProfile.value = false
    applyApiToLlmForm(data as Record<string, unknown>)
    syncLlmTaskBindingsFromApi(data as Record<string, unknown>)
    llmSaveResult.value = { ok: true, message: `已重置当前配置「${selectedName}」` }
  } catch {
    llmSaveResult.value = { ok: false, message: '无法连接到后端' }
  } finally {
    llmSaving.value = false
  }
}

function _llmTestBodyFromForm(): Record<string, unknown> {
  const body: Record<string, unknown> = {
    provider: llmForm.value.provider,
    temperature: llmForm.value.temperature,
    max_tokens: llmForm.value.max_tokens,
    timeout_seconds: llmForm.value.timeout_seconds,
    top_k: llmForm.value.top_k,
    top_p: llmForm.value.top_p,
    min_p: llmForm.value.min_p,
    repetition_penalty: llmForm.value.repetition_penalty,
    presence_penalty: llmForm.value.presence_penalty,
    enable_thinking: llmForm.value.enable_thinking,
  }
  const bu = llmForm.value.base_url.trim()
  const md = llmForm.value.model.trim()
  if (bu) body.base_url = bu
  if (md) body.model = md
  if (llmForm.value.api_key_input.trim()) body.api_key = llmForm.value.api_key_input.trim()
  return body
}

async function testLlmConnection() {
  llmTestLoading.value = true
  llmTestResult.value = null
  llmSaveResult.value = null
  try {
    const res = await fetch('/api/llm/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(_llmTestBodyFromForm()),
    })
    const data = await res.json().catch(() => ({}))
    if (res.status === 400) {
      const det = (data as { detail?: unknown }).detail
      let msg = '请求失败'
      if (typeof det === 'string') msg = det
      else if (Array.isArray(det) && det[0] && typeof (det[0] as { msg?: string }).msg === 'string') {
        msg = (det[0] as { msg: string }).msg
      }
      llmTestResult.value = { ok: false, message: msg }
      return
    }
    llmTestResult.value = {
      ok: !!(data as { ok?: boolean }).ok,
      message: !!(data as { ok?: boolean }).ok ? '请求成功' : '请求失败',
    }
  } catch {
    llmTestResult.value = { ok: false, message: '请求失败' }
  } finally {
    llmTestLoading.value = false
  }
}

async function discoverLlmModels() {
  llmTestResult.value = null
  llmSaveResult.value = null

  if (llmForm.value.provider === 'http_requests') {
    const u = llmForm.value.base_url.trim()
    const compact = u.replace(/\/+$/, '')
    const looksLikeVllmRoot = Boolean(
      u && !u.includes('chat/completions') && /\/v1$/i.test(compact),
    )
    llmSaveResult.value = {
      ok: false,
      message: looksLikeVllmRoot
        ? '当前是「HTTP 直连」模式，但你填的是 …/v1 根地址（应用 OpenAI SDK）。请先把上方「部署方式」改成「vLLM（OpenAI SDK）」，再点「拉取模型列表」。'
        : '「HTTP 直连」模式不会请求模型列表，请手动填写模型名。需要拉列表时请切换到 vLLM 模式。',
    }
    return
  }

  llmDiscoverLoading.value = true
  const timeoutMs = Math.min(Math.max((Number(llmForm.value.timeout_seconds) || 60) * 1000 + 8000, 15000), 130000)
  const ac = new AbortController()
  const timer = window.setTimeout(() => ac.abort(), timeoutMs)
  try {
    const body: Record<string, unknown> = {
      provider: llmForm.value.provider,
      timeout_seconds: llmForm.value.timeout_seconds,
    }
    if (llmForm.value.base_url.trim()) body.base_url = llmForm.value.base_url.trim()
    if (llmForm.value.api_key_input.trim()) body.api_key = llmForm.value.api_key_input.trim()
    const res = await fetch('/api/llm/models/discover', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: ac.signal,
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      const det = (data as { detail?: unknown }).detail
      let msg = `拉取失败（HTTP ${res.status}）`
      if (typeof det === 'string') msg = det
      else if (Array.isArray(det) && det[0] && typeof (det[0] as { msg?: string }).msg === 'string') {
        msg = (det[0] as { msg: string }).msg
      }
      llmSaveResult.value = { ok: false, message: msg }
      return
    }
    if ((data as { ok?: boolean }).ok && Array.isArray((data as { models?: string[] }).models)) {
      const models = (data as { models: string[] }).models.filter((x) => String(x).trim())
      llmModelSuggestions.value = models
      if (models.length === 1) {
        const only = models[0] as string
        llmForm.value.model = only
        llmSaveResult.value = {
          ok: true,
          message: (data as { message?: string }).message || `已拉取 1 个模型，已自动选择：${only}`,
        }
      } else if (models.length > 1) {
        const cur = llmForm.value.model.trim()
        if (cur && !models.includes(cur)) {
          llmForm.value.model = ''
        }
        llmSaveResult.value = {
          ok: true,
          message: (data as { message?: string }).message
            || `已拉取 ${models.length} 个模型，请在下拉框中选择`,
        }
      } else {
        llmSaveResult.value = {
          ok: false,
          message: (data as { message?: string }).message || '服务端返回的模型列表为空',
        }
      }
    } else {
      llmSaveResult.value = {
        ok: false,
        message: (data as { message?: string }).message || '拉取模型列表失败',
      }
    }
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') {
      llmSaveResult.value = {
        ok: false,
        message: `拉取超时（>${Math.round(timeoutMs / 1000)}s），请检查 vLLM 是否可达、防火墙与根地址是否正确`,
      }
    } else {
      llmSaveResult.value = { ok: false, message: '无法连接到后端' }
    }
  } finally {
    window.clearTimeout(timer)
    llmDiscoverLoading.value = false
  }
}

function createNewLlmProfile() {
  llmCreatingNewProfile.value = true
  llmSelectedProfileName.value = ''
  llmProfileName.value = ''
  llmTestResult.value = null
  llmForm.value = defaultLlmForm()
}

async function selectLlmProfile(name: string) {
  const n = name.trim()
  if (!n || n === llmProfileName.value) return
  llmProfileSwitching.value = true
  llmTestResult.value = null
  llmSaveResult.value = null
  try {
    const res = await fetch('/api/llm/config/select', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ profile_name: n }),
    })
    if (!res.ok) {
      llmSaveResult.value = { ok: false, message: '切换配置失败' }
      return
    }
    const d = await res.json()
    llmProfiles.value = Array.isArray(d.profiles) ? d.profiles : []
    llmProfileName.value = String(d.profile_name || n)
    llmSelectedProfileName.value = llmProfileName.value
    llmCreatingNewProfile.value = false
    applyApiToLlmForm(d as Record<string, unknown>)
    syncLlmTaskBindingsFromApi(d as Record<string, unknown>)
    llmSaveResult.value = null
  } catch {
    llmSaveResult.value = { ok: false, message: '切换配置失败' }
  } finally {
    llmProfileSwitching.value = false
  }
}

async function deleteCurrentLlmProfile() {
  const name = llmSelectedProfileName.value.trim() || llmProfileName.value.trim()
  if (!name) return
  if (llmProfiles.value.length <= 1) {
    llmSaveResult.value = { ok: false, message: '至少保留一个配置，无法删除最后一个' }
    return
  }
  if (!confirm(`确认删除配置「${name}」？`)) return
  llmDeleting.value = true
  llmTestResult.value = null
  llmSaveResult.value = null
  try {
    const res = await fetch(`/api/llm/config/${encodeURIComponent(name)}`, {
      method: 'DELETE',
    })
    const d = await res.json().catch(() => ({}))
    if (!res.ok) {
      llmSaveResult.value = { ok: false, message: String((d as { detail?: string }).detail || '删除配置失败') }
      return
    }
    llmProfiles.value = Array.isArray((d as { profiles?: unknown[] }).profiles)
      ? ((d as { profiles: LlmProfileItem[] }).profiles)
      : []
    llmProfileName.value = String((d as { profile_name?: string; active_profile?: string }).profile_name || (d as { active_profile?: string }).active_profile || '默认配置')
    llmSelectedProfileName.value = llmProfileName.value
    llmCreatingNewProfile.value = false
    applyApiToLlmForm(d as Record<string, unknown>)
    syncLlmTaskBindingsFromApi(d as Record<string, unknown>)
    llmSaveResult.value = { ok: true, message: `已删除配置「${name}」` }
  } catch {
    llmSaveResult.value = { ok: false, message: '删除配置失败' }
  } finally {
    llmDeleting.value = false
  }
}

// 页面载入时：
// 1) 主动探测凭证状态（过期则立即提示）
// 2) 若后台爬取仍在运行，自动恢复进度横幅与轮询
// 3) 加载 LLM 配置
onMounted(async () => {
  if (typeof window !== 'undefined') {
    window.addEventListener('mousedown', handleGlobalMouseDown)
  }
  restoreAuthStatusFromCache()
  void checkAuthStatus()
  await resumeCrawlBannerIfRunning()
})

let _llmTabLoaded = false
watch(configTab, (t) => {
  if (t === 'ai' && !_llmTabLoaded) {
    _llmTabLoaded = true
    void loadLlmConfig()
  }
})

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
      if (data.img) {
        qrcodeImg.value = data.img
        qrcodeAt.value = data.refreshed_at
        qrcodeLoading.value = false
      }
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
    await fetchQrcode()
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
  <div class="app-view-shell flex h-full flex-col overflow-hidden">
    <!-- 顶栏：标题与分页 -->
    <div class="shrink-0 border-b border-[var(--color-border)] bg-[var(--color-background)]/80 backdrop-blur-sm px-6 pt-4 pb-0">
      <div class="flex items-center gap-3 pb-3">
        <div class="flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--color-primary)]/10">
          <Settings class="h-5 w-5 text-[var(--color-primary)]" />
        </div>
        <div class="min-w-0 flex-1">
          <h1 class="text-lg font-semibold text-[var(--color-foreground)]">配置</h1>
          <p class="text-sm text-[var(--color-muted-foreground)]">公众号列表、AI 打标签与关于</p>
        </div>
      </div>
      <nav class="flex gap-0.5 border-b border-[var(--color-border)]" role="tablist" aria-label="配置分页">
        <button
          type="button"
          role="tab"
          :aria-selected="configTab === 'accounts'"
          class="-mb-px rounded-t-md border border-transparent px-3 py-2 text-sm font-medium transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-ring)]"
          :class="configTab === 'accounts'
            ? 'border-[var(--color-border)] border-b-[var(--color-background)] bg-[var(--color-background)] text-[var(--color-primary)] shadow-sm'
            : 'text-[var(--color-muted-foreground)] hover:bg-[var(--color-accent)] hover:text-[var(--color-foreground)] active:scale-[0.98]'"
          @click="configTab = 'accounts'"
        >
          公众号管理
        </button>
        <button
          type="button"
          role="tab"
          :aria-selected="configTab === 'ai'"
          class="-mb-px rounded-t-md border border-transparent px-3 py-2 text-sm font-medium transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-ring)]"
          :class="configTab === 'ai'
            ? 'border-[var(--color-border)] border-b-[var(--color-background)] bg-[var(--color-background)] text-[var(--color-primary)] shadow-sm'
            : 'text-[var(--color-muted-foreground)] hover:bg-[var(--color-accent)] hover:text-[var(--color-foreground)] active:scale-[0.98]'"
          @click="configTab = 'ai'"
        >
          AI 配置
        </button>
        <button
          type="button"
          role="tab"
          :aria-selected="configTab === 'about'"
          class="-mb-px rounded-t-md border border-transparent px-3 py-2 text-sm font-medium transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-ring)]"
          :class="configTab === 'about'
            ? 'border-[var(--color-border)] border-b-[var(--color-background)] bg-[var(--color-background)] text-[var(--color-primary)] shadow-sm'
            : 'text-[var(--color-muted-foreground)] hover:bg-[var(--color-accent)] hover:text-[var(--color-foreground)] active:scale-[0.98]'"
          @click="configTab = 'about'"
        >
          关于
        </button>
      </nav>
    </div>

    <div class="flex min-h-0 flex-1 flex-col overflow-hidden">
      <div
        v-show="configTab === 'accounts'"
        class="flex min-h-0 flex-1 flex-col overflow-hidden"
      >
        <!-- Stats bar -->
        <div class="shrink-0 border-b border-[var(--color-border)] bg-[var(--color-background)]/60 px-6 py-3">
          <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
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

    <!-- Auth status banner：紧凑条带，避免大块泥色底与高按钮 -->
    <div
      v-if="authLevel === 'error' || authLevel === 'warn'"
      class="shrink-0 border-b border-[var(--color-border)] px-6 py-2"
      :class="{
        'bg-[var(--color-destructive)]/[0.08]': authLevel === 'error',
        'bg-[var(--color-muted)]/55': authLevel === 'warn',
      }"
    >
      <div class="flex items-center gap-3">
        <ShieldOff
          v-if="authLevel === 'error'"
          class="h-4 w-4 shrink-0 text-red-600 dark:text-red-400"
          aria-hidden="true"
        />
        <ShieldAlert
          v-else-if="authLevel === 'warn'"
          class="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400"
          aria-hidden="true"
        />
        <div class="min-w-0 flex-1">
          <p class="text-sm font-medium leading-snug text-[var(--color-foreground)]">
            {{ authLevel === 'error' ? '凭证未配置，无法爬取' : '凭证可能已过期' }}
          </p>
          <p
            class="mt-0.5 truncate text-[11px] leading-4 text-[var(--color-muted-foreground)]"
            :title="authLevel === 'warn' ? (authStatus?.error || '') : undefined"
          >
            <template v-if="authLevel === 'error'">
              更新 <code class="rounded bg-[var(--color-muted)] px-1 py-px font-mono text-[10px]">data/id_info.json</code> 或扫码登录
            </template>
            <template v-else-if="authLevel === 'warn'">
              {{ authStatus?.error || 'invalid session' }}
            </template>
          </p>
        </div>

        <div class="flex shrink-0 items-center gap-2">
          <span v-if="loginPending" class="hidden items-center gap-1 text-[11px] text-[var(--color-muted-foreground)] sm:flex">
            <Loader2 class="h-3 w-3 animate-spin" />
            扫码中
          </span>
          <button
            @click="startLogin"
            :disabled="loginPending"
            class="h-7 shrink-0 rounded-md border border-[var(--color-border)] bg-[var(--color-card)] px-2.5 text-xs font-medium text-[var(--color-foreground)] transition-colors hover:bg-[var(--color-accent)] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {{ loginPending ? '登录中…' : '扫码登录' }}
          </button>
        </div>
      </div>
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
          class="flex items-center gap-1.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-2.5 py-1.5 text-xs font-medium text-[var(--color-foreground)]"
          :title="authLevel === 'ok'
            ? `凭证有效，token: ${authStatus.token_hint}，文件更新于 ${authStatus.id_info_mtime}`
            : authStatus.error || '凭证状态异常'"
        >
          <ShieldCheck v-if="authLevel === 'ok'" class="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
          <ShieldAlert v-else-if="authLevel === 'warn'" class="h-3.5 w-3.5 text-amber-600 dark:text-amber-400" />
          <ShieldOff v-else class="h-3.5 w-3.5 text-[var(--color-destructive)]" />
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
        v-if="showCrawlBanner && !(crawlStatus.auth_error && !crawlStatus.running)"
        class="shrink-0 border-b border-[var(--color-border)] bg-[var(--color-card)] px-6 py-3"
      >
        <div class="flex items-start gap-3">
          <!-- Icon -->
          <div class="mt-0.5 shrink-0">
            <Loader2 v-if="crawlStatus.running" class="h-4 w-4 animate-spin text-[var(--color-primary)]" />
            <CircleCheck v-else-if="crawlStatus.errors.length === 0" class="h-4 w-4 text-emerald-500" />
            <CircleX v-else class="h-4 w-4 text-orange-500" />
          </div>

          <!-- Content -->
          <div class="flex-1 min-w-0">
            <!-- Title row -->
            <div class="flex items-center justify-between gap-2 mb-1.5">
              <p class="text-sm font-medium text-[var(--color-foreground)]">
                <template v-if="crawlStatus.running">
                  {{ crawlStatus.cancel_requested ? '正在取消爬取' : '正在爬取' }}
                  <span v-if="crawlStatus.current" class="text-[var(--color-primary)]">「{{ crawlStatus.current }}」</span>
                  <span class="text-[var(--color-muted-foreground)] font-normal ml-1">（{{ crawlStatus.done }}/{{ crawlStatus.total }}）</span>
                </template>
                <template v-else-if="crawlStatus.finished_at">
                  {{ crawlStatus.cancelled ? '爬取已取消' : '爬取完成' }} — 新增 <span class="text-emerald-500">{{ crawlStatus.new_articles }}</span> 篇文章
                  <span v-if="crawlStatus.errors.length > 0" class="text-orange-500 ml-1">，{{ crawlStatus.errors.length }} 个账号失败</span>
                </template>
              </p>
              <div class="shrink-0 flex items-center gap-1">
                <button
                  v-if="crawlStatus.running"
                  @click="cancelCrawl"
                  :disabled="crawlStatus.cancel_requested || crawlCancelling"
                  class="rounded-md border border-[var(--color-border)] px-2 py-0.5 text-[11px] text-[var(--color-muted-foreground)] hover:bg-[var(--color-accent)] disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {{ crawlStatus.cancel_requested || crawlCancelling ? '取消中…' : '取消爬取' }}
                </button>
                <button
                  v-else
                  @click="dismissCrawlBanner"
                  class="flex h-5 w-5 items-center justify-center rounded-md text-[var(--color-muted-foreground)] hover:bg-[var(--color-accent)] hover:text-[var(--color-foreground)] transition-colors"
                >
                  <X class="h-3.5 w-3.5" />
                </button>
              </div>
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
    <div class="flex min-h-0 flex-1 overflow-y-auto px-6 py-6">
      <div class="w-full">
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

      <div v-else class="grid w-full gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        <div
          v-for="acc in filteredAccounts"
          :key="acc.name"
          class="group relative flex flex-col rounded-xl border bg-[var(--color-card)] p-4 transition-all duration-200"
          :class="
            configStore.isVisible(acc.name)
              ? 'border-[var(--color-border)] opacity-100 hover:shadow-md'
              : 'border-[var(--color-border)] opacity-50 hover:shadow-md'
          "
        >
          <!-- 仅眼睛按钮切换信息流显示/隐藏 -->
          <button
            type="button"
            class="absolute top-2.5 right-2.5 z-10 flex h-7 w-7 items-center justify-center rounded-full transition-colors outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-card)]"
            :class="
              configStore.isVisible(acc.name)
                ? 'bg-emerald-500 text-white hover:bg-emerald-600'
                : 'bg-[var(--color-muted)] text-[var(--color-muted-foreground)] hover:bg-[var(--color-border)]'
            "
            :title="configStore.isVisible(acc.name) ? '在信息流中隐藏' : '在信息流中显示'"
            @click.stop="configStore.toggleAccount(acc.name)"
          >
            <Eye v-if="configStore.isVisible(acc.name)" class="h-3.5 w-3.5" />
            <EyeOff v-else class="h-3.5 w-3.5" />
          </button>

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
    </div>
      </div>

      <div
        v-show="configTab === 'ai'"
        class="flex min-h-0 flex-1 flex-col overflow-y-auto"
      >
        <div class="mx-auto w-full max-w-6xl space-y-4 px-6 py-6">
          <div class="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)]/40 px-6 py-4">
            <div class="mb-3 flex items-center gap-2">
              <Sparkles class="h-4 w-4 text-[var(--color-primary)]" />
              <h2 class="text-sm font-semibold text-[var(--color-foreground)]">模型配置</h2>
            </div>
            <div v-if="llmLoading" class="flex items-center gap-2 py-8 text-xs text-[var(--color-muted-foreground)]">
              <Loader2 class="h-3.5 w-3.5 animate-spin" />
              加载配置…
            </div>
            <div v-else class="flex flex-col gap-4 lg:flex-row lg:items-start">
              <aside class="w-full shrink-0 space-y-3 lg:sticky lg:top-4 lg:w-[19rem]">
                <div class="space-y-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] p-3">
                  <div class="flex items-center justify-between gap-2">
                    <p class="text-xs font-medium text-[var(--color-foreground)]">已保存配置</p>
                    <div class="flex shrink-0 items-center gap-1">
                      <span v-if="llmProfileSwitching" class="inline-flex items-center text-[10px] text-[var(--color-muted-foreground)]">
                        <Loader2 class="mr-1 h-3 w-3 animate-spin" />
                        切换中
                      </span>
                      <button
                        type="button"
                        class="rounded-md border border-[var(--color-border)] px-2 py-1 text-[11px] text-[var(--color-muted-foreground)] hover:bg-[var(--color-accent)]"
                        @click="createNewLlmProfile"
                      >
                        新建
                      </button>
                      <button
                        type="button"
                        :disabled="llmDeleting || llmProfiles.length <= 1"
                        class="rounded-md border border-red-200 px-2 py-1 text-[11px] text-red-600 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-900/20"
                        @click="deleteCurrentLlmProfile"
                      >
                        {{ llmDeleting ? '删除中…' : '删除' }}
                      </button>
                    </div>
                  </div>
                  <div v-if="llmProfiles.length > 0" class="flex flex-wrap gap-2">
                    <button
                      v-for="p in llmProfiles"
                      :key="p.name"
                      type="button"
                      class="rounded-md border px-2 py-1 text-[11px] transition-colors"
                      :class="p.name === llmProfileName
                        ? 'border-[var(--color-primary)] bg-[var(--color-primary)]/10 text-[var(--color-primary)]'
                        : 'border-[var(--color-border)] text-[var(--color-muted-foreground)] hover:bg-[var(--color-accent)] hover:text-[var(--color-foreground)]'"
                      @click="selectLlmProfile(p.name)"
                    >
                      {{ p.name }}
                    </button>
                  </div>
                  <p v-else class="text-[11px] text-[var(--color-muted-foreground)]">暂无已保存配置，右侧保存后会出现在这里。</p>
                  <label class="flex flex-col gap-1 text-xs">
                    <span class="text-[var(--color-muted-foreground)]">配置名称</span>
                    <input
                      v-model="llmProfileName"
                      type="text"
                      placeholder="例如：本地 vLLM / OpenAI 线上"
                      class="h-9 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-3 text-sm text-[var(--color-foreground)] outline-none focus:border-[var(--color-ring)]"
                    />
                  </label>
                </div>
                <div class="space-y-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] p-3">
                  <p class="text-xs font-medium text-[var(--color-foreground)]">任务所用配置</p>
                  <div class="flex flex-col gap-1 text-xs">
                    <span class="text-[var(--color-muted-foreground)]">任务模型配置选择</span>
                    <div ref="llmTaskDropdownRef" class="relative" @keydown.esc="llmTaskProfileMenuOpen = false">
                      <button
                        type="button"
                        :disabled="llmTaskBindSaving"
                        class="flex h-9 w-full items-center justify-between rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-2 text-sm text-[var(--color-foreground)] outline-none focus:border-[var(--color-ring)] disabled:opacity-60"
                        @click="toggleTaskProfileMenu"
                      >
                        <span class="truncate">{{ llmTaskProfileLabel }}</span>
                        <ChevronDown class="h-4 w-4 opacity-70" />
                      </button>
                      <div
                        v-if="llmTaskProfileMenuOpen"
                        class="absolute bottom-full left-0 z-20 mb-1 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] p-1 shadow-lg"
                      >
                        <button
                          v-for="p in llmProfiles"
                          :key="'bind-task-' + p.name"
                          type="button"
                          class="flex h-8 w-full items-center rounded-md px-2 text-left text-sm hover:bg-[var(--color-accent)]"
                          :class="llmTaskProfile === p.name ? 'text-[var(--color-foreground)]' : 'text-[var(--color-muted-foreground)]'"
                          @click="chooseTaskProfile(p.name)"
                        >
                          {{ p.name }}
                        </button>
                      </div>
                    </div>
                  </div>
                  <label class="flex cursor-pointer items-center gap-2 pt-1 text-xs">
                    <input
                      id="llm-enabled-for-crawl"
                      v-model="llmCrawlLlmEnabled"
                      type="checkbox"
                      :disabled="llmSaving || llmLoading || llmTaskBindSaving"
                      class="rounded border-[var(--color-border)]"
                      @change="toggleLlmEnabledForCrawl"
                    />
                    <span class="text-[var(--color-muted-foreground)]">爬取时启用模型总结和打标</span>
                  </label>
                  <label class="flex cursor-pointer items-center gap-2 pt-1 text-xs">
                    <input
                      id="llm-multithread-for-crawl"
                      v-model="llmCrawlLlmMultithreadEnabled"
                      type="checkbox"
                      :disabled="llmSaving || llmLoading || llmTaskBindSaving || !llmCrawlLlmEnabled"
                      class="rounded border-[var(--color-border)]"
                      @change="toggleLlmMultithreadForCrawl"
                    />
                    <span class="text-[var(--color-muted-foreground)]">爬取总结/打标启用多线程</span>
                  </label>
                  <div
                    class="flex flex-col gap-2 pl-6 pt-1 text-xs"
                    :class="(!llmCrawlLlmEnabled || !llmCrawlLlmMultithreadEnabled) ? 'pointer-events-none opacity-50' : ''"
                  >
                    <span class="text-[var(--color-muted-foreground)]">并发线程数</span>
                    <div
                      class="llm-multithread-workers-segment"
                      role="radiogroup"
                      aria-label="并发线程数"
                    >
                      <button
                        v-for="preset in CRAWL_LLM_MULTITHREAD_PRESETS"
                        :key="'crawl-workers-seg-' + preset.value"
                        type="button"
                        role="radio"
                        :aria-checked="llmCrawlLlmMultithreadWorkers === preset.value"
                        :disabled="llmSaving || llmLoading || llmTaskBindSaving || llmMultithreadWorkersPersisting || !llmCrawlLlmEnabled || !llmCrawlLlmMultithreadEnabled"
                        class="llm-multithread-workers-segment-btn"
                        :class="{ 'is-active': llmCrawlLlmMultithreadWorkers === preset.value }"
                        @click="selectCrawlLlmMultithreadPreset(preset.value)"
                      >
                        <span class="segment-label">{{ preset.label }}</span>
                        <span class="segment-value">{{ preset.value }} 线程</span>
                      </button>
                    </div>
                    <p class="rounded-lg bg-[var(--color-accent)]/50 px-3 py-2 text-[12px] leading-relaxed text-[var(--color-muted-foreground)]">
                      {{ activeCrawlLlmMultithreadPreset.desc }}
                    </p>
                  </div>
                  <p v-if="llmTaskBindSaving" class="flex items-center gap-1 text-[10px] text-[var(--color-muted-foreground)]">
                    <Loader2 class="h-3 w-3 animate-spin" />
                    正在写入任务模型配置…
                  </p>
                </div>
              </aside>
              <div class="min-w-0 flex-1 space-y-3">
              <div class="space-y-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] p-3">
                <p class="text-xs font-medium text-[var(--color-foreground)]">连接与凭证</p>
                <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  <div class="flex flex-col gap-1 text-xs">
                    <span class="text-[var(--color-muted-foreground)]">部署方式</span>
                    <div ref="llmProviderDropdownRef" class="relative" @keydown.esc="llmProviderMenuOpen = false">
                      <button
                        type="button"
                        class="flex h-9 w-full items-center justify-between rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-2 text-sm text-[var(--color-foreground)] outline-none focus:border-[var(--color-ring)]"
                        @click="toggleLlmProviderMenu"
                      >
                        <span>{{ llmProviderLabel }}</span>
                        <ChevronDown class="h-4 w-4 opacity-70" />
                      </button>
                      <div
                        v-if="llmProviderMenuOpen"
                        class="absolute bottom-full left-0 z-20 mb-1 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] p-1 shadow-lg"
                      >
                        <button
                          v-for="opt in llmProviderOptions"
                          :key="opt.value"
                          type="button"
                          class="flex h-8 w-full items-center rounded-md px-2 text-left text-sm hover:bg-[var(--color-accent)]"
                          :class="llmForm.provider === opt.value ? 'text-[var(--color-foreground)]' : 'text-[var(--color-muted-foreground)]'"
                          @click="chooseLlmProvider(opt.value)"
                        >
                          {{ opt.label }}
                        </button>
                      </div>
                    </div>
                  </div>
                  <label class="flex flex-col gap-1 text-xs sm:col-span-2 lg:col-span-3">
                    <span class="text-[var(--color-muted-foreground)]">{{ llmBaseUrlLabel }}</span>
                    <input
                      v-model="llmForm.base_url"
                      type="url"
                      :placeholder="llmBaseUrlPlaceholder"
                      class="h-9 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-3 text-sm text-[var(--color-foreground)] placeholder-[var(--color-muted-foreground)] outline-none focus:border-[var(--color-ring)]"
                    />
                  </label>
                  <label class="flex flex-col gap-1 text-xs sm:col-span-2 lg:col-span-3">
                    <span class="text-[var(--color-muted-foreground)]">API Key（可选）</span>
                    <input
                      v-model="llmForm.api_key_input"
                      type="password"
                      autocomplete="off"
                      :placeholder="llmForm.has_api_key ? `已配置 ${llmForm.api_key_hint}，留空不改` : '未设置'"
                      class="h-9 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-3 text-sm text-[var(--color-foreground)] outline-none focus:border-[var(--color-ring)]"
                    />
                  </label>
                </div>
              </div>
              <div class="space-y-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] p-3">
                <p class="text-xs font-medium text-[var(--color-foreground)]">模型与采样</p>
                <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  <div class="flex flex-col gap-1 text-xs sm:col-span-2 lg:col-span-3">
                    <span class="text-[var(--color-muted-foreground)]">模型名 model</span>
                    <div class="flex flex-wrap items-stretch gap-2">
                      <select
                        v-if="llmForm.provider === 'vllm' && llmModelSuggestions.length > 1"
                        v-model="llmForm.model"
                        class="min-w-[12rem] flex-1 rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-3 py-2 text-sm text-[var(--color-foreground)] outline-none focus:border-[var(--color-ring)]"
                      >
                        <option
                          v-if="llmModelSuggestions.length > 1 && (!llmForm.model || !llmModelSuggestions.includes(llmForm.model))"
                          disabled
                          value=""
                        >
                          请选择模型…
                        </option>
                        <option v-for="m in llmModelSuggestions" :key="m" :value="m">{{ m }}</option>
                      </select>
                      <input
                        v-else
                        v-model="llmForm.model"
                        type="text"
                        :placeholder="llmForm.provider === 'vllm' ? '先点「拉取模型列表」或手动填写模型 id' : '可选：需要时再填写模型名'"
                        class="min-w-[12rem] flex-1 rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-3 py-2 text-sm text-[var(--color-foreground)] outline-none focus:border-[var(--color-ring)]"
                      />
                      <button
                        type="button"
                        :disabled="llmDiscoverLoading || llmSaving"
                        title="需先选择 vLLM 模式；若误选 HTTP 直连，点击后会提示如何切换"
                        class="rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-3 py-2 text-xs text-[var(--color-foreground)] hover:bg-[var(--color-accent)] disabled:opacity-50"
                        @click="discoverLlmModels"
                      >
                        <Loader2 v-if="llmDiscoverLoading" class="mr-1 inline h-3.5 w-3.5 animate-spin" />
                        拉取模型列表
                      </button>
                    </div>
                  </div>
                  <div class="flex flex-col gap-1 text-xs sm:col-span-2 lg:col-span-3">
                    <div class="flex gap-2">
                      <label class="flex flex-1 flex-col gap-0.5">
                        <span class="text-[10px] text-[var(--color-muted-foreground)]">temperature</span>
                        <input
                          v-model.number="llmForm.temperature"
                          type="number"
                          step="0.1"
                          min="0"
                          max="2"
                          class="h-9 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-2 text-sm"
                        />
                      </label>
                      <label class="flex flex-1 flex-col gap-0.5">
                        <span class="text-[10px] text-[var(--color-muted-foreground)]">max_tokens</span>
                        <input
                          v-model.number="llmForm.max_tokens"
                          type="number"
                          min="1"
                          class="h-9 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-2 text-sm"
                        />
                      </label>
                      <label class="flex flex-1 flex-col gap-0.5">
                        <span class="text-[10px] text-[var(--color-muted-foreground)]">超时(s)</span>
                        <input
                          v-model.number="llmForm.timeout_seconds"
                          type="number"
                          min="5"
                          class="h-9 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-2 text-sm"
                        />
                      </label>
                    </div>
                  </div>
                  <div class="flex flex-wrap gap-2 sm:col-span-2 lg:col-span-3">
                    <label class="flex w-[4.5rem] flex-col gap-0.5">
                      <span class="text-[10px] text-[var(--color-muted-foreground)]">top_k</span>
                      <input v-model.number="llmForm.top_k" type="number" min="0" class="h-9 rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-1 text-sm" />
                    </label>
                    <label class="flex w-[4.5rem] flex-col gap-0.5">
                      <span class="text-[10px] text-[var(--color-muted-foreground)]">top_p</span>
                      <input v-model.number="llmForm.top_p" type="number" step="0.05" min="0" max="1" class="h-9 rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-1 text-sm" />
                    </label>
                    <label class="flex w-[4.5rem] flex-col gap-0.5">
                      <span class="text-[10px] text-[var(--color-muted-foreground)]">min_p</span>
                      <input v-model.number="llmForm.min_p" type="number" step="0.05" min="0" max="1" class="h-9 rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-1 text-sm" />
                    </label>
                    <label class="flex w-[5rem] flex-col gap-0.5">
                      <span class="text-[10px] text-[var(--color-muted-foreground)]">rep_pen</span>
                      <input v-model.number="llmForm.repetition_penalty" type="number" step="0.1" min="0" class="h-9 rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-1 text-sm" />
                    </label>
                    <label class="flex w-[5rem] flex-col gap-0.5">
                      <span class="text-[10px] text-[var(--color-muted-foreground)]">pres_pen</span>
                      <input v-model.number="llmForm.presence_penalty" type="number" step="0.1" class="h-9 rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-1 text-sm" />
                    </label>
                    <label class="flex items-center gap-2 pt-5 text-[11px]">
                      <input v-model="llmForm.enable_thinking" type="checkbox" class="rounded border-[var(--color-border)]" />
                      <span>enable_thinking</span>
                    </label>
                  </div>
                </div>
              </div>
              <div class="flex flex-wrap items-center gap-2">
              <button
                type="button"
                :disabled="llmSaving"
                class="rounded-lg bg-[var(--color-primary)] px-3 py-1.5 text-xs font-medium text-white hover:opacity-90 disabled:opacity-50"
                @click="() => saveLlmConfig()"
              >
                {{ llmSaving ? '保存中…' : '保存当前配置' }}
              </button>
              <button
                type="button"
                :disabled="llmSaving"
                class="rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-3 py-1.5 text-xs text-[var(--color-muted-foreground)] hover:bg-[var(--color-accent)] disabled:opacity-50"
                @click="resetCurrentLlmConfig"
              >
                重置当前配置
              </button>
              <button
                type="button"
                :disabled="llmSaving || llmTestLoading"
                class="rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-3 py-1.5 text-xs text-[var(--color-foreground)] hover:bg-[var(--color-accent)] disabled:opacity-50"
                title="使用当前表单（可与已保存配置合并），无需先保存"
                @click="testLlmConnection"
              >
                <Loader2 v-if="llmTestLoading" class="mr-1 inline h-3.5 w-3.5 animate-spin" />
                测试连通
              </button>
              </div>
              </div>
            </div>
            <p
              v-if="llmNotice"
              class="mt-2 rounded-lg px-3 py-2 text-xs"
              :class="llmNotice.kind === 'error'
                ? 'border border-red-500/30 bg-red-500/8 text-red-700 dark:text-red-400'
                : llmNotice.kind === 'ok'
                  ? 'border border-[var(--color-primary)]/35 bg-[var(--color-primary)]/8 text-[var(--color-foreground)]'
                  : 'border border-[var(--color-border)] bg-[var(--color-muted)]/55 text-[var(--color-foreground)]'"
            >
              {{ llmNotice.message }}
            </p>
          </div>
        </div>
      </div>

      <div
        v-show="configTab === 'about'"
        class="flex min-h-0 flex-1 flex-col overflow-y-auto px-6 py-8"
      >
        <div class="mx-auto max-w-xl space-y-5 text-sm text-[var(--color-foreground)]">
          <div class="flex items-center gap-2">
            <Info class="h-5 w-5 text-[var(--color-primary)]" />
            <h2 class="text-base font-semibold">关于 WeChatOA_Aggregation</h2>
          </div>
          <p class="leading-relaxed text-[var(--color-muted-foreground)]">
            本地订阅与聚合阅读微信公众号文章；配置页用于管理追踪列表、爬取与可选的大模型打标签。
          </p>
          <dl class="grid gap-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-4 text-xs">
            <div class="flex justify-between gap-4">
              <dt class="text-[var(--color-muted-foreground)]">前端运行模式</dt>
              <dd class="font-mono text-[var(--color-foreground)]">{{ viteMode }}</dd>
            </div>
            <div class="flex justify-between gap-4">
              <dt class="text-[var(--color-muted-foreground)]">仓库</dt>
              <dd>
                <a
                  href="https://github.com/ZejunCao/WeChatOA_Aggregation"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="inline-flex items-center gap-1 font-medium text-[var(--color-primary)] hover:underline"
                >
                  GitHub
                  <ExternalLink class="h-3 w-3" />
                </a>
              </dd>
            </div>
          </dl>
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

<style scoped>
.llm-multithread-workers-segment {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.375rem;
  padding: 0.25rem;
  border-radius: 0.75rem;
  background: color-mix(in srgb, var(--color-muted-foreground) 10%, transparent);
}

.llm-multithread-workers-segment-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.125rem;
  min-height: 2.75rem;
  padding: 0.4rem 0.5rem;
  border-radius: 0.55rem;
  background: transparent;
  color: var(--color-muted-foreground);
  border: 1px solid transparent;
  cursor: pointer;
  transition: background-color 0.15s ease, color 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
}

.llm-multithread-workers-segment-btn:hover:not(:disabled):not(.is-active) {
  background: color-mix(in srgb, var(--color-accent) 70%, transparent);
  color: var(--color-foreground);
}

.llm-multithread-workers-segment-btn.is-active {
  background: var(--color-card);
  color: var(--color-primary);
  border-color: color-mix(in srgb, var(--color-primary) 55%, transparent);
  box-shadow: 0 1px 2px color-mix(in srgb, var(--color-foreground) 8%, transparent);
}

.llm-multithread-workers-segment-btn:disabled {
  cursor: not-allowed;
}

.llm-multithread-workers-segment-btn .segment-label {
  font-size: 12px;
  font-weight: 600;
  line-height: 1;
}

.llm-multithread-workers-segment-btn .segment-value {
  font-size: 10px;
  line-height: 1;
  opacity: 0.75;
}
</style>
