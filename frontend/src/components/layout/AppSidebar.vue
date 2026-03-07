<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Rss, Settings, ScrollText, ChevronLeft, ChevronRight } from 'lucide-vue-next'
import { useArticlesStore } from '@/stores/articles'
import { useConfigStore } from '@/stores/config'
import ThemeToggle from './ThemeToggle.vue'

const props = defineProps<{
  collapsed: boolean
  selectedAccount: string
}>()

const emit = defineEmits<{
  'update:collapsed': [value: boolean]
  'update:selectedAccount': [value: string]
}>()

const router = useRouter()
const route = useRoute()
const articlesStore = useArticlesStore()
const configStore = useConfigStore()

const navItems = [
  { name: '文章', icon: Rss, path: '/' },
  { name: '配置', icon: Settings, path: '/config' },
  { name: '日志', icon: ScrollText, path: '/logs' },
]

const visibleAccounts = computed(() =>
  articlesStore.accounts
    .filter((a) => configStore.isVisible(a.name))
    .sort((a, b) => b.latest_update_time.localeCompare(a.latest_update_time)),
)

function selectAccount(name: string) {
  const newVal = props.selectedAccount === name ? '' : name
  emit('update:selectedAccount', newVal)
  if (route.path !== '/') router.push('/')
}
</script>

<template>
  <aside
    class="flex h-full flex-col border-r border-[var(--color-border)] bg-[var(--color-card)] transition-all duration-300"
    :class="collapsed ? 'w-14' : 'w-56'"
  >
    <!-- Logo / Brand -->
    <div class="flex h-14 shrink-0 items-center border-b border-[var(--color-border)] px-3">
      <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[var(--color-primary)]">
        <Rss class="h-4 w-4 text-white" />
      </div>
      <span
        v-if="!collapsed"
        class="ml-2.5 truncate text-sm font-semibold text-[var(--color-foreground)]"
      >公众号聚合</span>
    </div>

    <!-- Navigation -->
    <nav class="p-2 space-y-0.5">
      <router-link
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        class="flex h-9 items-center gap-2.5 rounded-lg px-2.5 text-sm font-medium transition-colors"
        :class="
          route.path === item.path
            ? 'bg-[var(--color-accent)] text-[var(--color-foreground)]'
            : 'text-[var(--color-muted-foreground)] hover:bg-[var(--color-accent)] hover:text-[var(--color-foreground)]'
        "
        :title="collapsed ? item.name : ''"
      >
        <component :is="item.icon" class="h-4 w-4 shrink-0" />
        <span v-if="!collapsed">{{ item.name }}</span>
      </router-link>
    </nav>

    <!-- Account list (only on feed page) -->
    <div v-if="!collapsed && route.path === '/'" class="flex-1 overflow-hidden flex flex-col">
      <div class="px-3 pt-3 pb-1.5">
        <span class="text-[11px] font-semibold uppercase tracking-wider text-[var(--color-muted-foreground)]">
          公众号
        </span>
      </div>
      <div class="flex-1 overflow-y-auto px-2 pb-2 space-y-0.5">
        <button
          class="w-full flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-sm transition-colors text-left"
          :class="
            selectedAccount === ''
              ? 'bg-[var(--color-accent)] text-[var(--color-foreground)] font-medium'
              : 'text-[var(--color-muted-foreground)] hover:bg-[var(--color-accent)] hover:text-[var(--color-foreground)]'
          "
          @click="emit('update:selectedAccount', '')"
        >
          <span class="flex-1 truncate">全部</span>
          <span class="text-xs opacity-60">{{ articlesStore.stats.totalArticles }}</span>
        </button>
        <button
          v-for="acc in visibleAccounts"
          :key="acc.name"
          class="w-full flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-sm transition-colors text-left"
          :class="
            selectedAccount === acc.name
              ? 'bg-[var(--color-accent)] text-[var(--color-foreground)] font-medium'
              : 'text-[var(--color-muted-foreground)] hover:bg-[var(--color-accent)] hover:text-[var(--color-foreground)]'
          "
          @click="selectAccount(acc.name)"
        >
          <span class="flex-1 truncate">{{ acc.name }}</span>
          <span class="text-xs opacity-60">{{ acc.article_count }}</span>
        </button>
      </div>
    </div>

    <div v-else class="flex-1" />

    <!-- Footer -->
    <div class="shrink-0 border-t border-[var(--color-border)] p-2 flex items-center" :class="collapsed ? 'justify-center' : 'justify-between'">
      <ThemeToggle v-if="!collapsed" />
      <button
        @click="emit('update:collapsed', !collapsed)"
        class="flex h-8 w-8 items-center justify-center rounded-lg text-[var(--color-muted-foreground)] transition-colors hover:bg-[var(--color-accent)] hover:text-[var(--color-accent-foreground)]"
        :title="collapsed ? '展开侧栏' : '折叠侧栏'"
      >
        <ChevronLeft v-if="!collapsed" class="h-4 w-4" />
        <ChevronRight v-else class="h-4 w-4" />
      </button>
      <ThemeToggle v-if="collapsed" />
    </div>
  </aside>
</template>
