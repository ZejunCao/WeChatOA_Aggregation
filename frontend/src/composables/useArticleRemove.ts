import { ref } from 'vue'
import type { Article } from '@/types'
import { useReadingStore } from '@/stores/reading'
import { useArticlesStore } from '@/stores/articles'

type ArticleRef = Article & { account: string }

export function useArticleRemove(
  getArticle: () => ArticleRef,
  importMode: () => boolean,
) {
  const removing = ref(false)
  const readingStore = useReadingStore()
  const articlesStore = useArticlesStore()

  async function handleRemove(e: MouseEvent) {
    e.preventDefault()
    e.stopPropagation()
    const article = getArticle()
    const inImportTab = importMode()

    if (inImportTab) {
      const importOnly = article.source === 'import'
      const msg = importOnly
        ? `移出「${article.title}」？\n该文为链接导入，移出后将从库中删除。`
        : `从导入列表移出「${article.title}」？\n文章仍保留在「全部」中。`
      if (!confirm(msg)) return
    } else if (
      !confirm(
        `从列表中删除「${article.title}」？\n将从本地数据移除，且以后爬取也不会再入库。`,
      )
    ) {
      return
    }

    removing.value = true
    try {
      const endpoint = inImportTab
        ? '/api/articles/remove-from-import'
        : '/api/articles/remove'
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          article_id: article.id,
          account: article.account,
        }),
      })
      const data = (await res.json().catch(() => ({}))) as {
        detail?: string
        action?: 'deleted' | 'unlisted'
      }
      if (!res.ok) {
        alert(data.detail || (inImportTab ? '移出失败' : '删除失败'))
        return
      }
      if (!inImportTab || data.action === 'deleted') {
        readingStore.removeArticleTracking(article.id)
      }
      articlesStore.removeArticleLocally(article.account, article.id)
      if (inImportTab) {
        await articlesStore.fetchImportTotal()
      }
    } catch {
      alert('无法连接后端，请确认 api.py 已启动')
    } finally {
      removing.value = false
    }
  }

  return { removing, handleRemove }
}
