<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Edit, Refresh, Search, View } from '@element-plus/icons-vue';
import { createApiClient } from '@/api/client';
import type {
  SiteDetail,
  SiteSummary,
  SiteUpdateRequest,
} from '@/api/types';
import { readApiTokenFromStorage, writeApiTokenToStorage } from '@/utils/token';

const api = createApiClient();

const apiToken = ref('');
const keyword = ref('');
const statusFilter = ref('');
const sites = ref<SiteSummary[]>([]);
const total = ref(0);
const currentPage = ref(1);
const pageSize = ref(10);
const isLoading = ref(false);
const isSubmittingEdit = ref(false);
const deletingSiteId = ref<number | null>(null);

const detailVisible = ref(false);
const detailLoading = ref(false);
const siteDetail = ref<SiteDetail | null>(null);

const editVisible = ref(false);
const editingSiteId = ref<number | null>(null);

const editForm = reactive<{
  name: string;
  notes: string;
  status: 'draft' | 'active';
}>({
  name: '',
  notes: '',
  status: 'draft',
});

const canQuery = computed(() => Boolean(apiToken.value.trim()));
const detailVersions = computed(() => siteDetail.value?.recent_versions ?? []);
const detailRuns = computed(() => siteDetail.value?.recent_runs ?? []);

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

function openEditDialog(site: SiteSummary): void {
  editingSiteId.value = site.id;
  editForm.name = site.name;
  editForm.notes = site.notes ?? '';
  editForm.status = site.status === 'active' ? 'active' : 'draft';
  editVisible.value = true;
}

async function loadSites(): Promise<void> {
  const token = requireToken();
  isLoading.value = true;
  try {
    const payload = await api.listSites(
      {
        keyword: keyword.value.trim() || undefined,
        status: statusFilter.value || undefined,
        page: currentPage.value,
        pageSize: pageSize.value,
      },
      token,
    );
    sites.value = payload.items;
    total.value = payload.page_meta.total;
  } finally {
    isLoading.value = false;
  }
}

async function handleSearch(): Promise<void> {
  currentPage.value = 1;
  try {
    await loadSites();
  } catch (error) {
    ElMessage.error(normalizeError(error));
  }
}

async function handleRefresh(): Promise<void> {
  try {
    await loadSites();
    ElMessage.success('站点列表已刷新');
  } catch (error) {
    ElMessage.error(normalizeError(error));
  }
}

async function handlePageChange(page: number): Promise<void> {
  currentPage.value = page;
  try {
    await loadSites();
  } catch (error) {
    ElMessage.error(normalizeError(error));
  }
}

async function handlePageSizeChange(size: number): Promise<void> {
  pageSize.value = size;
  currentPage.value = 1;
  try {
    await loadSites();
  } catch (error) {
    ElMessage.error(normalizeError(error));
  }
}

async function loadSiteDetail(siteId: number): Promise<void> {
  const token = requireToken();
  detailLoading.value = true;
  try {
    siteDetail.value = await api.getSite(siteId, token);
    detailVisible.value = true;
  } finally {
    detailLoading.value = false;
  }
}

async function handleView(siteId: number): Promise<void> {
  try {
    await loadSiteDetail(siteId);
  } catch (error) {
    ElMessage.error(normalizeError(error));
  }
}

async function handleUpdate(): Promise<void> {
  const token = requireToken();
  if (!editingSiteId.value) {
    return;
  }

  const body: SiteUpdateRequest = {
    name: editForm.name.trim() || null,
    notes: editForm.notes.trim() || null,
    status: editForm.status,
  };

  isSubmittingEdit.value = true;
  try {
    await api.updateSite(editingSiteId.value, body, token);
    editVisible.value = false;
    await loadSites();
    if (detailVisible.value && siteDetail.value?.id === editingSiteId.value) {
      await loadSiteDetail(editingSiteId.value);
    }
    ElMessage.success('站点信息已更新');
  } catch (error) {
    ElMessage.error(normalizeError(error));
  } finally {
    isSubmittingEdit.value = false;
  }
}

async function handleDelete(site: SiteSummary): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `将删除站点“${site.name}”及其关联版本、运行和文章记录。此操作不可恢复。`,
      '确认删除',
      {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消',
      },
    );
  } catch {
    return;
  }

  const token = requireToken();
  deletingSiteId.value = site.id;
  try {
    await api.deleteSite(site.id, token);
    if (siteDetail.value?.id === site.id) {
      detailVisible.value = false;
      siteDetail.value = null;
    }

    if (sites.value.length === 1 && currentPage.value > 1) {
      currentPage.value -= 1;
    }
    await loadSites();
    ElMessage.success('站点已删除');
  } catch (error) {
    ElMessage.error(normalizeError(error));
  } finally {
    deletingSiteId.value = null;
  }
}

onMounted(async () => {
  apiToken.value = readApiTokenFromStorage();
  if (apiToken.value.trim()) {
    try {
      await loadSites();
    } catch (error) {
      ElMessage.error(normalizeError(error));
    }
  }
});
</script>

<template>
  <main class="page-shell sites-page">
    <section class="toolbar-card sites-toolbar">
      <el-input
        v-model="apiToken"
        class="toolbar-input token-input"
        placeholder="输入 X-API-Token"
        show-password
        @change="persistToken"
        @keyup.enter="handleSearch"
      />
      <el-input
        v-model="keyword"
        class="toolbar-input"
        placeholder="按站点名称、域名或种子 URL 搜索"
        @keyup.enter="handleSearch"
      />
      <el-select v-model="statusFilter" placeholder="全部状态" clearable class="status-filter">
        <el-option label="草稿" value="draft" />
        <el-option label="启用" value="active" />
      </el-select>
      <el-button :icon="Search" :disabled="!canQuery" @click="handleSearch">查询</el-button>
      <el-button :icon="Refresh" :disabled="!canQuery" @click="handleRefresh">刷新</el-button>
    </section>

    <section class="hint-card">
      <div class="status-wrap">
        <span class="dot ok" />
        <span class="status-text">站点管理页支持查看、编辑和删除站点。</span>
      </div>
      <div class="hint-text">删除会级联移除关联版本、运行、文章和任务数据。</div>
    </section>

    <section class="sites-layout">
      <section class="table-card">
        <div class="panel-head">
          <h2 class="panel-title">站点列表</h2>
          <el-tag type="info" effect="plain">共 {{ total }} 个</el-tag>
        </div>

        <el-empty
          v-if="!apiToken.trim()"
          description="请输入 X-API-Token 后查询站点列表。"
        />
        <template v-else>
          <el-table
            v-loading="isLoading"
            :data="sites"
            row-key="id"
            class="sites-table"
            empty-text="暂无站点"
          >
            <el-table-column prop="name" label="站点" min-width="220">
              <template #default="{ row }">
                <div class="site-name-cell">
                  <strong>{{ row.name }}</strong>
                  <span>{{ row.domain }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="seed_url" label="Seed URL" min-width="260" show-overflow-tooltip />
            <el-table-column label="状态" width="110">
              <template #default="{ row }">
                <el-tag :type="row.status === 'active' ? 'success' : 'info'" effect="plain">
                  {{ row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="正式版本" width="120">
              <template #default="{ row }">
                {{ row.approved_version_no ? `V${row.approved_version_no}` : '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="article_count" label="文章数" width="90" />
            <el-table-column prop="today_new_count" label="今日新增" width="100" />
            <el-table-column label="最近运行" min-width="150">
              <template #default="{ row }">
                {{ row.last_run_status || '-' }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="220" fixed="right">
              <template #default="{ row }">
                <div class="site-actions">
                  <el-button text :icon="View" @click="handleView(row.id)">详情</el-button>
                  <el-button text :icon="Edit" @click="openEditDialog(row)">编辑</el-button>
                  <el-button
                    text
                    type="danger"
                    :loading="deletingSiteId === row.id"
                    @click="handleDelete(row)"
                  >
                    删除
                  </el-button>
                </div>
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
              :page-sizes="[10, 20, 50]"
              @current-change="handlePageChange"
              @size-change="handlePageSizeChange"
            />
          </div>
        </template>
      </section>
    </section>

    <el-dialog v-model="editVisible" title="编辑站点" width="560px">
      <el-form label-position="top">
        <el-form-item label="站点名称">
          <el-input v-model="editForm.name" placeholder="请输入站点名称" @keyup.enter="handleUpdate" />
        </el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="editForm.status">
            <el-radio value="draft">draft</el-radio>
            <el-radio value="active">active</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="editForm.notes"
            type="textarea"
            :rows="4"
            placeholder="可填写备注或默认列表定位器"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="isSubmittingEdit" @click="handleUpdate">
          保存
        </el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="detailVisible" size="620px" title="站点详情">
      <div v-loading="detailLoading" class="detail-panel">
        <template v-if="siteDetail">
          <section class="panel-card">
            <div class="panel-head">
              <h2 class="panel-title">{{ siteDetail.name }}</h2>
              <el-tag :type="siteDetail.status === 'active' ? 'success' : 'info'" effect="plain">
                {{ siteDetail.status }}
              </el-tag>
            </div>
            <el-descriptions :column="1" border class="status-grid">
              <el-descriptions-item label="域名">{{ siteDetail.domain }}</el-descriptions-item>
              <el-descriptions-item label="Seed URL">
                {{ siteDetail.seed_url }}
              </el-descriptions-item>
              <el-descriptions-item label="备注">
                {{ siteDetail.notes || '-' }}
              </el-descriptions-item>
              <el-descriptions-item label="文章数">
                {{ siteDetail.article_count }}
              </el-descriptions-item>
              <el-descriptions-item label="正式版本">
                {{
                  siteDetail.approved_version
                    ? `V${siteDetail.approved_version.version_no} (${siteDetail.approved_version.status})`
                    : '-'
                }}
              </el-descriptions-item>
            </el-descriptions>
          </section>

          <section class="panel-card">
            <div class="panel-head">
              <h2 class="panel-title">最近版本</h2>
              <el-tag type="info" effect="plain">{{ detailVersions.length }} 条</el-tag>
            </div>
            <el-empty v-if="detailVersions.length === 0" description="暂无版本记录" />
            <div v-else class="detail-list">
              <div v-for="version in detailVersions" :key="version.id" class="detail-list-item">
                <strong>V{{ version.version_no }}</strong>
                <span>{{ version.status }}</span>
                <span>{{ version.latest_run_status || '-' }}</span>
              </div>
            </div>
          </section>

          <section class="panel-card">
            <div class="panel-head">
              <h2 class="panel-title">最近运行</h2>
              <el-tag type="info" effect="plain">{{ detailRuns.length }} 条</el-tag>
            </div>
            <el-empty v-if="detailRuns.length === 0" description="暂无运行记录" />
            <div v-else class="detail-list">
              <div v-for="run in detailRuns" :key="run.id" class="detail-list-item">
                <strong>#{{ run.id }}</strong>
                <span>{{ run.run_type }}</span>
                <span>{{ run.status }}</span>
              </div>
            </div>
          </section>
        </template>
      </div>
    </el-drawer>
  </main>
</template>
