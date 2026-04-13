<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { buildPreviewDocument } from '@/utils/html';
import { getIframeEventElementTarget } from '@/utils/iframe';
import { buildSelectorOutput } from '@/utils/selector';

const props = defineProps<{
  htmlContent: string;
  pageUrl: string;
  selectorMode: boolean;
}>();

const emit = defineEmits<{
  select: [
    payload: {
      cssSelector: string;
      xpathSelector: string;
      metaText: string;
    },
  ];
}>();

const frameRef = ref<HTMLIFrameElement | null>(null);
let cleanup: (() => void) | null = null;
let selectedElement: Element | null = null;

const frameLabel = computed(() => props.pageUrl || '尚未加载页面');

function clearHooks(): void {
  cleanup?.();
  cleanup = null;
  selectedElement = null;
}

function attachInspector(): void {
  clearHooks();

  const iframe = frameRef.value;
  if (!iframe?.contentDocument || !iframe.contentWindow) {
    return;
  }
  const doc = iframe.contentDocument;
  const win = iframe.contentWindow;

  const style = doc.createElement('style');
  style.textContent = `
    .__selector_hover_box__, .__selector_selected_box__ {
      position: absolute;
      pointer-events: none;
      z-index: 2147483647;
      box-sizing: border-box;
    }
    .__selector_hover_box__ {
      border: 2px solid #38bdf8;
      background: rgba(56, 189, 248, 0.12);
    }
    .__selector_selected_box__ {
      border: 2px solid #22c55e;
      background: rgba(34, 197, 94, 0.14);
    }
  `;
  doc.head.appendChild(style);

  const hoverBox = doc.createElement('div');
  hoverBox.className = '__selector_hover_box__';
  const selectedBox = doc.createElement('div');
  selectedBox.className = '__selector_selected_box__';
  doc.body.appendChild(hoverBox);
  doc.body.appendChild(selectedBox);

  function placeBox(box: HTMLDivElement, el: Element | null): void {
    if (!el || el === doc.documentElement || el === doc.body) {
      box.style.display = 'none';
      return;
    }

    const rect = el.getBoundingClientRect();
    box.style.display = 'block';
    box.style.left = `${rect.left + win.scrollX}px`;
    box.style.top = `${rect.top + win.scrollY}px`;
    box.style.width = `${rect.width}px`;
    box.style.height = `${rect.height}px`;
  }

  function handleMouseMove(event: MouseEvent): void {
    if (!props.selectorMode) {
      hoverBox.style.display = 'none';
      return;
    }

    const target = getIframeEventElementTarget(event.target, doc);
    if (!target || target === hoverBox || target === selectedBox) {
      return;
    }

    placeBox(hoverBox, target);
  }

  function handleClick(event: MouseEvent): void {
    if (!props.selectorMode) {
      return;
    }

    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();

    const target = getIframeEventElementTarget(event.target, doc);
    if (!target || target === hoverBox || target === selectedBox) {
      return;
    }

    selectedElement = target;
    placeBox(selectedBox, target);
    emit('select', buildSelectorOutput(target));
  }

  function syncSelectedBox(): void {
    placeBox(selectedBox, selectedElement);
  }

  doc.addEventListener('mousemove', handleMouseMove, true);
  doc.addEventListener('click', handleClick, true);
  win.addEventListener('scroll', syncSelectedBox, true);
  win.addEventListener('resize', syncSelectedBox, true);

  cleanup = () => {
    doc.removeEventListener('mousemove', handleMouseMove, true);
    doc.removeEventListener('click', handleClick, true);
    win.removeEventListener('scroll', syncSelectedBox, true);
    win.removeEventListener('resize', syncSelectedBox, true);
  };
}

function loadIntoFrame(): void {
  const iframe = frameRef.value;
  if (!iframe) {
    return;
  }

  clearHooks();

  if (!props.htmlContent || !props.pageUrl) {
    iframe.srcdoc = `
      <!doctype html>
      <html lang="zh-CN">
        <body style="margin:0;display:grid;place-items:center;height:100vh;font-family:system-ui;background:#f8fafc;color:#475569;">
          <div>等待加载页面</div>
        </body>
      </html>
    `;
    return;
  }

  iframe.srcdoc = buildPreviewDocument(props.htmlContent, props.pageUrl);
}

watch(() => [props.htmlContent, props.pageUrl] as const, loadIntoFrame, { immediate: true });
watch(
  () => props.selectorMode,
  (enabled) => {
    const doc = frameRef.value?.contentDocument;
    if (!enabled && doc) {
      doc
        .querySelectorAll('.__selector_hover_box__, .__selector_selected_box__')
        .forEach((el) => {
        (el as HTMLElement).style.display = 'none';
      });
    }
  },
);

onBeforeUnmount(() => {
  clearHooks();
});
</script>

<template>
  <section class="viewport">
    <div class="frame-wrap">
      <div class="frame-bar">
        <span class="bubble" />
        <span>{{ frameLabel }}</span>
      </div>
      <iframe
        ref="frameRef"
        sandbox="allow-same-origin allow-forms allow-popups allow-modals allow-downloads"
        @load="attachInspector"
      />
    </div>
  </section>
</template>
