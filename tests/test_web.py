from __future__ import annotations

from fastapi.testclient import TestClient

from ai_news_spider.app import build_app
from ai_news_spider.llm import HeuristicSiteSpecGenerator

from tests.helpers import FIXTURE_URL_1, wait_for_task_completion


def test_api_flow_create_regenerate_approve_and_run(settings, fixture_map) -> None:
    app = build_app(
        settings=settings,
        spec_generator=HeuristicSiteSpecGenerator(),
        with_scheduler=True,
    )
    with TestClient(app) as client:
        create_response = client.post(
            "/api/v1/sites",
            json={
                "seed_url": FIXTURE_URL_1,
                "list_locator_hint": "/html[1]/body[1]/div[1]",
            },
        )
        assert create_response.status_code == 202
        create_task = wait_for_task_completion(
            client, create_response.json()["task_id"]
        )
        assert create_task["status"] == "succeeded"
        site_id = create_task["result_json"]["site_id"]
        version_id = create_task["result_json"]["version_id"]
        preview_run_id = create_task["result_json"]["run_id"]

        run_detail_response = client.get(f"/api/v1/runs/{preview_run_id}")
        assert run_detail_response.status_code == 200
        run_detail = run_detail_response.json()
        assert run_detail["result"]["items"][0]["title"] == "第一条新闻"
        assert run_detail["spec_summary"]["list_item_selector"]

        regenerate_response = client.post(
            f"/api/v1/versions/{version_id}/regenerate",
            json={"list_locator_hint": ".main_conRCb"},
        )
        assert regenerate_response.status_code == 202
        regenerate_task = wait_for_task_completion(
            client,
            regenerate_response.json()["task_id"],
        )
        assert regenerate_task["status"] == "succeeded"
        regenerated_version_id = regenerate_task["result_json"]["version_id"]
        assert regenerated_version_id > version_id

        approve_response = client.post(
            f"/api/v1/versions/{regenerated_version_id}/approve"
        )
        assert approve_response.status_code == 200
        approval = approve_response.json()
        assert approval["site"]["approved_version_id"] == regenerated_version_id

        sites_response = client.get("/api/v1/sites")
        assert sites_response.status_code == 200
        assert sites_response.json()["items"][0]["name"] == "示例站点"

        site_detail_response = client.get(f"/api/v1/sites/{site_id}")
        assert site_detail_response.status_code == 200
        site_detail = site_detail_response.json()
        assert site_detail["approved_version"]["id"] == regenerated_version_id
        assert len(site_detail["recent_versions"]) >= 2

        run_prod_response = client.post(f"/api/v1/sites/{site_id}/runs")
        assert run_prod_response.status_code == 202
        prod_task = wait_for_task_completion(
            client, run_prod_response.json()["task_id"]
        )
        assert prod_task["status"] == "succeeded"
        prod_run_id = prod_task["result_json"]["run_id"]

        articles_response = client.get("/api/v1/articles", params={"site_id": site_id})
        assert articles_response.status_code == 200
        articles = articles_response.json()["items"]
        assert len(articles) == 5
        assert articles[0]["run_id"] == prod_run_id
        assert all(item["site_id"] == site_id for item in articles)

        global_articles_response = client.get(
            "/api/v1/articles",
            params={"site_id": site_id, "title": "第一条", "run_id": prod_run_id},
        )
        assert global_articles_response.status_code == 200
        filtered_articles = global_articles_response.json()["items"]
        assert len(filtered_articles) == 1
        assert filtered_articles[0]["title"] == "第一条新闻"
        assert filtered_articles[0]["site_name"] == "示例站点"

        published_articles_response = client.get(
            "/api/v1/articles",
            params={
                "site_id": site_id,
                "published_from": "2026-04-08T00:00:00+08:00",
                "published_to": "2026-04-10T23:59:59+08:00",
            },
        )
        assert published_articles_response.status_code == 200
        published_articles = published_articles_response.json()["items"]
        assert len(published_articles) == 3
        assert {item["title"] for item in published_articles} == {
            "第一条新闻",
            "第二条新闻",
            "第三条新闻",
        }

        site_runs_response = client.get(f"/api/v1/sites/{site_id}/runs")
        assert site_runs_response.status_code == 200
        assert any(
            item["run_type"] == "prod" for item in site_runs_response.json()["items"]
        )


def test_scheduler_run_now_and_proxy_html(settings, fixture_map) -> None:
    app = build_app(
        settings=settings,
        spec_generator=HeuristicSiteSpecGenerator(),
        with_scheduler=True,
    )
    with TestClient(app) as client:
        create_response = client.post(
            "/api/v1/sites",
            json={"seed_url": FIXTURE_URL_1, "list_locator_hint": ".main_conRCb"},
        )
        create_task = wait_for_task_completion(
            client, create_response.json()["task_id"]
        )
        version_id = create_task["result_json"]["version_id"]
        client.post(f"/api/v1/versions/{version_id}/approve")

        scheduler_response = client.get("/api/v1/scheduler")
        assert scheduler_response.status_code == 200
        assert scheduler_response.json()["job_id"] == "approved-sites-batch"

        run_now_response = client.post("/api/v1/scheduler/run-now")
        assert run_now_response.status_code == 202
        batch_task = wait_for_task_completion(
            client, run_now_response.json()["task_id"]
        )
        assert batch_task["status"] == "succeeded"
        assert batch_task["result_json"]["site_count"] == 1
        assert len(batch_task["result_json"]["run_ids"]) == 1

        proxy_response = client.get(
            "/api/v1/tools/proxy/html", params={"url": FIXTURE_URL_1}
        )
        assert proxy_response.status_code == 200
        payload = proxy_response.json()
        assert payload["url"] == FIXTURE_URL_1
        assert "第一条新闻" in payload["html"]
