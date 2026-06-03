<script setup lang="ts">
// ─────────────────────────────────────────────────────────────────────────────
// NoteCard — 笔记时间线卡片（笔记为主体，文章为出处）
// 点击卡片：打开文章预览并直接展开笔记编辑。
// ─────────────────────────────────────────────────────────────────────────────

import { computed, ref } from 'vue'
import DOMPurify from 'dompurify'
import { ExternalLink, Trash2, Loader2, Pencil } from 'lucide-vue-next'
import type { Article } from '@/types'
import { useArticlePreviewStore } from '@/stores/articlePreview'
import { accountColor } from '@/lib/accountColor'
import { displayText } from '@/lib/displayText'

const props = defineProps<{
  article: Article & { account: string }
}>()

const emit = defineEmits<{
  deleted: [id: string]
}>()

const previewStore = useArticlePreviewStore()

const title = computed(() => displayText(props.article.title) || '无标题')
const accountName = computed(() => displayText(props.article.account))
const dotColor = computed(() => accountColor(props.article.account))

const safeNoteHtml = computed(() =>
  DOMPurify.sanitize(props.article.note_content || '', {
    USE_PROFILES: { html: true },
  }),
)

const localCoverSrc = computed(
  () => `/data/covers/${props.article.id.replace(/\//g, '_')}.jpg`,
)
const coverError = ref(false)

/** 相对时间：刚刚 / N分钟前 / N小时前 / N天前 / YYYY-MM-DD */
const editedLabel = computed(() => {
  const raw = props.article.note_updated_at
  if (!raw) return ''
  const t = new Date(raw.replace(' ', 'T')).getTime()
  if (Number.isNaN(t)) return raw.slice(0, 10)
  const diff = Date.now() - t
  const min = Math.floor(diff / 60000)
  if (min < 1) return '刚刚编辑'
  if (min < 60) return `${min} 分钟前编辑`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr} 小时前编辑`
  const day = Math.floor(hr / 24)
  if (day < 7) return `${day} 天前编辑`
  return `编辑于 ${raw.slice(0, 10)}`
})

function openNote() {
  void previewStore.openPreview(props.article, { expandNote: true })
}

function openOriginal(e: MouseEvent) {
  e.stopPropagation()
  if (props.article.link) {
    window.open(props.article.link, '_blank', 'noopener,noreferrer')
  }
}

const deleting = ref(false)
async function removeNote(e: MouseEvent) {
  e.stopPropagation()
  if (deleting.value) return
  if (!window.confirm(`删除「${title.value}」的笔记？此操作不可恢复。`)) return
  deleting.value = true
  try {
    const res = await fetch(
      `/api/articles/${encodeURIComponent(props.article.id)}/note`,
      {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: '' }),
      },
    )
    if (res.ok) emit('deleted', props.article.id)
  } finally {
    deleting.value = false
  }
}
</script>

<template>
  <article
    class="note-card group"
    role="button"
    tabindex="0"
    @click="openNote"
    @keydown.enter.prevent="openNote"
    @keydown.space.prevent="openNote"
  >
    <!-- 顶部：出处 + 编辑时间 + 悬停操作 -->
    <header class="note-card-head">
      <span class="note-card-dot" :style="{ backgroundColor: dotColor }" />
      <span class="note-card-account">{{ accountName }}</span>
      <span v-if="editedLabel" class="note-card-sep">·</span>
      <span v-if="editedLabel" class="note-card-time">{{ editedLabel }}</span>

      <div class="note-card-actions">
        <button
          type="button"
          class="note-card-act"
          title="在微信中打开原文"
          @click="openOriginal"
        >
          <ExternalLink class="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          class="note-card-act note-card-act--danger"
          title="删除笔记"
          :disabled="deleting"
          @click="removeNote"
        >
          <Loader2 v-if="deleting" class="h-3.5 w-3.5 animate-spin" />
          <Trash2 v-else class="h-3.5 w-3.5" />
        </button>
      </div>
    </header>

    <!-- 笔记内容（主体） -->
    <div
      v-if="safeNoteHtml"
      class="note-card-content"
      v-html="safeNoteHtml"
    />
    <p v-else class="note-card-empty">（空笔记）</p>

    <!-- 底部：来源文章引用 -->
    <footer class="note-card-source">
      <div class="note-card-thumb">
        <img
          v-if="!coverError"
          :src="localCoverSrc"
          :alt="title"
          loading="lazy"
          @error="coverError = true"
        />
        <div
          v-else
          class="note-card-thumb-fallback"
          :style="{ backgroundColor: dotColor }"
        >
          {{ accountName.slice(0, 2) }}
        </div>
      </div>
      <div class="note-card-source-meta">
        <span class="note-card-source-label">原文</span>
        <span class="note-card-source-title">{{ title }}</span>
      </div>
      <span class="note-card-edit-hint">
        <Pencil class="h-3 w-3" />
        点击编辑
      </span>
    </footer>
  </article>
</template>

<style scoped>
.note-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px 18px;
  margin-bottom: 14px;
  border-radius: 16px;
  border: 1px solid var(--color-border);
  background: var(--color-card);
  cursor: pointer;
  break-inside: avoid;
  page-break-inside: avoid;
  transition: border-color 0.2s, box-shadow 0.2s, transform 0.2s;
}

@media (min-width: 768px) {
  .note-card {
    margin-bottom: 16px;
  }
}

.note-card:hover {
  border-color: var(--feed-accent-soft, var(--color-primary));
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.06);
  transform: translateY(-1px);
}

.note-card-head {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--color-muted-foreground);
}

.note-card-dot {
  width: 8px;
  height: 8px;
  border-radius: 9999px;
  flex-shrink: 0;
}

.note-card-account {
  font-weight: 600;
  color: var(--color-foreground);
  max-width: 40%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.note-card-sep {
  opacity: 0.5;
}

.note-card-actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s;
}

.note-card:hover .note-card-actions,
.note-card:focus-within .note-card-actions {
  opacity: 1;
}

.note-card-act {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  color: var(--color-muted-foreground);
  transition: background 0.15s, color 0.15s;
}

.note-card-act:hover {
  background: var(--color-accent);
  color: var(--color-foreground);
}

.note-card-act--danger:hover {
  background: rgba(239, 68, 68, 0.12);
  color: #ef4444;
}

/* 笔记正文（来自 Tiptap 的 HTML） */
.note-card-content {
  font-size: 14px;
  line-height: 1.7;
  color: var(--color-foreground);
  word-break: break-word;
}

.note-card-content :deep(p) {
  margin: 0 0 6px;
}
.note-card-content :deep(p:last-child) {
  margin-bottom: 0;
}
.note-card-content :deep(h1),
.note-card-content :deep(h2),
.note-card-content :deep(h3) {
  font-weight: 700;
  margin: 8px 0 4px;
  line-height: 1.4;
}
.note-card-content :deep(h1) { font-size: 17px; }
.note-card-content :deep(h2) { font-size: 15px; }
.note-card-content :deep(h3) { font-size: 14px; }
.note-card-content :deep(ul),
.note-card-content :deep(ol) {
  margin: 4px 0;
  padding-left: 20px;
}
.note-card-content :deep(li) { margin: 2px 0; }
.note-card-content :deep(blockquote) {
  border-left: 3px solid var(--color-border);
  padding-left: 10px;
  margin: 6px 0;
  color: var(--color-muted-foreground);
}
.note-card-content :deep(code) {
  background: var(--color-muted);
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 13px;
}
.note-card-content :deep(pre) {
  background: var(--color-muted);
  padding: 10px 12px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 6px 0;
}
.note-card-content :deep(pre code) {
  background: transparent;
  padding: 0;
}
.note-card-content :deep(a) {
  color: var(--color-primary);
  text-decoration: underline;
}
.note-card-content :deep(ul[data-type='taskList']) {
  list-style: none;
  padding-left: 4px;
}
.note-card-content :deep(ul[data-type='taskList'] li) {
  display: flex;
  align-items: flex-start;
  gap: 6px;
}
.note-card-content :deep(table) {
  border-collapse: collapse;
  margin: 6px 0;
}
.note-card-content :deep(td),
.note-card-content :deep(th) {
  border: 1px solid var(--color-border);
  padding: 3px 8px;
}

.note-card-empty {
  font-size: 13px;
  color: var(--color-muted-foreground);
  font-style: italic;
}

.note-card-source {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-top: 12px;
  border-top: 1px dashed var(--color-border);
}

.note-card-thumb {
  width: 44px;
  height: 44px;
  border-radius: 8px;
  overflow: hidden;
  flex-shrink: 0;
  background: var(--color-muted);
}

.note-card-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.note-card-thumb-fallback {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 12px;
  font-weight: 700;
}

.note-card-source-meta {
  min-width: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.note-card-source-label {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--color-muted-foreground);
}

.note-card-source-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-foreground);
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.note-card-edit-hint {
  margin-left: auto;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--color-muted-foreground);
  opacity: 0;
  transition: opacity 0.2s;
}

.note-card:hover .note-card-edit-hint {
  opacity: 1;
}
</style>
