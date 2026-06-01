<script setup lang="ts">
import { computed, ref, watch, onMounted, onUnmounted } from 'vue'
import DOMPurify from 'dompurify'
import {
  X,
  ExternalLink,
  Link2,
  Check,
  Bookmark,
  BookmarkCheck,
  ChevronLeft,
  ChevronRight,
  Loader2,
} from 'lucide-vue-next'
import { useArticlePreviewStore } from '@/stores/articlePreview'
import { useReadingStore } from '@/stores/reading'

const store = useArticlePreviewStore()
const readingStore = useReadingStore()

type CopyState = 'idle' | 'ok' | 'fail'
const copyState = ref<CopyState>('idle')
let copyResetTimer: ReturnType<typeof setTimeout> | undefined

const safePreviewHtml = computed(() => {
  const raw = store.previewHtml
  if (!raw) return ''
  return DOMPurify.sanitize(raw, { WHOLE_DOCUMENT: true })
})

const showNav = computed(
  () => store.navigationTotal > 1 && store.navigationIndex >= 0,
)

const navProgress = computed(() => {
  if (!showNav.value) return 0
  return ((store.navigationIndex + 1) / store.navigationTotal) * 100
})

async function copyLink() {
  if (copyResetTimer) clearTimeout(copyResetTimer)
  const ok = await store.copyOriginalLink()
  copyState.value = ok ? 'ok' : 'fail'
  copyResetTimer = setTimeout(() => {
    copyState.value = 'idle'
  }, 2200)
}

function toggleBookmark() {
  const id = store.display?.id
  if (id) void readingStore.toggleBookmark(id)
}

function isBookmarked(id: string) {
  return readingStore.isBookmarked(id)
}

function onKeydown(e: KeyboardEvent) {
  if (!store.open) return
  if (e.key === 'Escape') {
    e.preventDefault()
    store.close()
  } else if (e.key === 'ArrowLeft' && store.canGoPrev) {
    e.preventDefault()
    store.goPrev()
  } else if (e.key === 'ArrowRight' && store.canGoNext) {
    e.preventDefault()
    store.goNext()
  }
}

watch(
  () => store.open,
  (isOpen) => {
    document.body.style.overflow = isOpen ? 'hidden' : ''
    if (!isOpen) {
      copyState.value = 'idle'
      if (copyResetTimer) clearTimeout(copyResetTimer)
    }
  },
)

watch(
  () => store.display?.id,
  () => {
    copyState.value = 'idle'
  },
)

onMounted(() => window.addEventListener('keydown', onKeydown))
onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  document.body.style.overflow = ''
  if (copyResetTimer) clearTimeout(copyResetTimer)
})
</script>

<template>
  <Teleport to="body">
    <Transition name="article-preview-fade">
      <button
        v-if="store.open"
        type="button"
        class="article-preview-backdrop"
        aria-label="关闭预览"
        @click="store.close"
      />
    </Transition>

    <Transition name="article-preview-slide">
      <aside
        v-if="store.open && store.display"
        class="article-preview-panel article-preview-panel--iframe"
        role="dialog"
        aria-modal="true"
        :aria-label="store.display.title"
        @click.stop
      >
        <header class="article-preview-toolbar shrink-0">
          <nav
            v-if="showNav"
            class="article-preview-nav"
            aria-label="切换文章"
          >
            <div class="article-preview-nav-track" aria-hidden="true">
              <span
                class="article-preview-nav-track-fill"
                :style="{ width: `${navProgress}%` }"
              />
            </div>
            <div class="article-preview-nav-row">
              <button
                type="button"
                class="article-preview-nav-btn"
                :disabled="!store.canGoPrev"
                aria-label="上一篇"
                @click="store.goPrev"
              >
                <ChevronLeft class="h-4 w-4" />
              </button>
              <span class="article-preview-nav-label" aria-live="polite">
                <span class="article-preview-nav-current">{{ store.navigationIndex + 1 }}</span>
                <span class="article-preview-nav-sep">/</span>
                <span class="article-preview-nav-total">{{ store.navigationTotal }}</span>
              </span>
              <button
                type="button"
                class="article-preview-nav-btn"
                :disabled="!store.canGoNext"
                aria-label="下一篇"
                @click="store.goNext"
              >
                <ChevronRight class="h-4 w-4" />
              </button>
            </div>
          </nav>

          <div class="article-preview-toolbar-actions">
            <div class="article-preview-action-group">
              <button
                type="button"
                class="article-preview-action-btn"
                :class="{ 'is-active': isBookmarked(store.display.id) }"
                :aria-label="isBookmarked(store.display.id) ? '取消收藏' : '收藏'"
                @click="toggleBookmark"
              >
                <BookmarkCheck v-if="isBookmarked(store.display.id)" class="h-4 w-4" />
                <Bookmark v-else class="h-4 w-4" />
              </button>
              <button
                type="button"
                class="article-preview-action-btn"
                :class="{
                  'is-success': copyState === 'ok',
                  'is-error': copyState === 'fail',
                }"
                :aria-label="copyState === 'ok' ? '已复制链接' : copyState === 'fail' ? '复制失败' : '复制原文链接'"
                @click="copyLink"
              >
                <Check v-if="copyState === 'ok'" class="h-4 w-4" />
                <Link2 v-else class="h-4 w-4" />
              </button>
            </div>
            <button
              type="button"
              class="article-preview-action-btn article-preview-action-btn--close"
              aria-label="关闭预览"
              @click="store.close"
            >
              <X class="h-4 w-4" />
            </button>
          </div>
        </header>

        <div class="article-preview-iframe-wrap">
          <div v-if="store.loading" class="article-preview-iframe-loading">
            <Loader2 class="h-6 w-6 animate-spin text-[var(--color-muted-foreground)]" />
            <span class="text-sm text-[var(--color-muted-foreground)]">正在加载排版…</span>
          </div>

          <div v-else-if="store.error" class="article-preview-iframe-fallback">
            <p class="text-sm text-amber-700 dark:text-amber-300 mb-3">{{ store.error }}</p>
            <button type="button" class="article-preview-primary-btn max-w-xs" @click="store.openOriginal">
              <ExternalLink class="h-4 w-4" />
              在微信中打开
            </button>
          </div>

          <iframe
            v-else-if="safePreviewHtml"
            :key="store.display.id"
            class="article-preview-iframe"
            title="微信公众号原文预览"
            sandbox="allow-same-origin allow-popups"
            :srcdoc="safePreviewHtml"
          />

          <button
            v-if="!store.loading && !store.error && store.display?.link"
            type="button"
            class="article-preview-open-original"
            @click="store.openOriginal"
          >
            <ExternalLink class="h-3.5 w-3.5 shrink-0" />
            在微信中打开原文
          </button>
        </div>
      </aside>
    </Transition>
  </Teleport>
</template>
