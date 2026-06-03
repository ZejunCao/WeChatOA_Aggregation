/** 模板安全展示：避免对象被渲染成 [object Object] */
export function displayText(value: unknown): string {
  if (value == null) return ''
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  return ''
}

/** LLM 标签可能是字符串或 { name / label / tag } */
export function tagLabel(tag: unknown): string {
  if (typeof tag === 'string') return tag
  if (tag && typeof tag === 'object') {
    const o = tag as Record<string, unknown>
    if (typeof o.name === 'string') return o.name
    if (typeof o.label === 'string') return o.label
    if (typeof o.tag === 'string') return o.tag
  }
  return displayText(tag)
}
