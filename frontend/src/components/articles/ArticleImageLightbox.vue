<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { X, ZoomIn, ZoomOut, RotateCcw } from 'lucide-vue-next'

const props = defineProps<{
  open: boolean
  src: string
}>()

const emit = defineEmits<{
  close: []
}>()

/** 打开灯箱时图片目标占屏比例（宽、高取较小缩放比） */
const INITIAL_VIEWPORT_FILL = 0.7

const imgRef = ref<HTMLImageElement | null>(null)
const baseScale = ref(1)
const scale = ref(1)
const panX = ref(0)
const panY = ref(0)
const dragging = ref(false)
let dragStartX = 0
let dragStartY = 0
let dragPanStartX = 0
let dragPanStartY = 0
let movedDuringDrag = false

const MAX_SCALE = 6

const transformStyle = computed(
  () => `translate(${panX.value}px, ${panY.value}px) scale(${scale.value})`,
)

const isZoomed = computed(() => scale.value > baseScale.value * 1.001)

function resetView() {
  scale.value = baseScale.value
  panX.value = 0
  panY.value = 0
}

function clampScale(v: number) {
  return Math.max(baseScale.value, Math.min(MAX_SCALE, v))
}

function zoomBy(delta: number) {
  scale.value = clampScale(scale.value + delta)
  if (scale.value <= baseScale.value * 1.001) resetView()
}

function computeInitialScale(img: HTMLImageElement): number {
  const w = img.getBoundingClientRect().width
  const h = img.getBoundingClientRect().height
  if (w < 1 || h < 1) return 1
  const targetW = window.innerWidth * INITIAL_VIEWPORT_FILL
  const targetH = window.innerHeight * INITIAL_VIEWPORT_FILL
  const factor = Math.min(targetW / w, targetH / h)
  return Math.max(1, Math.min(MAX_SCALE, factor))
}

function applyInitialScale(img: HTMLImageElement) {
  const next = computeInitialScale(img)
  baseScale.value = next
  scale.value = next
  panX.value = 0
  panY.value = 0
}

function onImageLoad(e: Event) {
  applyInitialScale(e.target as HTMLImageElement)
}

function prepareForNewImage() {
  baseScale.value = 1
  scale.value = 1
  panX.value = 0
  panY.value = 0
}

function onWheel(e: WheelEvent) {
  if (!props.open) return
  e.preventDefault()
  const step = Math.min(0.8, Math.max(0.06, Math.abs(e.deltaY) / 500))
  zoomBy(e.deltaY < 0 ? step : -step)
}

function onPointerDown(e: PointerEvent) {
  if (!isZoomed.value || e.button !== 0) return
  dragging.value = true
  movedDuringDrag = false
  dragStartX = e.clientX
  dragStartY = e.clientY
  dragPanStartX = panX.value
  dragPanStartY = panY.value
  ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
}

function onPointerMove(e: PointerEvent) {
  if (!dragging.value) return
  const dx = e.clientX - dragStartX
  const dy = e.clientY - dragStartY
  if (Math.abs(dx) > 2 || Math.abs(dy) > 2) movedDuringDrag = true
  panX.value = dragPanStartX + dx
  panY.value = dragPanStartY + dy
}

function onPointerUp(e: PointerEvent) {
  if (!dragging.value) return
  dragging.value = false
  try {
    ;(e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId)
  } catch {
    /* ignore */
  }
}

function onImageClick(e: MouseEvent) {
  e.stopPropagation()
  if (movedDuringDrag) {
    movedDuringDrag = false
    return
  }
  if (scale.value <= baseScale.value * 1.001) {
    scale.value = clampScale(baseScale.value * 2)
  }
}

function onStageClick(e: MouseEvent) {
  if (movedDuringDrag) {
    movedDuringDrag = false
    return
  }
  const target = e.target as HTMLElement | null
  if (target?.closest('.article-img-lightbox-image')) return
  emit('close')
}

function onBackdropClick(e: MouseEvent) {
  const target = e.target as HTMLElement | null
  if (!target?.classList.contains('article-img-lightbox')) return
  emit('close')
}

function onKeydown(e: KeyboardEvent) {
  if (!props.open) return
  if (e.key === 'Escape') {
    e.preventDefault()
    e.stopPropagation()
    emit('close')
    return
  }
  if (e.key === '+' || e.key === '=') {
    e.preventDefault()
    zoomBy(0.2)
    return
  }
  if (e.key === '-') {
    e.preventDefault()
    zoomBy(-0.2)
  }
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      prepareForNewImage()
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
      prepareForNewImage()
    }
  },
)

watch(
  () => [props.open, props.src] as const,
  ([open, src]) => {
    if (!open || !src) return
    prepareForNewImage()
    void nextTick(() => {
      const img = imgRef.value
      if (img?.complete && img.naturalWidth > 0) applyInitialScale(img)
    })
  },
)

onMounted(() => window.addEventListener('keydown', onKeydown, true))
onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown, true)
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <Transition name="article-img-lightbox-fade">
      <div
        v-if="open && src"
        class="article-img-lightbox"
        role="dialog"
        aria-modal="true"
        aria-label="图片全屏预览"
        @click="onBackdropClick"
        @wheel.prevent="onWheel"
      >
        <div class="article-img-lightbox-toolbar">
          <button type="button" class="article-img-lightbox-tool" title="缩小" @click.stop="zoomBy(-0.25)">
            <ZoomOut class="h-4 w-4" />
          </button>
          <button type="button" class="article-img-lightbox-tool" title="放大" @click.stop="zoomBy(0.25)">
            <ZoomIn class="h-4 w-4" />
          </button>
          <button type="button" class="article-img-lightbox-tool" title="还原" @click.stop="resetView">
            <RotateCcw class="h-4 w-4" />
          </button>
          <button type="button" class="article-img-lightbox-tool" title="关闭" @click.stop="emit('close')">
            <X class="h-4 w-4" />
          </button>
        </div>

        <div
          class="article-img-lightbox-stage"
          :class="{ 'is-dragging': dragging, 'is-zoomed': isZoomed }"
          @click="onStageClick"
        >
          <img
            ref="imgRef"
            :key="src"
            :src="src"
            alt="全屏预览"
            class="article-img-lightbox-image"
            :style="{ transform: transformStyle }"
            draggable="false"
            @load="onImageLoad"
            @click="onImageClick"
            @pointerdown="onPointerDown"
            @pointermove="onPointerMove"
            @pointerup="onPointerUp"
            @pointercancel="onPointerUp"
            @dblclick.prevent.stop="resetView"
          />
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.article-img-lightbox {
  position: fixed;
  inset: 0;
  z-index: 300;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.92);
  touch-action: none;
}

.article-img-lightbox-toolbar {
  position: absolute;
  top: 16px;
  right: 16px;
  z-index: 2;
  display: flex;
  gap: 8px;
}

.article-img-lightbox-tool {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
  cursor: pointer;
  transition: background 0.15s;
}

.article-img-lightbox-tool:hover {
  background: rgba(255, 255, 255, 0.22);
}

.article-img-lightbox-stage {
  flex: 1;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  padding: 48px 24px 56px;
}

.article-img-lightbox-image {
  max-width: min(96vw, 100%);
  max-height: min(88vh, 100%);
  object-fit: contain;
  transform-origin: center center;
  transition: transform 0.06s ease-out;
  cursor: zoom-in;
  user-select: none;
  -webkit-user-drag: none;
}

.article-img-lightbox-stage.is-zoomed .article-img-lightbox-image {
  cursor: grab;
  max-width: none;
  max-height: none;
}

.article-img-lightbox-stage.is-dragging .article-img-lightbox-image {
  cursor: grabbing;
  transition: none;
}

.article-img-lightbox-fade-enter-active,
.article-img-lightbox-fade-leave-active {
  transition: opacity 0.18s ease;
}

.article-img-lightbox-fade-enter-from,
.article-img-lightbox-fade-leave-to {
  opacity: 0;
}
</style>
