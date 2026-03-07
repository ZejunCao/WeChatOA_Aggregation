<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Menu } from 'lucide-vue-next'
import AppSidebar from '@/components/layout/AppSidebar.vue'
import { useArticlesStore } from '@/stores/articles'
import { useConfigStore } from '@/stores/config'

const articlesStore = useArticlesStore()
const configStore = useConfigStore()

const sidebarCollapsed = ref(false)
const mobileSidebarOpen = ref(false)
const selectedAccount = ref('')

onMounted(async () => {
  configStore.initTheme()
  await articlesStore.loadData()
})
</script>

<template>
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
</template>
