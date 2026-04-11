from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup, Tag
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

from ai_news_spider.crawler import fixture_html_for_url
from ai_news_spider.crawler import fetch_static_html
from ai_news_spider.models import (
    ExtractedItem,
    RunInput,
    RunnerDebug,
    RunnerResult,
    SiteSpec,
)
from ai_news_spider.models import parse_known_date, select_first

logger = logging.getLogger(__name__)
DATE_RE = re.compile(r"\d{4}(?:[-/.]\d{2}[-/.]\d{2}|年\d{2}月\d{2}日)")


def canonicalize_url(url: str) -> str:
    parsed = urlparse(url)
    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        fragment="",
    )
    return urlunparse(normalized)


def resolve_url(base_url: str, raw_url: str, mode: str) -> str:
    if mode == "absolute":
        return raw_url
    return urljoin(base_url, raw_url)


def parse_published_at(
    raw_value: str, timezone_name: str, date_format: str
) -> str | None:
    parsed = parse_known_date(raw_value, date_format)
    if not parsed:
        return None
    return parsed.replace(tzinfo=ZoneInfo(timezone_name)).isoformat()


async def fetch_page_html(
    crawler: AsyncWebCrawler | None,
    url: str,
    *,
    requires_js: bool,
    wait_for: str | None,
) -> str:
    fixture = fixture_html_for_url(url)
    if fixture is not None:
        logger.info("Runtime using fixture page url=%s", url)
        return fixture

    if not requires_js:
        try:
            logger.info("Runtime fetching static HTML directly url=%s", url)
            html, _ = fetch_static_html(url)
            return html
        except Exception as exc:  # noqa: BLE001
            logger.warning("Runtime static HTML fetch failed url=%s error=%s", url, exc)

    run_config = CrawlerRunConfig(
        page_timeout=60000 if requires_js else 30000,
        wait_for=wait_for,
        remove_overlay_elements=True,
    )
    if crawler is None:
        async with AsyncWebCrawler(config=BrowserConfig(headless=True)) as new_crawler:
            result = await new_crawler.arun(url=url, config=run_config)
    else:
        result = await crawler.arun(url=url, config=run_config)
    if not result.success:
        logger.error("Runtime crawl failed for page url=%s", url)
        raise RuntimeError(f"crawl failed for {url}")
    return result.html or ""


def extract_items_from_html(
    html: str,
    page_url: str,
    spec: SiteSpec,
    debug: RunnerDebug,
) -> list[ExtractedItem]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[ExtractedItem] = []
    nodes = soup.select(spec.list_item_selector)
    debug.selected_item_count_per_page.append(
        {"page_url": page_url, "selected_count": len(nodes)}
    )
    for node in nodes:
        title_el = select_first(node, spec.title_selector)
        link_el = select_first(node, spec.link_selector)
        date_el = select_first(node, spec.date_selector) if spec.date_selector else None
        if title_el is None or link_el is None:
            continue
        href = (link_el.get("href") or "").strip()
        if not href:
            continue
        raw_date = extract_date_text(date_el, node)
        title = extract_title_text(title_el, raw_date)
        published_at = parse_published_at(raw_date, spec.timezone, spec.date_format)
        if raw_date and not published_at:
            debug.date_parse_errors.append(
                {"page_url": page_url, "raw_value": raw_date, "title": title}
            )
        items.append(
            ExtractedItem(
                title=title,
                url=resolve_url(page_url, href, spec.url_join_mode),
                published_at=published_at,
                source_list_url=page_url,
            )
        )
    return items


def extract_date_text(date_el: Tag | None, item_node: Tag) -> str:
    if date_el is not None:
        candidate = date_el.get_text(" ", strip=True)
        match = DATE_RE.search(candidate)
        if match:
            return match.group(0)
    item_text = item_node.get_text(" ", strip=True)
    match = DATE_RE.search(item_text)
    return match.group(0) if match else ""


def extract_title_text(title_el: Tag, raw_date: str) -> str:
    if raw_date:
        for descendant in title_el.find_all(True):
            descendant_text = descendant.get_text(" ", strip=True)
            if descendant_text == raw_date:
                descendant.extract()
    title = title_el.get_text(" ", strip=True)
    if raw_date and raw_date in title:
        title = title.replace(raw_date, "").strip()
    return " ".join(title.split())


def extract_next_page_url(html: str, page_url: str, spec: SiteSpec) -> str | None:
    if spec.pagination_mode == "none" or not spec.next_page_selector:
        return None
    soup = BeautifulSoup(html, "html.parser")
    next_node = soup.select_one(spec.next_page_selector)
    if next_node is None:
        return None
    href = (next_node.get("href") or "").strip()
    if not href:
        return None
    return resolve_url(page_url, href, spec.url_join_mode)


def is_older_than_window(published_at: str | None, max_days: int) -> bool:
    if not published_at:
        return False
    published = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    cutoff = datetime.now(UTC) - timedelta(days=max_days)
    return published < cutoff


async def run_site_spec(spec: SiteSpec, payload: dict) -> dict:
    run_input = RunInput.model_validate(payload)
    logger.info(
        "Runtime starting site spec run seed_url=%s run_type=%s max_pages=%s max_days=%s",
        run_input.seed_url,
        run_input.run_type,
        run_input.max_pages,
        run_input.max_days,
    )
    debug = RunnerDebug(spec_summary=spec.summary())
    result = RunnerResult(debug=debug)
    seen = {canonicalize_url(url) for url in run_input.last_seen_checkpoint}
    visited_pages: set[str] = set()
    current_url = run_input.seed_url

    if fixture_html_for_url(current_url) is None:
        async with AsyncWebCrawler(config=BrowserConfig(headless=True)) as crawler:
            return await _run_with_crawler(
                spec,
                run_input,
                result,
                debug,
                seen,
                visited_pages,
                current_url,
                crawler,
            )
    return await _run_with_crawler(
        spec, run_input, result, debug, seen, visited_pages, current_url
    )


async def _run_with_crawler(
    spec: SiteSpec,
    run_input: RunInput,
    result: RunnerResult,
    debug: RunnerDebug,
    seen: set[str],
    visited_pages: set[str],
    current_url: str,
    crawler: AsyncWebCrawler | None = None,
) -> dict:
    stop_reason = "unknown"
    while result.stats.pages_crawled < run_input.max_pages:
        if current_url in visited_pages:
            stop_reason = "page_loop"
            break
        visited_pages.add(current_url)
        logger.info(
            "Runtime crawling page=%s page_index=%s",
            current_url,
            result.stats.pages_crawled + 1,
        )

        html = await fetch_page_html(
            crawler,
            current_url,
            requires_js=spec.requires_js,
            wait_for=spec.wait_for,
        )
        items = extract_items_from_html(html, current_url, spec, debug)
        logger.info("Runtime extracted page=%s item_count=%s", current_url, len(items))
        result.items.extend(items)
        result.stats.pages_crawled += 1
        result.stats.items_found += len(items)

        duplicate_count = 0
        older_count = 0
        dated_count = 0
        for item in items:
            canonical = canonicalize_url(item.url)
            if canonical in seen:
                duplicate_count += 1
            else:
                result.stats.items_new += 1
                seen.add(canonical)
            if item.published_at:
                dated_count += 1
                if is_older_than_window(item.published_at, run_input.max_days):
                    older_count += 1

        result.stats.items_duplicate += duplicate_count

        if not items:
            stop_reason = "no_items"
            break
        if run_input.run_type == "prod" and duplicate_count == len(items):
            stop_reason = "duplicate_hit"
            break
        if (
            run_input.run_type == "prod"
            and dated_count > 0
            and older_count == dated_count
        ):
            stop_reason = "age_window"
            break

        next_page_url = extract_next_page_url(html, current_url, spec)
        debug.next_page_trace.append(
            {"page_url": current_url, "next_page_url": next_page_url}
        )
        if not next_page_url:
            stop_reason = "no_next_page"
            break
        logger.info(
            "Runtime following next_page current=%s next=%s",
            current_url,
            next_page_url,
        )
        current_url = next_page_url
    else:
        stop_reason = "max_pages_reached"

    result.stats.stop_reason = stop_reason
    logger.info(
        "Runtime completed run_type=%s pages=%s items_found=%s stop_reason=%s",
        run_input.run_type,
        result.stats.pages_crawled,
        result.stats.items_found,
        stop_reason,
    )
    return result.model_dump(mode="json")
