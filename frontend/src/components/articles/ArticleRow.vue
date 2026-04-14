<script setup lang="ts">
// ─────────────────────────────────────────────────────────────────────────────
// ArticleRow — 文章行组件（列表/行视图模式）
//
// 外观：横向布局，左边是小缩略图（128×80），右边是标题、摘要、元信息。
// 使用场景：FeedView 切换到"列表视图"时渲染，适合密集阅读。
// ─────────────────────────────────────────────────────────────────────────────

import { computed, ref } from 'vue'
import { ExternalLink, Tag, Bot, Bookmark, BookmarkCheck, Trash2, Loader2 } from 'lucide-vue-next'
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
    class="group article-glass-row"
    :class="isRead ? 'is-read' : ''"
    @click="handleClick"
  >
    <!-- 左侧缩略图（与 demo 列表视图一致的 72×50） -->
    <div class="article-glass-row-cover relative bg-[var(--color-muted)] sm:mt-0.5">
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
        class="flex h-full w-full items-center justify-center text-white text-sm font-bold opacity-90"
        :style="{ backgroundColor: coverFallback }"
      >
        {{ article.account.slice(0, 2) }}
      </div>
    </div>

    <!-- 右侧内容区 -->
    <div class="flex-1 min-w-0 space-y-1">
      <div class="flex items-start justify-between gap-2">
        <div class="flex items-start gap-2 flex-1 min-w-0">
          <span v-if="!isRead" class="feed-dot-unread mt-1" />
          <div class="min-w-0 flex-1 space-y-1">
            <h3 class="article-glass-row-title line-clamp-2 leading-snug">
              {{ article.title }}
            </h3>
            <p v-if="displayDigest" class="line-clamp-2 text-xs leading-relaxed text-[var(--feed-text-muted)] dark:text-[var(--feed-text-muted)]">
              {{ displayDigest }}
            </p>
            <div class="article-glass-row-sub flex flex-wrap items-center gap-x-2 gap-y-1">
              <span>{{ article.account }}</span>
              <span>·</span>
              <span>{{ formattedDate }}</span>
              <span v-if="article.summary" class="inline-flex items-center gap-0.5 rounded-md bg-violet-500/15 px-1.5 py-px text-[10px] font-semibold text-violet-700 dark:text-violet-300">
                <Bot class="h-3 w-3" />
                AI
              </span>
            </div>
            <div v-if="article.tags && article.tags.length" class="flex flex-wrap gap-1 pt-0.5">
              <span
                v-for="(tag, ti) in article.tags.slice(0, 3)"
                :key="tag"
                class="article-glass-tag inline-flex items-center gap-0.5 py-px"
                :class="tagToneClass(ti)"
              >
                <Tag class="h-2.5 w-2.5 opacity-80" />
                {{ tag }}
              </span>
            </div>
          </div>
        </div>
        <div class="flex items-center gap-1 shrink-0 pt-0.5">
          <button
            type="button"
            @click="removeArticle"
            :disabled="removing"
            class="flex h-7 w-7 items-center justify-center rounded-[10px] border border-white/60 bg-white/85 text-[var(--feed-text-subtle)] opacity-0 shadow-sm transition-all hover:border-red-300 hover:bg-red-50 hover:text-red-500 group-hover:opacity-100 disabled:opacity-40 dark:border-white/15 dark:bg-[rgba(30,27,46,0.8)] dark:hover:bg-red-950/40"
            title="从列表删除"
          >
            <Loader2 v-if="removing" class="h-3.5 w-3.5 animate-spin" />
            <Trash2 v-else class="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            @click="toggleBookmark"
            class="flex h-7 w-7 items-center justify-center rounded-[10px] border border-white/60 bg-white/85 text-[var(--feed-text-subtle)] shadow-sm transition-all group-hover:opacity-100 dark:border-white/15 dark:bg-[rgba(30,27,46,0.8)]"
            :class="isBookmarked
              ? 'opacity-100 border-amber-300/50 bg-amber-100/50 text-amber-700 dark:bg-amber-950/30 dark:text-amber-400'
              : 'opacity-0 hover:border-amber-200 hover:text-amber-600 dark:hover:text-amber-400'"
            :title="isBookmarked ? '取消收藏' : '收藏'"
          >
            <BookmarkCheck v-if="isBookmarked" class="h-3.5 w-3.5" />
            <Bookmark v-else class="h-3.5 w-3.5" />
          </button>
          <ExternalLink class="h-3.5 w-3.5 shrink-0 text-[var(--feed-accent)] opacity-0 group-hover:opacity-60 transition-opacity mt-0.5" />
        </div>
      </div>
    </div>
  </a>
</template>
