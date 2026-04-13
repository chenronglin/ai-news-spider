import { ApiError, createApiClient } from '@/api/client';

describe('api client', () => {
  it('injects token header when requesting proxy html', async () => {
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({
          url: 'https://example.com',
          final_url: 'https://example.com',
          html: '<html></html>',
          rendered_by: 'crawl4ai',
        }),
        { status: 200 },
      ),
    );

    const client = createApiClient('http://127.0.0.1:8000', fetchMock as typeof fetch);
    await client.proxyHtml('https://example.com', 'token-1');

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toContain('/api/v1/tools/proxy/html?url=');
    expect((init.headers as Record<string, string>)['X-API-Token']).toBe('token-1');
  });

  it('throws ApiError using detail field from json payload', async () => {
    const fetchMock = vi.fn(async () =>
      new Response(JSON.stringify({ detail: 'invalid api token' }), { status: 401 }),
    );

    const client = createApiClient('http://127.0.0.1:8000', fetchMock as typeof fetch);

    await expect(client.getTask(1, 'bad-token')).rejects.toEqual(
      expect.objectContaining({
        name: 'ApiError',
        message: 'invalid api token',
        status: 401,
      }),
    );
  });

  it('sends pagination and filters when requesting site list', async () => {
    const fetchMock = vi.fn(async () =>
      new Response(JSON.stringify({ items: [], page_meta: { page: 2, page_size: 10, total: 0 } }), {
        status: 200,
      }),
    );

    const client = createApiClient('http://127.0.0.1:8000', fetchMock as typeof fetch);
    await client.listSites({ status: 'active', keyword: 'example', page: 2, pageSize: 10 }, 'token-2');

    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toContain('/api/v1/sites?');
    expect(url).toContain('status=active');
    expect(url).toContain('keyword=example');
    expect(url).toContain('page=2');
    expect(url).toContain('page_size=10');
    expect((init.headers as Record<string, string>)['X-API-Token']).toBe('token-2');
  });

  it('sends article filters using backend query parameter names', async () => {
    const fetchMock = vi.fn(async () =>
      new Response(JSON.stringify({ items: [], page_meta: { page: 1, page_size: 20, total: 0 } }), {
        status: 200,
      }),
    );

    const client = createApiClient('http://127.0.0.1:8000', fetchMock as typeof fetch);
    await client.listArticles(
      {
        siteId: 7,
        runId: 9,
        title: '第一条',
        keyword: '新闻',
        sourceListUrl: 'https://example.com/news',
        publishedFrom: '2026-04-08T00:00:00+08:00',
        publishedTo: '2026-04-10T23:59:59+08:00',
        page: 3,
        pageSize: 50,
      },
      'token-4',
    );

    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toContain('/api/v1/articles?');
    expect(url).toContain('site_id=7');
    expect(url).toContain('run_id=9');
    expect(url).toContain('title=%E7%AC%AC%E4%B8%80%E6%9D%A1');
    expect(url).toContain('keyword=%E6%96%B0%E9%97%BB');
    expect(url).toContain('source_list_url=');
    expect(url).toContain('published_from=');
    expect(url).toContain('published_to=');
    expect(url).toContain('page=3');
    expect(url).toContain('page_size=50');
    expect((init.headers as Record<string, string>)['X-API-Token']).toBe('token-4');
  });

  it('uses PATCH for site updates and DELETE for site removal', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: 1,
            name: '示例站点',
            domain: 'example.com',
            seed_url: 'https://example.com/news',
            status: 'draft',
            approved_version_id: null,
            approved_version_no: null,
            notes: 'note',
            created_at: '2026-04-13T00:00:00Z',
            last_run_at: null,
            last_run_status: null,
            recent_error: null,
            article_count: 0,
            today_new_count: 0,
          }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }));

    const client = createApiClient('http://127.0.0.1:8000', fetchMock as typeof fetch);

    await client.updateSite(1, { name: '示例站点', status: 'draft' }, 'token-3');
    await client.deleteSite(1, 'token-3');

    const [, patchInit] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    const [, deleteInit] = fetchMock.mock.calls[1] as unknown as [string, RequestInit];
    expect(patchInit.method).toBe('PATCH');
    expect(deleteInit.method).toBe('DELETE');
  });
});
