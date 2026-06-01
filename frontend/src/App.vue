<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { onClickOutside } from '@vueuse/core'
import { TooltipProvider } from 'reka-ui'
import { Menu, Settings2, X, ExternalLink } from 'lucide-vue-next'
import AppSidebar from '@/components/layout/AppSidebar.vue'
import ThemeToggle from '@/components/layout/ThemeToggle.vue'
import FeedThemePicker from '@/components/layout/FeedThemePicker.vue'
import ArticlePreviewPanel from '@/components/articles/ArticlePreviewPanel.vue'
import { useArticlesStore } from '@/stores/articles'
import { useConfigStore } from '@/stores/config'

const articlesStore = useArticlesStore()
const configStore = useConfigStore()

const sidebarCollapsed = ref(false)
const mobileSidebarOpen = ref(false)
const selectedAccount = ref('')
const settingsOpen = ref(false)
const settingsRef = ref<HTMLElement | null>(null)

onClickOutside(settingsRef, () => {
  settingsOpen.value = false
})

onMounted(async () => {
  configStore.initTheme()
  await articlesStore.loadData()
})
</script>

<template>
  <TooltipProvider :delay-duration="500">
  <div class="flex h-screen overflow-hidden bg-[var(--color-background)] text-[var(--color-foreground)]">

    <!-- Mobile sidebar overlay -->
    <div
      v-if="mobileSidebarOpen"
      class="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm md:hidden"
      @click="mobileSidebarOpen = false"
    />

    <!-- Sidebar: hidden on mobile unless open -->
    <div
      class="fixed inset-y-0 left-0 z-50 md:relative md:z-auto md:block transition-transform duration-300"
      :class="mobileSidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'"
    >
      <AppSidebar
        v-model:collapsed="sidebarCollapsed"
        v-model:selectedAccount="selectedAccount"
        @click.stop
      />
    </div>

    <!-- Main -->
    <main class="flex-1 overflow-hidden flex flex-col min-w-0">
      <div ref="settingsRef" class="pointer-events-none fixed right-3 top-3 z-[65] md:right-4 md:top-4">
        <div class="pointer-events-auto relative">
          <button
            type="button"
            class="flex h-9 w-9 items-center justify-center rounded-xl border border-[var(--color-border)] bg-[var(--color-card)]/85 text-[var(--color-muted-foreground)] shadow-sm backdrop-blur transition-colors hover:bg-[var(--color-accent)] hover:text-[var(--color-foreground)]"
            :title="settingsOpen ? '关闭设置' : '打开设置'"
            @click="settingsOpen = !settingsOpen"
          >
            <X v-if="settingsOpen" class="h-4 w-4" />
            <Settings2 v-else class="h-4 w-4" />
          </button>

          <Transition
            enter-active-class="transition duration-120 ease-out"
            enter-from-class="opacity-0 scale-95 -translate-y-1"
            enter-to-class="opacity-100 scale-100 translate-y-0"
            leave-active-class="transition duration-90 ease-in"
            leave-from-class="opacity-100 scale-100 translate-y-0"
            leave-to-class="opacity-0 scale-95 -translate-y-1"
          >
            <div
              v-if="settingsOpen"
              class="absolute right-0 top-11 w-72 rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)]/92 p-2.5 shadow-xl shadow-black/10 backdrop-blur"
            >
              <div class="mb-2 flex items-center justify-between rounded-lg px-2 py-1 text-xs text-[var(--color-muted-foreground)]">
                <span>显示模式</span>
                <ThemeToggle />
              </div>
              <div class="mb-1 flex items-center justify-between gap-2 rounded-lg px-2 py-1 text-xs text-[var(--color-muted-foreground)]">
                <span class="shrink-0">Feed 主题</span>
                <div class="w-44 max-w-[70%]">
                  <FeedThemePicker />
                </div>
              </div>
              <div class="mt-2 border-t border-[var(--color-border)] pt-2">
                <a
                  href="https://github.com/ZejunCao/WeChatOA_Aggregation"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="flex items-center gap-1.5 rounded-lg px-2 py-1 text-[11px] text-[var(--color-muted-foreground)] transition-colors hover:bg-[var(--color-accent)] hover:text-[var(--color-foreground)]"
                  title="项目来源仓库（点击打开）"
                >
                  <ExternalLink class="h-3.5 w-3.5 shrink-0" />
                  <span class="truncate">项目来源：ZejunCao/WeChatOA_Aggregation</span>
                </a>
              </div>
            </div>
          </Transition>
        </div>
      </div>

      <!-- Mobile top bar -->
      <div class="flex md:hidden h-12 shrink-0 items-center gap-3 border-b border-[var(--color-border)] px-4">
        <button
          @click="mobileSidebarOpen = true"
          class="flex h-8 w-8 items-center justify-center rounded-lg text-[var(--color-muted-foreground)] hover:bg-[var(--color-accent)] hover:text-[var(--color-foreground)] transition-colors"
        >
          <Menu class="h-5 w-5" />
        </button>
        <span class="text-sm font-semibold text-[var(--color-foreground)]">微信公众号聚合</span>
      </div>

      <router-view
        :selected-account="selectedAccount"
        @update:selectedAccount="selectedAccount = $event"
        class="flex-1 overflow-hidden"
      />
    </main>
  </div>
    <ArticlePreviewPanel />
  </TooltipProvider>
</template>
