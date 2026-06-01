<script setup lang="ts">
// ─────────────────────────────────────────────────────────────────────────────
// ArticleCard — 文章卡片组件（网格/卡片视图模式）
//
// 外观：竖向卡片，上方是封面图（16:9），下方是标题、摘要、标签、底部信息。
// 使用场景：FeedView 切换到"卡片视图"时渲染。
// ─────────────────────────────────────────────────────────────────────────────

import { computed, ref } from 'vue'
import { TooltipContent, TooltipPortal, TooltipRoot, TooltipTrigger } from 'reka-ui'
import { Tag, Bot, Bookmark, BookmarkCheck, Trash2, LogOut, Loader2 } from 'lucide-vue-next'
import type { Article } from '@/types'
import { useReadingStore } from '@/stores/reading'
import { useArticleOpen } from '@/composables/useArticleOpen'
import { useArticleRemove } from '@/composables/useArticleRemove'

const props = defineProps<{
  article: Article & { account: string }  // 文章数据 + 所属公众号名称
  importMode?: boolean
}>()

const readingStore = useReadingStore()
const { onArticleClick, onArticleKeydown } = useArticleOpen()
const { removing, handleRemove } = useArticleRemove(
  () => props.article,
  () => !!props.importMode,
)

// 当前文章的已读/收藏状态（响应式，store 变化时自动更新）
const isRead = computed(() => readingStore.isRead(props.article.id))
const isBookmarked = computed(() => readingStore.isBookmarked(props.article.id))

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
    '#6366f1', '#8b5cf6', '#c94f7c', '#f97316', '#14b8a6', '#3b82f6', '#10b981',
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

const tagTones = ['article-glass-tag--ai', 'article-glass-tag--tech', 'article-glass-tag--prod', 'article-glass-tag--design'] as const
function tagToneClass(i: number) {
  return tagTones[i % 4]
}
</script>

<template>
  <div
    role="button"
    tabindex="0"
    draggable="false"
    class="group relative article-glass-card cursor-pointer"
    :class="isRead ? 'is-read' : ''"
    @click="onArticleClick($event, article)"
    @keydown="onArticleKeydown($event, article)"
  >
    <!-- 封面图区域（16:9 比例） -->
    <div class="article-glass-cover bg-[var(--color-muted)] shrink-0">
      <!-- 优先显示本地封面，@error 时切换到颜色占位块 -->
      <img
        v-if="!coverError"
        :src="localCoverSrc"
        :alt="article.title"
        draggable="false"
        class="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
        loading="lazy"
        @error="coverError = true"
        @dragstart.prevent
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
      <div v-if="article.summary" class="article-glass-badge-ai">
        <Bot class="h-3 w-3 shrink-0" />
        <span>AI 摘要</span>
      </div>

      <TooltipRoot>
        <TooltipTrigger as-child>
          <button
            type="button"
            class="article-glass-btn-icon article-glass-btn-icon--del disabled:opacity-50 disabled:cursor-not-allowed"
            :disabled="removing"
            @click="handleRemove"
          >
            <Loader2 v-if="removing" class="h-3.5 w-3.5 animate-spin" />
            <LogOut v-else-if="importMode" class="h-[13px] w-[13px]" />
            <Trash2 v-else class="h-[13px] w-[13px]" />
          </button>
        </TooltipTrigger>
        <TooltipPortal>
          <TooltipContent side="right" :side-offset="8" class="article-action-tooltip">
            {{
              importMode
                ? (article.source === 'import' ? '移出导入并删除' : '从导入列表移出')
                : '从列表中删除此文，并不再抓取'
            }}
          </TooltipContent>
        </TooltipPortal>
      </TooltipRoot>

      <TooltipRoot>
        <TooltipTrigger as-child>
          <button
            type="button"
            class="article-glass-btn-icon article-glass-btn-icon--bm"
            :class="isBookmarked ? 'is-on is-visible' : ''"
            @click="toggleBookmark"
          >
            <BookmarkCheck v-if="isBookmarked" class="h-3.5 w-3.5" />
            <Bookmark v-else class="h-3.5 w-3.5" />
          </button>
        </TooltipTrigger>
        <TooltipPortal>
          <TooltipContent side="left" :side-offset="8" class="article-action-tooltip">
            {{ isBookmarked ? '取消收藏' : '加入收藏' }}
          </TooltipContent>
        </TooltipPortal>
      </TooltipRoot>
    </div>

    <!-- 文字内容区 -->
    <div class="article-glass-body">
      <div class="flex items-start gap-2">
        <span v-if="!isRead" class="feed-dot-unread" />
        <h3 class="article-glass-title line-clamp-2">
          {{ article.title }}
        </h3>
      </div>

      <TooltipRoot v-if="displayDigest">
        <TooltipTrigger as-child>
          <p class="article-glass-digest line-clamp-2">
            {{ displayDigest }}
          </p>
        </TooltipTrigger>
        <TooltipPortal>
          <TooltipContent
            side="top"
            :side-offset="6"
            class="article-digest-tooltip z-[200] max-w-sm rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-3 py-2 text-xs leading-relaxed text-[var(--color-foreground)] shadow-lg outline-none"
          >
            {{ displayDigest }}
          </TooltipContent>
        </TooltipPortal>
      </TooltipRoot>

      <div v-if="article.tags && article.tags.length" class="flex flex-wrap gap-1.5">
        <span
          v-for="(tag, ti) in article.tags.slice(0, 3)"
          :key="tag"
          class="article-glass-tag inline-flex items-center gap-0.5"
          :class="tagToneClass(ti)"
        >
          <Tag class="h-2.5 w-2.5 opacity-80" />
          {{ tag }}
        </span>
      </div>

      <div class="article-glass-ft">
        <span class="article-glass-ft-acct">
          {{ article.account }}
        </span>
        <div class="article-glass-ft-meta">
          <span v-if="article.word_count && article.word_count > 0">{{ article.word_count }} 字</span>
          <span v-if="article.word_count && article.word_count > 0">·</span>
          <span>{{ formattedDate }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
