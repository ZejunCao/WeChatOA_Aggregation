<script setup lang="ts">
// ─────────────────────────────────────────────────────────────────────────────
// ArticleRow — 文章行组件（列表/行视图模式）
//
// 外观：横向布局，左边是小缩略图（128×80），右边是标题、摘要、元信息。
// 使用场景：FeedView 切换到"列表视图"时渲染，适合密集阅读。
// ─────────────────────────────────────────────────────────────────────────────

import { computed, ref } from 'vue'
import { ExternalLink, Tag, Bot, Bookmark, BookmarkCheck } from 'lucide-vue-next'
import type { Article } from '@/types'
import { useReadingStore } from '@/stores/reading'

const props = defineProps<{
  article: Article & { account: string }
}>()

const readingStore = useReadingStore()

// 已读/收藏状态（与 ArticleCard 相同的逻辑）
const isRead = computed(() => readingStore.isRead(props.article.id))
const isBookmarked = computed(() => readingStore.isBookmarked(props.article.id))

/** 点击行时标记为已读 */
function handleClick() {
  readingStore.markRead(props.article.id)
}

/** 切换收藏，阻止冒泡避免触发外层链接跳转 */
function toggleBookmark(e: MouseEvent) {
  e.preventDefault()
  e.stopPropagation()
  readingStore.toggleBookmark(props.article.id)
}

/** 封面加载失败时的备用颜色（与 ArticleCard 算法相同，保证同公众号颜色一致） */
const coverFallback = computed(() => {
  const colors = ['#6366f1', '#8b5cf6', '#ec4899', '#f97316', '#14b8a6', '#3b82f6', '#10b981']
  const idx = props.article.account.charCodeAt(0) % colors.length
  return colors[idx]
})

// 本地封面路径 + 失败标志（与 ArticleCard 相同）
const localCoverSrc = computed(
  () => `/data/covers/${props.article.id.replace(/\//g, '_')}.jpg`,
)
const coverError = ref(false)

/** 日期截取（只保留 YYYY-MM-DD 部分） */
const formattedDate = computed(() => props.article.create_time?.slice(0, 10) || '')

/** 优先 LLM 摘要，无则原始摘要 */
const displayDigest = computed(() => props.article.summary || props.article.digest || '')
</script>

<template>
  <a
    :href="article.link"
    target="_blank"
    rel="noopener noreferrer"
    class="group flex items-start gap-4 rounded-xl border bg-[var(--color-card)] p-4 transition-all duration-200 hover:shadow-md"
    :class="isRead
      ? 'border-[var(--color-border)] opacity-70 hover:opacity-100'
      : 'border-[var(--color-border)] hover:border-[var(--color-ring)]/30'"
    @click="handleClick"
  >
    <!-- 左侧缩略图（固定宽高 128×80，不会被文字撑开） -->
    <div class="relative h-20 w-32 shrink-0 overflow-hidden rounded-lg bg-[var(--color-muted)]">
      <img
        v-if="!coverError"
        :src="localCoverSrc"
        :alt="article.title"
        class="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
        loading="lazy"
        @error="coverError = true"
      />
      <!-- 封面失败时的颜色占位块 -->
      <div
        v-else
        class="flex h-full w-full items-center justify-center text-white text-lg font-bold opacity-80"
        :style="{ backgroundColor: coverFallback }"
      >
        {{ article.account.slice(0, 2) }}
      </div>
    </div>

    <!-- 右侧内容区 -->
    <div class="flex-1 min-w-0 space-y-1">
      <!-- 标题行：左边未读点+标题，右边收藏按钮+外链图标 -->
      <div class="flex items-start justify-between gap-2">
        <div class="flex items-start gap-1.5 flex-1 min-w-0">
          <!-- 未读蓝点 -->
          <span v-if="!isRead" class="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--color-primary)]" />
          <h3 class="line-clamp-2 text-sm font-semibold leading-snug text-[var(--color-foreground)] group-hover:text-[var(--color-primary)] transition-colors">
            {{ article.title }}
          </h3>
        </div>
        <div class="flex items-center gap-1 shrink-0">
          <!-- 收藏按钮：悬停时出现，已收藏时高亮常驻 -->
          <button
            @click="toggleBookmark"
            class="flex h-6 w-6 items-center justify-center rounded-md transition-all"
            :class="isBookmarked
              ? 'text-amber-500 opacity-100'
              : 'text-[var(--color-muted-foreground)] opacity-0 group-hover:opacity-100 hover:text-amber-500'"
            :title="isBookmarked ? '取消收藏' : '收藏'"
          >
            <BookmarkCheck v-if="isBookmarked" class="h-3.5 w-3.5" />
            <Bookmark v-else class="h-3.5 w-3.5" />
          </button>
          <ExternalLink class="h-3.5 w-3.5 text-[var(--color-muted-foreground)] opacity-0 group-hover:opacity-100 transition-opacity mt-0.5" />
        </div>
      </div>

      <!-- 摘要（2 行省略） -->
      <p v-if="displayDigest" class="line-clamp-2 text-xs leading-relaxed text-[var(--color-muted-foreground)]">
        {{ displayDigest }}
      </p>

      <!-- 底部元信息行：公众号名、日期、AI 摘要标识、标签 -->
      <div class="flex items-center gap-3 pt-1">
        <span class="text-xs font-medium text-[var(--color-muted-foreground)]">{{ article.account }}</span>
        <span class="text-xs text-[var(--color-muted-foreground)]">{{ formattedDate }}</span>
        <!-- AI 摘要标识（有 LLM 生成的 summary 时出现） -->
        <div v-if="article.summary" class="flex items-center gap-0.5 text-[10px] text-[var(--color-primary)]">
          <Bot class="h-3 w-3" />
          <span>AI 摘要</span>
        </div>
        <!-- 标签列表（最多 3 个） -->
        <div v-if="article.tags && article.tags.length" class="flex flex-wrap gap-1">
          <span
            v-for="tag in article.tags.slice(0, 3)"
            :key="tag"
            class="flex items-center gap-0.5 rounded-full bg-[var(--color-primary)]/10 px-1.5 py-0.5 text-[10px] text-[var(--color-primary)]"
          >
            <Tag class="h-2.5 w-2.5" />
            {{ tag }}
          </span>
        </div>
      </div>
    </div>
  </a>
</template>
