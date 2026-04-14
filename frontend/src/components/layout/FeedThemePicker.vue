<script setup lang="ts">
import { computed, ref } from 'vue'
import { onClickOutside } from '@vueuse/core'
import { Check, ChevronUp } from 'lucide-vue-next'
import { useConfigStore } from '@/stores/config'
import { FEED_THEMES, type FeedThemeId } from '@/themes/feed-themes'

const config = useConfigStore()
const open = ref(false)
const containerRef = ref<HTMLElement | null>(null)

const currentTheme = computed(() => FEED_THEMES.find((t) => t.id === config.feedTheme))

onClickOutside(containerRef, () => {
  open.value = false
})

function selectTheme(id: FeedThemeId) {
  config.setFeedTheme(id)
  open.value = false
}
</script>

<template>
  <div ref="containerRef" class="feed-theme-picker relative w-full min-w-0">
    <button
      type="button"
      class="feed-theme-picker__trigger flex w-full max-w-full items-center justify-between gap-1 rounded-lg px-2 py-1.5 text-[11px] font-medium outline-none transition-colors"
      :class="open ? 'is-open' : ''"
      :title="currentTheme?.hint"
      aria-haspopup="listbox"
      :aria-expanded="open"
      @click="open = !open"
    >
      <span class="truncate">{{ currentTheme?.label ?? '选择主题' }}</span>
      <ChevronUp class="h-3.5 w-3.5 shrink-0 transition-transform duration-200" :class="open ? '' : 'rotate-180'" />
    </button>

    <Transition
      enter-active-class="transition duration-100 ease-out"
      enter-from-class="opacity-0 scale-95 translate-y-1"
      enter-to-class="opacity-100 scale-100 translate-y-0"
      leave-active-class="transition duration-75 ease-in"
      leave-from-class="opacity-100 scale-100 translate-y-0"
      leave-to-class="opacity-0 scale-95 translate-y-1"
    >
      <div
        v-if="open"
        role="listbox"
        class="feed-theme-picker__panel absolute bottom-full left-0 z-50 mb-1.5 w-full overflow-hidden rounded-xl border py-1 shadow-lg shadow-black/10"
      >
        <button
          v-for="theme in FEED_THEMES"
          :key="theme.id"
          type="button"
          class="feed-theme-picker__item flex w-full items-center gap-2 px-2 py-1.5 text-left text-[11px] transition-colors"
          :class="theme.id === config.feedTheme ? 'is-active' : ''"
          :title="theme.hint"
          @click="selectTheme(theme.id)"
        >
          <Check class="h-3.5 w-3.5 shrink-0" :class="theme.id === config.feedTheme ? 'opacity-100' : 'opacity-0'" />
          <span class="truncate">{{ theme.label }}</span>
        </button>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.feed-theme-picker__trigger {
  color: var(--sb-text, var(--color-foreground));
  background: rgba(255, 252, 248, 0.55);
  border: 1px solid rgba(201, 79, 124, 0.18);
  box-shadow: 0 1px 2px rgba(80, 60, 70, 0.06);
}

.feed-theme-picker__trigger:hover {
  border-color: rgba(201, 79, 124, 0.28);
  background: rgba(255, 252, 248, 0.72);
}

.feed-theme-picker__trigger.is-open {
  border-color: rgba(201, 79, 124, 0.42);
  box-shadow: 0 0 0 2px rgba(201, 79, 124, 0.2);
}

.feed-theme-picker__panel {
  border-color: rgba(201, 79, 124, 0.2);
  background: rgba(255, 252, 248, 0.94);
  backdrop-filter: blur(14px) saturate(140%);
  -webkit-backdrop-filter: blur(14px) saturate(140%);
}

.feed-theme-picker__item {
  color: var(--sb-text-muted, var(--color-muted-foreground));
}

.feed-theme-picker__item:hover {
  background: rgba(201, 79, 124, 0.08);
  color: var(--sb-text, var(--color-foreground));
}

.feed-theme-picker__item.is-active {
  color: var(--sb-accent, var(--color-primary));
  background: rgba(201, 79, 124, 0.12);
}

:global(html.dark) .feed-theme-picker__trigger {
  color: var(--sb-text, var(--color-foreground));
  background: rgba(40, 36, 48, 0.55);
  border-color: rgba(244, 114, 182, 0.22);
}

:global(html.dark) .feed-theme-picker__trigger:hover {
  background: rgba(48, 44, 56, 0.65);
  border-color: rgba(244, 114, 182, 0.32);
}

:global(html.dark) .feed-theme-picker__trigger.is-open {
  border-color: rgba(244, 114, 182, 0.45);
  box-shadow: 0 0 0 2px rgba(244, 114, 182, 0.18);
}

:global(html.dark) .feed-theme-picker__panel {
  border-color: rgba(244, 114, 182, 0.25);
  background: rgba(32, 28, 40, 0.95);
}

:global(html.dark) .feed-theme-picker__item:hover {
  background: rgba(244, 114, 182, 0.12);
}

:global(html.dark) .feed-theme-picker__item.is-active {
  background: rgba(244, 114, 182, 0.16);
}
</style>
