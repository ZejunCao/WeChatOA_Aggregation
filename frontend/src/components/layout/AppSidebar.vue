<script setup lang="ts">
import { computed, ref, watch, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Rss, Settings, ChevronLeft, ChevronRight, NotebookPen } from 'lucide-vue-next'
import { useArticlesStore } from '@/stores/articles'
import { useConfigStore } from '@/stores/config'
import type { AccountInfo } from '@/types'

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
const draggingAccount = ref('')
const pendingDragAccount = ref('')
const displayAccounts = ref<AccountInfo[]>([])
const accountsScrollRef = ref<HTMLElement | null>(null)
const dragging = ref(false)
const dragGhostX = ref(0)
const dragGhostY = ref(0)
let dragOffsetX = 0
let dragOffsetY = 0
let dragGhostFixedX = 0
let dragGhostMinY = 0
let dragGhostMaxY = 0
let startX = 0
let startY = 0
let hasMoved = false
let accountGhostClickListener: ((e: MouseEvent) => void) | null = null
let accountGhostClickTimeout: ReturnType<typeof setTimeout> | null = null

function clearAccountGhostClickAbsorb() {
  if (accountGhostClickListener) {
    document.removeEventListener('click', accountGhostClickListener, true)
    accountGhostClickListener = null
  }
  if (accountGhostClickTimeout !== null) {
    clearTimeout(accountGhostClickTimeout)
    accountGhostClickTimeout = null
  }
}

/** 拖拽松手后浏览器可能补发一次 click；只拦截落在公众号列表上的那一次，不误伤后续真实点击 */
function scheduleAccountGhostClickAbsorb() {
  clearAccountGhostClickAbsorb()
  accountGhostClickListener = (e: MouseEvent) => {
    clearAccountGhostClickAbsorb()
    const t = e.target as HTMLElement | null
    if (t?.closest('.app-sidebar-accounts-scroll [data-acct-name]')) {
      e.preventDefault()
      e.stopImmediatePropagation()
    }
  }
  setTimeout(() => {
    if (!accountGhostClickListener) return
    document.addEventListener('click', accountGhostClickListener, true)
    accountGhostClickTimeout = setTimeout(() => clearAccountGhostClickAbsorb(), 400)
  }, 0)
}

const navItems = [
  { label: '文章', icon: Rss, path: '/' },
  { label: '笔记', icon: NotebookPen, path: '/notes' },
  { label: '配置', icon: Settings, path: '/config' },
]

function goNav(path: string) {
  if (route.path !== path) router.push(path)
}

const visibleAccounts = computed(() => {
  const orderMap = new Map(configStore.accountOrder.map((name, idx) => [name, idx]))
  return articlesStore.accounts
    .filter((a) => configStore.isVisible(a.name))
    .sort((a, b) => {
      const ai = orderMap.get(a.name)
      const bi = orderMap.get(b.name)
      if (ai !== undefined && bi !== undefined) return ai - bi
      if (ai !== undefined) return -1
      if (bi !== undefined) return 1
      return b.latest_update_time.localeCompare(a.latest_update_time)
    })
})

watch(
  visibleAccounts,
  (list) => {
    // 拖拽过程中由 onAccountDragOver 实时调整，不覆盖
    if (draggingAccount.value) return
    displayAccounts.value = [...list]
  },
  { immediate: true },
)

function selectAccount(name: string) {
  const newVal = props.selectedAccount === name ? '' : name
  emit('update:selectedAccount', newVal)
  if (route.path !== '/' && route.path !== '/notes') router.push('/')
}

function onAccountClick(name: string) {
  selectAccount(name)
}

function persistAccountOrder(orderedVisible: string[]) {
  // 其余（隐藏或当前不可见）账号顺序保持不变，拖拽只调整可见列表内部顺序
  const allKnown = [
    ...configStore.accountOrder.filter((name) => articlesStore.accounts.some((a) => a.name === name)),
    ...articlesStore.accounts.map((a) => a.name),
  ].filter((name, idx, arr) => arr.indexOf(name) === idx)

  const remaining = allKnown.filter((name) => !orderedVisible.includes(name))
  configStore.setAccountOrder([...orderedVisible, ...remaining])
}

function onAccountDragStart(name: string, ev: MouseEvent) {
  if (ev.button !== 0) return
  pendingDragAccount.value = name
  const currentEl = ev.currentTarget as HTMLElement | null
  if (currentEl) {
    const rect = currentEl.getBoundingClientRect()
    dragOffsetX = ev.clientX - rect.left
    dragOffsetY = ev.clientY - rect.top
    dragGhostX.value = rect.left
    dragGhostY.value = rect.top
    dragGhostFixedX = rect.left
    const wrapRect = accountsScrollRef.value?.getBoundingClientRect()
    if (wrapRect) {
      dragGhostMinY = wrapRect.top
      dragGhostMaxY = Math.max(wrapRect.top, wrapRect.bottom - rect.height)
    } else {
      dragGhostMinY = 0
      dragGhostMaxY = Number.POSITIVE_INFINITY
    }
  } else {
    dragOffsetX = 12
    dragOffsetY = 12
    dragGhostX.value = ev.clientX - dragOffsetX
    dragGhostY.value = ev.clientY - dragOffsetY
    dragGhostFixedX = dragGhostX.value
    dragGhostMinY = 0
    dragGhostMaxY = Number.POSITIVE_INFINITY
  }
  startX = ev.clientX
  startY = ev.clientY
  hasMoved = false
  window.addEventListener('mousemove', onAccountDragMove)
  window.addEventListener('mouseup', onAccountDragEnd)
}

function onAccountDragOver(targetName: string, clientY: number, targetEl: HTMLElement) {
  const sourceName = draggingAccount.value
  if (!sourceName || sourceName === targetName) return

  const current = displayAccounts.value.map((a) => a.name)
  const from = current.indexOf(sourceName)
  const to = current.indexOf(targetName)
  if (from < 0 || to < 0) return

  const rect = targetEl.getBoundingClientRect()
  const midY = rect.top + rect.height / 2
  const isAfterHalf = clientY > midY

  // 只有越过目标项中线才触发重排，避免在边界附近频繁抖动
  let desired = to
  if (from < to && !isAfterHalf) desired = to - 1
  if (from > to && isAfterHalf) desired = to + 1
  if (desired === from) return

  const reordered = [...displayAccounts.value]
  const [moved] = reordered.splice(from, 1)
  if (!moved) return
  reordered.splice(desired, 0, moved)
  displayAccounts.value = reordered
}

function onAccountDragMove(ev: MouseEvent) {
  if (!dragging.value) {
    if (!pendingDragAccount.value) return
    const movedEnough = Math.abs(ev.clientX - startX) > 5 || Math.abs(ev.clientY - startY) > 5
    if (!movedEnough) return
    // 超过阈值才真正进入拖拽，普通点击不触发拖动
    draggingAccount.value = pendingDragAccount.value
    dragging.value = true
    hasMoved = true
    document.body.classList.add('is-account-dragging')
  }
  if (!draggingAccount.value) return
  // 锁定仅纵向拖拽：X 固定，Y 限制在侧边栏列表容器范围内
  dragGhostX.value = dragGhostFixedX
  const nextY = ev.clientY - dragOffsetY
  dragGhostY.value = Math.max(dragGhostMinY, Math.min(nextY, dragGhostMaxY))
  const wrapRect = accountsScrollRef.value?.getBoundingClientRect()
  const probeX = dragGhostFixedX + 24
  const probeY = wrapRect
    ? Math.max(wrapRect.top + 1, Math.min(ev.clientY, wrapRect.bottom - 1))
    : ev.clientY
  const target =
    (document.elementFromPoint(probeX, probeY) as HTMLElement | null)?.closest<HTMLElement>('[data-acct-name]') ??
    (() => {
      // 鼠标在按钮间隙/边缘时，自动吸附到最近项，降低拖拽难度
      const buttons = Array.from(accountsScrollRef.value?.querySelectorAll<HTMLElement>('[data-acct-name]') ?? [])
      if (!buttons.length) return null
      let best: HTMLElement | null = null
      let bestDist = Number.POSITIVE_INFINITY
      for (const btn of buttons) {
        const r = btn.getBoundingClientRect()
        const centerY = r.top + r.height / 2
        const dist = Math.abs(centerY - probeY)
        if (dist < bestDist) {
          bestDist = dist
          best = btn
        }
      }
      return best
    })()
  if (!target) return
  const targetName = target.dataset.acctName
  if (!targetName) return
  onAccountDragOver(targetName, probeY, target)
}

function onAccountDragEnd() {
  window.removeEventListener('mousemove', onAccountDragMove)
  window.removeEventListener('mouseup', onAccountDragEnd)
  document.body.classList.remove('is-account-dragging')
  const didReorderDrag = dragging.value && hasMoved
  if (dragging.value && draggingAccount.value) {
    persistAccountOrder(displayAccounts.value.map((a) => a.name))
  }
  if (didReorderDrag) scheduleAccountGhostClickAbsorb()
  dragging.value = false
  hasMoved = false
  pendingDragAccount.value = ''
  draggingAccount.value = ''
  // 回到由真实排序驱动的显示列表（确保与持久化结果一致）
  displayAccounts.value = [...visibleAccounts.value]
}

onUnmounted(() => {
  window.removeEventListener('mousemove', onAccountDragMove)
  window.removeEventListener('mouseup', onAccountDragEnd)
  document.body.classList.remove('is-account-dragging')
  clearAccountGhostClickAbsorb()
})

const draggingAccountInfo = computed(
  () => displayAccounts.value.find((a) => a.name === draggingAccount.value) ?? null,
)
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
        <div v-if="!collapsed" class="app-sidebar-logo">
          <Rss class="h-4 w-4" />
        </div>
        <span v-if="!collapsed" class="app-sidebar-title">公众号聚合</span>
        <button
          v-if="!collapsed"
          type="button"
          class="app-sidebar-icon-btn ml-auto"
          title="折叠侧栏"
          @click="emit('update:collapsed', true)"
        >
          <ChevronLeft class="h-4 w-4" />
        </button>
        <button
          v-else
          type="button"
          class="app-sidebar-icon-btn"
          title="展开侧栏"
          @click="emit('update:collapsed', false)"
        >
          <ChevronRight class="h-4 w-4" />
        </button>
      </div>

      <!-- Navigation -->
      <nav class="app-sidebar-nav space-y-1">
        <button
          v-for="nav in navItems"
          :key="nav.path"
          type="button"
          class="app-sidebar-link w-full"
          :class="[
            route.path === nav.path ? 'app-sidebar-link--active' : '',
            collapsed ? 'app-sidebar-link--collapsed' : '',
          ]"
          :title="collapsed ? nav.label : undefined"
          :aria-current="route.path === nav.path ? 'page' : undefined"
          @click="goNav(nav.path)"
        >
          <component :is="nav.icon" class="h-4 w-4 shrink-0" />
          <span v-if="!collapsed" class="truncate">{{ nav.label }}</span>
        </button>
      </nav>

      <!-- Account list（文章页且展开时） -->
      <div v-if="!collapsed && route.path === '/'" class="app-sidebar-accounts-wrap">
        <div class="app-sidebar-section-hd">
          <span class="app-sidebar-section-label">公众号</span>
        </div>
        <div ref="accountsScrollRef" class="app-sidebar-accounts-scroll space-y-0.5">
          <button
            type="button"
            class="app-sidebar-acct-btn"
            :class="selectedAccount === '' ? 'app-sidebar-acct-btn--active' : ''"
            @click="emit('update:selectedAccount', '')"
          >
            <span class="min-w-0 flex-1 truncate">全部</span>
            <span class="app-sidebar-acct-count">{{ articlesStore.stats.totalArticles }}</span>
          </button>
          <TransitionGroup name="sidebar-acct" tag="div" class="space-y-0.5">
            <button
              v-for="acc in displayAccounts"
              :key="acc.name"
              type="button"
              class="app-sidebar-acct-btn"
              :class="[
                selectedAccount === acc.name ? 'app-sidebar-acct-btn--active' : '',
                draggingAccount === acc.name ? 'app-sidebar-acct-btn--drag-placeholder' : '',
              ]"
              :data-acct-name="acc.name"
              @click="onAccountClick(acc.name)"
              :title="'拖拽调整顺序'"
              @mousedown="onAccountDragStart(acc.name, $event)"
            >
              <span class="min-w-0 flex-1 truncate">{{ acc.name }}</span>
              <span class="app-sidebar-acct-count">{{ acc.article_count }}</span>
            </button>
          </TransitionGroup>
          <button
            v-if="dragging && draggingAccountInfo"
            type="button"
            class="app-sidebar-acct-btn app-sidebar-acct-btn--drag-ghost"
            :style="{
              transform: `translate3d(${dragGhostX}px, ${dragGhostY}px, 0) scale(1.02)`,
            }"
          >
            <span class="min-w-0 flex-1 truncate">{{ draggingAccountInfo.name }}</span>
            <span class="app-sidebar-acct-count">{{ draggingAccountInfo.article_count }}</span>
          </button>
        </div>
      </div>

      <div v-else class="app-sidebar-spacer" />
    </div>
  </aside>
</template>
