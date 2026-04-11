from __future__ import annotations

import os

import pytest

from ai_news_spider.crawler import CrawlClient


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("RUN_LIVE_SITE_TESTS") != "1", reason="live site smoke test disabled"
)
async def test_live_yjsy_site_smoke() -> None:
    sample = await CrawlClient().fetch_sample("https://yjsy.ncut.edu.cn/index/zxdt.htm")
    assert "最新动态" in sample.title
    assert "line_u10_0" in sample.html
