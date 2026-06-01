import type { Article } from '@/types'
import { useArticlePreviewStore, type FeedArticle } from '@/stores/articlePreview'
import { useReadingStore } from '@/stores/reading'

/** 列表项点击：默认打开就地预览；⌘/Ctrl+点击仍在新标签打开微信原文 */
export function useArticleOpen() {
  const previewStore = useArticlePreviewStore()
  const readingStore = useReadingStore()

  function onArticleClick(e: MouseEvent, item: FeedArticle) {
    const sel = window.getSelection()
    if (sel && !sel.isCollapsed && sel.toString().trim().length > 0) {
      e.preventDefault()
      return
    }
    if (e.metaKey || e.ctrlKey) {
      e.preventDefault()
      void readingStore.markRead(item.id)
      window.open(item.link, '_blank', 'noopener,noreferrer')
      return
    }
    e.preventDefault()
    void previewStore.openPreview(item)
  }

  function onArticleKeydown(e: KeyboardEvent, item: Article & { account: string }) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      void previewStore.openPreview(item)
    }
  }

  return { onArticleClick, onArticleKeydown }
}
