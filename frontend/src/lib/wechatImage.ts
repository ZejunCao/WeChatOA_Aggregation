/** 微信 CDN 图片走同源代理，避免预览/头像防盗链裂图 */
export function proxyWechatImageUrl(url: string): string {
  const u = url.trim()
  if (!u) return ''
  if (u.startsWith('/api/wechat-image')) return u
  if (/^https?:\/\//i.test(u)) {
    return `/api/wechat-image?url=${encodeURIComponent(u)}`
  }
  return u
}
