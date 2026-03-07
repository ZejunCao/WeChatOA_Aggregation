<script setup lang="ts">
import { ref, computed } from 'vue'
import { onClickOutside } from '@vueuse/core'
import { Check, ChevronDown } from 'lucide-vue-next'

interface Option {
  value: string
  label: string
}

const props = defineProps<{
  options: Option[]
  modelValue: string
  placeholder?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const open = ref(false)
const containerRef = ref<HTMLElement | null>(null)

onClickOutside(containerRef, () => {
  open.value = false
})

const currentLabel = computed(() => {
  return props.options.find((o) => o.value === props.modelValue)?.label ?? props.placeholder ?? ''
})

function select(value: string) {
  emit('update:modelValue', value)
  open.value = false
}
</script>

<template>
  <div ref="containerRef" class="relative">
    <button
      type="button"
      @click="open = !open"
      class="flex h-9 items-center gap-1.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-3 text-sm text-[var(--color-foreground)] transition-colors hover:bg-[var(--color-accent)] focus:outline-none"
      :class="open ? 'border-[var(--color-ring)] ring-1 ring-[var(--color-ring)]' : ''"
    >
      <span>{{ currentLabel }}</span>
      <ChevronDown
        class="h-3.5 w-3.5 text-[var(--color-muted-foreground)] transition-transform duration-200"
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
        class="absolute left-0 top-full z-50 mt-1.5 min-w-[10rem] overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] py-1 shadow-lg shadow-black/10"
      >
        <button
          v-for="opt in options"
          :key="opt.value"
          type="button"
          @click="select(opt.value)"
          class="flex w-full items-center gap-2 px-3 py-2 text-sm transition-colors hover:bg-[var(--color-accent)]"
          :class="
            opt.value === modelValue
              ? 'text-[var(--color-foreground)] font-medium'
              : 'text-[var(--color-muted-foreground)]'
          "
        >
          <Check
            class="h-3.5 w-3.5 shrink-0 text-[var(--color-primary)]"
            :class="opt.value === modelValue ? 'opacity-100' : 'opacity-0'"
          />
          {{ opt.label }}
        </button>
      </div>
    </Transition>
  </div>
</template>
