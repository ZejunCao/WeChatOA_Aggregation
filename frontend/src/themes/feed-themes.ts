//文章 Feed 区界面预设（与深浅色无关；深浅仍由 ThemeToggle 控制）
// 新增预设：在此加 id + 文案，并在 feed-theme-presets.css / demo-index-feed.css 写覆盖样式

export const FEED_THEME_IDS = ['cream-mesh', 'ocean', 'demo-glass'] as const

export type FeedThemeId = (typeof FEED_THEME_IDS)[number]

export function normalizeFeedTheme(v: unknown): FeedThemeId {
  if (typeof v === 'string' && (FEED_THEME_IDS as readonly string[]).includes(v)) {
    return v as FeedThemeId
  }
  return 'cream-mesh'
}

export const FEED_THEMES: { id: FeedThemeId; label: string; hint?: string }[] = [
  {
    id: 'cream-mesh',
    label: '奶白·磨砂网格',
    hint: '浅粉顶区 + 中下青蓝/淡紫/暖杏色团，高模糊低填充玻璃',
  },
  { id: 'ocean', label: '清蓝网格', hint: '蓝青系 mesh + 玻璃' },
  {
    id: 'demo-glass',
    label: '粉紫渐变玻璃',
    hint: '粉紫蓝黄渐变、四色圆、磨砂玻璃（与仓库 demo/index 同源样式）',
  },
]
