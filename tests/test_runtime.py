from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_news_spider.crawler import CrawlSample
from ai_news_spider.llm import HeuristicSiteSpecGenerator
from ai_news_spider.models import SiteSpec
from ai_news_spider.runtime import run_site_spec

from tests.helpers import FIXTURE_URL_1, FIXTURE_URL_2


def build_spec() -> SiteSpec:
    return SiteSpec.model_validate(
        {
            "seed_url": FIXTURE_URL_1,
            "site_name": "示例站点",
            "allowed_domains": ["example.com"],
            "requires_js": False,
            "wait_for": None,
            "list_item_selector": ".main_conRCb ul > li",
            "title_selector": "a",
            "link_selector": "a",
            "date_selector": "span",
            "date_format": "%Y-%m-%d",
            "timezone": "Asia/Shanghai",
            "pagination_mode": "next_link",
            "next_page_selector": "#fanye270287 a.Next",
            "max_pages_default": 3,
            "url_join_mode": "auto",
        }
    )


@pytest.mark.asyncio
async def test_runtime_follows_dom_next_link(fixture_map) -> None:
    result = await run_site_spec(
        build_spec(),
        {
            "seed_url": FIXTURE_URL_1,
            "site_id": 1,
            "max_days": 3650,
            "max_pages": 2,
            "run_type": "preview",
            "last_seen_checkpoint": [],
        },
    )
    assert result["stats"]["pages_crawled"] == 2
    assert result["items"][0]["title"] == "第一条新闻"
    assert result["debug"]["next_page_trace"][0]["next_page_url"] == FIXTURE_URL_2


@pytest.mark.asyncio
async def test_runtime_stops_on_duplicate_page_for_prod(fixture_map) -> None:
    result = await run_site_spec(
        build_spec(),
        {
            "seed_url": FIXTURE_URL_1,
            "site_id": 1,
            "max_days": 10,
            "max_pages": 3,
            "run_type": "prod",
            "last_seen_checkpoint": [
                "https://example.com/info/1001.htm",
                "https://example.com/info/1002.htm",
            ],
        },
    )
    assert result["stats"]["stop_reason"] == "duplicate_hit"


@pytest.mark.asyncio
async def test_runtime_extracts_title_and_date_when_date_is_inside_anchor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    html = Path("tests/fixtures/chemeng_notice.html").read_text()
    map_path = tmp_path / "chemeng_fixture_map.json"
    map_path.write_text(
        json.dumps({"https://www.chemeng.tsinghua.edu.cn/xwxx/gg.htm": html})
    )
    monkeypatch.setenv("AI_NEWS_SPIDER_FIXTURE_MAP", str(map_path))

    sample = CrawlSample(
        seed_url="https://www.chemeng.tsinghua.edu.cn/xwxx/gg.htm",
        final_url="https://www.chemeng.tsinghua.edu.cn/xwxx/gg.htm",
        title="公告-清华大学化学工程系",
        html=html,
        markdown=html,
        links={"internal": []},
        list_html_excerpt=html,
        markdown_excerpt=html,
    )
    spec = await HeuristicSiteSpecGenerator().generate(sample)
    result = await run_site_spec(
        spec,
        {
            "seed_url": "https://www.chemeng.tsinghua.edu.cn/xwxx/gg.htm",
            "site_id": 1,
            "max_days": 3650,
            "max_pages": 1,
            "run_type": "preview",
            "last_seen_checkpoint": [],
        },
    )
    assert result["stats"]["items_found"] == 3
    assert result["items"][0]["title"].endswith("综合考核名单公示")
    assert result["items"][0]["published_at"] == "2025-08-11T00:00:00+08:00"


@pytest.mark.asyncio
async def test_runtime_extracts_anchor_wrapped_items_for_bnu(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    html = Path("tests/fixtures/bnu_env_notice.html").read_text()
    map_path = tmp_path / "bnu_fixture_map.json"
    map_path.write_text(
        json.dumps({"https://env.bnu.edu.cn/tzgg4/index.htm": html})
    )
    monkeypatch.setenv("AI_NEWS_SPIDER_FIXTURE_MAP", str(map_path))

    sample = CrawlSample(
        seed_url="https://env.bnu.edu.cn/tzgg4/index.htm",
        final_url="https://env.bnu.edu.cn/tzgg4/index.htm",
        title="北京师范大学环境学院",
        html=html,
        markdown=html,
        links={"internal": []},
        list_html_excerpt=html,
        markdown_excerpt=html,
    )
    spec = await HeuristicSiteSpecGenerator().generate(sample)
    result = await run_site_spec(
        spec,
        {
            "seed_url": "https://env.bnu.edu.cn/tzgg4/index.htm",
            "site_id": 1,
            "max_days": 3650,
            "max_pages": 1,
            "run_type": "preview",
            "last_seen_checkpoint": [],
        },
    )
    assert result["stats"]["items_found"] >= 10
    assert result["items"][0]["title"] == "招聘-诚邀海内外优秀学者加入北京师范大学环境学院"
    assert result["items"][0]["published_at"] == "2025-07-31T00:00:00+08:00"
    assert result["debug"]["next_page_trace"][0]["next_page_url"] == "https://env.bnu.edu.cn/tzgg4/index1.htm"
