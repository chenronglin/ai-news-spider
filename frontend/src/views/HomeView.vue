<script setup lang="ts">
import { computed, onMounted } from 'vue';
import { storeToRefs } from 'pinia';
import { ElMessage } from 'element-plus';
import PagePreview from '@/components/PagePreview.vue';
import WorkflowPanel from '@/components/WorkflowPanel.vue';
import { useWorkflowStore } from '@/stores/workflow';

const store = useWorkflowStore();
const { selectorMode } = storeToRefs(store);

const statusDotClass = computed(() => ({
  dot: true,
  ok: store.statusTone === 'ok',
  fail: store.statusTone === 'fail',
}));

const selectorModeText = computed(() => `选择模式：${selectorMode.value ? '开启' : '关闭'}`);

const tokenModel = computed({
  get: () => store.apiToken,
  set: (value: string) => store.setApiToken(value),
});

onMounted(() => {
  store.hydrateToken();
});

async function handleVisit(): Promise<void> {
  try {
    await store.visitUrl();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '访问失败');
  }
}
</script>

<template>
  <main class="page-shell">
    <section class="toolbar-card">
      <el-input
        v-model="store.urlInput"
        class="toolbar-input"
        placeholder="输入新闻列表页 URL，例如 https://example.com/news"
        @keyup.enter="handleVisit"
      />
      <el-input
        v-model="tokenModel"
        class="toolbar-input token-input"
        placeholder="输入 X-API-Token"
        show-password
        @keyup.enter="handleVisit"
      />
      <el-button
        type="success"
        size="large"
        :loading="store.isLoadingHtml"
        :disabled="store.isSubmittingRule || store.isApproving"
        @click="handleVisit"
      >
        访问
      </el-button>
      <el-switch
        :model-value="store.selectorMode"
        inline-prompt
        active-text="开"
        inactive-text="关"
        @change="store.setSelectorMode"
      />
      <span class="selector-label">{{ selectorModeText }}</span>
    </section>

    <section class="hint-card">
      <div class="status-wrap">
        <span :class="statusDotClass" />
        <span class="status-text">{{ store.statusText }}</span>
      </div>
      <div class="hint-text">悬浮高亮，点击列表区域后自动生成 CSS Selector</div>
    </section>

    <section class="workspace">
      <PagePreview
        :html-content="store.previewHtml"
        :page-url="store.finalUrl"
        :selector-mode="store.selectorMode"
        @select="store.setSelectedRegion"
      />
      <WorkflowPanel />
    </section>
  </main>
</template>
