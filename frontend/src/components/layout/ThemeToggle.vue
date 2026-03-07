<script setup lang="ts">
import { computed } from 'vue'
import { Sun, Moon, Monitor } from 'lucide-vue-next'
import { useConfigStore } from '@/stores/config'

const configStore = useConfigStore()

const themeOptions = [
  { value: 'light' as const, icon: Sun, label: '浅色' },
  { value: 'dark' as const, icon: Moon, label: '深色' },
  { value: 'system' as const, icon: Monitor, label: '系统' },
]

const currentIndex = computed(() => themeOptions.findIndex((t) => t.value === configStore.theme))

function cycleTheme() {
  const next = themeOptions[(currentIndex.value + 1) % themeOptions.length]!
  configStore.setTheme(next.value)
}
</script>

<template>
  <button
    @click="cycleTheme"
    class="flex h-8 w-8 items-center justify-center rounded-lg text-[var(--color-muted-foreground)] transition-colors hover:bg-[var(--color-accent)] hover:text-[var(--color-accent-foreground)]"
    :title="`当前: ${themeOptions[currentIndex]?.label}，点击切换`"
  >
      <component :is="themeOptions[currentIndex]?.icon" class="h-4 w-4" />
  </button>
</template>
