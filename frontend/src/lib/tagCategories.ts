/**
 * 与后端 `article_tagging.py` 中提示词一致：标签在存储时为扁平列表，
 * 此处按约定词表归类到「内容类型 / 核心主题 / 技术范围 / 特殊标记」便于筛选展示。
 */

export type TagFilterCategory = 'content' | 'theme' | 'tech' | 'special' | 'untagged'

/** 分组标题与展示顺序（核心主题靠前，便于扫具体技术点） */
export const TAG_SECTION_ORDER: TagFilterCategory[] = ['content', 'theme', 'tech', 'special', 'untagged']

export const TAG_SECTION_LABELS: Record<TagFilterCategory, string> = {
  content: '内容类型',
  theme: '核心主题',
  tech: '技术范围',
  special: '特殊标记',
  untagged: '未打标签',
}

/** 提示词「内容类型标签」枚举 */
const CONTENT_TYPES = new Set([
  '教程',
  '原理解析',
  '实战案例',
  '资讯',
  '论文解读',
  '工具推荐',
])

/** 提示词「特殊标签」枚举 */
const SPECIAL_TAGS = new Set(['推广', '开源项目', '官方文档', '博主经验'])

/**
 * 提示词「技术范围」常见词 + 高频工程向词；未命中则归入「核心主题」。
 */
const TECH_SCOPE = new Set([
  'Python',
  'Java',
  'Go',
  'Rust',
  'C++',
  'C#',
  'PHP',
  'Ruby',
  'Swift',
  'Kotlin',
  'JavaScript',
  'TypeScript',
  'Node',
  'Node.js',
  '前端',
  '后端',
  '全栈',
  'LLM',
  'AI',
  '机器学习',
  '深度学习',
  '大模型',
  '数据库',
  'MySQL',
  'PostgreSQL',
  'MongoDB',
  'Redis',
  'Elasticsearch',
  'Kafka',
  'RabbitMQ',
  'Kubernetes',
  'K8s',
  'Docker',
  '云原生',
  '微服务',
  '运维',
  'DevOps',
  'CI/CD',
  '安全',
  '网络安全',
  '算法',
  '数据结构',
  'iOS',
  'Android',
  '微信小程序',
  'Flutter',
  'React',
  'Vue',
  'Angular',
  'Linux',
  '网络',
  'HTTP',
  'RPC',
  'gRPC',
  'NLP',
  '计算机视觉',
  'RAG',
  'Agent',
  'GPU',
  'CUDA',
])

/**
 * 将单个标签归入筛选 UI 用的类别（不含 __untagged__，由调用方单独处理）。
 */
export function classifyTagForFilter(tag: string): Exclude<TagFilterCategory, 'untagged'> {
  if (CONTENT_TYPES.has(tag)) return 'content'
  if (SPECIAL_TAGS.has(tag)) return 'special'
  if (TECH_SCOPE.has(tag)) return 'tech'
  return 'theme'
}
