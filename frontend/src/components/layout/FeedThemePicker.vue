<script setup lang="ts">
import { useConfigStore } from '@/stores/config'
import { FEED_THEMES, type FeedThemeId } from '@/themes/feed-themes'

const config = useConfigStore()

function onChange(ev: Event) {
  const v = (ev.target as HTMLSelectElement).value as FeedThemeId
  config.setFeedTheme(v)
}
</script>

<template>
  <div class="feed-theme-picker w-full min-w-0">
    <label class="sr-only" for="feed-theme-select">文章区界面主题</label>
    <select
      id="feed-theme-select"
      :value="config.feedTheme"
      class="feed-theme-picker__select w-full max-w-full truncate rounded-lg px-2 py-1.5 text-[11px] font-medium outline-none transition-colors"
      :title="FEED_THEMES.find((t) => t.id === config.feedTheme)?.hint"
      @change="onChange"
    >
      <option v-for="t in FEED_THEMES" :key="t.id" :value="t.id" :title="t.hint">
        {{ t.label }}
      </option>
    </select>
  </div>
</template>

<style scoped>
.feed-theme-picker__select {
  color: var(--sb-text, var(--color-foreground));
  background: rgba(255, 252, 248, 0.55);
  border: 1px solid rgba(201, 79, 124, 0.18);
  box-shadow: 0 1px 2px rgba(80, 60, 70, 0.06);
}

.feed-theme-picker__select:hover {
  border-color: rgba(201, 79, 124, 0.28);
  background: rgba(255, 252, 248, 0.72);
}

.feed-theme-picker__select:focus-visible {
  border-color: rgba(201, 79, 124, 0.45);
  box-shadow: 0 0 0 2px rgba(201, 79, 124, 0.2);
}

:global(html.dark) .feed-theme-picker__select {
  color: var(--sb-text, var(--color-foreground));
  background: rgba(40, 36, 48, 0.55);
  border-color: rgba(244, 114, 182, 0.22);
}

:global(html.dark) .feed-theme-picker__select:hover {
  background: rgba(48, 44, 56, 0.65);
  border-color: rgba(244, 114, 182, 0.32);
}
</style>
