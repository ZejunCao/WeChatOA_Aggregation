import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useConfigStore = defineStore(
  'config',
  () => {
    const hiddenAccounts = ref<string[]>([])
    const theme = ref<'light' | 'dark' | 'system'>('system')

    function toggleAccount(name: string) {
      const idx = hiddenAccounts.value.indexOf(name)
      if (idx === -1) {
        hiddenAccounts.value.push(name)
      } else {
        hiddenAccounts.value.splice(idx, 1)
      }
    }

    function isVisible(name: string): boolean {
      return !hiddenAccounts.value.includes(name)
    }

    function showAll() {
      hiddenAccounts.value = []
    }

    function hideAll(names: string[]) {
      hiddenAccounts.value = [...names]
    }

    function setTheme(t: 'light' | 'dark' | 'system') {
      theme.value = t
      applyTheme(t)
    }

    function applyTheme(t: 'light' | 'dark' | 'system') {
      const root = document.documentElement
      if (t === 'dark') {
        root.classList.add('dark')
      } else if (t === 'light') {
        root.classList.remove('dark')
      } else {
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
        root.classList.toggle('dark', prefersDark)
      }
    }

    function initTheme() {
      applyTheme(theme.value)
    }

    return {
      hiddenAccounts,
      theme,
      toggleAccount,
      isVisible,
      showAll,
      hideAll,
      setTheme,
      initTheme,
    }
  },
  {
    persist: true,
  },
)
