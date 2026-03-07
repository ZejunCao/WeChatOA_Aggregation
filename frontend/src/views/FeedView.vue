<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Loader2, AlertCircle, Inbox } from 'lucide-vue-next'
import { useArticlesStore } from '@/stores/articles'
import { useFilters } from '@/composables/useFilters'
import FilterBar from '@/components/articles/FilterBar.vue'
import ArticleCard from '@/components/articles/ArticleCard.vue'
import ArticleRow from '@/components/articles/ArticleRow.vue'

const props = defineProps<{
  selectedAccount: string
}>()

const emit = defineEmits<{
  'update:selectedAccount': [value: string]
}>()

const articlesStore = useArticlesStore()
const { filters, groupedArticles, resetFilters, activeFilterCount } = useFilters()

const viewMode = ref<'grid' | 'list'>('grid')

// Sync sidebar selectedAccount into filters
watch(
  () => props.selectedAccount,
  (val) => {
    filters.accounts = val ? [val] : []
  },
)

// Sync filters.accounts back to sidebar (single account quick-select)
watch(
  () => filters.accounts,
  (val) => {
    if (val.length === 1 && val[0]) {
      emit('update:selectedAccount', val[0])
    } else {
      emit('update:selectedAccount', '')
    }
  },
)

function handleReset() {
  resetFilters()
  emit('update:selectedAccount', '')
}

const totalCount = computed(() => groupedArticles.value.reduce((s, g) => s + g.articles.length, 0))
</script>

<template>
  <div class="flex h-full flex-col overflow-hidden">
    <!-- Sticky header -->
    <div class="shrink-0 border-b border-[var(--color-border)] bg-[var(--color-background)]/80 backdrop-blur-sm px-6 py-4 space-y-3">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-lg font-semibold text-[var(--color-foreground)]">
            {{ filters.accounts.length === 1 ? filters.accounts[0] : '全部文章' }}
          </h1>
          <p class="text-sm text-[var(--color-muted-foreground)]">
            共 <span class="font-medium text-[var(--color-foreground)]">{{ totalCount }}</span> 篇
          </p>
        </div>
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

    <!-- Content -->
    <div class="flex-1 overflow-y-auto px-6 py-6">
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
