import { createPinia, setActivePinia } from 'pinia';
import type { ApiClient } from '@/api/client';
import { __resetWorkflowDeps, __setWorkflowDeps, useWorkflowStore } from '@/stores/workflow';

function createApiMock(): ApiClient {
  return {
    proxyHtml: vi.fn(),
    listArticles: vi.fn(),
    listSites: vi.fn(),
    createSite: vi.fn(),
    getSite: vi.fn(),
    updateSite: vi.fn(),
    deleteSite: vi.fn(),
    getTask: vi.fn(),
    getRun: vi.fn(),
    regenerateVersion: vi.fn(),
    approveVersion: vi.fn(),
  };
}

describe('workflow store', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  afterEach(() => {
    __resetWorkflowDeps();
    vi.restoreAllMocks();
  });

  it('hydrates token from localStorage', () => {
    window.localStorage.setItem('ai-news-spider.api-token', 'persisted-token');
    const store = useWorkflowStore();
    store.hydrateToken();
    expect(store.apiToken).toBe('persisted-token');
  });

  it('creates a site and reaches previewReady on successful preview', async () => {
    const api = createApiMock();
    vi.mocked(api.createSite).mockResolvedValue({
      task_id: 11,
      task: {
        id: 11,
        task_type: 'create_site_preview',
        status: 'pending',
        params_json: {},
        result_json: {},
        error_log: '',
        site_id: null,
        version_id: null,
        run_id: null,
        created_at: '',
        started_at: null,
        finished_at: null,
      },
    });
    vi.mocked(api.getTask).mockResolvedValue({
      id: 11,
      task_type: 'create_site_preview',
      status: 'succeeded',
      params_json: {},
      result_json: { site_id: 7, version_id: 8, run_id: 9 },
      error_log: '',
      site_id: 7,
      version_id: 8,
      run_id: 9,
      created_at: '',
      started_at: null,
      finished_at: null,
    });
    vi.mocked(api.getRun).mockResolvedValue({
      id: 9,
      status: 'succeeded',
      error_log: '',
      result: {
        items: [
          {
            title: '第一条新闻',
            url: 'https://example.com/a1',
            source_list_url: 'https://example.com/news',
          },
        ],
      },
    });

    __setWorkflowDeps({
      api,
      sleep: async () => {},
      now: () => 0,
    });

    const store = useWorkflowStore();
    store.setApiToken('token-1');
    store.urlInput = 'https://example.com/news';
    vi.mocked(api.proxyHtml).mockResolvedValue({
      url: 'https://example.com/news',
      final_url: 'https://example.com/news',
      html: '<div class="news-list"></div>',
      rendered_by: 'crawl4ai',
    });

    await store.visitUrl();
    store.setSelectedRegion({
      cssSelector: '.news-list',
      xpathSelector: '/html/body/div[1]',
      metaText: '标签: div',
    });
    await store.generateRule();

    expect(api.createSite).toHaveBeenCalledWith(
      {
        seed_url: 'https://example.com/news',
        list_locator_hint: '.news-list',
      },
      'token-1',
    );
    expect(store.workflowStatus).toBe('previewReady');
    expect(store.previewItems).toHaveLength(1);
    expect(store.versionId).toBe(8);
  });

  it('uses regenerateVersion when version already exists and marks previewFailed for empty items', async () => {
    const api = createApiMock();
    vi.mocked(api.regenerateVersion).mockResolvedValue({
      task_id: 22,
      task: {
        id: 22,
        task_type: 'regenerate_version_preview',
        status: 'pending',
        params_json: {},
        result_json: {},
        error_log: '',
        site_id: 4,
        version_id: 5,
        run_id: null,
        created_at: '',
        started_at: null,
        finished_at: null,
      },
    });
    vi.mocked(api.getTask).mockResolvedValue({
      id: 22,
      task_type: 'regenerate_version_preview',
      status: 'succeeded',
      params_json: {},
      result_json: { site_id: 4, version_id: 6, run_id: 7 },
      error_log: '',
      site_id: 4,
      version_id: 6,
      run_id: 7,
      created_at: '',
      started_at: null,
      finished_at: null,
    });
    vi.mocked(api.getRun).mockResolvedValue({
      id: 7,
      status: 'succeeded',
      error_log: '',
      result: {
        items: [],
      },
    });

    __setWorkflowDeps({
      api,
      sleep: async () => {},
      now: () => 0,
    });

    const store = useWorkflowStore();
    store.setApiToken('token-2');
    store.seedUrl = 'https://example.com/news';
    store.previewHtml = '<div class="news-list"></div>';
    store.versionId = 5;
    store.setSelectedRegion({
      cssSelector: '.news-list',
      xpathSelector: '/html/body/div[1]',
      metaText: '标签: div',
    });

    await store.generateRule();

    expect(api.regenerateVersion).toHaveBeenCalledWith(
      5,
      { list_locator_hint: '.news-list' },
      'token-2',
    );
    expect(store.workflowStatus).toBe('previewFailed');
    expect(store.previewError).toBe('未抽取到结果，请再次生成。');
    expect(store.versionId).toBe(6);
  });

  it('approves current version and enters approved state', async () => {
    const api = createApiMock();
    vi.mocked(api.approveVersion).mockResolvedValue({
      version: {
        id: 10,
        site_id: 5,
        version_no: 3,
        status: 'approved',
      },
      site: {
        status: 'active',
        approved_version_id: 10,
      },
    });

    __setWorkflowDeps({
      api,
      sleep: async () => {},
      now: () => 0,
    });

    const store = useWorkflowStore();
    store.setApiToken('token-3');
    store.versionId = 10;
    store.previewItems = [
      {
        title: '第一条新闻',
        url: 'https://example.com/a1',
        source_list_url: 'https://example.com/news',
      },
    ];
    store.workflowStatus = 'previewReady';

    await store.approveCurrentVersion();

    expect(store.workflowStatus).toBe('approved');
    expect(store.approvedVersionNo).toBe(3);
    expect(store.approvedSiteStatus).toBe('active');
  });
});
