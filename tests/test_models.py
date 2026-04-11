from __future__ import annotations

from pathlib import Path

import pytest

from ai_news_spider.llm import (
    HeuristicSiteSpecGenerator,
    detect_locator_kind,
    resolve_locator_root,
)
from ai_news_spider.crawler import CrawlSample
from ai_news_spider.models import SiteSpec


def test_site_spec_validate_on_html_accepts_yjsy_fixture() -> None:
    html = Path("tests/fixtures/yjsy_list.html").read_text()
    spec = SiteSpec.model_validate(
        {
            "seed_url": "https://yjsy.ncut.edu.cn/index/zxdt.htm",
            "site_name": "北方工业大学研究生院",
            "allowed_domains": ["yjsy.ncut.edu.cn", "www.ncut.edu.cn"],
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
    assert spec.validate_on_html(html) == []


@pytest.mark.asyncio
async def test_heuristic_generator_matches_expected_shape_for_yjsy() -> None:
    html = Path("tests/fixtures/yjsy_list.html").read_text()
    sample = CrawlSample(
        seed_url="https://yjsy.ncut.edu.cn/index/zxdt.htm",
        final_url="https://yjsy.ncut.edu.cn/index/zxdt.htm",
        title="最新动态-北方工业大学 研究生院 | 学科建设办公室",
        html=html,
        markdown=html,
        links={"internal": []},
        list_html_excerpt=html,
        markdown_excerpt=html,
    )
    spec = await HeuristicSiteSpecGenerator().generate(sample)
    assert ".main_conRCb" in spec.list_item_selector
    assert spec.link_selector == "a"
    assert spec.date_selector == "span"
    assert spec.pagination_mode == "next_link"
    assert spec.validate_on_html(html) == []


@pytest.mark.asyncio
async def test_heuristic_generator_respects_xpath_locator_hint() -> None:
    html = Path("tests/fixtures/yjsy_list.html").read_text()
    sample = CrawlSample(
        seed_url="https://yjsy.ncut.edu.cn/index/zxdt.htm",
        final_url="https://yjsy.ncut.edu.cn/index/zxdt.htm",
        title="最新动态-北方工业大学 研究生院 | 学科建设办公室",
        html=html,
        markdown=html,
        links={"internal": []},
        list_html_excerpt=html,
        markdown_excerpt=html,
    )
    spec = await HeuristicSiteSpecGenerator().generate(
        sample,
        list_locator_hint="/html[1]/body[1]/div[1]",
    )
    assert ".main_conRCb" in spec.list_item_selector
    assert spec.validate_on_html(html) == []


def test_detect_locator_kind_supports_css_and_xpath() -> None:
    assert detect_locator_kind(".class-list") == "css"
    assert detect_locator_kind("//div[@class='class-list']") == "xpath_relative"
    assert detect_locator_kind("/html[1]/body[1]/div[1]") == "xpath_absolute"


def test_resolve_locator_root_supports_css_and_relative_xpath() -> None:
    html = Path("tests/fixtures/yjsy_list.html").read_text()
    css_root = resolve_locator_root(html, ".main_conRCb")
    xpath_root = resolve_locator_root(html, "//div[@class='main_conRCb']")
    assert css_root is not None
    assert xpath_root is not None
    assert css_root.name == "div"
    assert xpath_root.name == "div"
    assert "main_conRCb" in (css_root.get("class") or [])
    assert "main_conRCb" in (xpath_root.get("class") or [])


@pytest.mark.asyncio
async def test_heuristic_generator_matches_expected_shape_for_chemeng() -> None:
    html = Path("tests/fixtures/chemeng_notice.html").read_text()
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
    assert ".new-list" in spec.list_item_selector
    assert spec.link_selector == "a"
    assert spec.date_selector.endswith("em")
    assert spec.pagination_mode == "none"
    assert spec.validate_on_html(html) == []


@pytest.mark.asyncio
async def test_heuristic_generator_matches_expected_shape_for_bnu_env() -> None:
    html = Path("tests/fixtures/bnu_env_notice.html").read_text()
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
    assert spec.list_item_selector == "ul.listconrn > a"
    assert spec.title_selector == "div.listconrn-rb"
    assert spec.link_selector == ":self"
    assert spec.date_selector == "span.time"
    assert spec.next_page_selector == "div.page-navigation > a:nth-of-type(2)"
    assert spec.validate_on_html(html) == []
