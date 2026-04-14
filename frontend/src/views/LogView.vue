<script setup lang="ts">
// ─────────────────────────────────────────────────────────────────────────────
// LogView — 操作日志页面
//
// 展示后端写入 data/operation_logs.jsonl 的所有操作记录，
// 包括：爬取开始/完成/失败、添加/移除公众号、清理缓存。
// 支持展开单条日志查看详细 JSON 数据。
// ─────────────────────────────────────────────────────────────────────────────

import { ref, computed, onMounted } from 'vue'
import {
  ScrollText,
  RefreshCw,
  Loader2,
  RefreshCcw,
  UserPlus,
  UserMinus,
  Eraser,
  AlertTriangle,
  CircleCheck,
  ChevronDown,
  ChevronUp,
  Inbox,
  Trash2,
} from 'lucide-vue-next'

// 与后端 LogEntry Pydantic 模型对应的前端接口
interface LogEntry {
  timestamp: string                    // 时间戳 "YYYY-MM-DD HH:MM:SS"
  type: string                         // 日志类型（crawl_start / account_add 等）
  message: string                      // 简短描述
  details: Record<string, unknown>     // 附加结构化数据（可展开查看）
}

const logs = ref<LogEntry[]>([])
const loading = ref(false)
const expandedIdx = ref<number | null>(null)  // 当前展开详情的日志索引（null=全部折叠）

// 每种日志类型对应的显示元数据（图标、颜色、背景色、中文标签）
const LOG_META: Record<string, { label: string; color: string; bg: string; icon: unknown }> = {
  crawl_start:    { label: '爬取开始', color: 'text-blue-500',    bg: 'bg-blue-500/10',    icon: RefreshCw },
  crawl_finish:   { label: '爬取完成', color: 'text-emerald-500', bg: 'bg-emerald-500/10', icon: CircleCheck },
  crawl_error:    { label: '爬取失败', color: 'text-red-500',     bg: 'bg-red-500/10',     icon: AlertTriangle },
  account_add:    { label: '添加公众号', color: 'text-indigo-500', bg: 'bg-indigo-500/10', icon: UserPlus },
  account_remove: { label: '移除公众号', color: 'text-orange-500', bg: 'bg-orange-500/10', icon: UserMinus },
  cache_clear:    { label: '清理缓存',  color: 'text-purple-500', bg: 'bg-purple-500/10', icon: Eraser },
  article_delete: { label: '删除文章', color: 'text-rose-500', bg: 'bg-rose-500/10', icon: Trash2 },
}

/** 根据日志类型获取元数据，未知类型返回默认样式 */
function getMeta(type: string) {
  return LOG_META[type] ?? { label: type, color: 'text-[var(--color-muted-foreground)]', bg: 'bg-[var(--color-muted)]', icon: ScrollText }
}

/** 从后端拉取最近 300 条日志（已按时间倒序） */
async function loadLogs() {
  loading.value = true
  try {
    const res = await fetch('/api/logs?limit=300')
    if (res.ok) logs.value = await res.json()
  } catch { /* 静默 */ } finally {
    loading.value = false
  }
}

/** 展开/折叠某条日志的详情 JSON（同一时间只展开一条） */
function toggleExpand(idx: number) {
  expandedIdx.value = expandedIdx.value === idx ? null : idx
}

/** 判断某条日志是否有可展开的详情（details 不为空对象） */
const hasDetails = (entry: LogEntry) => Object.keys(entry.details).length > 0

/** 各类型日志的数量统计，用于头部的分类徽标 */
const stats = computed(() => {
  const counts: Record<string, number> = {}
  for (const log of logs.value) {
    counts[log.type] = (counts[log.type] ?? 0) + 1
  }
  return counts
})

// 页面挂载后立即加载日志
onMounted(loadLogs)
</script>

<template>
  <div class="app-view-shell flex h-full flex-col overflow-hidden">
    <!-- Header -->
    <div class="shrink-0 border-b border-[var(--color-border)] bg-[var(--color-background)]/80 backdrop-blur-sm px-6 py-5">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--color-primary)]/10">
            <ScrollText class="h-5 w-5 text-[var(--color-primary)]" />
          </div>
          <div>
            <h1 class="text-lg font-semibold text-[var(--color-foreground)]">操作日志</h1>
            <p class="text-sm text-[var(--color-muted-foreground)]">记录爬取、账号管理、缓存清理等操作历史</p>
          </div>
        </div>
        <button
          @click="loadLogs"
          :disabled="loading"
          class="flex items-center gap-1.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-3 py-1.5 text-sm font-medium text-[var(--color-foreground)] hover:bg-[var(--color-accent)] transition-colors disabled:opacity-50"
        >
          <Loader2 v-if="loading" class="h-4 w-4 animate-spin" />
          <RefreshCcw v-else class="h-4 w-4" />
          刷新
        </button>
      </div>

      <!-- 统计小徽章 -->
      <div v-if="logs.length > 0" class="flex flex-wrap gap-2 mt-4">
        <div
          v-for="(meta, type) in LOG_META"
          :key="type"
          v-show="stats[type]"
          class="flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium"
          :class="[meta.bg, meta.color]"
        >
          <component :is="meta.icon" class="h-3 w-3" />
          {{ meta.label }} × {{ stats[type] ?? 0 }}
        </div>
      </div>
    </div>

    <!-- Log list -->
    <div class="flex-1 overflow-y-auto px-6 py-5">
      <!-- Loading -->
      <div v-if="loading" class="flex items-center justify-center gap-3 py-24">
        <Loader2 class="h-5 w-5 animate-spin text-[var(--color-primary)]" />
        <span class="text-sm text-[var(--color-muted-foreground)]">加载中...</span>
      </div>

      <!-- Empty -->
      <div v-else-if="logs.length === 0" class="flex flex-col items-center justify-center gap-3 py-24">
        <Inbox class="h-10 w-10 text-[var(--color-muted-foreground)]" />
        <p class="text-sm text-[var(--color-muted-foreground)]">暂无操作记录</p>
        <p class="text-xs text-[var(--color-muted-foreground)]">执行爬取、添加或删除公众号、清理缓存后，操作将记录在此</p>
      </div>

      <!-- Timeline -->
      <div v-else class="relative">
        <!-- vertical line -->
        <div class="absolute left-[19px] top-0 bottom-0 w-px bg-[var(--color-border)]" />

        <div class="space-y-1">
          <div
            v-for="(entry, idx) in logs"
            :key="idx"
            class="relative flex gap-4"
          >
            <!-- Icon dot -->
            <div
              class="relative z-10 mt-3 flex h-10 w-10 shrink-0 items-center justify-center rounded-full border-2 border-[var(--color-background)]"
              :class="getMeta(entry.type).bg"
            >
              <component :is="getMeta(entry.type).icon" class="h-4 w-4" :class="getMeta(entry.type).color" />
            </div>

            <!-- Card -->
            <div class="flex-1 min-w-0 pb-1">
              <div
                class="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] overflow-hidden transition-shadow hover:shadow-sm"
              >
                <!-- Main row -->
                <div
                  class="flex items-start gap-3 px-4 py-3"
                  :class="hasDetails(entry) ? 'cursor-pointer' : ''"
                  @click="hasDetails(entry) ? toggleExpand(idx) : undefined"
                >
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2 flex-wrap">
                      <span
                        class="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold"
                        :class="[getMeta(entry.type).bg, getMeta(entry.type).color]"
                      >{{ getMeta(entry.type).label }}</span>
                      <p class="text-sm text-[var(--color-foreground)] leading-snug">{{ entry.message }}</p>
                    </div>
                    <p class="mt-0.5 text-xs text-[var(--color-muted-foreground)]">{{ entry.timestamp }}</p>
                  </div>
                  <button
                    v-if="hasDetails(entry)"
                    class="shrink-0 mt-0.5 flex h-6 w-6 items-center justify-center rounded-md text-[var(--color-muted-foreground)] hover:bg-[var(--color-accent)] transition-colors"
                  >
                    <ChevronUp v-if="expandedIdx === idx" class="h-3.5 w-3.5" />
                    <ChevronDown v-else class="h-3.5 w-3.5" />
                  </button>
                </div>

                <!-- Expanded details -->
                <Transition name="slide-down">
                  <div
                    v-if="expandedIdx === idx && hasDetails(entry)"
                    class="border-t border-[var(--color-border)] bg-[var(--color-muted)]/40 px-4 py-3"
                  >
                    <pre class="text-xs text-[var(--color-muted-foreground)] whitespace-pre-wrap break-all font-mono leading-relaxed">{{ JSON.stringify(entry.details, null, 2) }}</pre>
                  </div>
                </Transition>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
