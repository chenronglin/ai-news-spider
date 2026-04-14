from __future__ import annotations

import json
import sys
from types import SimpleNamespace

import pytest

from ai_news_spider.models import SiteSpec
from ai_news_spider.runner import CandidateRunner

from tests.helpers import FIXTURE_URL_1


@pytest.mark.asyncio
async def test_candidate_runner_returns_standard_json(settings, fixture_map) -> None:
    settings.ensure_directories()
    spec = SiteSpec.model_validate(
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
    runner = CandidateRunner(settings)
    execution = await runner.run(
        spec,
        {
            "seed_url": FIXTURE_URL_1,
            "site_id": 1,
            "max_days": 3650,
            "max_pages": 1,
            "run_type": "preview",
            "last_seen_checkpoint": [],
        },
    )
    assert execution.result["stats"]["pages_crawled"] == 1
    assert execution.result["items"][0]["title"] == "第一条新闻"
    assert "spec_summary" in execution.result["debug"]


@pytest.mark.asyncio
async def test_candidate_runner_uses_python_executable_instead_of_uv(
    settings, fixture_map, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings.ensure_directories()
    spec = SiteSpec.model_validate(
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
    runner = CandidateRunner(settings)
    captured: dict[str, object] = {}

    def fake_run(*args, **kwargs):
        captured["cmd"] = args[0]
        captured["cwd"] = kwargs.get("cwd")
        captured["input"] = kwargs.get("input")
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"stats": {}, "items": [], "debug": {}}),
            stderr="",
        )

    monkeypatch.setattr("ai_news_spider.runner.subprocess.run", fake_run)

    await runner.run(
        spec,
        {
            "seed_url": FIXTURE_URL_1,
            "site_id": 1,
            "max_days": 3650,
            "max_pages": 1,
            "run_type": "preview",
            "last_seen_checkpoint": [],
        },
    )

    command = captured["cmd"]
    assert isinstance(command, list)
    assert command[0] == sys.executable
    assert command[0] != "uv"
