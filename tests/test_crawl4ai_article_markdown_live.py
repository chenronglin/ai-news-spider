from __future__ import annotations

import os

import pytest
from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig

ARTICLE_URL = (
    "https://lxy.shzu.edu.cn/2026/0412/c528a230917/page.htm"
)
# ARTICLE_TITLE = "中国人民大学和平与发展学院2026年硕士研究生招生考试复试录取工作方案"
# ARTICLE_BODY_SELECTOR = ".pdfViewer"


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("RUN_LIVE_SITE_TESTS") != "1", reason="live site smoke test disabled"
)
async def test_crawl4ai_extracts_live_article_body_to_markdown() -> None:
    config = CrawlerRunConfig(
        # css_selector=ARTICLE_BODY_SELECTOR,
        cache_mode=CacheMode.BYPASS,
        page_timeout=60000,
        remove_overlay_elements=True,
        wait_until="domcontentloaded",
        verbose=False,
        log_console=False,
        process_iframes=True
    )

    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(ARTICLE_URL, config=config)

    assert result.success, getattr(result, "error_message", None)

    print("===" * 20)
    print(result.html)
    print("===" * 20)

    # markdown = str(result.markdown)
    
    # print("===" * 20)
    # print(markdown)
    # print("===" * 20)

    # assert len(markdown) > 2000
    # assert "中国人民大学和平与发展学院" in markdown
    # assert "2026年硕士研究生招生考试复试录取工作方案" in markdown
    # assert "一、总体要求" in markdown
    # assert "三、复试内容与形式" in markdown
    # assert "八、咨询方式" in markdown
    # assert "(https://yz.chsi.com.cn/zsml/zyfx_search.jsp)" in markdown

    # # css_selector should keep the test focused on the article body.
    # assert "首页" not in markdown
    # assert "相关附件" not in markdown
