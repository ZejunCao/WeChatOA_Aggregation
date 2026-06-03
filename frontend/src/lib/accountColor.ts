/** 公众号名称 → 稳定配色（hash，不与首字符绑定） */
const ACCOUNT_COLORS = [
  '#6366f1',
  '#8b5cf6',
  '#ec4899',
  '#f97316',
  '#14b8a6',
  '#3b82f6',
  '#10b981',
  '#f59e0b',
  '#ef4444',
  '#84cc16',
] as const

function hashString(s: string): number {
  let h = 0
  for (let i = 0; i < s.length; i++) {
    h = (h * 31 + s.charCodeAt(i)) | 0
  }
  return Math.abs(h)
}

export function accountColor(name: string): string {
  const key = name.trim() || '?'
  const idx = hashString(key) % ACCOUNT_COLORS.length
  return ACCOUNT_COLORS[idx] ?? ACCOUNT_COLORS[0]
}
