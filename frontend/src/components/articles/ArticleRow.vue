<script setup lang="ts">
import { computed, ref } from 'vue'
import { ExternalLink, Tag, Bot } from 'lucide-vue-next'
import type { Article } from '@/types'

const props = defineProps<{
  article: Article & { account: string }
}>()

const coverFallback = computed(() => {
  const colors = ['#6366f1', '#8b5cf6', '#ec4899', '#f97316', '#14b8a6', '#3b82f6', '#10b981']
  const idx = props.article.account.charCodeAt(0) % colors.length
  return colors[idx]
})

// 优先加载本地已下载的封面，失败则显示彩色头像占位
const localCoverSrc = computed(
  () => `/data/covers/${props.article.id.replace(/\//g, '_')}.jpg`,
)
const coverError = ref(false)

const formattedDate = computed(() => props.article.create_time?.slice(0, 10) || '')
const displayDigest = computed(() => props.article.summary || props.article.digest || '')
</script>

<template>
  <a
    :href="article.link"
    target="_blank"
    rel="noopener noreferrer"
    class="group flex items-start gap-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-4 transition-all duration-200 hover:border-[var(--color-ring)]/30 hover:shadow-md"
  >
    <!-- Thumbnail -->
    <div class="relative h-20 w-32 shrink-0 overflow-hidden rounded-lg bg-[var(--color-muted)]">
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
        class="flex h-full w-full items-center justify-center text-white text-lg font-bold opacity-80"
        :style="{ backgroundColor: coverFallback }"
      >
        {{ article.account.slice(0, 2) }}
      </div>
    </div>

    <!-- Content -->
    <div class="flex-1 min-w-0 space-y-1">
      <div class="flex items-start justify-between gap-2">
        <h3 class="line-clamp-2 text-sm font-semibold leading-snug text-[var(--color-foreground)] group-hover:text-[var(--color-primary)] transition-colors">
          {{ article.title }}
        </h3>
        <ExternalLink class="h-3.5 w-3.5 shrink-0 text-[var(--color-muted-foreground)] opacity-0 group-hover:opacity-100 transition-opacity mt-0.5" />
      </div>

      <p v-if="displayDigest" class="line-clamp-2 text-xs leading-relaxed text-[var(--color-muted-foreground)]">
        {{ displayDigest }}
      </p>

      <div class="flex items-center gap-3 pt-1">
        <span class="text-xs font-medium text-[var(--color-muted-foreground)]">{{ article.account }}</span>
        <span class="text-xs text-[var(--color-muted-foreground)]">{{ formattedDate }}</span>
        <div v-if="article.summary" class="flex items-center gap-0.5 text-[10px] text-[var(--color-primary)]">
          <Bot class="h-3 w-3" />
          <span>AI 摘要</span>
        </div>
        <div v-if="article.tags && article.tags.length" class="flex flex-wrap gap-1">
          <span
            v-for="tag in article.tags.slice(0, 3)"
            :key="tag"
            class="flex items-center gap-0.5 rounded-full bg-[var(--color-primary)]/10 px-1.5 py-0.5 text-[10px] text-[var(--color-primary)]"
          >
            <Tag class="h-2.5 w-2.5" />
            {{ tag }}
          </span>
        </div>
      </div>
    </div>
  </a>
</template>
