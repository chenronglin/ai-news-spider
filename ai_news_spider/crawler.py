from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CrawlSample:
    seed_url: str
    final_url: str
    title: str
    html: str
    markdown: str
    links: dict[str, list[Any]]
    list_html_excerpt: str
    markdown_excerpt: str


def _load_fixture_map() -> dict[str, str]:
    raw = os.getenv("AI_NEWS_SPIDER_FIXTURE_MAP")
    if not raw:
        return {}
    candidate = Path(raw)
    if candidate.exists():
        return json.loads(candidate.read_text())
    return json.loads(raw)


def fixture_html_for_url(url: str) -> str | None:
    return _load_fixture_map().get(url)


def extract_likely_list_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    date_pattern = re.compile(r"\d{4}(?:[-/.]\d{2}[-/.]\d{2}|年\d{2}月\d{2}日)")
    best_fragment = ""
    best_score = -1
    for node in soup.find_all(["div", "section", "ul", "ol", "table", "tbody"]):
        links = node.select("li a, tr a")
        if len(links) < 3:
            continue
        li_count = len(node.select("li"))
        tr_count = len(node.select("tr"))
        text = node.get_text(" ", strip=True)
        date_hits = len(date_pattern.findall(text))
        score = (li_count + tr_count) * 5 + date_hits * 10
        if score > best_score:
            best_score = score
            best_fragment = str(node)[:5000]
    return best_fragment or html[:5000]


def extract_links_from_html(base_url: str, html: str) -> dict[str, list[dict[str, str]]]:
    soup = BeautifulSoup(html, "html.parser")
    internal: list[dict[str, str]] = []
    external: list[dict[str, str]] = []
    from urllib.parse import urljoin, urlparse

    base_netloc = urlparse(base_url).netloc
    for anchor in soup.select("a[href]"):
        href = (anchor.get("href") or "").strip()
        if not href:
            continue
        absolute = urljoin(base_url, href)
        item = {"href": absolute, "text": anchor.get_text(" ", strip=True)}
        if urlparse(absolute).netloc == base_netloc:
            internal.append(item)
        else:
            external.append(item)
    return {"internal": internal, "external": external}


def fetch_static_html(url: str) -> tuple[str, str]:
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            )
        },
    )
    with urlopen(request, timeout=30) as response:
        raw = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
        html = raw.decode(charset, errors="replace")
        return html, response.geturl()


class CrawlClient:
    def __init__(self) -> None:
        self.browser_config = BrowserConfig(headless=True)

    async def fetch_html(
        self,
        url: str,
        *,
        requires_js: bool = False,
        wait_for: str | None = None,
    ) -> tuple[str, str, dict[str, list[Any]], str]:
        fixture = fixture_html_for_url(url)
        if fixture is not None:
            logger.info("Using fixture HTML for url=%s", url)
            return fixture, fixture, extract_links_from_html(url, fixture), url

        if not requires_js:
            try:
                logger.info("Fetching static HTML directly url=%s", url)
                html, final_url = fetch_static_html(url)
                links = extract_links_from_html(final_url, html)
                logger.info(
                    "Fetched static page url=%s final_url=%s html_len=%s",
                    url,
                    final_url,
                    len(html),
                )
                return html, html, links, final_url
            except Exception as exc:  # noqa: BLE001
                logger.warning("Static HTML fetch failed url=%s error=%s", url, exc)

        logger.info(
            "Fetching sample page with Crawl4AI url=%s requires_js=%s wait_for=%s",
            url,
            requires_js,
            wait_for,
        )
        run_config = CrawlerRunConfig(
            page_timeout=60000 if requires_js else 30000,
            wait_for=wait_for,
            remove_overlay_elements=True,
        )
        async with AsyncWebCrawler(config=self.browser_config) as crawler:
            result = await crawler.arun(url=url, config=run_config)
        if not result.success:
            logger.error("Crawl failed for url=%s", url)
            raise RuntimeError(f"crawl failed for {url}")
        logger.info(
            "Fetched page url=%s final_url=%s html_len=%s markdown_len=%s",
            url,
            result.url or url,
            len(result.html or ""),
            len(str(result.markdown or "")),
        )
        return (
            result.html or "",
            str(result.markdown or ""),
            result.links or {},
            result.url or url,
        )

    async def fetch_sample(
        self,
        url: str,
        *,
        requires_js: bool = False,
        wait_for: str | None = None,
    ) -> CrawlSample:
        html, markdown, links, final_url = await self.fetch_html(
            url,
            requires_js=requires_js,
            wait_for=wait_for,
        )
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.get_text(strip=True) if soup.title else final_url
        return CrawlSample(
            seed_url=url,
            final_url=final_url,
            title=title,
            html=html,
            markdown=markdown,
            links=links,
            list_html_excerpt=extract_likely_list_html(html),
            markdown_excerpt=markdown[:5000],
        )
