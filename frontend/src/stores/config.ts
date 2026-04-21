// ─────────────────────────────────────────────────────────────────────────────
// 用户配置 Store（Pinia）
//
// 职责：
//   - 记录用户在配置页"隐藏"的公众号（不出现在文章流中）
//   - 记录用户选择的主题（亮色/暗色/跟随系统）
//
// 持久化：
//   整个 store 自动保存到 localStorage（persist: true），
//   刷新后主题偏好和隐藏列表都会恢复。
// ─────────────────────────────────────────────────────────────────────────────

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { normalizeFeedTheme, type FeedThemeId } from '@/themes/feed-themes'

export const useConfigStore = defineStore(
  'config',
  () => {
    // 被用户手动隐藏的公众号名称列表
    // 这些公众号的文章不会出现在信息流中，但数据仍然保留
    const hiddenAccounts = ref<string[]>([])

    // 当前主题设置：'light' | 'dark' | 'system'（跟随操作系统）
    const theme = ref<'light' | 'dark' | 'system'>('system')

    // 文章 Feed 区界面预设（奶白网格 / 简约 / 蓝青等），持久化到 localStorage
    const feedTheme = ref<FeedThemeId>('cream-mesh')

    // 侧边栏公众号自定义顺序（拖拽后写入，未命中的账号会自动追加）
    const accountOrder = ref<string[]>([])

    // ── 公众号可见性 ──────────────────────────────────────────────────────────

    /** 切换某个公众号的可见状态（隐藏/取消隐藏） */
    function toggleAccount(name: string) {
      const idx = hiddenAccounts.value.indexOf(name)
      if (idx === -1) {
        hiddenAccounts.value.push(name)    // 不在列表中 → 添加到隐藏列表
      } else {
        hiddenAccounts.value.splice(idx, 1) // 已在列表中 → 从隐藏列表移除
      }
    }

    /** 判断某公众号是否可见（未被隐藏） */
    function isVisible(name: string): boolean {
      return !hiddenAccounts.value.includes(name)
    }

    /** 取消隐藏所有公众号（全部可见） */
    function showAll() {
      hiddenAccounts.value = []
    }

    /** 隐藏指定的公众号列表（全不选时使用） */
    function hideAll(names: string[]) {
      hiddenAccounts.value = [...names]
    }

    /** 更新公众号顺序（去重并保留非空项） */
    function setAccountOrder(names: string[]) {
      const seen = new Set<string>()
      accountOrder.value = names.filter((n) => {
        const v = n.trim()
        if (!v || seen.has(v)) return false
        seen.add(v)
        return true
      })
    }

    // ── 主题 ──────────────────────────────────────────────────────────────────

    /** 设置主题并立即应用到 DOM */
    function setTheme(t: 'light' | 'dark' | 'system') {
      theme.value = t
      applyTheme(t)
    }

    /**
     * 将主题应用到 <html> 元素的 class。
     * Tailwind CSS 通过 .dark class 切换暗色主题。
     */
    function applyTheme(t: 'light' | 'dark' | 'system') {
      const root = document.documentElement
      if (t === 'dark') {
        root.classList.add('dark')
      } else if (t === 'light') {
        root.classList.remove('dark')
      } else {
        // 跟随系统：读取操作系统的颜色偏好设置
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
        root.classList.toggle('dark', prefersDark)
      }
    }

    /**
     * 应用初始化：在 App.vue 挂载时调用，确保持久化的主题设置立即生效，
     * 避免页面刷新时出现闪白/闪黑的问题。
     */
    /** 同步 Feed 预设到 <html data-feed-theme>，供 CSS 变量覆盖 */
    function applyFeedTheme(id: FeedThemeId) {
      document.documentElement.setAttribute('data-feed-theme', id)
    }

    function setFeedTheme(id: FeedThemeId) {
      feedTheme.value = id
      applyFeedTheme(id)
    }

    function initTheme() {
      feedTheme.value = normalizeFeedTheme(feedTheme.value)
      applyTheme(theme.value)
      applyFeedTheme(feedTheme.value)
    }

    return {
      hiddenAccounts,
      theme,
      feedTheme,
      accountOrder,
      toggleAccount,
      isVisible,
      showAll,
      hideAll,
      setAccountOrder,
      setTheme,
      setFeedTheme,
      initTheme,
    }
  },
  {
    // persist: true 使用默认配置，将整个 store 序列化保存到 localStorage
    persist: true,
  },
)
