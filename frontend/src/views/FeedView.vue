<script setup lang="ts">
// ─────────────────────────────────────────────────────────────────────────────
// FeedView — 文章信息流主页面
//
// 职责：
//   - 展示筛选/排序/分组后的文章列表（支持卡片视图和列表视图切换）
//   - 提供 FilterBar 筛选面板
//   - 与侧边栏的"公众号快速筛选"双向同步（props/emit）
//   - 提供"全部已读"快捷操作
// ─────────────────────────────────────────────────────────────────────────────

import { ref, computed, watch } from 'vue'
import { Loader2, AlertCircle, Inbox, CheckCheck } from 'lucide-vue-next'
import { useArticlesStore } from '@/stores/articles'
import { useReadingStore } from '@/stores/reading'
import { useFilters } from '@/composables/useFilters'
import FilterBar from '@/components/articles/FilterBar.vue'
import ArticleCard from '@/components/articles/ArticleCard.vue'
import ArticleRow from '@/components/articles/ArticleRow.vue'

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
// useFilters 提供响应式筛选条件和计算后的文章列表
const { filters, filteredArticles, groupedArticles, resetFilters, activeFilterCount } = useFilters()

/** 将当前视图（筛选后）所有文章标为已读 */
function markAllReadInView() {
  const ids = filteredArticles.value.map((a) => a.id)
  readingStore.markAllRead(ids)
}

// 视图模式：'grid'=卡片视图（多列）/ 'list'=列表视图（单列紧凑）
const viewMode = ref<'grid' | 'list'>('grid')

// ── 侧边栏 ↔ FilterBar 双向同步 ───────────────────────────────────────────────
// 侧边栏点击公众号 → selectedAccount prop 变化 → 同步到 filters.accounts
watch(
  () => props.selectedAccount,
  (val) => {
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

/** 当前视图展示的文章总数（跨所有分组求和） */
const totalCount = computed(() => groupedArticles.value.reduce((s, g) => s + g.articles.length, 0))
</script>

<template>
  <!-- overflow-hidden 不能加在这里，否则会裁剪 FilterBar 的下拉弹出层 -->
  <div class="flex h-full flex-col">
    <!-- Sticky header：z-10 确保下拉层叠在文章列表上方 -->
    <div class="relative z-10 shrink-0 border-b border-[var(--color-border)] bg-[var(--color-background)]/80 backdrop-blur-sm px-6 py-4 space-y-3">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-lg font-semibold text-[var(--color-foreground)]">
            {{ filters.accounts.length === 1 ? filters.accounts[0] : '全部文章' }}
          </h1>
          <p class="text-sm text-[var(--color-muted-foreground)]">
            共 <span class="font-medium text-[var(--color-foreground)]">{{ totalCount }}</span> 篇
            <template v-if="readingStore.unreadCount > 0">
              · <span class="font-medium text-[var(--color-primary)]">{{ readingStore.unreadCount }} 未读</span>
            </template>
          </p>
        </div>
        <!-- Mark all read button -->
        <button
          v-if="filters.readFilter !== 'bookmarked' && totalCount > 0"
          @click="markAllReadInView"
          class="flex items-center gap-1.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-3 py-1.5 text-xs font-medium text-[var(--color-muted-foreground)] hover:bg-[var(--color-accent)] hover:text-[var(--color-foreground)] transition-colors"
          title="将当前视图所有文章标为已读"
        >
          <CheckCheck class="h-3.5 w-3.5" />
          全部已读
        </button>
      </div>
      <FilterBar
        :filters="filters"
        :active-count="activeFilterCount"
        :view-mode="viewMode"
        @update:filters="Object.assign(filters, $event)"
        @update:viewMode="viewMode = $event"
        @reset="handleReset"
      />
    </div>

    <!-- Content：min-h-0 防止 flex 子元素撑破父容器高度 -->
    <div class="flex-1 min-h-0 overflow-y-auto px-6 py-6">
      <!-- Loading -->
      <div v-if="articlesStore.loading" class="flex flex-col items-center justify-center py-24 gap-3">
        <Loader2 class="h-8 w-8 animate-spin text-[var(--color-primary)]" />
        <p class="text-sm text-[var(--color-muted-foreground)]">加载数据中...</p>
      </div>

      <!-- Error -->
      <div v-else-if="articlesStore.error" class="flex flex-col items-center justify-center py-24 gap-3">
        <AlertCircle class="h-10 w-10 text-[var(--color-destructive)]" />
        <p class="text-sm font-medium text-[var(--color-foreground)]">加载失败</p>
        <p class="text-xs text-[var(--color-muted-foreground)]">{{ articlesStore.error }}</p>
        <button
          @click="articlesStore.loadData()"
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
        <div v-for="group in groupedArticles" :key="group.key" class="space-y-4">
          <!-- Group header -->
          <div v-if="filters.groupBy !== 'none'" class="flex items-center gap-3">
            <h2 class="text-sm font-semibold text-[var(--color-foreground)]">{{ group.label }}</h2>
            <div class="flex-1 h-px bg-[var(--color-border)]" />
            <span class="text-xs text-[var(--color-muted-foreground)]">{{ group.articles.length }} 篇</span>
          </div>

          <!-- Grid view -->
          <div
            v-if="viewMode === 'grid'"
            class="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
          >
            <ArticleCard v-for="article in group.articles" :key="article.id" :article="article" />
          </div>

          <!-- List view -->
          <div v-else class="space-y-2">
            <ArticleRow v-for="article in group.articles" :key="article.id" :article="article" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
