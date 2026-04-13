import { defineStore } from 'pinia';
import { createApiClient, type ApiClient } from '@/api/client';
import type { ExtractedItem, RunDetail, TaskSummary } from '@/api/types';
import { readApiTokenFromStorage, writeApiTokenToStorage } from '@/utils/token';

export type WorkflowStatus =
  | 'idle'
  | 'htmlLoaded'
  | 'selectorChosen'
  | 'taskRunning'
  | 'previewReady'
  | 'previewFailed'
  | 'approved';

const TASK_POLL_INTERVAL_MS = 1500;
const TASK_TIMEOUT_MS = 120000;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

interface WorkflowDeps {
  api: ApiClient;
  sleep: (ms: number) => Promise<void>;
  now: () => number;
}

const defaultDeps: WorkflowDeps = {
  api: createApiClient(),
  sleep,
  now: () => Date.now(),
};

let deps: WorkflowDeps = defaultDeps;

export function __setWorkflowDeps(nextDeps: Partial<WorkflowDeps>): void {
  deps = {
    ...defaultDeps,
    ...nextDeps,
  };
}

export function __resetWorkflowDeps(): void {
  deps = defaultDeps;
}

function normalizeError(error: unknown): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return '发生未知错误';
}

function toPreviewError(runDetail: RunDetail): string {
  if (runDetail.error_log?.trim()) {
    return runDetail.error_log;
  }
  return '预览运行失败，请再次生成。';
}

export const useWorkflowStore = defineStore('workflow', {
  state: () => ({
    apiToken: '',
    urlInput: '',
    workflowStatus: 'idle' as WorkflowStatus,
    selectorMode: true,
    statusTone: 'idle' as 'idle' | 'ok' | 'fail',
    statusText: '等待输入 URL 和 API Token。说明：当前版本通过服务端代理接口抓取 HTML，再由前端查看器做点选。',
    previewHtml: '',
    seedUrl: '',
    finalUrl: '',
    selectedSelector: '',
    selectedXPath: '',
    selectedMeta: '尚未选择列表区域',
    siteId: null as number | null,
    versionId: null as number | null,
    runId: null as number | null,
    taskId: null as number | null,
    taskStatus: '',
    taskError: '',
    previewError: '',
    previewItems: [] as ExtractedItem[],
    previewRunStatus: '',
    approvedVersionNo: null as number | null,
    approvedSiteStatus: '',
    isLoadingHtml: false,
    isSubmittingRule: false,
    isApproving: false,
  }),
  getters: {
    canGenerate(state): boolean {
      return Boolean(
        state.selectedSelector &&
          !state.isLoadingHtml &&
          !state.isSubmittingRule &&
          state.previewHtml,
      );
    },
    canApprove(state): boolean {
      return Boolean(
        state.workflowStatus === 'previewReady' &&
          state.previewItems.length > 0 &&
          !state.isApproving,
      );
    },
    generateButtonText(state): string {
      return state.versionId ? '再次生成' : '生成规则';
    },
    workflowLabel(state): string {
      const labels: Record<WorkflowStatus, string> = {
        idle: '待开始',
        htmlLoaded: '页面已加载',
        selectorChosen: '已选列表区域',
        taskRunning: '正在生成',
        previewReady: '预览成功',
        previewFailed: '需要调整',
        approved: '已确认',
      };
      return labels[state.workflowStatus];
    },
    },
  actions: {
    hydrateToken(): void {
      this.apiToken = readApiTokenFromStorage();
    },
    setApiToken(value: string): void {
      this.apiToken = value;
      writeApiTokenToStorage(value);
    },
    setSelectorMode(enabled: boolean): void {
      this.selectorMode = enabled;
      this.statusTone = 'ok';
      this.statusText = enabled ? '选择模式已开启。' : '选择模式已关闭。';
    },
    resetGeneratedState(): void {
      this.selectedSelector = '';
      this.selectedXPath = '';
      this.selectedMeta = '尚未选择列表区域';
      this.siteId = null;
      this.versionId = null;
      this.runId = null;
      this.taskId = null;
      this.taskStatus = '';
      this.taskError = '';
      this.previewError = '';
      this.previewItems = [];
      this.previewRunStatus = '';
      this.approvedVersionNo = null;
      this.approvedSiteStatus = '';
    },
    async visitUrl(): Promise<void> {
      const token = this.apiToken.trim();
      const rawUrl = this.urlInput.trim();
      if (!rawUrl) {
        throw new Error('请输入 URL');
      }
      if (!token) {
        throw new Error('请输入 X-API-Token');
      }

      const normalizedUrl = new URL(rawUrl).toString();
      this.isLoadingHtml = true;
      this.statusTone = 'idle';
      this.statusText = '正在通过代理接口抓取页面 HTML...';
      this.workflowStatus = 'idle';
      this.taskError = '';
      this.previewError = '';

      try {
        const payload = await deps.api.proxyHtml(normalizedUrl, token);
        this.previewHtml = payload.html;
        this.seedUrl = normalizedUrl;
        this.finalUrl = payload.final_url || payload.url || normalizedUrl;
        this.resetGeneratedState();
        this.workflowStatus = 'htmlLoaded';
        this.statusTone = 'ok';
        this.statusText = '页面已加载，请在左侧点选新闻列表区域。';
      } catch (error) {
        this.previewHtml = '';
        this.finalUrl = '';
        this.seedUrl = normalizedUrl;
        this.resetGeneratedState();
        this.workflowStatus = 'idle';
        this.statusTone = 'fail';
        this.statusText = normalizeError(error);
        throw error;
      } finally {
        this.isLoadingHtml = false;
      }
    },
    setSelectedRegion(payload: {
      cssSelector: string;
      xpathSelector: string;
      metaText: string;
    }): void {
      this.selectedSelector = payload.cssSelector;
      this.selectedXPath = payload.xpathSelector;
      this.selectedMeta = payload.metaText;
      this.previewError = '';
      this.taskError = '';
      this.previewItems = [];
      this.previewRunStatus = '';
      this.taskId = null;
      this.runId = null;
      this.workflowStatus = 'selectorChosen';
      this.statusTone = 'ok';
      this.statusText = '已选中列表区域，可以生成规则。';
    },
    async generateRule(): Promise<void> {
      const token = this.apiToken.trim();
      if (!token) {
        throw new Error('请输入 X-API-Token');
      }
      if (!this.seedUrl) {
        throw new Error('请先访问新闻列表页面');
      }
      if (!this.selectedSelector.trim()) {
        throw new Error('请先在左侧点选列表区域');
      }

      this.isSubmittingRule = true;
      this.workflowStatus = 'taskRunning';
      this.statusTone = 'idle';
      this.statusText = '正在生成规则并等待预览任务完成...';
      this.taskError = '';
      this.previewError = '';
      this.previewItems = [];
      this.previewRunStatus = '';
      this.runId = null;

      try {
        const accepted = this.versionId
          ? await deps.api.regenerateVersion(
              this.versionId,
              { list_locator_hint: this.selectedSelector },
              token,
            )
          : await deps.api.createSite(
              { seed_url: this.seedUrl, list_locator_hint: this.selectedSelector },
              token,
            );

        this.taskId = accepted.task_id;
        this.taskStatus = accepted.task.status;

        const task = await this.pollTask(accepted.task_id, token);
        this.applyTaskContext(task);

        if (task.status !== 'succeeded') {
          const message =
            task.error_log ||
            String(task.result_json.error_log ?? '') ||
            '规则生成失败，请再次生成。';
          this.taskError = message;
          this.workflowStatus = 'previewFailed';
          this.statusTone = 'fail';
          this.statusText = message;
          return;
        }

        if (!this.runId) {
          this.previewError = '任务已完成，但没有返回预览运行结果。';
          this.workflowStatus = 'previewFailed';
          this.statusTone = 'fail';
          this.statusText = this.previewError;
          return;
        }

        const runDetail = await deps.api.getRun(this.runId, token);
        this.previewRunStatus = runDetail.status;

        if (runDetail.status !== 'succeeded') {
          this.previewError = toPreviewError(runDetail);
          this.workflowStatus = 'previewFailed';
          this.statusTone = 'fail';
          this.statusText = this.previewError;
          return;
        }

        this.previewItems = runDetail.result.items ?? [];
        if (this.previewItems.length === 0) {
          this.previewError = '未抽取到结果，请再次生成。';
          this.workflowStatus = 'previewFailed';
          this.statusTone = 'fail';
          this.statusText = this.previewError;
          return;
        }

        this.workflowStatus = 'previewReady';
        this.statusTone = 'ok';
        this.statusText = '预览成功，请核对右侧结果并确认。';
      } catch (error) {
        const message = normalizeError(error);
        this.taskError = message;
        this.previewError = message;
        this.workflowStatus = 'previewFailed';
        this.statusTone = 'fail';
        this.statusText = message;
        throw error;
      } finally {
        this.isSubmittingRule = false;
      }
    },
    async approveCurrentVersion(): Promise<void> {
      const token = this.apiToken.trim();
      if (!token) {
        throw new Error('请输入 X-API-Token');
      }
      if (!this.versionId) {
        throw new Error('当前没有可确认的版本');
      }
      if (this.previewItems.length === 0) {
        throw new Error('预览结果为空，不能确认成功');
      }

      this.isApproving = true;
      this.statusTone = 'idle';
      this.statusText = '正在确认当前版本...';

      try {
        const payload = await deps.api.approveVersion(this.versionId, token);
        this.approvedVersionNo = payload.version.version_no;
        this.approvedSiteStatus = String(payload.site.status ?? 'active');
        this.workflowStatus = 'approved';
        this.statusTone = 'ok';
        this.statusText = '版本已确认，站点已激活。';
      } catch (error) {
        const message = normalizeError(error);
        this.statusTone = 'fail';
        this.statusText = message;
        throw error;
      } finally {
        this.isApproving = false;
      }
    },
    applyTaskContext(task: TaskSummary): void {
      const resultSiteId = Number(task.result_json.site_id ?? task.site_id ?? 0) || null;
      const resultVersionId =
        Number(task.result_json.version_id ?? task.version_id ?? 0) || null;
      const resultRunId = Number(task.result_json.run_id ?? task.run_id ?? 0) || null;

      this.taskStatus = task.status;
      this.siteId = resultSiteId;
      this.versionId = resultVersionId;
      this.runId = resultRunId;
    },
    async pollTask(taskId: number, token: string): Promise<TaskSummary> {
      const startAt = deps.now();
      while (deps.now() - startAt <= TASK_TIMEOUT_MS) {
        const task = await deps.api.getTask(taskId, token);
        this.taskStatus = task.status;
        if (task.status === 'succeeded' || task.status === 'failed') {
          return task;
        }
        await deps.sleep(TASK_POLL_INTERVAL_MS);
      }

      throw new Error('预览任务轮询超时，请重试。');
    },
  },
});
