<script setup lang="ts">
import { computed } from 'vue';
import { storeToRefs } from 'pinia';
import { ElMessage } from 'element-plus';
import { Link, CircleCheck, Refresh } from '@element-plus/icons-vue';
import { useWorkflowStore } from '@/stores/workflow';

const store = useWorkflowStore();
const {
  generateButtonText,
  canGenerate,
  canApprove,
} = storeToRefs(store);

const hasFailure = computed(() => Boolean(store.taskError || store.previewError));
const failureText = computed(() => store.previewError || store.taskError);

async function handleGenerate(): Promise<void> {
  try {
    await store.generateRule();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '生成规则失败');
  }
}

async function handleApprove(): Promise<void> {
  try {
    await store.approveCurrentVersion();
    ElMessage.success('版本已确认，站点已激活');
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '确认失败');
  }
}
</script>

<template>
  <aside class="workflow-panel">
    <section class="panel-card">
      <div class="panel-head">
        <h2 class="panel-title">已选列表区域</h2>
      </div>

      <div class="field-group">
        <label>元素信息</label>
        <el-input :model-value="store.selectedMeta" type="textarea" :rows="6" readonly />
      </div>

      <el-alert
        v-if="hasFailure"
        :title="failureText"
        type="error"
        show-icon
        :closable="false"
        class="inline-alert"
      />
    </section>

    <section class="panel-card">
      <div class="panel-head">
        <h2 class="panel-title">规则生成</h2>
        <el-tag v-if="store.taskStatus" type="warning" effect="plain">
          任务状态：{{ store.taskStatus }}
        </el-tag>
      </div>

      <p class="panel-note">
        首次生成会创建站点与预览任务；后续会基于当前 selector 再次生成新版本。
      </p>

      <div class="action-stack">
        <el-button
          type="success"
          size="large"
          :icon="store.versionId ? Refresh : Link"
          :loading="store.isSubmittingRule"
          :disabled="!canGenerate"
          @click="handleGenerate"
        >
          {{ generateButtonText }}
        </el-button>
        <el-button
          type="primary"
          plain
          size="large"
          :icon="CircleCheck"
          :loading="store.isApproving"
          :disabled="!canApprove"
          @click="handleApprove"
        >
          确认成功
        </el-button>
      </div>

      <p v-if="store.approvedVersionNo" class="approval-note">
        当前已确认版本：V{{ store.approvedVersionNo }}，站点状态：{{ store.approvedSiteStatus || 'active' }}
      </p>
    </section>

    <section class="panel-card panel-fill">
      <div class="panel-head">
        <h2 class="panel-title">预览结果</h2>
        <el-tag
          v-if="store.previewRunStatus"
          :type="store.previewRunStatus === 'succeeded' ? 'success' : 'danger'"
          effect="plain"
        >
          运行状态：{{ store.previewRunStatus }}
        </el-tag>
      </div>

      <el-empty
        v-if="store.previewItems.length === 0"
        description="暂无可确认的预览结果。请选择列表区域并生成规则。"
      />
      <el-scrollbar v-else class="result-scroll">
        <div class="result-list">
          <a
            v-for="(item, index) in store.previewItems"
            :key="`${item.url}-${index}`"
            :href="item.url"
            class="result-item"
            target="_blank"
            rel="noreferrer"
          >
            <span class="result-index">{{ index + 1 }}</span>
            <span class="result-title">{{ item.title }}</span>
          </a>
        </div>
      </el-scrollbar>
    </section>
  </aside>
</template>
