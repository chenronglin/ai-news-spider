export interface ProxyHtmlResponse {
  url: string;
  final_url: string;
  html: string;
  rendered_by: string;
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
}

export interface VersionApprovalResponse {
  version: VersionSummary;
  site: Record<string, unknown>;
}

export interface CreateSiteRequest {
  seed_url: string;
  list_locator_hint: string;
}

export interface RegenerateVersionRequest {
  list_locator_hint: string;
}
