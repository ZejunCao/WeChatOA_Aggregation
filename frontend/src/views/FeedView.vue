<script setup lang="ts">
defineOptions({ name: 'FeedView' })
// ─────────────────────────────────────────────────────────────────────────────
// FeedView — 文章信息流主页面
//
// 职责：
//   - 展示筛选/排序/分组后的文章列表（支持卡片视图和列表视图切换）
//   - 提供 FilterBar 筛选面板
//   - 与侧边栏的"公众号快速筛选"双向同步（props/emit）
//   - 提供"全部已读"快捷操作
// ─────────────────────────────────────────────────────────────────────────────

import { ref, computed, watch, onMounted, onUnmounted, onActivated, onDeactivated, nextTick, TransitionGroup } from 'vue'
import { Loader2, AlertCircle, Inbox, CheckCheck } from 'lucide-vue-next'
import { useArticlesStore } from '@/stores/articles'
import { useReadingStore } from '@/stores/reading'
import { useConfigStore } from '@/stores/config'
import { useFilters } from '@/composables/useFilters'
import FilterBar from '@/components/articles/FilterBar.vue'
import ArticleCard from '@/components/articles/ArticleCard.vue'
import ArticleRow from '@/components/articles/ArticleRow.vue'
import { useArticlePreviewStore } from '@/stores/articlePreview'

// selectedAccount：侧边栏点击公众号时传入，用于快速筛选该公众号的文章
const props = defineProps<{
  selectedAccount: string
}>()

// 反向通知侧边栏：当用户在 FilterBar 里切换公众号筛选时，同步更新侧边栏高亮
const emit = defineEmits<{
  'update:selectedAccount': [value: string]
}>()

const articlesStore = useArticlesStore()
const readingStore = useReadingStore()
const configStore = useConfigStore()
const previewStore = useArticlePreviewStore()

/** 与 demo/index.html 一致：四块色团 + 同源 CSS（data-feed-theme="demo-glass"） */
const isDemoGlassFeed = computed(() => configStore.feedTheme === 'demo-glass')
// useFilters 提供响应式筛选条件和计算后的文章列表
const { filters, filteredArticles, groupedArticles, resetFilters, activeFilterCount } = useFilters()

watch(
  filteredArticles,
  (list) => {
    previewStore.setNavigationIds(list.map((a) => a.id))
  },
  { immediate: true },
)

/** 将当前视图（筛选后）所有文章标为已读 */
function markAllReadInView() {
  const ids = filteredArticles.value.map((a) => a.id)
  readingStore.markAllRead(ids)
}

async function onLinkImported(payload: { articleId: string }) {
  filters.readFilter = 'imported'
  filters.accounts = []
  articlesStore.markFeedDirty('full')
  await articlesStore.syncFeedOnActivate(filters)
  const article = articlesStore.allArticles.find((a) => a.id === payload.articleId)
  await nextTick()
  const target = scrollRef.value?.querySelector<HTMLElement>(
    `[data-article-id="${CSS.escape(payload.articleId)}"]`,
  )
  if (target) {
    target.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' })
    flashImportedTarget(target)
  }
  if (article) {
    void previewStore.openPreview(article)
  }
}

// 视图模式：'grid'=卡片视图（多列）/ 'list'=列表视图（单列紧凑）
const viewMode = ref<'grid' | 'list'>('grid')

// ── 增量渲染（懒加载） ──────────────────────────────────────────────────────
/** JSON 模式：客户端已加载文章数；SQLite：服务端总数 */
const loadedInViewCount = computed(() =>
  groupedArticles.value.reduce((s, g) => s + g.articles.length, 0),
)

const totalCount = computed(() => {
  if (articlesStore.isSqlite) {
    return articlesStore.sqliteFilterTotalCount || loadedInViewCount.value
  }
  return loadedInViewCount.value
})

const INITIAL_COUNT = 30
const PAGE_SIZE = 20
const displayLimit = ref(INITIAL_COUNT)
const sentinelRef = ref<HTMLElement | null>(null)
const scrollRef = ref<HTMLElement | null>(null)
let savedScrollTop = 0
let observer: IntersectionObserver | null = null
let loadMoreLocked = false
let importHighlightTimer: ReturnType<typeof setTimeout> | undefined

function flashImportedTarget(target: HTMLElement) {
  if (importHighlightTimer) {
    clearTimeout(importHighlightTimer)
    importHighlightTimer = undefined
  }
  scrollRef.value
    ?.querySelectorAll<HTMLElement>('.article-import-highlight')
    .forEach((el) => el.classList.remove('article-import-highlight'))
  target.classList.add('article-import-highlight')
  importHighlightTimer = setTimeout(() => {
    target.classList.remove('article-import-highlight')
  }, 1150)
}

/** SQLite 加载更多后保持滚动位置，避免列表增高后视口被顶下去 */
async function loadMoreSqlitePreserveScroll() {
  const el = scrollRef.value
  const sentinel = sentinelRef.value
  if (!el || articlesStore.sqliteLoadingMore || loadMoreLocked) return
  loadMoreLocked = true
  if (sentinel) observer?.unobserve(sentinel)
  const scrollTop = el.scrollTop
  try {
    await articlesStore.loadMoreArticles(filters)
    await nextTick()
    el.scrollTop = scrollTop
  } finally {
    await nextTick()
    if (sentinel && observer) observer.observe(sentinel)
    loadMoreLocked = false
  }
}

function setupScrollObserver() {
  observer?.disconnect()
  observer = new IntersectionObserver(
    (entries) => {
      if (!entries[0]?.isIntersecting || !hasMore.value || loadMoreLocked) return
      if (articlesStore.isSqlite) {
        void loadMoreSqlitePreserveScroll()
      } else {
        displayLimit.value += PAGE_SIZE
      }
    },
    { root: scrollRef.value, rootMargin: '80px' },
  )
  if (sentinelRef.value) observer.observe(sentinelRef.value)
}

/** JSON 模式截断渲染；SQLite 展示已拉取的全部条目 */
const displayedGroups = computed(() => {
  const groups = groupedArticles.value
  if (articlesStore.isSqlite) {
    return groups
  }
  const limit = displayLimit.value
  let remaining = limit
  const result: typeof groups = []
  for (const group of groups) {
    if (remaining <= 0) break
    if (group.articles.length <= remaining) {
      result.push(group)
      remaining -= group.articles.length
    } else {
      result.push({ ...group, articles: group.articles.slice(0, remaining) })
      remaining = 0
    }
  }
  return result
})

const displayedCount = computed(() =>
  displayedGroups.value.reduce((s, g) => s + g.articles.length, 0),
)
const hasMoreLocal = computed(() => displayedCount.value < loadedInViewCount.value)
const hasMore = computed(() =>
  articlesStore.isSqlite ? articlesStore.sqliteHasMore : hasMoreLocal.value,
)

onMounted(() => {
  displayLimit.value = INITIAL_COUNT
  nextTick(() => setupScrollObserver())
})

onActivated(() => {
  void articlesStore.syncFeedOnActivate(filters).then(() => {
    nextTick(() => {
      if (scrollRef.value && savedScrollTop > 0) {
        scrollRef.value.scrollTop = savedScrollTop
      }
      setupScrollObserver()
    })
  })
})

onDeactivated(() => {
  savedScrollTop = scrollRef.value?.scrollTop ?? 0
})

// sentinel / 滚动容器在 loading 结束后才挂载，需重新绑定 observer
watch(sentinelRef, (el, oldEl) => {
  if (oldEl) observer?.unobserve(oldEl)
  if (el && observer) observer.observe(el)
})
watch(scrollRef, () => {
  if (scrollRef.value && observer) setupScrollObserver()
})

onUnmounted(() => {
  observer?.disconnect()
  if (importHighlightTimer) clearTimeout(importHighlightTimer)
})

// 筛选条件变化时重置显示数量
watch(
  () => [filters.keyword, filters.accounts, filters.tags, filters.dateFrom, filters.dateTo, filters.readFilter, filters.sortOrder, filters.groupBy],
  () => {
    displayLimit.value = INITIAL_COUNT
    nextTick(() => scrollRef.value?.scrollTo({ top: 0 }))
    if (articlesStore.isSqlite) {
      void articlesStore.loadArticlesPage(filters, { reset: true })
    }
  },
)

// ── 自定义滚动条 ──────────────────────────────────────────────────────────────
const trackRef = ref<HTMLElement | null>(null)
const thumbRatio = ref(1)   // clientHeight / scrollHeight
const scrollRatio = ref(0)  // scrollTop / (scrollHeight - clientHeight)
const needsScrollbar = computed(() => thumbRatio.value < 1)
const isDragging = ref(false)
let dragStartY = 0
let dragStartScrollTop = 0

function updateScrollbar() {
  const el = scrollRef.value
  if (!el) return
  const { scrollTop, scrollHeight, clientHeight } = el
  thumbRatio.value = scrollHeight > 0 ? clientHeight / scrollHeight : 1
  const maxScroll = scrollHeight - clientHeight
  scrollRatio.value = maxScroll > 0 ? scrollTop / maxScroll : 0
}

function onTrackClick(e: MouseEvent) {
  const el = scrollRef.value
  const track = trackRef.value
  if (!el || !track || isDragging.value) return
  const rect = track.getBoundingClientRect()
  const clickRatio = (e.clientY - rect.top) / rect.height
  const maxScroll = el.scrollHeight - el.clientHeight
  el.scrollTo({ top: clickRatio * maxScroll, behavior: 'smooth' })
}

function onThumbMousedown(e: MouseEvent) {
  e.preventDefault()
  e.stopPropagation()
  isDragging.value = true
  dragStartY = e.clientY
  dragStartScrollTop = scrollRef.value?.scrollTop ?? 0
  document.addEventListener('mousemove', onThumbMousemove)
  document.addEventListener('mouseup', onThumbMouseup)
}

function onThumbMousemove(e: MouseEvent) {
  const el = scrollRef.value
  const track = trackRef.value
  if (!el || !track) return
  const trackHeight = track.clientHeight
  const deltaY = e.clientY - dragStartY
  const scrollRange = el.scrollHeight - el.clientHeight
  el.scrollTop = dragStartScrollTop + (deltaY / trackHeight) * scrollRange
}

function onThumbMouseup() {
  isDragging.value = false
  document.removeEventListener('mousemove', onThumbMousemove)
  document.removeEventListener('mouseup', onThumbMouseup)
}

// ── 侧边栏 ↔ FilterBar 双向同步 ───────────────────────────────────────────────
watch(
  () => filters.readFilter,
  (v) => {
    if (v === 'imported') {
      filters.accounts = []
      filters.groupBy = 'none'
      viewMode.value = 'grid'
      if (props.selectedAccount) emit('update:selectedAccount', '')
    }
  },
)

// 侧边栏点击公众号 → selectedAccount prop 变化 → 同步到 filters.accounts
watch(
  () => props.selectedAccount,
  (val) => {
    if (val && filters.readFilter === 'imported') {
      filters.readFilter = 'all'
    }
    filters.accounts = val ? [val] : []
  },
)

// FilterBar 选中单个公众号 → 同步回侧边栏高亮
watch(
  () => filters.accounts,
  (val) => {
    if (val.length === 1 && val[0]) {
      emit('update:selectedAccount', val[0])
    } else {
      emit('update:selectedAccount', '')  // 多选或无选时清除侧边栏高亮
    }
  },
)

/** 重置筛选时同时清除侧边栏高亮 */
function handleReset() {
  resetFilters()
  emit('update:selectedAccount', '')
}

</script>

<template>
  <div class="feed-shell flex h-full min-h-0 flex-col">
    <!-- demo-glass：与 demo/index.html 相同的四块圆形色团；其它主题用 mesh 渐变 -->
    <div
      v-if="isDemoGlassFeed"
      class="feed-shell__demo-shapes"
      aria-hidden="true"
    >
      <div class="demo-bg-shape demo-bg-shape-1" />
      <div class="demo-bg-shape demo-bg-shape-2" />
      <div class="demo-bg-shape demo-bg-shape-3" />
      <div class="demo-bg-shape demo-bg-shape-4" />
    </div>
    <div v-else class="feed-shell__mesh" aria-hidden="true" />
    <div class="relative z-[1] flex h-full min-h-0 flex-col">
 <!-- overflow-hidden 不能加在外层，否则会裁剪 FilterBar 的下拉弹出层 -->
    <div class="flex h-full min-h-0 flex-col">
    <!-- 顶部玻璃面板：与 demo 一致 -->
    <div class="relative z-10 shrink-0 px-4 pt-5 pb-3 sm:px-6 sm:pt-6">
      <div class="feed-glass-top px-5 py-5 sm:px-7 sm:py-6 space-y-4">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 class="feed-title">
            {{
              filters.readFilter === 'imported'
                ? '链接导入'
                : filters.accounts.length === 1
                  ? filters.accounts[0]
                  : '全部文章'
            }}
          </h1>
          <p class="feed-subtitle">
            共 <strong>{{ totalCount }}</strong> 篇
            <template v-if="readingStore.unreadCount > 0">
              · <span class="feed-unread-count">{{ readingStore.unreadCount }} 未读</span>
            </template>
            <template v-if="articlesStore.feedRefreshing">
              · <span class="text-[var(--color-muted-foreground)]">同步中…</span>
            </template>
          </p>
        </div>
        <button
          v-if="filters.readFilter !== 'bookmarked' && filters.readFilter !== 'imported' && totalCount > 0"
          type="button"
          @click="markAllReadInView"
          class="feed-mark-all-btn"
          title="将当前视图所有文章标为已读"
        >
          <CheckCheck class="h-3.5 w-3.5 shrink-0" />
          全部已读
        </button>
      </div>
      <FilterBar
        :filters="filters"
        :active-count="activeFilterCount"
        :view-mode="viewMode"
        glass
        @update:filters="Object.assign(filters, $event)"
        @update:viewMode="viewMode = $event"
        @reset="handleReset"
        @link-imported="onLinkImported"
      />
      </div>
    </div>

    <!-- Content：min-h-0 防止 flex 子元素撑破父容器高度 -->
    <div class="relative flex-1 min-h-0">
      <div ref="scrollRef" class="feed-content-scroll h-full overflow-y-auto px-4 py-5 sm:px-6 sm:py-6 hide-scrollbar" @scroll="updateScrollbar">
      <!-- Loading -->
      <div v-if="articlesStore.loading && !articlesStore.feedInitialized" class="flex flex-col items-center justify-center py-24 gap-3">
        <Loader2 class="h-8 w-8 animate-spin text-[var(--color-primary)]" />
        <p class="text-sm text-[var(--color-muted-foreground)]">加载数据中...</p>
      </div>

      <!-- Error -->
      <div v-else-if="articlesStore.error" class="flex flex-col items-center justify-center py-24 gap-3">
        <AlertCircle class="h-10 w-10 text-[var(--color-destructive)]" />
        <p class="text-sm font-medium text-[var(--color-foreground)]">加载失败</p>
        <p class="text-xs text-[var(--color-muted-foreground)]">{{ articlesStore.error }}</p>
        <button
          @click="articlesStore.loadData(filters)"
          class="mt-2 rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 transition-opacity"
        >
          重试
        </button>
      </div>

      <!-- Empty -->
      <div v-else-if="totalCount === 0 && !articlesStore.loading" class="flex flex-col items-center justify-center py-24 gap-3">
        <Inbox class="h-12 w-12 text-[var(--color-muted-foreground)]" />
        <p class="text-sm font-medium text-[var(--color-foreground)]">没有找到文章</p>
        <p class="text-xs text-[var(--color-muted-foreground)]">尝试调整筛选条件</p>
        <button
          v-if="activeFilterCount > 0"
          @click="handleReset"
          class="mt-2 rounded-lg border border-[var(--color-border)] px-4 py-2 text-sm text-[var(--color-foreground)] hover:bg-[var(--color-accent)] transition-colors"
        >
          清除筛选
        </button>
      </div>

      <!-- Article groups -->
      <div v-else class="space-y-8">
        <div v-for="group in displayedGroups" :key="group.key" class="space-y-4">
          <!-- Group header -->
          <div v-if="filters.groupBy !== 'none'" class="flex items-center gap-3">
            <h2 class="feed-section-label">{{ group.label }}</h2>
            <div class="feed-section-line" />
            <span class="feed-section-count">{{ group.articles.length }} 篇</span>
          </div>

          <!-- Grid view：TransitionGroup 让删除后其余卡片平滑补位 -->
          <TransitionGroup
            v-if="viewMode === 'grid'"
            name="article-fade"
            tag="div"
            :class="
              isDemoGlassFeed
                ? 'relative grid feed-demo-card-grid'
                : 'relative grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4'
            "
          >
            <ArticleCard
              v-for="article in group.articles"
              :key="article.id"
              :article="article"
              :import-mode="filters.readFilter === 'imported'"
            />
          </TransitionGroup>

          <!-- List view -->
          <TransitionGroup
            v-else
            name="article-fade"
            tag="div"
            class="relative flex flex-col gap-2"
          >
            <ArticleRow
              v-for="article in group.articles"
              :key="article.id"
              :article="article"
              :import-mode="filters.readFilter === 'imported'"
            />
          </TransitionGroup>
        </div>

        <!-- 懒加载哨兵 -->
        <div ref="sentinelRef" class="feed-scroll-sentinel flex items-center justify-center py-6">
          <p v-if="hasMore" class="text-xs text-[var(--color-muted-foreground)]">
            <Loader2 class="inline h-3.5 w-3.5 animate-spin align-text-bottom mr-1" />
            已加载 {{ displayedCount }} / {{ totalCount }} 篇<template v-if="articlesStore.sqliteLoadingMore">（加载中）</template><template v-else>，滚动加载更多...</template>
          </p>
          <p v-else class="text-xs text-[var(--color-muted-foreground)]">
            共 {{ totalCount }} 篇，已全部加载
          </p>
        </div>
      </div>
    </div>

      <!-- 自定义滚动条 -->
      <div
        v-if="needsScrollbar"
        ref="trackRef"
        class="absolute right-0.5 top-1 bottom-1 w-1.5 rounded-full bg-white/35 cursor-pointer z-10 transition-opacity dark:bg-white/10"
        :class="isDragging ? 'opacity-100' : 'opacity-60 hover:opacity-100'"
        @mousedown="onTrackClick"
      >
        <div
          class="absolute left-0 w-full rounded-full transition-colors bg-[color-mix(in_srgb,var(--feed-accent)_65%,transparent)] hover:bg-[var(--feed-accent)]"
          :class="isDragging ? 'opacity-100' : ''"
          :style="{
            height: `${Math.max(thumbRatio * 100, 8)}%`,
            top: `${scrollRatio * (100 - Math.max(thumbRatio * 100, 8))}%`,
          }"
          @mousedown="onThumbMousedown"
        />
      </div>
    </div>
    </div>
    </div>
  </div>
</template>
