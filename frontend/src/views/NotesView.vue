<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Loader2, NotebookPen, Search } from 'lucide-vue-next'
import type { Article } from '@/types'
import NoteCard from '@/components/articles/NoteCard.vue'

type FeedArticle = Article & { account: string }

const props = defineProps<{
  selectedAccount: string
}>()

const emit = defineEmits<{
  'update:selectedAccount': [value: string]
}>()

const loading = ref(false)
const error = ref('')
const q = ref('')
const items = ref<FeedArticle[]>([])

function extractDetail(detail: unknown, status: number): string {
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail)) {
    const msg = detail
      .map((d) => (d && typeof d === 'object' && 'msg' in d ? String((d as { msg: unknown }).msg) : ''))
      .filter(Boolean)
      .join('；')
    if (msg) return msg
  }
  return `请求失败 (${status})`
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { cache: 'no-store', ...init })
  const data = (await res.json()) as T & { detail?: unknown }
  if (!res.ok) throw new Error(extractDetail(data.detail, res.status))
  return data
}

async function loadNotes() {
  loading.value = true
  error.value = ''
  try {
    const params = new URLSearchParams()
    params.set('limit', '200')
    if (props.selectedAccount) params.set('account', props.selectedAccount)
    if (q.value.trim()) params.set('q', q.value.trim())
    const data = await fetchJson<{ items: FeedArticle[] }>(`/api/notes/articles?${params}`)
    items.value = data.items || []
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

watch(
  () => props.selectedAccount,
  () => {
    void loadNotes()
  },
)

onMounted(() => {
  void loadNotes()
})

const pageTitle = computed(() => {
  if (props.selectedAccount) return `${props.selectedAccount} · 笔记`
  return '我的笔记'
})

const countLabel = computed(() => `${items.value.length} 条笔记`)

function onDeleted(id: string) {
  items.value = items.value.filter((a) => a.id !== id)
}
</script>

<template>
  <div class="feed-shell flex h-full min-h-0 flex-col">
    <div class="relative z-[1] flex h-full min-h-0 flex-col">
      <div class="shrink-0 border-b border-[var(--color-border)] bg-[var(--color-background)] px-6 py-4">
        <div class="mb-3 flex items-center justify-between gap-3">
          <div class="flex items-baseline gap-3 min-w-0">
            <h1 class="notes-page-heading flex items-center gap-2">
              <NotebookPen class="h-4 w-4 shrink-0" aria-hidden="true" />
              <span class="truncate">{{ pageTitle }}</span>
            </h1>
            <span v-if="!loading && !error" class="shrink-0 text-xs text-[var(--color-muted-foreground)]">
              {{ countLabel }}
            </span>
          </div>
          <button
            v-if="selectedAccount"
            type="button"
            class="shrink-0 rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-3 py-1.5 text-xs text-[var(--color-muted-foreground)] hover:bg-[var(--color-accent)]"
            @click="emit('update:selectedAccount', '')"
          >
            清除账号筛选
          </button>
        </div>
        <div class="relative max-w-lg">
          <Search class="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--color-muted-foreground)]" />
          <input
            v-model="q"
            type="text"
            placeholder="搜索笔记内容或文章标题..."
            class="h-9 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] pl-8 pr-3 text-sm"
            @keydown.enter.prevent="loadNotes"
            @input="q.trim() === '' && loadNotes()"
          />
        </div>
      </div>

      <div class="flex min-h-0 flex-1 flex-col overflow-y-auto px-4 py-4 sm:px-6">
        <div v-if="loading" class="flex flex-1 items-center justify-center gap-2 text-[var(--color-muted-foreground)]">
          <Loader2 class="h-5 w-5 animate-spin" />
          正在加载…
        </div>
        <div v-else-if="error" class="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-700">
          {{ error }}
        </div>
        <div
          v-else-if="items.length === 0"
          class="flex flex-1 flex-col items-center justify-center gap-2 text-center text-[var(--color-muted-foreground)]"
        >
          <NotebookPen class="h-8 w-8 opacity-40" />
          <p class="text-sm">{{ q.trim() ? '没有匹配的笔记' : '还没有笔记' }}</p>
          <p v-if="!q.trim()" class="text-xs opacity-80">在文章预览里写下的笔记会出现在这里</p>
        </div>
        <div v-else class="notes-masonry mx-auto w-full max-w-6xl">
          <NoteCard
            v-for="article in items"
            :key="article.id"
            :article="article"
            @deleted="onDeleted"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 两列瀑布流：移动端单列 */
.notes-masonry {
  column-count: 1;
  column-gap: 14px;
}

@media (min-width: 768px) {
  .notes-masonry {
    column-count: 2;
    column-gap: 16px;
  }
}
</style>
