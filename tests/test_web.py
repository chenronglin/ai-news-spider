from __future__ import annotations

from fastapi.testclient import TestClient

from ai_news_spider.app import build_app
from ai_news_spider.llm import HeuristicSiteSpecGenerator

from tests.helpers import FIXTURE_URL_1


def test_web_flow_generate_approve_and_run(settings, fixture_map) -> None:
    app = build_app(
        settings=settings,
        spec_generator=HeuristicSiteSpecGenerator(),
        with_scheduler=False,
    )
    with TestClient(app) as client:
        create_response = client.post(
            "/sites",
            data={
                "seed_url": FIXTURE_URL_1,
                "list_locator_hint": "/html[1]/body[1]/div[1]",
            },
            follow_redirects=False,
        )
        assert create_response.status_code == 303
        run_url = create_response.headers["location"]

        detail_response = client.get(run_url)
        assert detail_response.status_code == 200
        assert "第一条新闻" in detail_response.text

        approve_response = client.post("/versions/1/approve", follow_redirects=False)
        assert approve_response.status_code == 303

        sites_response = client.get("/sites")
        assert sites_response.status_code == 200
        assert "示例站点" in sites_response.text

        prod_response = client.post("/sites/1/run", follow_redirects=False)
        assert prod_response.status_code == 303


def test_url_selector_page_and_proxy(settings, fixture_map) -> None:
    app = build_app(
        settings=settings,
        spec_generator=HeuristicSiteSpecGenerator(),
        with_scheduler=False,
    )
    with TestClient(app) as client:
        tool_response = client.get("/tools/url-selector")
        assert tool_response.status_code == 200
        assert "服务端代理抓取 HTML" in tool_response.text

        proxy_response = client.get("/api/proxy/html", params={"url": FIXTURE_URL_1})
        assert proxy_response.status_code == 200
        payload = proxy_response.json()
        assert payload["url"] == FIXTURE_URL_1
        assert "第一条新闻" in payload["html"]
