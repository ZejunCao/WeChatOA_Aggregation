<script setup lang="ts">
import { ref, computed } from 'vue'
import { Search, X, Tags, LayoutGrid, List, Bookmark, BookmarkCheck, Circle, Link2 } from 'lucide-vue-next'
import { useArticlesStore } from '@/stores/articles'
import { useReadingStore } from '@/stores/reading'
import { TAG_UNTAGGED, type FilterState, type SortOrder, type ReadFilter } from '@/types'
import {
  TAG_SECTION_LABELS,
  TAG_SECTION_ORDER,
  classifyTagForFilter,
  type TagFilterCategory,
} from '@/lib/tagCategories'
import Dropdown from '@/components/ui/Dropdown.vue'
import DateRangePicker from '@/components/ui/DateRangePicker.vue'
import ImportLinkPopover from '@/components/articles/ImportLinkPopover.vue'

const props = withDefaults(
  defineProps<{
    filters: FilterState
    activeCount: number
    viewMode: 'grid' | 'list'
    /** 文章 Feed 玻璃拟态样式（仅 FeedView 使用） */
    glass?: boolean
  }>(),
  { glass: false },
)

const emit = defineEmits<{
  'update:filters': [value: FilterState]
  'update:viewMode': [value: 'grid' | 'list']
  reset: []
  'link-imported': [payload: { articleId: string; status: 'created' | 'exists' }]
}>()

const articlesStore = useArticlesStore()
const readingStore = useReadingStore()
const showTagFilter = ref(false)
const expandTags = ref(false)

function onDatePickerOpenChange(isOpen: boolean) {
  if (!isOpen) return
  // 打开时间筛选时自动收起标签筛选，避免多个面板叠在一起
  showTagFilter.value = false
  expandTags.value = false
}

function onTopDropdownOpenChange(isOpen: boolean) {
  if (!isOpen) return
  // 打开排序下拉时收起标签筛选，保持面板互斥
  showTagFilter.value = false
  expandTags.value = false
}

const readTabs: { value: ReadFilter; label: string; icon: unknown }[] = [
  { value: 'all',        label: '全部',   icon: Circle },
  { value: 'unread',     label: '未读',   icon: Circle },
  { value: 'bookmarked', label: '收藏',   icon: Bookmark },
  { value: 'imported',   label: '导入',   icon: Link2 },
]

function selectReadTab(value: ReadFilter) {
  const next: FilterState = { ...props.filters, readFilter: value }
  if (value === 'imported') {
    next.accounts = []
  }
  emit('update:filters', next)
}

function update<K extends keyof FilterState>(key: K, value: FilterState[K]) {
  emit('update:filters', { ...props.filters, [key]: value })
}

function toggleTag(tag: string) {
  const tags = props.filters.tags.includes(tag)
    ? props.filters.tags.filter((t) => t !== tag)
    : [...props.filters.tags, tag]
  update('tags', tags)
}

const sortOptions = [
  { value: 'newest' as SortOrder, label: '最新优先' },
  { value: 'oldest' as SortOrder, label: '最旧优先' },
]

const activeFilters = computed(() => {
  const list: { label: string; remove: () => void }[] = []
  if (props.filters.keyword) {
    list.push({ label: `"${props.filters.keyword}"`, remove: () => update('keyword', '') })
  }
  props.filters.tags.forEach((tag) => {
    list.push({
      label: tag === TAG_UNTAGGED ? '未打标签' : `#${tag}`,
      remove: () => toggleTag(tag),
    })
  })
  return list
})

/** 标签在列表中展示的最小篇数（低于此数量不出现在筛选面板，减少噪声） */
const MIN_TAG_LIST_COUNT = 5

const tagOptions = computed(() => {
  const counts = new Map<string, number>()
  let untaggedCount = 0

  for (const article of articlesStore.allArticles) {
    const tags = article.tags ?? []
    if (tags.length === 0) {
      untaggedCount++
      continue
    }
    for (const tag of tags) {
      counts.set(tag, (counts.get(tag) ?? 0) + 1)
    }
  }

  const result = Array.from(counts.entries())
    .filter(([, count]) => count >= MIN_TAG_LIST_COUNT)
    .sort((a, b) => (b[1] - a[1]) || a[0].localeCompare(b[0]))
    .map(([value, count]) => ({ value, label: value, count }))

  if (untaggedCount >= MIN_TAG_LIST_COUNT) {
    result.push({ value: TAG_UNTAGGED, label: '未打标签', count: untaggedCount })
  }

  return result
})

type TagOptionItem = { value: string; label: string; count: number }

/** 展开后按「内容类型 / 核心主题 / 技术范围 / 特殊标记 / 未打标签」分组 */
const tagSectionsForDisplay = computed(() => {
  const buckets = new Map<TagFilterCategory, TagOptionItem[]>()
  for (const k of TAG_SECTION_ORDER) buckets.set(k, [])
  for (const opt of tagOptions.value) {
    const cat: TagFilterCategory =
      opt.value === TAG_UNTAGGED ? 'untagged' : classifyTagForFilter(opt.value)
    buckets.get(cat)!.push(opt)
  }
  const sortBucket = (items: TagOptionItem[]) =>
    [...items].sort((a, b) => b.count - a.count || a.label.localeCompare(b.label))
  return TAG_SECTION_ORDER.map((key) => ({
    key,
    label: TAG_SECTION_LABELS[key],
    items: sortBucket(buckets.get(key) ?? []),
  })).filter((s) => s.items.length > 0)
})

const showExpandTagsBtn = computed(() => tagOptions.value.length > 10)

function tagChipClasses(tagValue: string) {
  const active = props.filters.tags.includes(tagValue)
  if (props.glass) {
    return active
      ? 'feed-chip-active font-medium'
      : 'feed-chip-idle hover:border-[var(--feed-accent-soft)]/40'
  }
  return active
    ? 'border-[var(--color-primary)] bg-[var(--color-primary)]/10 text-[var(--color-primary)] font-medium'
    : 'border-[var(--color-border)] text-[var(--color-muted-foreground)] hover:border-[var(--color-foreground)]/20 hover:text-[var(--color-foreground)]'
}
</script>

<template>
  <div class="space-y-2.5" :class="{ 'feed-filter-glass': glass }">
    <!-- Read filter tabs -->
    <div class="flex flex-wrap items-center gap-2">
      <button
        v-for="tab in readTabs"
        :key="tab.value"
        type="button"
        @click="selectReadTab(tab.value)"
        class="relative inline-flex items-center gap-1.5 text-sm font-medium transition-colors"
        :class="glass
          ? ['feed-pill', filters.readFilter === tab.value ? 'is-active' : '']
          : [
              'rounded-lg px-3 py-1.5',
              filters.readFilter === tab.value
                ? 'bg-[var(--color-accent)] text-[var(--color-foreground)]'
                : 'text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)] hover:bg-[var(--color-accent)]/60',
            ]"
      >
        <BookmarkCheck v-if="tab.value === 'bookmarked'" class="h-3.5 w-3.5" />
        <Link2 v-else-if="tab.value === 'imported'" class="h-3.5 w-3.5" />
        <span
          v-else-if="tab.value === 'unread' && readingStore.unreadCount > 0"
          class="inline-flex h-5 min-w-5 shrink-0 items-center justify-center rounded-full bg-[var(--color-primary)] px-1.5 text-[10px] font-bold tabular-nums leading-none text-white"
        >{{ readingStore.unreadCount > 99 ? '99+' : readingStore.unreadCount }}</span>
        {{ tab.label }}
        <span
          v-if="tab.value === 'bookmarked' && readingStore.bookmarkCount > 0"
          class="rounded-full bg-[var(--color-primary)]/15 px-1.5 py-0.5 text-[10px] font-semibold text-[var(--color-primary)]"
        >{{ readingStore.bookmarkCount }}</span>
        <span
          v-if="tab.value === 'imported' && articlesStore.importTotalCount > 0"
          class="rounded-full bg-[var(--color-primary)]/15 px-1.5 py-0.5 text-[10px] font-semibold text-[var(--color-primary)]"
        >{{ articlesStore.importTotalCount }}</span>
      </button>
    </div>

    <!-- Main toolbar row -->
    <div class="flex items-center gap-2">
      <!-- Search -->
      <div class="relative flex-1 min-w-0">
        <Search class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--color-muted-foreground)] pointer-events-none" />
        <input
          :value="filters.keyword"
          @input="update('keyword', ($event.target as HTMLInputElement).value)"
          type="text"
          placeholder="搜索标题或内容..."
          class="w-full text-sm outline-none transition-colors"
          :class="glass
            ? 'feed-glass-input'
            : 'h-9 rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] pl-9 pr-8 text-[var(--color-foreground)] placeholder-[var(--color-muted-foreground)] focus:border-[var(--color-ring)] focus:ring-1 focus:ring-[var(--color-ring)]'"
        />
        <button
          v-if="filters.keyword"
          @click="update('keyword', '')"
          class="absolute right-2.5 top-1/2 -translate-y-1/2 rounded text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)] transition-colors"
        >
          <X class="h-3.5 w-3.5" />
        </button>
      </div>

      <ImportLinkPopover :glass="glass" @imported="emit('link-imported', $event)" />

      <!-- Date range picker -->
      <DateRangePicker
        class="hidden md:block"
        :class="glass ? 'feed-glass-dd' : ''"
        :date-from="filters.dateFrom"
        :date-to="filters.dateTo"
        @open-change="onDatePickerOpenChange"
        @update:dateFrom="update('dateFrom', $event)"
        @update:dateTo="update('dateTo', $event)"
      />

      <!-- Sort dropdown -->
      <Dropdown
        class="hidden sm:block"
        :class="glass ? 'feed-glass-dd' : ''"
        :options="sortOptions"
        :model-value="filters.sortOrder"
        @open-change="onTopDropdownOpenChange"
        @update:modelValue="update('sortOrder', $event as SortOrder)"
      />

      <!-- Tag toggle -->
      <button
        type="button"
        @click="showTagFilter = !showTagFilter"
        class="shrink-0 text-sm transition-colors"
        :class="glass
          ? [
              'feed-glass-tool',
              showTagFilter || filters.tags.length > 0 ? 'is-active' : '',
            ]
          : [
              'flex h-9 items-center gap-1.5 rounded-lg border px-3',
              showTagFilter || filters.tags.length > 0
                ? 'border-[var(--color-primary)] bg-[var(--color-primary)]/10 text-[var(--color-primary)]'
                : 'border-[var(--color-border)] bg-[var(--color-card)] text-[var(--color-muted-foreground)] hover:bg-[var(--color-accent)] hover:text-[var(--color-foreground)]',
            ]"
        :title="showTagFilter ? '收起标签筛选' : '展开标签筛选'"
      >
        <Tags class="h-4 w-4" />
        <span class="hidden sm:inline">标签</span>
        <span v-if="filters.tags.length > 0" class="text-xs font-semibold tabular-nums">{{ filters.tags.length }}</span>
      </button>

      <!-- View mode toggle -->
      <div
        class="hidden sm:flex shrink-0"
        :class="glass ? 'feed-view-toggle' : 'rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] p-0.5 gap-0.5'"
      >
        <button
          type="button"
          @click="emit('update:viewMode', 'grid')"
          title="网格视图"
          :class="glass
            ? ['flex items-center justify-center transition-colors', viewMode === 'grid' ? 'is-active' : '']
            : [
                'flex h-7 w-7 items-center justify-center rounded-md transition-colors',
                viewMode === 'grid'
                  ? 'bg-[var(--color-accent)] text-[var(--color-foreground)]'
                  : 'text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)]',
              ]"
        >
          <LayoutGrid class="h-[15px] w-[15px]" />
        </button>
        <button
          type="button"
          @click="emit('update:viewMode', 'list')"
          title="列表视图"
          :class="glass
            ? ['flex items-center justify-center transition-colors', viewMode === 'list' ? 'is-active' : '']
            : [
                'flex h-7 w-7 items-center justify-center rounded-md transition-colors',
                viewMode === 'list'
                  ? 'bg-[var(--color-accent)] text-[var(--color-foreground)]'
                  : 'text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)]',
              ]"
        >
          <List class="h-[15px] w-[15px]" />
        </button>
      </div>
    </div>

    <!-- Tag filters panel -->
    <Transition
      enter-active-class="transition duration-150 ease-out"
      enter-from-class="opacity-0 -translate-y-1"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition duration-100 ease-in"
      leave-from-class="opacity-100 translate-y-0"
      leave-to-class="opacity-0 -translate-y-1"
    >
      <div
        v-if="showTagFilter"
        class="p-4 space-y-4 rounded-xl"
        :class="glass ? 'feed-glass-advanced' : 'border border-[var(--color-border)] bg-[var(--color-card)]'"
      >
        <!-- Tag filter -->
        <div v-if="tagOptions.length">
          <div class="mb-2 flex items-center justify-between gap-2">
            <p class="text-[11px] font-semibold uppercase tracking-wider text-[var(--color-muted-foreground)]">标签</p>
            <button
              v-if="showExpandTagsBtn"
              type="button"
              class="shrink-0 text-[11px] text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)]"
              :title="expandTags ? '收起标签列表' : '展开标签列表'"
              @click="expandTags = !expandTags"
            >
              {{ expandTags ? '收起' : '展开' }}
            </button>
          </div>
          <!-- 收起：单行横向滚动；展开：分类展示 + 独立滚动区域，避免撑满屏且无法翻动 -->
          <div
            class="flex gap-1.5"
            :class="
              expandTags
                ? 'flex-col space-y-4 max-h-[min(70vh,28rem)] overflow-y-auto overscroll-contain pr-1 -mr-0.5'
                : 'flex-nowrap overflow-x-auto hide-scrollbar pr-1'
            "
          >
            <template v-if="!expandTags">
              <button
                v-for="tag in tagOptions"
                :key="tag.value"
                type="button"
                @click="toggleTag(tag.value)"
                class="shrink-0 whitespace-nowrap rounded-full border px-2.5 py-1 text-xs transition-colors"
                :class="tagChipClasses(tag.value)"
              >
                {{ tag.value === TAG_UNTAGGED ? '未打标签' : `#${tag.label}` }}
                <span class="ml-1 opacity-50">{{ tag.count }}</span>
              </button>
            </template>
            <template v-else>
              <div
                v-for="section in tagSectionsForDisplay"
                :key="section.key"
                class="space-y-2 min-w-0"
              >
                <p
                  class="text-[10px] font-semibold uppercase tracking-wider text-[var(--color-muted-foreground)]"
                >
                  {{ section.label }}
                  <span class="ml-1 font-normal normal-case opacity-70">({{ section.items.length }})</span>
                </p>
                <div class="flex flex-wrap gap-1.5">
                  <button
                    v-for="tag in section.items"
                    :key="tag.value"
                    type="button"
                    @click="toggleTag(tag.value)"
                    class="shrink-0 whitespace-nowrap rounded-full border px-2.5 py-1 text-xs transition-colors"
                    :class="tagChipClasses(tag.value)"
                  >
                    {{ tag.value === TAG_UNTAGGED ? '未打标签' : `#${tag.label}` }}
                    <span class="ml-1 opacity-50">{{ tag.count }}</span>
                  </button>
                </div>
              </div>
            </template>
          </div>
        </div>

        <!-- Mobile-only: date / sort -->
        <div class="md:hidden space-y-2">
          <p class="text-[11px] font-semibold uppercase tracking-wider text-[var(--color-muted-foreground)]">日期范围</p>
          <DateRangePicker
            :class="glass ? 'feed-glass-dd' : ''"
            :date-from="filters.dateFrom"
            :date-to="filters.dateTo"
            @update:dateFrom="update('dateFrom', $event)"
            @update:dateTo="update('dateTo', $event)"
          />
        </div>
        <div class="sm:hidden">
          <Dropdown
            class="w-full"
            :class="glass ? 'feed-glass-dd' : ''"
            :options="sortOptions"
            :model-value="filters.sortOrder"
            @open-change="onTopDropdownOpenChange"
            @update:modelValue="update('sortOrder', $event as SortOrder)"
          />
        </div>

        <!-- Reset -->
        <div class="flex justify-end pt-1">
          <button
            @click="emit('reset')"
            class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)] hover:bg-[var(--color-accent)] transition-colors"
          >
            <X class="h-3.5 w-3.5" />
            清除全部
          </button>
        </div>
      </div>
    </Transition>

    <!-- Active filter chips -->
    <div v-if="activeFilters.length" class="flex flex-wrap gap-1.5">
      <span
        v-for="(filter, i) in activeFilters"
        :key="i"
        class="flex items-center gap-1 rounded-full bg-[var(--color-primary)]/10 border border-[var(--color-primary)]/20 px-2.5 py-0.5 text-xs text-[var(--color-primary)]"
      >
        {{ filter.label }}
        <button @click="filter.remove()" class="ml-0.5 rounded-full hover:opacity-70 transition-opacity">
          <X class="h-3 w-3" />
        </button>
      </span>
    </div>
  </div>
</template>
