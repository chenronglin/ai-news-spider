<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { ElMessage } from 'element-plus';
import { Refresh, Search } from '@element-plus/icons-vue';
import { createApiClient } from '@/api/client';
import type { ArticleSummary } from '@/api/types';
import { readApiTokenFromStorage, writeApiTokenToStorage } from '@/utils/token';

const api = createApiClient();

const apiToken = ref('');
const articles = ref<ArticleSummary[]>([]);
const total = ref(0);
const currentPage = ref(1);
const pageSize = ref(20);
const isLoading = ref(false);

const filters = reactive({
  siteId: '',
  runId: '',
  title: '',
  keyword: '',
  sourceListUrl: '',
  publishedFrom: '',
  publishedTo: '',
});

const canQuery = computed(() => Boolean(apiToken.value.trim()));

function normalizeError(error: unknown): string {
  return error instanceof Error ? error.message : '发生未知错误';
}

function persistToken(): void {
  writeApiTokenToStorage(apiToken.value);
}

function requireToken(): string {
  const token = apiToken.value.trim();
  if (!token) {
    throw new Error('请输入 X-API-Token');
  }
  writeApiTokenToStorage(token);
  return token;
}

function parseOptionalNumber(value: string): number | undefined {
  const trimmed = value.trim();
  if (!trimmed) {
    return undefined;
  }
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return '-';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

async function loadArticles(): Promise<void> {
  const token = requireToken();
  isLoading.value = true;
  try {
    const payload = await api.listArticles(
      {
        siteId: parseOptionalNumber(filters.siteId),
        runId: parseOptionalNumber(filters.runId),
        title: filters.title.trim() || undefined,
        keyword: filters.keyword.trim() || undefined,
        sourceListUrl: filters.sourceListUrl.trim() || undefined,
        publishedFrom: filters.publishedFrom.trim() || undefined,
        publishedTo: filters.publishedTo.trim() || undefined,
        page: currentPage.value,
        pageSize: pageSize.value,
      },
      token,
    );
    articles.value = payload.items;
    total.value = payload.page_meta.total;
  } finally {
    isLoading.value = false;
  }
}

async function handleSearch(): Promise<void> {
  currentPage.value = 1;
  try {
    await loadArticles();
  } catch (error) {
    ElMessage.error(normalizeError(error));
  }
}

async function handleRefresh(): Promise<void> {
  try {
    await loadArticles();
    ElMessage.success('新闻列表已刷新');
  } catch (error) {
    ElMessage.error(normalizeError(error));
  }
}

async function handlePageChange(page: number): Promise<void> {
  currentPage.value = page;
  try {
    await loadArticles();
  } catch (error) {
    ElMessage.error(normalizeError(error));
  }
}

async function handlePageSizeChange(size: number): Promise<void> {
  pageSize.value = size;
  currentPage.value = 1;
  try {
    await loadArticles();
  } catch (error) {
    ElMessage.error(normalizeError(error));
  }
}

onMounted(async () => {
  apiToken.value = readApiTokenFromStorage();
  if (apiToken.value.trim()) {
    try {
      await loadArticles();
    } catch (error) {
      ElMessage.error(normalizeError(error));
    }
  }
});
</script>

<template>
  <main class="page-shell articles-page">
    <section class="toolbar-card articles-toolbar">
      <el-input
        v-model="apiToken"
        class="toolbar-input token-input"
        placeholder="输入 X-API-Token"
        show-password
        @change="persistToken"
        @keyup.enter="handleSearch"
      />
      <el-input
        v-model="filters.keyword"
        class="toolbar-input"
        placeholder="关键词，匹配标题、URL、来源页"
        @keyup.enter="handleSearch"
      />
      <el-input
        v-model="filters.title"
        class="toolbar-input"
        placeholder="按标题片段过滤"
        @keyup.enter="handleSearch"
      />
      <el-button :icon="Search" :disabled="!canQuery" @click="handleSearch">查询</el-button>
      <el-button :icon="Refresh" :disabled="!canQuery" @click="handleRefresh">刷新</el-button>
    </section>

    <section class="hint-card">
      <div class="status-wrap">
        <span class="dot ok" />
        <span class="status-text">新闻列表页展示 `/api/v1/articles` 的爬取结果，可跨站点检索。</span>
      </div>
      <div class="hint-text">标题可直接打开原文，支持按站点、运行、来源页和发布时间区间筛选。</div>
    </section>

    <section class="table-card article-filter-card">
      <div class="panel-head">
        <h2 class="panel-title">筛选条件</h2>
        <el-tag type="info" effect="plain">共 {{ total }} 条</el-tag>
      </div>

      <div class="article-filter-grid">
        <el-input
          v-model="filters.siteId"
          class="toolbar-input"
          placeholder="站点 ID"
          @keyup.enter="handleSearch"
        />
        <el-input
          v-model="filters.runId"
          class="toolbar-input"
          placeholder="运行 ID"
          @keyup.enter="handleSearch"
        />
        <el-input
          v-model="filters.sourceListUrl"
          class="toolbar-input"
          placeholder="来源列表页 URL"
          @keyup.enter="handleSearch"
        />
        <el-input
          v-model="filters.publishedFrom"
          class="toolbar-input"
          placeholder="发布时间起，例如 2026-04-08T00:00:00+08:00"
          @keyup.enter="handleSearch"
        />
        <el-input
          v-model="filters.publishedTo"
          class="toolbar-input"
          placeholder="发布时间止，例如 2026-04-10T23:59:59+08:00"
          @keyup.enter="handleSearch"
        />
      </div>
    </section>

    <section class="table-card articles-table-card">
      <div class="panel-head">
        <h2 class="panel-title">新闻列表</h2>
        <el-tag type="info" effect="plain">分页 {{ currentPage }}</el-tag>
      </div>

      <el-empty
        v-if="!apiToken.trim()"
        description="请输入 X-API-Token 后查询新闻列表。"
      />
      <template v-else>
        <el-table
          v-loading="isLoading"
          :data="articles"
          row-key="id"
          class="sites-table"
          empty-text="暂无新闻数据"
        >
          <el-table-column label="标题" min-width="340">
            <template #default="{ row }">
              <a :href="row.url" target="_blank" rel="noreferrer" class="article-link">
                {{ row.title }}
              </a>
            </template>
          </el-table-column>
          <el-table-column label="站点" min-width="180">
            <template #default="{ row }">
              <div class="site-name-cell">
                <strong>{{ row.site_name || `站点 #${row.site_id}` }}</strong>
                <span>ID: {{ row.site_id }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="published_at" label="发布时间" min-width="170">
            <template #default="{ row }">
              {{ formatDateTime(row.published_at) }}
            </template>
          </el-table-column>
          <el-table-column label="运行 ID" width="100">
            <template #default="{ row }">
              #{{ row.run_id }}
            </template>
          </el-table-column>
          <el-table-column label="首次发现" min-width="170">
            <template #default="{ row }">
              {{ formatDateTime(row.first_seen_at) }}
            </template>
          </el-table-column>
          <el-table-column label="最近发现" min-width="170">
            <template #default="{ row }">
              {{ formatDateTime(row.last_seen_at) }}
            </template>
          </el-table-column>
        </el-table>

        <div class="site-pagination">
          <el-pagination
            background
            layout="total, sizes, prev, pager, next"
            :total="total"
            :current-page="currentPage"
            :page-size="pageSize"
            :page-sizes="[20, 50, 100]"
            @current-change="handlePageChange"
            @size-change="handlePageSizeChange"
          />
        </div>
      </template>
    </section>
  </main>
</template>
