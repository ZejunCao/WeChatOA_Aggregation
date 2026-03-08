<script setup lang="ts">
// ─────────────────────────────────────────────────────────────────────────────
// ArticleCard — 文章卡片组件（网格/卡片视图模式）
//
// 外观：竖向卡片，上方是封面图（16:9），下方是标题、摘要、标签、底部信息。
// 使用场景：FeedView 切换到"卡片视图"时渲染。
// ─────────────────────────────────────────────────────────────────────────────

import { computed, ref } from 'vue'
import { ExternalLink, Tag, Bot, Bookmark, BookmarkCheck } from 'lucide-vue-next'
import type { Article } from '@/types'
import { useReadingStore } from '@/stores/reading'

const props = defineProps<{
  article: Article & { account: string }  // 文章数据 + 所属公众号名称
}>()

const readingStore = useReadingStore()

// 当前文章的已读/收藏状态（响应式，store 变化时自动更新）
const isRead = computed(() => readingStore.isRead(props.article.id))
const isBookmarked = computed(() => readingStore.isBookmarked(props.article.id))

/** 点击卡片跳转原文时，标记为已读 */
function handleClick() {
  readingStore.markRead(props.article.id)
}

/**
 * 切换收藏状态。
 * 注意：需要阻止事件冒泡（stopPropagation），否则点击收藏按钮也会触发
 * 卡片的 @click → handleClick → 标记已读 + 打开链接。
 */
function toggleBookmark(e: MouseEvent) {
  e.preventDefault()
  e.stopPropagation()
  readingStore.toggleBookmark(props.article.id)
}

/**
 * 封面图加载失败时的备用颜色（用公众号名首字符的 charCode 取模，
 * 保证同一公众号始终显示同一颜色）。
 */
const coverFallback = computed(() => {
  const colors = [
    '#6366f1', '#8b5cf6', '#ec4899', '#f97316', '#14b8a6', '#3b82f6', '#10b981',
  ]
  const idx = props.article.account.charCodeAt(0) % colors.length
  return colors[idx]
})

/**
 * 本地封面图路径：爬取时已下载到 data/covers/{id}.jpg。
 * article.id 中可能有 "/"（格式 "msgid-aid-time"），文件名中替换为 "_"。
 */
const localCoverSrc = computed(
  () => `/data/covers/${props.article.id.replace(/\//g, '_')}.jpg`,
)
// 封面图加载失败标志（img 的 @error 事件触发时置为 true，显示颜色占位块）
const coverError = ref(false)

/** 只取日期部分（"YYYY-MM-DD HH:MM" → "YYYY-MM-DD"） */
const formattedDate = computed(() => {
  const d = props.article.create_time
  if (!d) return ''
  return d.slice(0, 10)
})

/** 优先显示 LLM 摘要（summary），没有则显示原始摘要（digest） */
const displayDigest = computed(() => {
  return props.article.summary || props.article.digest || ''
})
</script>

<template>
  <a
    :href="article.link"
    target="_blank"
    rel="noopener noreferrer"
    class="group relative flex flex-col overflow-hidden rounded-xl border bg-[var(--color-card)] transition-all duration-200 hover:shadow-lg hover:-translate-y-0.5"
    :class="isRead
      ? 'border-[var(--color-border)] opacity-70 hover:opacity-100'
      : 'border-[var(--color-border)] hover:border-[var(--color-ring)]/30'"
    @click="handleClick"
  >
    <!-- 封面图区域（16:9 比例） -->
    <div class="relative aspect-[16/9] overflow-hidden bg-[var(--color-muted)] shrink-0">
      <!-- 优先显示本地封面，@error 时切换到颜色占位块 -->
      <img
        v-if="!coverError"
        :src="localCoverSrc"
        :alt="article.title"
        class="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
        loading="lazy"
        @error="coverError = true"
      />
      <!-- 封面不存在/加载失败时：用颜色块 + 公众号名前两字代替 -->
      <div
        v-else
        class="flex h-full w-full items-center justify-center text-white text-2xl font-bold opacity-80"
        :style="{ backgroundColor: coverFallback }"
      >
        {{ article.account.slice(0, 2) }}
      </div>

      <!-- AI 摘要徽标：有 LLM 生成的 summary 时显示 -->
      <div
        v-if="article.summary"
        class="absolute top-2 right-2 flex items-center gap-1 rounded-full bg-black/60 px-2 py-0.5 text-[10px] text-white backdrop-blur-sm"
      >
        <Bot class="h-3 w-3" />
        <span>AI 摘要</span>
      </div>

      <!-- 收藏按钮：悬停时出现，已收藏时常驻显示 -->
      <button
        @click="toggleBookmark"
        class="absolute bottom-2 right-2 flex h-7 w-7 items-center justify-center rounded-full transition-all"
        :class="isBookmarked
          ? 'bg-amber-500/90 text-white opacity-100'
          : 'bg-black/40 text-white opacity-0 group-hover:opacity-100 hover:bg-amber-500/80'"
        :title="isBookmarked ? '取消收藏' : '收藏'"
      >
        <BookmarkCheck v-if="isBookmarked" class="h-3.5 w-3.5" />
        <Bookmark v-else class="h-3.5 w-3.5" />
      </button>
    </div>

    <!-- 文字内容区 -->
    <div class="flex flex-1 flex-col gap-2 p-4">
      <div class="flex items-start gap-2">
        <!-- 未读蓝点：已读后消失 -->
        <span
          v-if="!isRead"
          class="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--color-primary)]"
        />
        <h3 class="line-clamp-2 text-sm font-semibold leading-snug text-[var(--color-foreground)] group-hover:text-[var(--color-primary)] transition-colors">
          {{ article.title }}
        </h3>
      </div>

      <!-- 摘要：优先 AI 摘要，line-clamp-3 超出省略 -->
      <p
        v-if="displayDigest"
        class="line-clamp-3 text-xs leading-relaxed text-[var(--color-muted-foreground)]"
      >
        {{ displayDigest }}
      </p>

      <!-- 标签列表（最多显示 3 个，避免占用太多空间） -->
      <div v-if="article.tags && article.tags.length" class="flex flex-wrap gap-1">
        <span
          v-for="tag in article.tags.slice(0, 3)"
          :key="tag"
          class="flex items-center gap-0.5 rounded-full bg-[var(--color-primary)]/10 px-2 py-0.5 text-[10px] font-medium text-[var(--color-primary)]"
        >
          <Tag class="h-2.5 w-2.5" />
          {{ tag }}
        </span>
      </div>

      <!-- 底部：公众号名 + 日期 + 外链图标 -->
      <div class="mt-auto flex items-center justify-between pt-1">
        <span class="text-xs font-medium text-[var(--color-muted-foreground)] truncate max-w-[60%]">
          {{ article.account }}
        </span>
        <div class="flex items-center gap-1.5 shrink-0">
          <span class="text-xs text-[var(--color-muted-foreground)]">{{ formattedDate }}</span>
          <!-- 悬停时出现的外链图标，提示用户点击会跳转 -->
          <ExternalLink class="h-3 w-3 text-[var(--color-muted-foreground)] opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>
      </div>
    </div>
  </a>
</template>
