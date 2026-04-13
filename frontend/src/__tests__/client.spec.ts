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
});
