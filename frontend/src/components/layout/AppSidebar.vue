<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Rss, Settings, ScrollText, ChevronLeft, ChevronRight } from 'lucide-vue-next'
import { useArticlesStore } from '@/stores/articles'
import { useConfigStore } from '@/stores/config'
import ThemeToggle from './ThemeToggle.vue'
import FeedThemePicker from './FeedThemePicker.vue'

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
    class="app-sidebar-shell flex h-full flex-col transition-[width] duration-300 ease-out"
    :class="collapsed ? 'w-14' : 'w-56'"
  >
    <div class="relative z-[1] flex h-full min-h-0 flex-col">
      <!-- Logo / Brand -->
      <div
        class="app-sidebar-brand"
        :class="collapsed ? 'justify-center px-2' : ''"
      >
        <div class="app-sidebar-logo">
          <Rss class="h-4 w-4" />
        </div>
        <span v-if="!collapsed" class="app-sidebar-title">公众号聚合</span>
      </div>

      <!-- Navigation -->
      <nav class="app-sidebar-nav space-y-1">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="app-sidebar-link"
          :class="[
            route.path === item.path ? 'app-sidebar-link--active' : '',
            collapsed ? 'app-sidebar-link--collapsed' : '',
          ]"
          :title="collapsed ? item.name : ''"
        >
          <component :is="item.icon" class="h-4 w-4 shrink-0" />
          <span v-if="!collapsed">{{ item.name }}</span>
        </router-link>
      </nav>

      <!-- Account list（文章页且展开时） -->
      <div v-if="!collapsed && route.path === '/'" class="app-sidebar-accounts-wrap">
        <div class="app-sidebar-section-hd">
          <span class="app-sidebar-section-label">公众号</span>
        </div>
        <div class="app-sidebar-accounts-scroll space-y-0.5">
          <button
            type="button"
            class="app-sidebar-acct-btn"
            :class="selectedAccount === '' ? 'app-sidebar-acct-btn--active' : ''"
            @click="emit('update:selectedAccount', '')"
          >
            <span class="min-w-0 flex-1 truncate">全部</span>
            <span class="app-sidebar-acct-count">{{ articlesStore.stats.totalArticles }}</span>
          </button>
          <button
            v-for="acc in visibleAccounts"
            :key="acc.name"
            type="button"
            class="app-sidebar-acct-btn"
            :class="selectedAccount === acc.name ? 'app-sidebar-acct-btn--active' : ''"
            @click="selectAccount(acc.name)"
          >
            <span class="min-w-0 flex-1 truncate">{{ acc.name }}</span>
            <span class="app-sidebar-acct-count">{{ acc.article_count }}</span>
          </button>
        </div>
      </div>

      <div v-else class="app-sidebar-spacer" />

      <!-- Footer -->
      <div
        class="app-sidebar-footer"
        :class="collapsed ? 'flex-row justify-center gap-1' : 'flex-col gap-2'"
      >
        <FeedThemePicker v-if="!collapsed" />
        <div
          class="flex w-full gap-1"
          :class="collapsed ? 'justify-center' : 'justify-between'"
        >
          <ThemeToggle v-if="!collapsed" class="app-sidebar-icon-btn" />
          <button
            type="button"
            class="app-sidebar-icon-btn"
            :title="collapsed ? '展开侧栏' : '折叠侧栏'"
            @click="emit('update:collapsed', !collapsed)"
          >
            <ChevronLeft v-if="!collapsed" class="h-4 w-4" />
            <ChevronRight v-else class="h-4 w-4" />
          </button>
          <ThemeToggle v-if="collapsed" class="app-sidebar-icon-btn" />
        </div>
      </div>
    </div>
  </aside>
</template>
