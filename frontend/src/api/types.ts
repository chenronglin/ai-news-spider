export interface ProxyHtmlResponse {
  url: string;
  final_url: string;
  html: string;
  rendered_by: string;
}

export interface PageMeta {
  page: number;
  page_size: number;
  total: number;
}

export interface SiteSummary {
  id: number;
  name: string;
  domain: string;
  seed_url: string;
  status: 'draft' | 'active' | string;
  approved_version_id: number | null;
  approved_version_no: number | null;
  notes: string | null;
  created_at: string;
  last_run_at: string | null;
  last_run_status: string | null;
  recent_error: string | null;
  article_count: number;
  today_new_count: number;
}

export interface SiteListResponse {
  items: SiteSummary[];
  page_meta: PageMeta;
}

export interface ArticleSummary {
  id: number;
  site_id: number;
  site_name?: string | null;
  title: string;
  url: string;
  url_canonical: string;
  published_at?: string | null;
  source_list_url: string;
  first_seen_at: string;
  last_seen_at: string;
  run_id: number;
}

export interface ArticleListResponse {
  items: ArticleSummary[];
  page_meta: PageMeta;
}

export interface TaskSummary {
  id: number;
  task_type: string;
  status: string;
  params_json: Record<string, unknown>;
  result_json: Record<string, unknown>;
  error_log: string;
  site_id: number | null;
  version_id: number | null;
  run_id: number | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface TaskAcceptedResponse {
  task_id: number;
  task: TaskSummary;
}

export interface ExtractedItem {
  title: string;
  url: string;
  published_at?: string | null;
  source_list_url: string;
}

export interface RunSummary {
  id: number;
  site_id: number;
  site_name?: string | null;
  version_id: number;
  version_no?: number | null;
  run_type: string;
  status: string;
  started_at: string;
  finished_at?: string | null;
  stop_reason?: string | null;
  items_found?: number;
  items_new?: number;
  items_duplicate?: number;
}

export interface RunDetail {
  id: number;
  status: string;
  error_log: string;
  result: {
    items?: ExtractedItem[];
    stats?: Record<string, unknown>;
    debug?: Record<string, unknown>;
  };
  spec_summary?: Record<string, unknown>;
}

export interface VersionSummary {
  id: number;
  site_id: number;
  version_no: number;
  status: string;
  feedback_text?: string | null;
  created_at?: string;
  spec_summary?: Record<string, unknown>;
  latest_run_id?: number | null;
  latest_run_status?: string | null;
  latest_run_finished_at?: string | null;
}

export interface SiteDetail {
  id: number;
  name: string;
  domain: string;
  seed_url: string;
  status: 'draft' | 'active' | string;
  approved_version_id: number | null;
  notes: string | null;
  created_at: string;
  article_count: number;
  approved_version: VersionSummary | null;
  latest_run: RunSummary | null;
  recent_versions: VersionSummary[];
  recent_runs: RunSummary[];
}

export interface VersionApprovalResponse {
  version: VersionSummary;
  site: Record<string, unknown>;
}

export interface CreateSiteRequest {
  seed_url: string;
  list_locator_hint?: string | null;
}

export interface RegenerateVersionRequest {
  list_locator_hint: string;
}

export interface SiteUpdateRequest {
  name?: string | null;
  notes?: string | null;
  status?: 'draft' | 'active' | null;
}

export interface ListArticlesParams {
  siteId?: number;
  runId?: number;
  title?: string;
  keyword?: string;
  sourceListUrl?: string;
  publishedFrom?: string;
  publishedTo?: string;
  page?: number;
  pageSize?: number;
}
