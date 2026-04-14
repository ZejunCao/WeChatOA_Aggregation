<script setup lang="ts">
// ─────────────────────────────────────────────────────────────────────────────
// ArticleCard — 文章卡片组件（网格/卡片视图模式）
//
// 外观：竖向卡片，上方是封面图（16:9），下方是标题、摘要、标签、底部信息。
// 使用场景：FeedView 切换到"卡片视图"时渲染。
// ─────────────────────────────────────────────────────────────────────────────

import { computed, ref } from 'vue'
import { ExternalLink, Tag, Bot, Bookmark, BookmarkCheck, Trash2, Loader2 } from 'lucide-vue-next'
import type { Article } from '@/types'
import { useReadingStore } from '@/stores/reading'
import { useArticlesStore } from '@/stores/articles'

const props = defineProps<{
  article: Article & { account: string }  // 文章数据 + 所属公众号名称
}>()

const readingStore = useReadingStore()
const articlesStore = useArticlesStore()
const removing = ref(false)

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

/** 从本地列表删除并写入黑名单，后续爬取会跳过该 id */
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
   <a
    :href="article.link"
    target="_blank"
    rel="noopener noreferrer"
    class="group relative article-glass-card"
    :class="isRead ? 'is-read' : ''"
    @click="handleClick"
  >
    <!-- 封面图区域（16:9 比例） -->
    <div class="article-glass-cover bg-[var(--color-muted)] shrink-0">
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
      <div v-if="article.summary" class="article-glass-badge-ai">
        <Bot class="h-3 w-3 shrink-0" />
        <span>AI 摘要</span>
      </div>

      <!-- 删除：从列表移除并加入黑名单 -->
      <button
        type="button"
        @click="removeArticle"
        :disabled="removing"
        class="article-glass-btn-icon article-glass-btn-icon--del disabled:opacity-50 disabled:cursor-not-allowed"
        title="从列表删除"
      >
        <Loader2 v-if="removing" class="h-3.5 w-3.5 animate-spin" />
        <Trash2 v-else class="h-[13px] w-[13px]" />
      </button>

      <!-- 收藏按钮：悬停时出现，已收藏时常驻显示 -->
      <button
        type="button"
        @click="toggleBookmark"
        class="article-glass-btn-icon article-glass-btn-icon--bm"
        :class="isBookmarked ? 'is-on is-visible' : ''"
        :title="isBookmarked ? '取消收藏' : '收藏'"
      >
        <BookmarkCheck v-if="isBookmarked" class="h-3.5 w-3.5" />
        <Bookmark v-else class="h-3.5 w-3.5" />
      </button>
    </div>

    <!-- 文字内容区 -->
    <div class="article-glass-body">
      <div class="flex items-start gap-2">
        <span v-if="!isRead" class="feed-dot-unread" />
        <h3 class="article-glass-title line-clamp-2">
          {{ article.title }}
        </h3>
      </div>

      <p v-if="displayDigest" class="article-glass-digest line-clamp-3">
        {{ displayDigest }}
      </p>

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
          <span>{{ formattedDate }}</span>
          <ExternalLink class="h-3 w-3 shrink-0" />
        </div>
      </div>
    </div>
  </a>
</template>
