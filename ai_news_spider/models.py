from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any, Literal
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


DateFormat = Literal["%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "auto"]
PaginationMode = Literal["next_link", "none"]
UrlJoinMode = Literal["auto", "absolute"]
RunType = Literal["preview", "prod"]


class SiteSpec(BaseModel):
    seed_url: str
    site_name: str
    allowed_domains: list[str] = Field(default_factory=list)
    requires_js: bool = False
    wait_for: str | None = None
    list_item_selector: str
    title_selector: str
    link_selector: str
    date_selector: str | None = None
    date_format: DateFormat = "auto"
    timezone: str = "Asia/Shanghai"
    pagination_mode: PaginationMode = "next_link"
    next_page_selector: str | None = None
    max_pages_default: int = 3
    url_join_mode: UrlJoinMode = "auto"
    detail_enabled: bool = True
    detail_requires_js: bool | None = None
    detail_wait_for: str | None = None

    @field_validator("seed_url")
    @classmethod
    def validate_seed_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("seed_url must be an absolute URL")
        return value

    @field_validator("allowed_domains")
    @classmethod
    def validate_allowed_domains(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item.strip()]
        if not cleaned:
            raise ValueError("allowed_domains cannot be empty")
        return cleaned

    @field_validator("wait_for", "next_page_selector", "date_selector", mode="before")
    @classmethod
    def normalize_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("max_pages_default")
    @classmethod
    def validate_max_pages_default(cls, value: int) -> int:
        if value < 1:
            raise ValueError("max_pages_default must be >= 1")
        return value

    def model_post_init(self, __context: Any) -> None:
        del __context
        if self.detail_requires_js is None:
            self.detail_requires_js = self.requires_js
        if self.detail_wait_for is None:
            self.detail_wait_for = self.wait_for

    def summary(self) -> dict[str, Any]:
        return {
            "site_name": self.site_name,
            "requires_js": self.requires_js,
            "list_item_selector": self.list_item_selector,
            "title_selector": self.title_selector,
            "link_selector": self.link_selector,
            "date_selector": self.date_selector,
            "pagination_mode": self.pagination_mode,
            "next_page_selector": self.next_page_selector,
            "max_pages_default": self.max_pages_default,
            "detail_enabled": self.detail_enabled,
            "detail_requires_js": self.detail_requires_js,
            "detail_wait_for": self.detail_wait_for,
        }

    def validate_on_html(self, html: str, page_url: str | None = None) -> list[str]:
        del page_url
        soup = BeautifulSoup(html, "html.parser")
        errors: list[str] = []
        try:
            items = soup.select(self.list_item_selector)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Invalid CSS selector for list_item_selector=%s",
                self.list_item_selector,
            )
            return [
                f"list_item_selector '{self.list_item_selector}' is not a valid CSS selector: {exc}"
            ]
        if not items:
            return [
                f"list_item_selector '{self.list_item_selector}' matched 0 elements"
            ]

        first = items[0]
        try:
            title_el = select_first(first, self.title_selector)
        except Exception as exc:  # noqa: BLE001
            title_el = None
            errors.append(
                f"title_selector '{self.title_selector}' is not valid CSS: {exc}"
            )
        try:
            link_el = select_first(first, self.link_selector)
        except Exception as exc:  # noqa: BLE001
            link_el = None
            errors.append(
                f"link_selector '{self.link_selector}' is not valid CSS: {exc}"
            )
        date_el = None
        if self.date_selector:
            try:
                date_el = select_first(first, self.date_selector)
            except Exception as exc:  # noqa: BLE001
                errors.append(
                    f"date_selector '{self.date_selector}' is not valid CSS: {exc}"
                )

        if title_el is None or not title_el.get_text(strip=True):
            errors.append(
                f"title_selector '{self.title_selector}' did not produce text"
            )
        if link_el is None or not link_el.get("href"):
            errors.append(f"link_selector '{self.link_selector}' did not produce href")
        if self.date_selector and date_el is None:
            errors.append(
                f"date_selector '{self.date_selector}' did not produce a node"
            )

        if self.pagination_mode == "next_link":
            if not self.next_page_selector:
                errors.append(
                    "next_page_selector is required when pagination_mode=next_link"
                )
            else:
                try:
                    next_link = select_first(soup, self.next_page_selector)
                except Exception as exc:  # noqa: BLE001
                    next_link = None
                    errors.append(
                        f"next_page_selector '{self.next_page_selector}' is not valid CSS: {exc}"
                    )
                if next_link is None or not next_link.get("href"):
                    errors.append(
                        f"next_page_selector '{self.next_page_selector}' did not produce href"
                    )
        return errors


class ExtractedItem(BaseModel):
    title: str
    url: str
    published_at: str | None = None
    source_list_url: str


class RunnerStats(BaseModel):
    pages_crawled: int = 0
    items_found: int = 0
    items_new: int = 0
    items_duplicate: int = 0
    stop_reason: str = "unknown"


class RunnerDebug(BaseModel):
    spec_summary: dict[str, Any] = Field(default_factory=dict)
    selected_item_count_per_page: list[dict[str, Any]] = Field(default_factory=list)
    next_page_trace: list[dict[str, Any]] = Field(default_factory=list)
    date_parse_errors: list[dict[str, Any]] = Field(default_factory=list)


class RunnerResult(BaseModel):
    items: list[ExtractedItem] = Field(default_factory=list)
    stats: RunnerStats = Field(default_factory=RunnerStats)
    debug: RunnerDebug = Field(default_factory=RunnerDebug)


class RunInput(BaseModel):
    seed_url: str
    site_id: int
    max_days: int
    max_pages: int
    run_type: RunType
    last_seen_checkpoint: list[str] = Field(default_factory=list)


def strip_markdown_fences(payload: str) -> str:
    cleaned = payload.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
    return cleaned.strip()


def dump_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)


def parse_known_date(raw_value: str, date_format: DateFormat) -> datetime | None:
    raw_value = normalize_date_text(raw_value)
    known_formats = ["%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"]
    formats = known_formats if date_format == "auto" else [date_format]
    for current_format in formats:
        try:
            return datetime.strptime(raw_value, current_format)
        except ValueError:
            continue
    return None


def is_self_selector(selector: str | None) -> bool:
    return selector in {":self", ":scope", None}


def select_first(root: BeautifulSoup | Tag, selector: str | None) -> Tag | None:
    if is_self_selector(selector):
        return root if isinstance(root, Tag) else None
    return root.select_one(selector)


def normalize_date_text(raw_value: str) -> str:
    text = " ".join(raw_value.replace("\xa0", " ").split()).strip()
    normalized = (
        text.replace("年", "-")
        .replace("月", "-")
        .replace("日", "")
        .replace("／", "/")
        .replace("．", ".")
        .replace("－", "-")
    )
    normalized = re.sub(r"-(\d)(?!\d)", r"-0\1", normalized)
    normalized = re.sub(r"/(\d)(?!\d)", r"/0\1", normalized)
    normalized = re.sub(r"\.(\d)(?!\d)", r".0\1", normalized)
    return normalized
