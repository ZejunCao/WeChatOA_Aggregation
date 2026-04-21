<script setup lang="ts">
// ─────────────────────────────────────────────────────────────────────────────
// ArticleRow — 文章行组件（列表/行视图模式）
//
// 外观：固定等高行；左 16:9 封面（高度为行内槽位约 86%，垂直居中）；右为标题 + 摘要 + 底栏。
// 使用场景：FeedView 切换到"列表视图"时渲染，适合密集阅读。
// ─────────────────────────────────────────────────────────────────────────────

import { computed, ref } from 'vue'
import { TooltipContent, TooltipPortal, TooltipRoot, TooltipTrigger } from 'reka-ui'
import { Tag, Bot, Bookmark, BookmarkCheck, Trash2, Loader2 } from 'lucide-vue-next'
import type { Article } from '@/types'
import { useReadingStore } from '@/stores/reading'
import { useArticlesStore } from '@/stores/articles'

const props = defineProps<{
  article: Article & { account: string }
}>()

const readingStore = useReadingStore()
const articlesStore = useArticlesStore()
const removing = ref(false)

// 已读/收藏状态（与 ArticleCard 相同的逻辑）
const isRead = computed(() => readingStore.isRead(props.article.id))
const isBookmarked = computed(() => readingStore.isBookmarked(props.article.id))

/** 点击行打开链接并标记已读；划词结束时的 click 不跳转 */
function handleClick(e: MouseEvent) {
  const sel = window.getSelection()
  if (sel && !sel.isCollapsed && sel.toString().trim().length > 0) {
    e.preventDefault()
    return
  }
  readingStore.markRead(props.article.id)
}

/** 切换收藏，阻止冒泡避免触发外层链接跳转 */
function toggleBookmark(e: MouseEvent) {
  e.preventDefault()
  e.stopPropagation()
  readingStore.toggleBookmark(props.article.id)
}

async function removeArticle(e: MouseEvent) {
  e.preventDefault()
  e.stopPropagation()
  if (
    !confirm(
      `从列表中删除「${props.article.title}」？\n将从本地数据移除，且以后爬取也不会再入库。`,
    )
  ) {
    return
  }
  removing.value = true
  try {
    const res = await fetch('/api/articles/remove', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        article_id: props.article.id,
        account: props.article.account,
      }),
    })
    const data = (await res.json().catch(() => ({}))) as { detail?: string }
    if (!res.ok) {
      alert(data.detail || '删除失败')
      return
    }
    readingStore.removeArticleTracking(props.article.id)
    articlesStore.removeArticleLocally(props.article.account, props.article.id)
  } catch {
    alert('无法连接后端，请确认 api.py 已启动')
  } finally {
    removing.value = false
  }
}

/** 封面加载失败时的备用颜色（与 ArticleCard 算法相同，保证同公众号颜色一致） */
const coverFallback = computed(() => {
  const colors = ['#6366f1', '#8b5cf6', '#c94f7c', '#f97316', '#14b8a6', '#3b82f6', '#10b981']
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

const tagTones = ['article-glass-tag--ai', 'article-glass-tag--tech', 'article-glass-tag--prod', 'article-glass-tag--design'] as const
function tagToneClass(i: number) {
  return tagTones[i % 4]
}
</script>

<template>
  <a
    :href="article.link"
    target="_blank"
    rel="noopener noreferrer"
    draggable="false"
    class="group article-glass-row"
    :class="isRead ? 'is-read' : ''"
    @click="handleClick"
  >
    <div class="article-glass-row-cover relative bg-[var(--color-muted)]">
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
      <!-- 封面失败时的颜色占位块 -->
      <div
        v-else
        class="flex h-full w-full items-center justify-center text-white text-sm font-bold opacity-90"
        :style="{ backgroundColor: coverFallback }"
      >
        {{ article.account.slice(0, 2) }}
      </div>
    </div>

    <div class="article-glass-row-body">
      <div class="article-glass-row-actions">
        <button
          type="button"
          @click="removeArticle"
          :disabled="removing"
          class="article-glass-row-action-btn article-glass-row-action-btn--del"
          title="从列表删除"
        >
          <Loader2 v-if="removing" class="h-3.5 w-3.5 animate-spin" />
          <Trash2 v-else class="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          @click="toggleBookmark"
          class="article-glass-row-action-btn article-glass-row-action-btn--bm"
          :class="isBookmarked ? 'is-on' : ''"
          :title="isBookmarked ? '取消收藏' : '收藏'"
        >
          <BookmarkCheck v-if="isBookmarked" class="h-3.5 w-3.5" />
          <Bookmark v-else class="h-3.5 w-3.5" />
        </button>
      </div>
      <div class="article-glass-row-main">
        <div class="flex items-start gap-2 min-w-0 min-h-0">
          <span v-if="!isRead" class="feed-dot-unread mt-1 shrink-0" />
          <div class="min-w-0 flex-1 flex flex-col gap-1 min-h-0">
            <h3 class="article-glass-row-title line-clamp-2 leading-snug shrink-0">
              {{ article.title }}
            </h3>
            <TooltipRoot v-if="displayDigest">
              <TooltipTrigger as-child>
                <p
                  class="line-clamp-2 text-xs leading-snug text-[var(--feed-text-muted)] dark:text-[var(--feed-text-muted)] shrink-0"
                >
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
            <div class="article-glass-row-footer">
              <div class="article-glass-row-sub flex min-w-0 items-center gap-x-1.5">
                <span class="min-w-0 truncate">{{ article.account }}</span>
                <span class="shrink-0">·</span>
                <span v-if="article.word_count && article.word_count > 0" class="shrink-0">{{ article.word_count }} 字</span>
                <span v-if="article.word_count && article.word_count > 0" class="shrink-0">·</span>
                <span class="shrink-0">{{ formattedDate }}</span>
                <span
                  v-if="article.summary"
                  class="inline-flex shrink-0 items-center gap-0.5 rounded-md bg-violet-500/15 px-1.5 py-px text-[10px] font-semibold text-violet-700 dark:text-violet-300"
                >
                  <Bot class="h-3 w-3" />
                  AI
                </span>
              </div>
              <div
                v-if="article.tags && article.tags.length"
                class="article-glass-row-tags hide-scrollbar"
              >
                <span
                  v-for="(tag, ti) in article.tags.slice(0, 3)"
                  :key="tag"
                  class="article-glass-tag inline-flex shrink-0 items-center gap-0.5 py-px"
                  :class="tagToneClass(ti)"
                >
                  <Tag class="h-2.5 w-2.5 opacity-80" />
                  {{ tag }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </a>
</template>
