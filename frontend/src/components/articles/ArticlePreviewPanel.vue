<script setup lang="ts">
import { computed, ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
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
  NotebookPen,
  Quote,
  Bold,
  Italic,
  Code2,
  Table,
  Heading1,
  Heading2,
  ListTodo,
  List,
  ListOrdered,
  Underline as UnderlineIcon,
  Link as LinkIcon,
  Minus,
} from 'lucide-vue-next'
import ArticleImageLightbox from '@/components/articles/ArticleImageLightbox.vue'
import PreviewAccountDialog from '@/components/articles/PreviewAccountDialog.vue'
import { useArticlePreviewStore } from '@/stores/articlePreview'
import { useReadingStore } from '@/stores/reading'
import { EditorContent, useEditor } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Underline from '@tiptap/extension-underline'
import Link from '@tiptap/extension-link'
import { Table as TableExt } from '@tiptap/extension-table'
import TableRow from '@tiptap/extension-table-row'
import TableHeader from '@tiptap/extension-table-header'
import TableCell from '@tiptap/extension-table-cell'
import TaskList from '@tiptap/extension-task-list'
import TaskItem from '@tiptap/extension-task-item'
import Placeholder from '@tiptap/extension-placeholder'

const store = useArticlePreviewStore()
const readingStore = useReadingStore()

type CopyState = 'idle' | 'ok' | 'fail'
const copyState = ref<CopyState>('idle')
let copyResetTimer: ReturnType<typeof setTimeout> | undefined

const iframeRef = ref<HTMLIFrameElement | null>(null)
const imgLightboxOpen = ref(false)
const imgLightboxSrc = ref('')
const accountDialogOpen = ref(false)

function onPreviewIframeMessage(ev: MessageEvent) {
  if (!store.open) return
  const data = ev.data
  if (!data || typeof data !== 'object') return
  if ((data as { type?: string }).type !== 'wx-preview-img-open') return
  const src = typeof (data as { src?: string }).src === 'string' ? (data as { src: string }).src.trim() : ''
  if (!src) return
  const okHttp = /^https?:\/\//i.test(src)
  const okProxy = src.startsWith('/api/wechat-image')
  if (!okHttp && !okProxy) return
  imgLightboxSrc.value = src
  imgLightboxOpen.value = true
}
/** HTML 已注入 iframe，首屏配图加载完成（或超时）后再展示 */
const mediaReady = ref(false)
let mediaReadyTimer: ReturnType<typeof setTimeout> | undefined
let mediaWaitGen = 0
let unlinkPreviewClickHandler: (() => void) | undefined

const PREVIEW_LINK_BASE = 'https://mp.weixin.qq.com/'

const FIRST_SCREEN_IMG_COUNT = 6
const MEDIA_READY_TIMEOUT_MS = 2800
const NOTE_AUTOSAVE_MS = 900

const notesExpanded = ref(false)
const noteLoading = ref(false)
const noteSaving = ref(false)
const noteHtml = ref('')
const noteUpdatedAt = ref('')
const noteLoadedFor = ref('')
const selectedQuoteText = ref('')
const quoteActionVisible = ref(false)
const quoteActionX = ref(0)
const quoteActionY = ref(0)
let noteSaveTimer: ReturnType<typeof setTimeout> | undefined
let selectingUnbind: (() => void) | undefined
let syncingNote = false
/** 中文输入法组字中，避免 Esc 被全局监听误关预览 */
const noteImeComposing = ref(false)

const noteEditor = useEditor({
  editorProps: {
    handleDOMEvents: {
      compositionstart: () => {
        noteImeComposing.value = true
        return false
      },
      compositionend: () => {
        noteImeComposing.value = false
        return false
      },
    },
  },
  extensions: [
    StarterKit.configure({
      heading: { levels: [1, 2, 3] },
    }),
    Underline,
    Link.configure({
      openOnClick: false,
      autolink: true,
      defaultProtocol: 'https',
    }),
    TableExt.configure({
      resizable: true,
    }),
    TableRow,
    TableHeader,
    TableCell,
    TaskList,
    TaskItem.configure({ nested: true }),
    Placeholder.configure({
      placeholder: '本文说了...',
    }),
  ],
  content: '',
  editable: true,
  onUpdate: ({ editor }) => {
    if (syncingNote || noteLoading.value) return
    noteHtml.value = editor.getHTML()
    scheduleNoteSave()
  },
})
const noteEditorInstance = computed(() => noteEditor.value)

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { cache: 'no-store', ...init })
  const data = (await res.json()) as T & { detail?: string }
  if (!res.ok) throw new Error(data.detail || `请求失败 (${res.status})`)
  return data
}

async function loadNote(articleId: string) {
  noteLoading.value = true
  noteEditor.value?.setEditable(false)
  try {
    const data = await fetchJson<{ content: string; updated_at: string }>(
      `/api/articles/${encodeURIComponent(articleId)}/note`,
    )
    syncingNote = true
    noteHtml.value = data.content || ''
    noteEditor.value?.commands.setContent(noteHtml.value || '<p></p>', { emitUpdate: false })
    noteUpdatedAt.value = data.updated_at || ''
    noteLoadedFor.value = articleId
  } catch {
    syncingNote = true
    noteHtml.value = ''
    noteEditor.value?.commands.setContent('<p></p>', { emitUpdate: false })
    noteUpdatedAt.value = ''
    noteLoadedFor.value = articleId
  } finally {
    noteLoading.value = false
    noteEditor.value?.setEditable(true)
    setTimeout(() => {
      syncingNote = false
    }, 0)
  }
}

async function saveNoteNow() {
  const articleId = store.display?.id
  if (!articleId || noteLoadedFor.value !== articleId) return
  noteSaving.value = true
  try {
    const data = await fetchJson<{ content: string; updated_at: string }>(
      `/api/articles/${encodeURIComponent(articleId)}/note`,
      {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: noteHtml.value }),
      },
    )
    noteUpdatedAt.value = data.updated_at || ''
  } finally {
    noteSaving.value = false
  }
}

function scheduleNoteSave() {
  if (noteSaveTimer) clearTimeout(noteSaveTimer)
  noteSaveTimer = setTimeout(() => {
    void saveNoteNow()
  }, NOTE_AUTOSAVE_MS)
}

function execRich(run: () => void) {
  if (noteLoading.value) return
  run()
}

function insertHtml(html: string) {
  execRich(() => {
    noteEditor.value?.chain().focus().insertContent(html).run()
  })
}

function hideQuoteAction() {
  quoteActionVisible.value = false
}

function updateQuoteActionPosition(rect: DOMRect) {
  const x = rect.left + rect.width / 2
  const y = rect.top - 10
  quoteActionX.value = x
  quoteActionY.value = y
  quoteActionVisible.value = true
}

async function appendQuoteBlock() {
  const quote = selectedQuoteText.value.trim()
  if (!quote) return
  if (!notesExpanded.value) {
    notesExpanded.value = true
    await nextTick()
  }
  const q = quote
    .split(/\n+/)
    .map((x) => x.trim())
    .filter(Boolean)
    .map((x) => x.replace(/[&<>"]/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch] || ch)))
    .join('<br>')
  insertHtml(
    `<p>【引用的原文】</p><blockquote>${q}</blockquote><p></p>`,
  )
  selectedQuoteText.value = ''
  hideQuoteAction()
}

function setHeading(level: 1 | 2 | 3) {
  execRich(() => {
    noteEditor.value?.chain().focus().toggleHeading({ level }).run()
  })
}

function setParagraph() {
  execRich(() => {
    noteEditor.value?.chain().focus().setParagraph().run()
  })
}

function toggleLink() {
  execRich(() => {
    const editor = noteEditor.value
    if (!editor) return
    const prev = editor.getAttributes('link').href as string | undefined
    const next = window.prompt('输入链接地址', prev || 'https://')
    if (next === null) return
    if (!next.trim()) {
      editor.chain().focus().unsetLink().run()
      return
    }
    editor.chain().focus().extendMarkRange('link').setLink({ href: next.trim() }).run()
  })
}

function isNoteActive(name: string, attrs?: Record<string, unknown>) {
  return !!noteEditor.value?.isActive(name, attrs)
}

function noteBold() {
  execRich(() => noteEditor.value?.chain().focus().toggleBold().run())
}
function noteItalic() {
  execRich(() => noteEditor.value?.chain().focus().toggleItalic().run())
}
function noteUnderline() {
  execRich(() => noteEditor.value?.chain().focus().toggleUnderline().run())
}
function noteBulletList() {
  execRich(() => noteEditor.value?.chain().focus().toggleBulletList().run())
}
function noteOrderedList() {
  execRich(() => noteEditor.value?.chain().focus().toggleOrderedList().run())
}
function noteTaskList() {
  execRich(() => noteEditor.value?.chain().focus().toggleTaskList().run())
}
function noteBlockquote() {
  execRich(() => noteEditor.value?.chain().focus().toggleBlockquote().run())
}
function noteInlineCode() {
  execRich(() => noteEditor.value?.chain().focus().toggleCode().run())
}
function noteCodeBlock() {
  execRich(() => noteEditor.value?.chain().focus().toggleCodeBlock().run())
}
function noteDivider() {
  execRich(() => noteEditor.value?.chain().focus().setHorizontalRule().run())
}
function noteInsertTable() {
  execRich(() =>
    noteEditor.value
      ?.chain()
      .focus()
      .insertTable({ rows: 2, cols: 2, withHeaderRow: true })
      .run(),
  )
}

function formatNoteTime(ts: string) {
  if (!ts) return ''
  return ts.replace('T', ' ').slice(0, 16)
}

const isPicturePreview = computed(() =>
  (store.previewHtml || '').includes('preview-picture-v'),
)
const isScriptedNormalPreview = computed(() =>
  (store.previewHtml || '').includes('preview-img-lightbox-v'),
)

/** 图片消息预览含自有轮播脚本，需保留 script 且 iframe 允许执行 */
const safePreviewHtml = computed(() => {
  const raw = store.previewHtml
  if (!raw) return ''
  if (isPicturePreview.value || isScriptedNormalPreview.value) {
    return raw
  }
  return DOMPurify.sanitize(raw, { WHOLE_DOCUMENT: true })
})

const previewIframeSandbox = computed(() =>
  (isPicturePreview.value || isScriptedNormalPreview.value)
    ? 'allow-same-origin allow-popups allow-scripts'
    : 'allow-same-origin allow-popups',
)

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

function shouldIgnorePreviewEscape(e: KeyboardEvent): boolean {
  if (e.isComposing || noteImeComposing.value) return true
  const active = document.activeElement
  if (!active) return false
  if (
    active.closest('.article-note-panel') ||
    active.closest('.ProseMirror') ||
    active.tagName === 'INPUT' ||
    active.tagName === 'TEXTAREA'
  ) {
    return true
  }
  return false
}

function onKeydown(e: KeyboardEvent) {
  if (!store.open) return
  if (imgLightboxOpen.value) return
  if (accountDialogOpen.value) {
    if (e.key === 'Escape') {
      e.preventDefault()
      accountDialogOpen.value = false
    }
    return
  }
  if (e.key === 'Escape') {
    if (shouldIgnorePreviewEscape(e)) return
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

function clearMediaReadyTimer() {
  if (mediaReadyTimer) {
    clearTimeout(mediaReadyTimer)
    mediaReadyTimer = undefined
  }
}

function finishMediaReady() {
  clearMediaReadyTimer()
  mediaReady.value = true
}

function waitForFirstScreenImages() {
  const gen = ++mediaWaitGen
  mediaReady.value = false
  clearMediaReadyTimer()
  mediaReadyTimer = setTimeout(() => {
    if (gen === mediaWaitGen) finishMediaReady()
  }, MEDIA_READY_TIMEOUT_MS)

  void nextTick(() => {
    if (gen !== mediaWaitGen) return
    const doc = iframeRef.value?.contentDocument
    if (!doc) {
      finishMediaReady()
      return
    }
    const imgs = Array.from(
      doc.querySelectorAll<HTMLImageElement>(
        '#js_content img, #js_article img, .wx-preview-img, .wx-picture-slide img',
      ),
    ).filter((el) => el.getAttribute('src'))
    const targets = imgs.slice(0, FIRST_SCREEN_IMG_COUNT)
    if (!targets.length) {
      finishMediaReady()
      return
    }
    const markLoaded = (img: HTMLImageElement) => {
      img.setAttribute('data-wx-img-state', 'loaded')
    }
    void Promise.all(
      targets.map(
        (img) =>
          new Promise<void>((resolve) => {
            if (img.complete && img.naturalWidth > 0) {
              markLoaded(img)
              resolve()
              return
            }
            const done = () => {
              if (img.naturalWidth > 0) markLoaded(img)
              resolve()
            }
            img.addEventListener('load', done, { once: true })
            img.addEventListener('error', done, { once: true })
          }),
      ),
    ).then(() => {
      if (gen === mediaWaitGen) finishMediaReady()
    })
  })
}

function openPreviewLinkInNewWindow(rawHref: string) {
  const href = rawHref.trim()
  if (!href || href.startsWith('#')) return
  const lower = href.toLowerCase()
  if (lower.startsWith('javascript:') || lower.startsWith('mailto:') || lower.startsWith('tel:')) {
    return
  }
  let url: string
  try {
    url = new URL(href, PREVIEW_LINK_BASE).href
  } catch {
    return
  }
  const win = window.open(url, '_blank', 'noopener,noreferrer')
  win?.focus()
}

function openAccountDialog() {
  const name = store.display?.account?.trim()
  if (!name) return
  accountDialogOpen.value = true
}

function bindPreviewLinkClicks() {
  unlinkPreviewClickHandler?.()
  unlinkPreviewClickHandler = undefined
  selectingUnbind?.()
  selectingUnbind = undefined
  const doc = iframeRef.value?.contentDocument
  if (!doc) return

  const onDocClick = (e: MouseEvent) => {
    const nicknameEl = (e.target as Element | null)?.closest?.(
      '.rich_media_meta_nickname, #js_name, .wx-preview-account',
    )
    if (nicknameEl) {
      e.preventDefault()
      e.stopPropagation()
      openAccountDialog()
      return
    }
    const anchor = (e.target as Element | null)?.closest?.('a')
    if (!anchor) return
    const href = anchor.getAttribute('href')
    if (!href || href.startsWith('#')) return
    e.preventDefault()
    e.stopPropagation()
    openPreviewLinkInNewWindow(href)
  }

  doc.addEventListener('click', onDocClick, true)
  const syncSelection = () => {
    const sel = doc.getSelection()
    const txt = (sel?.toString() || '').trim().replace(/\s+\n/g, '\n')
    if (!txt || !sel || sel.rangeCount === 0) {
      selectedQuoteText.value = ''
      hideQuoteAction()
      return
    }
    const rect = sel.getRangeAt(0).getBoundingClientRect()
    if (!rect || (rect.width === 0 && rect.height === 0)) {
      selectedQuoteText.value = ''
      hideQuoteAction()
      return
    }
    selectedQuoteText.value = txt.slice(0, 1200)
    updateQuoteActionPosition(rect)
  }
  doc.addEventListener('mouseup', syncSelection)
  doc.addEventListener('keyup', syncSelection)
  doc.addEventListener('selectionchange', syncSelection)
  doc.defaultView?.addEventListener('scroll', hideQuoteAction, { passive: true })
  unlinkPreviewClickHandler = () => {
    doc.removeEventListener('click', onDocClick, true)
  }
  selectingUnbind = () => {
    doc.removeEventListener('mouseup', syncSelection)
    doc.removeEventListener('keyup', syncSelection)
    doc.removeEventListener('selectionchange', syncSelection)
    doc.defaultView?.removeEventListener('scroll', hideQuoteAction)
  }
}

function onIframeLoad() {
  if (!store.previewHtml || store.loading) return
  const doc = iframeRef.value?.contentDocument
  const isPicture = doc?.body?.getAttribute('data-wx-preview-kind') === 'picture'
  bindPreviewLinkClicks()
  if (isPicture) {
    finishMediaReady()
    return
  }
  waitForFirstScreenImages()
}

watch(
  () => store.open,
  (isOpen) => {
    if (!isOpen) {
      imgLightboxOpen.value = false
      imgLightboxSrc.value = ''
    }
    document.body.style.overflow = isOpen ? 'hidden' : ''
    if (!isOpen) {
      accountDialogOpen.value = false
      noteImeComposing.value = false
      copyState.value = 'idle'
      if (copyResetTimer) clearTimeout(copyResetTimer)
      mediaReady.value = false
      clearMediaReadyTimer()
      mediaWaitGen++
      unlinkPreviewClickHandler?.()
      unlinkPreviewClickHandler = undefined
      selectingUnbind?.()
      selectingUnbind = undefined
      selectedQuoteText.value = ''
      hideQuoteAction()
      if (noteSaveTimer) clearTimeout(noteSaveTimer)
    }
  },
)

watch(
  () => store.display?.id,
  (id) => {
    copyState.value = 'idle'
    mediaReady.value = false
    mediaWaitGen++
    selectedQuoteText.value = ''
    hideQuoteAction()
    if (id) void loadNote(id)
  },
)

watch(
  () => notesExpanded.value,
  (expanded) => {
    if (!expanded) return
    void nextTick(() => {
      if (!noteEditor.value) return
      noteEditor.value.commands.focus('end')
    })
  },
)

// 来自「笔记」页：打开预览时自动展开笔记面板
watch(
  () => store.expandNoteRequest,
  () => {
    notesExpanded.value = true
  },
)

watch(
  () => [store.loading, store.previewHtml] as const,
  ([loading, html]) => {
    if (loading || !html) {
      mediaReady.value = false
      mediaWaitGen++
    }
  },
)

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
  window.addEventListener('message', onPreviewIframeMessage)
})
onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  window.removeEventListener('message', onPreviewIframeMessage)
  imgLightboxOpen.value = false
  document.body.style.overflow = ''
  if (copyResetTimer) clearTimeout(copyResetTimer)
  clearMediaReadyTimer()
  if (noteSaveTimer) clearTimeout(noteSaveTimer)
  unlinkPreviewClickHandler?.()
  selectingUnbind?.()
  hideQuoteAction()
  noteEditor.value?.destroy()
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
          <button
            type="button"
            class="article-preview-action-btn article-preview-notes-toggle"
            :class="{ 'is-active': notesExpanded }"
            :aria-label="notesExpanded ? '收起笔记' : '展开笔记'"
            @click="notesExpanded = !notesExpanded"
          >
            <NotebookPen class="h-4 w-4" />
          </button>
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

        <div class="article-preview-content">
          <aside v-if="notesExpanded" class="article-note-panel">
            <header class="article-note-panel-head">
              <div class="article-note-title-wrap">
                <NotebookPen class="h-4 w-4" />
                <h3 class="article-note-title">阅读笔记</h3>
              </div>
              <span class="article-note-status">
                {{ noteSaving ? '保存中...' : (noteUpdatedAt ? `已保存 ${formatNoteTime(noteUpdatedAt)}` : '未保存') }}
              </span>
            </header>
            <div class="article-note-toolbar">
              <button type="button" class="article-note-tool-btn" :class="{ 'is-active': isNoteActive('bold') }" title="加粗" @click="noteBold"><Bold class="h-3.5 w-3.5" /></button>
              <button type="button" class="article-note-tool-btn" :class="{ 'is-active': isNoteActive('italic') }" title="斜体" @click="noteItalic"><Italic class="h-3.5 w-3.5" /></button>
              <button type="button" class="article-note-tool-btn" :class="{ 'is-active': isNoteActive('underline') }" title="下划线" @click="noteUnderline"><UnderlineIcon class="h-3.5 w-3.5" /></button>
              <button type="button" class="article-note-tool-btn" :class="{ 'is-active': isNoteActive('heading', { level: 1 }) }" title="一级标题" @click="setHeading(1)"><Heading1 class="h-3.5 w-3.5" /></button>
              <button type="button" class="article-note-tool-btn" :class="{ 'is-active': isNoteActive('heading', { level: 2 }) }" title="二级标题" @click="setHeading(2)"><Heading2 class="h-3.5 w-3.5" /></button>
              <button type="button" class="article-note-tool-btn" title="正文" @click="setParagraph">正文</button>
              <button type="button" class="article-note-tool-btn" :class="{ 'is-active': isNoteActive('bulletList') }" title="无序列表" @click="noteBulletList"><List class="h-3.5 w-3.5" /></button>
              <button type="button" class="article-note-tool-btn" :class="{ 'is-active': isNoteActive('orderedList') }" title="有序列表" @click="noteOrderedList"><ListOrdered class="h-3.5 w-3.5" /></button>
              <button type="button" class="article-note-tool-btn" :class="{ 'is-active': isNoteActive('taskList') }" title="待办清单" @click="noteTaskList"><ListTodo class="h-3.5 w-3.5" /></button>
              <button type="button" class="article-note-tool-btn" :class="{ 'is-active': isNoteActive('blockquote') }" title="引用块" @click="noteBlockquote"><Quote class="h-3.5 w-3.5" /></button>
              <button type="button" class="article-note-tool-btn" :class="{ 'is-active': isNoteActive('code') }" title="行内代码" @click="noteInlineCode"><Code2 class="h-3.5 w-3.5" /></button>
              <button type="button" class="article-note-tool-btn" :class="{ 'is-active': isNoteActive('codeBlock') }" title="代码块" @click="noteCodeBlock">代码块</button>
              <button type="button" class="article-note-tool-btn" :class="{ 'is-active': isNoteActive('link') }" title="链接" @click="toggleLink"><LinkIcon class="h-3.5 w-3.5" /></button>
              <button type="button" class="article-note-tool-btn" title="分割线" @click="noteDivider"><Minus class="h-3.5 w-3.5" /></button>
              <button type="button" class="article-note-tool-btn" title="插入表格" @click="noteInsertTable"><Table class="h-3.5 w-3.5" /></button>
            </div>
            <EditorContent :editor="noteEditorInstance" class="article-note-editor" />
          </aside>

          <div class="article-preview-iframe-wrap">
            <button
              v-if="quoteActionVisible && selectedQuoteText"
              type="button"
              class="article-preview-quote-action"
              :style="{ left: `${quoteActionX}px`, top: `${quoteActionY}px` }"
              @click="appendQuoteBlock"
            >
              <Quote class="h-3.5 w-3.5" />
              引用
            </button>
            <div v-if="store.loading" class="article-preview-iframe-loading">
              <Loader2 class="h-6 w-6 animate-spin text-[var(--color-muted-foreground)]" />
              <span class="text-sm text-[var(--color-muted-foreground)]">正在加载…</span>
            </div>

            <div v-else-if="store.error" class="article-preview-iframe-fallback">
              <p class="text-sm text-amber-700 dark:text-amber-300 mb-3">{{ store.error }}</p>
              <button type="button" class="article-preview-primary-btn max-w-xs" @click="store.openOriginal">
                <ExternalLink class="h-4 w-4" />
                在微信中打开
              </button>
            </div>

            <div
              v-if="!store.loading && !store.error && safePreviewHtml && !mediaReady"
              class="article-preview-iframe-loading"
            >
              <Loader2 class="h-6 w-6 animate-spin text-[var(--color-muted-foreground)]" />
              <span class="text-sm text-[var(--color-muted-foreground)]">正在加载…</span>
            </div>

            <iframe
              v-if="!store.loading && !store.error && safePreviewHtml"
              ref="iframeRef"
              :key="store.display.id"
              class="article-preview-iframe"
              :class="{ 'is-media-ready': mediaReady }"
              title="微信公众号原文预览"
              :sandbox="previewIframeSandbox"
              :srcdoc="safePreviewHtml"
              @load="onIframeLoad"
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
        </div>
      </aside>
    </Transition>

    <ArticleImageLightbox
      :open="imgLightboxOpen"
      :src="imgLightboxSrc"
      @close="imgLightboxOpen = false"
    />

    <PreviewAccountDialog
      :open="accountDialogOpen"
      :account-name="store.display?.account || ''"
      @close="accountDialogOpen = false"
    />
  </Teleport>
</template>
