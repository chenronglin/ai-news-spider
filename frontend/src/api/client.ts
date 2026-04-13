import type {
  CreateSiteRequest,
  ProxyHtmlResponse,
  RegenerateVersionRequest,
  RunDetail,
  TaskAcceptedResponse,
  TaskSummary,
  VersionApprovalResponse,
} from './types';

export class ApiError extends Error {
  status: number;
  payload: unknown;

  constructor(message: string, status: number, payload: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.payload = payload;
  }
}

export interface ApiClient {
  proxyHtml(url: string, token: string): Promise<ProxyHtmlResponse>;
  createSite(body: CreateSiteRequest, token: string): Promise<TaskAcceptedResponse>;
  getTask(taskId: number, token: string): Promise<TaskSummary>;
  getRun(runId: number, token: string): Promise<RunDetail>;
  regenerateVersion(
    versionId: number,
    body: RegenerateVersionRequest,
    token: string,
  ): Promise<TaskAcceptedResponse>;
  approveVersion(versionId: number, token: string): Promise<VersionApprovalResponse>;
}

type HttpMethod = 'GET' | 'POST';

interface RequestOptions {
  method?: HttpMethod;
  token: string;
  query?: Record<string, string>;
  body?: unknown;
}

const DEFAULT_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

async function parsePayload(response: Response): Promise<unknown> {
  const rawText = await response.text();
  if (!rawText) {
    return null;
  }

  try {
    return JSON.parse(rawText);
  } catch {
    return rawText;
  }
}

function toErrorMessage(payload: unknown, fallback: string): string {
  if (payload && typeof payload === 'object' && 'detail' in payload) {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === 'string' && detail.trim()) {
      return detail;
    }
  }

  if (typeof payload === 'string' && payload.trim()) {
    return payload;
  }

  return fallback;
}

export function normalizeBaseUrl(baseUrl: string): string {
  return baseUrl.replace(/\/+$/, '');
}

export function createApiClient(
  baseUrl = DEFAULT_BASE_URL,
  fetchImpl: typeof fetch = fetch,
): ApiClient {
  const normalizedBaseUrl = normalizeBaseUrl(baseUrl);

  async function request<T>(path: string, options: RequestOptions): Promise<T> {
    const url = new URL(`${normalizedBaseUrl}${path}`);
    Object.entries(options.query ?? {}).forEach(([key, value]) => {
      url.searchParams.set(key, value);
    });

    const headers: Record<string, string> = {
      accept: 'application/json',
      'X-API-Token': options.token,
    };

    if (options.body !== undefined) {
      headers['Content-Type'] = 'application/json';
    }

    const response = await fetchImpl(url.toString(), {
      method: options.method ?? 'GET',
      headers,
      body: options.body ? JSON.stringify(options.body) : undefined,
    });

    const payload = await parsePayload(response);
    if (!response.ok) {
      throw new ApiError(
        toErrorMessage(payload, `HTTP ${response.status}`),
        response.status,
        payload,
      );
    }

    return payload as T;
  }

  return {
    proxyHtml(url, token) {
      return request<ProxyHtmlResponse>('/api/v1/tools/proxy/html', {
        token,
        query: { url },
      });
    },
    createSite(body, token) {
      return request<TaskAcceptedResponse>('/api/v1/sites', {
        method: 'POST',
        token,
        body,
      });
    },
    getTask(taskId, token) {
      return request<TaskSummary>(`/api/v1/tasks/${taskId}`, {
        token,
      });
    },
    getRun(runId, token) {
      return request<RunDetail>(`/api/v1/runs/${runId}`, {
        token,
      });
    },
    regenerateVersion(versionId, body, token) {
      return request<TaskAcceptedResponse>(`/api/v1/versions/${versionId}/regenerate`, {
        method: 'POST',
        token,
        body,
      });
    },
    approveVersion(versionId, token) {
      return request<VersionApprovalResponse>(`/api/v1/versions/${versionId}/approve`, {
        method: 'POST',
        token,
      });
    },
  };
}
