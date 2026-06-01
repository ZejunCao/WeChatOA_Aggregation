<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { onClickOutside } from '@vueuse/core'
import { Link2, Loader2, X } from 'lucide-vue-next'
import { useArticlesStore } from '@/stores/articles'

const emit = defineEmits<{
  imported: [payload: { articleId: string; status: 'created' | 'exists' }]
}>()

const props = withDefaults(
  defineProps<{
    glass?: boolean
  }>(),
  { glass: false },
)

const articlesStore = useArticlesStore()
const open = ref(false)
const url = ref('')
const loading = ref(false)
const feedback = ref<{ type: 'ok' | 'err'; text: string } | null>(null)
const containerRef = ref<HTMLElement | null>(null)
const inputRef = ref<HTMLInputElement | null>(null)

onClickOutside(containerRef, () => {
  if (open.value) close()
})

async function focusInput() {
  await nextTick()
  inputRef.value?.focus({ preventScroll: true })
}

function toggleOpen() {
  open.value = !open.value
}

watch(open, (isOpen) => {
  if (isOpen) void focusInput()
})

function close() {
  open.value = false
  feedback.value = null
}

async function submit() {
  if (loading.value) return
  feedback.value = null
  loading.value = true
  try {
    const res = await articlesStore.importByUrl(url.value)
    feedback.value = {
      type: 'ok',
      text: res.status === 'exists' ? '文章已在库中，已归入「导入」' : '导入成功',
    }
    url.value = ''
    emit('imported', { articleId: res.article_id, status: res.status })
    window.setTimeout(() => {
      close()
    }, 900)
  } catch (e) {
    feedback.value = {
      type: 'err',
      text: e instanceof Error ? e.message : '导入失败',
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div ref="containerRef" class="relative shrink-0">
    <button
      type="button"
      class="shrink-0 text-sm transition-colors"
      :class="glass
        ? ['feed-glass-tool', open ? 'is-active' : '']
        : [
            'flex h-9 items-center gap-1.5 rounded-lg border px-3',
            open
              ? 'border-[var(--color-primary)] bg-[var(--color-primary)]/10 text-[var(--color-primary)]'
              : 'border-[var(--color-border)] bg-[var(--color-card)] text-[var(--color-muted-foreground)] hover:bg-[var(--color-accent)] hover:text-[var(--color-foreground)]',
          ]"
      title="导入公众号文章链接"
      @click="toggleOpen"
    >
      <Link2 class="h-4 w-4" />
      <span class="hidden sm:inline">导入链接</span>
    </button>

    <Transition
      enter-active-class="transition duration-150 ease-out"
      enter-from-class="opacity-0 scale-95 translate-y-1"
      enter-to-class="opacity-100 scale-100 translate-y-0"
      leave-active-class="transition duration-100 ease-in"
      leave-from-class="opacity-100 scale-100 translate-y-0"
      leave-to-class="opacity-0 scale-95 translate-y-1"
    >
      <div
        v-if="open"
        class="absolute right-0 top-[calc(100%+8px)] z-[70] w-[min(92vw,360px)] rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-3 shadow-xl shadow-black/10"
        @click.stop
      >
        <div class="mb-2 flex items-center justify-between gap-2">
          <p class="text-sm font-semibold text-[var(--color-foreground)]">导入文章链接</p>
          <button
            type="button"
            class="rounded-lg p-1 text-[var(--color-muted-foreground)] hover:bg-[var(--color-muted)] hover:text-[var(--color-foreground)]"
            aria-label="关闭"
            @click="close"
          >
            <X class="h-4 w-4" />
          </button>
        </div>
        <p class="mb-2 text-xs leading-relaxed text-[var(--color-muted-foreground)]">
          粘贴 mp.weixin.qq.com 文章地址，自动抓取标题、公众号、正文与封面。
        </p>
        <input
          ref="inputRef"
          v-model="url"
          type="url"
          autocomplete="off"
          placeholder="https://mp.weixin.qq.com/s/..."
          class="mb-2 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm outline-none focus:outline-none focus:ring-0"
          @keydown.enter="submit"
        />
        <button
          type="button"
          class="flex w-full items-center justify-center gap-2 rounded-lg bg-[var(--color-primary)] px-3 py-2 text-sm font-medium text-[var(--color-primary-foreground)] disabled:opacity-50"
          :disabled="loading || !url.trim()"
          @click="submit"
        >
          <Loader2 v-if="loading" class="h-4 w-4 animate-spin" />
          {{ loading ? '导入中…' : '开始导入' }}
        </button>
        <p
          v-if="feedback"
          class="mt-2 text-xs"
          :class="feedback.type === 'ok' ? 'text-emerald-600' : 'text-red-600'"
        >
          {{ feedback.text }}
        </p>
      </div>
    </Transition>
  </div>
</template>
