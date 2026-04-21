<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { onClickOutside } from '@vueuse/core'
import { CalendarDays, ChevronDown, Check, X } from 'lucide-vue-next'

const props = defineProps<{
  dateFrom: string
  dateTo: string
}>()

const emit = defineEmits<{
  'update:dateFrom': [value: string]
  'update:dateTo': [value: string]
  'open-change': [value: boolean]
}>()

const open = ref(false)
const containerRef = ref<HTMLElement | null>(null)
const customFrom = ref(props.dateFrom)
const customTo = ref(props.dateTo)

onClickOutside(containerRef, () => {
  setOpen(false)
})

watch(() => props.dateFrom, (v) => { customFrom.value = v })
watch(() => props.dateTo, (v) => { customTo.value = v })

function today() {
  return new Date().toISOString().slice(0, 10)
}

function daysAgo(n: number) {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return d.toISOString().slice(0, 10)
}

function monthsAgo(n: number) {
  const d = new Date()
  d.setMonth(d.getMonth() - n)
  return d.toISOString().slice(0, 10)
}

function yearStart() {
  return `${new Date().getFullYear()}-01-01`
}

const presets = [
  { label: '不限时间', from: '', to: '' },
  { label: '今天', from: today(), to: today() },
  { label: '近 7 天', from: daysAgo(7), to: today() },
  { label: '近 30 天', from: daysAgo(30), to: today() },
  { label: '近 3 个月', from: monthsAgo(3), to: today() },
  { label: '今年', from: yearStart(), to: today() },
]

const activePreset = computed(() => {
  if (!props.dateFrom && !props.dateTo) return presets[0]
  return presets.find((p) => p.from === props.dateFrom && p.to === props.dateTo) ?? null
})

const buttonLabel = computed(() => {
  if (activePreset.value) return activePreset.value.label
  const parts: string[] = []
  if (props.dateFrom) parts.push(props.dateFrom)
  if (props.dateTo) parts.push(props.dateTo)
  return parts.length ? parts.join(' ~ ') : '选择日期'
})

const hasValue = computed(() => !!(props.dateFrom || props.dateTo))

function setOpen(value: boolean) {
  if (open.value === value) return
  open.value = value
  emit('open-change', value)
}

function applyPreset(preset: (typeof presets)[number]) {
  emit('update:dateFrom', preset.from)
  emit('update:dateTo', preset.to)
  customFrom.value = preset.from
  customTo.value = preset.to
  if (!preset.from && !preset.to) setOpen(false)
}

function applyCustom() {
  emit('update:dateFrom', customFrom.value)
  emit('update:dateTo', customTo.value)
  setOpen(false)
}

function clear() {
  emit('update:dateFrom', '')
  emit('update:dateTo', '')
  customFrom.value = ''
  customTo.value = ''
  setOpen(false)
}
</script>

<template>
  <div ref="containerRef" class="relative">
    <button
      type="button"
      @click="setOpen(!open)"
      class="flex h-9 items-center gap-1.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-3 text-sm transition-colors hover:bg-[var(--color-accent)] focus:outline-none"
      :class="[
        open ? 'border-[var(--color-ring)] ring-1 ring-[var(--color-ring)]' : '',
        hasValue ? 'text-[var(--color-foreground)]' : 'text-[var(--color-muted-foreground)]',
      ]"
    >
      <CalendarDays class="h-3.5 w-3.5 shrink-0" />
      <span class="max-w-[9rem] truncate">{{ buttonLabel }}</span>
      <X
        v-if="hasValue"
        class="h-3 w-3 shrink-0 text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)] transition-colors"
        @click.stop="clear"
      />
      <ChevronDown
        v-else
        class="h-3.5 w-3.5 shrink-0 text-[var(--color-muted-foreground)] transition-transform duration-200"
        :class="open ? 'rotate-180' : ''"
      />
    </button>

    <Transition
      enter-active-class="transition duration-100 ease-out"
      enter-from-class="opacity-0 scale-95 translate-y-[-4px]"
      enter-to-class="opacity-100 scale-100 translate-y-0"
      leave-active-class="transition duration-75 ease-in"
      leave-from-class="opacity-100 scale-100 translate-y-0"
      leave-to-class="opacity-0 scale-95 translate-y-[-4px]"
    >
      <div
        v-if="open"
        class="absolute left-0 top-full z-50 mt-1.5 w-64 overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] shadow-lg shadow-black/10"
      >
        <!-- Preset list -->
        <div class="py-1">
          <p class="px-3 pt-2 pb-1 text-[11px] font-semibold uppercase tracking-wider text-[var(--color-muted-foreground)]">
            快速选择
          </p>
          <button
            v-for="preset in presets"
            :key="preset.label"
            type="button"
            @click="applyPreset(preset)"
            class="flex w-full items-center gap-2 px-3 py-2 text-sm transition-colors hover:bg-[var(--color-accent)]"
            :class="
              activePreset?.label === preset.label
                ? 'text-[var(--color-foreground)] font-medium'
                : 'text-[var(--color-muted-foreground)]'
            "
          >
            <Check
              class="h-3.5 w-3.5 shrink-0 text-[var(--color-primary)]"
              :class="activePreset?.label === preset.label ? 'opacity-100' : 'opacity-0'"
            />
            {{ preset.label }}
          </button>
        </div>

        <!-- Custom range -->
        <div class="border-t border-[var(--color-border)] p-3 space-y-2">
          <p class="text-[11px] font-semibold uppercase tracking-wider text-[var(--color-muted-foreground)]">
            自定义范围
          </p>
          <div class="flex items-center gap-1.5">
            <input
              v-model="customFrom"
              type="text"
              placeholder="YYYY-MM-DD"
              maxlength="10"
              class="h-8 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] px-2 text-xs text-[var(--color-foreground)] placeholder-[var(--color-muted-foreground)] outline-none focus:border-[var(--color-ring)]"
            />
            <span class="text-[var(--color-muted-foreground)] text-xs shrink-0">—</span>
            <input
              v-model="customTo"
              type="text"
              placeholder="YYYY-MM-DD"
              maxlength="10"
              class="h-8 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] px-2 text-xs text-[var(--color-foreground)] placeholder-[var(--color-muted-foreground)] outline-none focus:border-[var(--color-ring)]"
            />
          </div>
          <button
            type="button"
            @click="applyCustom"
            class="w-full rounded-lg bg-[var(--color-primary)] py-1.5 text-xs font-medium text-white hover:opacity-90 transition-opacity"
          >
            应用
          </button>
        </div>
      </div>
    </Transition>
  </div>
</template>
