<script setup lang="ts">
import { computed, ref } from 'vue'
import { ExternalLink, Tag, Bot } from 'lucide-vue-next'
import type { Article } from '@/types'

const props = defineProps<{
  article: Article & { account: string }
}>()

const coverFallback = computed(() => {
  const colors = [
    '#6366f1', '#8b5cf6', '#ec4899', '#f97316', '#14b8a6', '#3b82f6', '#10b981',
  ]
  const idx = props.article.account.charCodeAt(0) % colors.length
  return colors[idx]
})

// 优先加载本地已下载的封面，失败则显示彩色头像占位
const localCoverSrc = computed(
  () => `/data/covers/${props.article.id.replace(/\//g, '_')}.jpg`,
)
const coverError = ref(false)

const formattedDate = computed(() => {
  const d = props.article.create_time
  if (!d) return ''
  return d.slice(0, 10)
})

const displayDigest = computed(() => {
  return props.article.summary || props.article.digest || ''
})
</script>

<template>
  <a
    :href="article.link"
    target="_blank"
    rel="noopener noreferrer"
    class="group flex flex-col overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] transition-all duration-200 hover:border-[var(--color-ring)]/30 hover:shadow-lg hover:-translate-y-0.5"
  >
    <!-- Cover -->
    <div class="relative aspect-[16/9] overflow-hidden bg-[var(--color-muted)] shrink-0">
      <img
        v-if="!coverError"
        :src="localCoverSrc"
        :alt="article.title"
        class="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
        loading="lazy"
        @error="coverError = true"
      />
      <div
        v-else
        class="flex h-full w-full items-center justify-center text-white text-2xl font-bold opacity-80"
        :style="{ backgroundColor: coverFallback }"
      >
        {{ article.account.slice(0, 2) }}
      </div>
      <!-- AI badge -->
      <div
        v-if="article.summary"
        class="absolute top-2 right-2 flex items-center gap-1 rounded-full bg-black/60 px-2 py-0.5 text-[10px] text-white backdrop-blur-sm"
      >
        <Bot class="h-3 w-3" />
        <span>AI 摘要</span>
      </div>
    </div>

    <!-- Content -->
    <div class="flex flex-1 flex-col gap-2 p-4">
      <h3 class="line-clamp-2 text-sm font-semibold leading-snug text-[var(--color-foreground)] group-hover:text-[var(--color-primary)] transition-colors">
        {{ article.title }}
      </h3>

      <p
        v-if="displayDigest"
        class="line-clamp-3 text-xs leading-relaxed text-[var(--color-muted-foreground)]"
      >
        {{ displayDigest }}
      </p>

      <!-- Tags -->
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

      <!-- Footer -->
      <div class="mt-auto flex items-center justify-between pt-1">
        <span class="text-xs font-medium text-[var(--color-muted-foreground)] truncate max-w-[60%]">
          {{ article.account }}
        </span>
        <div class="flex items-center gap-1.5 shrink-0">
          <span class="text-xs text-[var(--color-muted-foreground)]">{{ formattedDate }}</span>
          <ExternalLink class="h-3 w-3 text-[var(--color-muted-foreground)] opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>
      </div>
    </div>
  </a>
</template>
