from __future__ import annotations

import json
import logging
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag
from openai import OpenAI

from ai_news_spider.config import Settings
from ai_news_spider.crawler import CrawlSample
from ai_news_spider.models import (
    SiteSpec,
    dump_json,
    parse_known_date,
    select_first,
    strip_markdown_fences,
)
from ai_news_spider.runtime import extract_date_text, extract_title_text

logger = logging.getLogger(__name__)
DATE_RE = re.compile(r"\d{4}(?:[-/.]\d{2}[-/.]\d{2}|年\d{2}月\d{2}日)")
NEXT_PAGE_RE = re.compile(r"(下页|下一页|后页|后一页|next)", re.IGNORECASE)
TITLE_HINTS = (
    "title",
    "tit",
    "name",
    "headline",
    "subject",
    "news",
    "article",
    "notice",
    "caption",
    "listconrn-rb",
    "bt",
)
DATE_HINTS = ("date", "time", "publish", "pub", "rq", "sj")


class SpecGenerationError(RuntimeError):
    """Raised when site spec generation fails."""


class SiteSpecGenerator(Protocol):
    async def generate(
        self,
        sample: CrawlSample,
        *,
        site_name: str | None = None,
        list_locator_hint: str | None = None,
        feedback: str | None = None,
        previous_spec: dict[str, Any] | None = None,
        previous_run_result: dict[str, Any] | None = None,
    ) -> SiteSpec: ...


def detect_locator_kind(locator_hint: str | None) -> str | None:
    if not locator_hint or not locator_hint.strip():
        return None
    locator = locator_hint.strip()
    if locator.startswith("//") or locator.startswith(".//"):
        return "xpath_relative"
    if locator.startswith("/"):
        return "xpath_absolute"
    return "css"


@dataclass(slots=True)
class ItemGroupCandidate:
    selector: str
    nodes: list[Tag]
    score: float
    reason: str


@dataclass(slots=True)
class SpecCandidate:
    spec: SiteSpec
    score: float
    source: str
    diagnostics: dict[str, Any]
    validation_errors: list[str]

    def prompt_summary(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "score": round(self.score, 2),
            "selectors": {
                "list_item_selector": self.spec.list_item_selector,
                "title_selector": self.spec.title_selector,
                "link_selector": self.spec.link_selector,
                "date_selector": self.spec.date_selector,
                "next_page_selector": self.spec.next_page_selector,
            },
            "pagination_mode": self.spec.pagination_mode,
            "date_format": self.spec.date_format,
            "metrics": self.diagnostics,
            "validation_errors": self.validation_errors,
        }


class OpenAISiteSpecGenerator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = OpenAI(
            api_key=settings.api_key,
            base_url=settings.base_url,
        )

    async def generate(
        self,
        sample: CrawlSample,
        *,
        site_name: str | None = None,
        list_locator_hint: str | None = None,
        feedback: str | None = None,
        previous_spec: dict[str, Any] | None = None,
        previous_run_result: dict[str, Any] | None = None,
    ) -> SiteSpec:
        heuristic_candidates = build_heuristic_spec_candidates(
            sample,
            site_name=site_name,
            list_locator_hint=list_locator_hint,
        )
        best_heuristic = choose_best_candidate(heuristic_candidates)
        if best_heuristic is None:
            raise SpecGenerationError("启发式规则推断失败：未能生成任何候选规则")
        logger.info(
            "Prepared heuristic candidates url=%s candidate_count=%s best_score=%.2f",
            sample.seed_url,
            len(heuristic_candidates),
            best_heuristic.score,
        )
        for candidate in heuristic_candidates[:5]:
            logger.info("Heuristic candidate summary url=%s summary=%s", sample.seed_url, candidate.prompt_summary())

        if not self.settings.base_url or not self.settings.api_key:
            if best_heuristic.validation_errors:
                raise SpecGenerationError(
                    "缺少 BASE_URL 或 API_KEY，且启发式候选规则不可用："
                    + "; ".join(best_heuristic.validation_errors)
                )
            raise SpecGenerationError("缺少 BASE_URL 或 API_KEY，无法调用站点规则生成模型。")

        logger.info(
            "Generating site_spec via LLM url=%s model=%s",
            sample.seed_url,
            self.settings.model_name,
        )

        messages = self._build_messages(
            sample=sample,
            site_name=site_name,
            list_locator_hint=list_locator_hint,
            feedback=feedback,
            previous_spec=previous_spec,
            previous_run_result=previous_run_result,
            heuristic_candidates=heuristic_candidates[:5],
        )

        last_error = ""
        best_llm_candidate: SpecCandidate | None = None
        for attempt in range(1, 3):
            logger.info("LLM site_spec attempt=%s url=%s", attempt, sample.seed_url)
            response = self.client.chat.completions.create(
                model=self.settings.model_name,
                messages=messages,
            )
            content = response.choices[0].message.content or ""
            logger.info("LLM raw response attempt=%s content=%s", attempt, content[:2000])
            try:
                data = json.loads(strip_markdown_fences(content))
                spec = SiteSpec.model_validate(data)
                llm_candidate = evaluate_spec_candidate(
                    sample,
                    spec,
                    source=f"llm_attempt_{attempt}",
                )
                if llm_candidate.validation_errors:
                    last_error = "; ".join(llm_candidate.validation_errors)
                    logger.warning(
                        "LLM site_spec validation failed attempt=%s url=%s errors=%s",
                        attempt,
                        sample.seed_url,
                        last_error,
                    )
                    messages.extend(
                        [
                            {"role": "assistant", "content": content},
                            {
                                "role": "user",
                                "content": (
                                    "你返回的 JSON 通过了解析，但选择器自检失败。"
                                    f"请修复这些错误后仅返回 JSON：{last_error}"
                                ),
                            },
                        ]
                    )
                    continue

                best_llm_candidate = llm_candidate
                if llm_candidate.score + 8 < best_heuristic.score:
                    last_error = (
                        "规则可运行，但质量分数偏低。"
                        f"当前分数={llm_candidate.score:.2f}，最佳候选分数={best_heuristic.score:.2f}。"
                        "请优先使用提供的候选容器、标题、日期和分页选择器，仅返回修复后的 JSON。"
                    )
                    logger.warning(
                        "LLM site_spec score is weaker than heuristic attempt=%s url=%s llm_score=%.2f heuristic_score=%.2f",
                        attempt,
                        sample.seed_url,
                        llm_candidate.score,
                        best_heuristic.score,
                    )
                    messages.extend(
                        [
                            {"role": "assistant", "content": content},
                            {"role": "user", "content": last_error},
                        ]
                    )
                    continue

                logger.info(
                    "LLM site_spec accepted url=%s score=%.2f selectors=%s",
                    sample.seed_url,
                    llm_candidate.score,
                    llm_candidate.spec.summary(),
                )
                return llm_candidate.spec
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                logger.warning(
                    "LLM site_spec parse/validate exception attempt=%s url=%s error=%s",
                    attempt,
                    sample.seed_url,
                    last_error,
                )
                messages.extend(
                    [
                        {"role": "assistant", "content": content},
                        {
                            "role": "user",
                            "content": (
                                "你返回的内容不是可校验的 JSON。"
                                f"请修复并仅返回 JSON 对象。错误：{last_error}"
                            ),
                        },
                    ]
                )

        if best_llm_candidate and not best_llm_candidate.validation_errors:
            if best_llm_candidate.score >= best_heuristic.score - 5:
                logger.info(
                    "Using best LLM candidate after retries url=%s llm_score=%.2f heuristic_score=%.2f",
                    sample.seed_url,
                    best_llm_candidate.score,
                    best_heuristic.score,
                )
                return best_llm_candidate.spec

        logger.warning(
            "LLM site_spec failed or underperformed; falling back to heuristic url=%s error=%s",
            sample.seed_url,
            last_error,
        )
        if best_heuristic.validation_errors:
            raise SpecGenerationError(
                "站点规则生成失败，且启发式兜底也失败："
                + "; ".join(best_heuristic.validation_errors)
            )
        return best_heuristic.spec

    def _build_messages(
        self,
        *,
        sample: CrawlSample,
        site_name: str | None,
        list_locator_hint: str | None,
        feedback: str | None,
        previous_spec: dict[str, Any] | None,
        previous_run_result: dict[str, Any] | None,
        heuristic_candidates: list[SpecCandidate],
    ) -> list[dict[str, str]]:
        seed_domain = urlparse(sample.seed_url).netloc
        locator_kind = detect_locator_kind(list_locator_hint)
        locator_root = resolve_locator_root(sample.html, list_locator_hint)
        prompt = {
            "task": "根据新闻列表页样本输出 site_spec JSON，仅用于列表采集。",
            "requirements": {
                "fields": [
                    "seed_url",
                    "site_name",
                    "allowed_domains",
                    "requires_js",
                    "wait_for",
                    "list_item_selector",
                    "title_selector",
                    "link_selector",
                    "date_selector",
                    "date_format",
                    "timezone",
                    "pagination_mode",
                    "next_page_selector",
                    "max_pages_default",
                    "url_join_mode",
                ],
                "allowed_values": {
                    "pagination_mode": ["next_link", "none"],
                    "date_format": ["auto", "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"],
                    "url_join_mode": ["auto", "absolute"],
                },
                "rules": [
                    "只返回一个 JSON 对象，不要返回 Markdown。",
                    "不要生成解释说明，不要包含脚本代码。",
                    "所有 selector 必须使用 CSS selector，禁止输出 XPath。",
                    "date_selector 可以为 null，但不要输出空字符串。",
                    "link_selector 可以使用 :self，仅当列表项节点自身就是可点击链接时使用。",
                    "如果页面是静态列表，requires_js=false。",
                    "如果提供了列表定位器，优先在该定位器命中的范围内推断列表项和字段选择器。",
                    "分页必须优先跟随 DOM 中真实的下一页链接。",
                    "优先在给定候选中选择或小幅修正，不要凭空发明与候选完全无关的容器。",
                    "allowed_domains 至少包含种子域名，如果文章链接明显落在同机构域名，也可以加入。",
                ],
            },
            "context": {
                "seed_url": sample.seed_url,
                "site_name_hint": site_name or sample.title,
                "seed_domain": seed_domain,
                "page_title": sample.title,
                "feedback": feedback,
                "previous_spec": previous_spec,
                "previous_run_result": previous_run_result,
                "list_locator_kind": locator_kind,
                "list_locator_hint": list_locator_hint,
                "locator_scope_excerpt": (
                    str(locator_root)[:5000] if locator_root is not None else None
                ),
                "list_html_excerpt": sample.list_html_excerpt,
                "markdown_excerpt": sample.markdown_excerpt,
                "internal_links": sample.links.get("internal", [])[:20],
                "heuristic_candidates": [
                    candidate.prompt_summary() for candidate in heuristic_candidates
                ],
            },
        }

        return [
            {
                "role": "system",
                "content": (
                    "你是一个新闻列表页抽取规则生成器。"
                    "目标是输出可直接通过 Pydantic 校验的 site_spec JSON。"
                    "你会收到程序预先发现的候选规则，请优先在候选中做选择或修正。"
                ),
            },
            {"role": "user", "content": dump_json(prompt)},
        ]


class HeuristicSiteSpecGenerator:
    async def generate(
        self,
        sample: CrawlSample,
        *,
        site_name: str | None = None,
        list_locator_hint: str | None = None,
        feedback: str | None = None,
        previous_spec: dict[str, Any] | None = None,
        previous_run_result: dict[str, Any] | None = None,
    ) -> SiteSpec:
        del feedback, previous_spec, previous_run_result
        logger.info("Using heuristic site_spec generator url=%s", sample.seed_url)

        candidates = build_heuristic_spec_candidates(
            sample,
            site_name=site_name,
            list_locator_hint=list_locator_hint,
        )
        best = choose_best_candidate(candidates)
        if best is None:
            raise SpecGenerationError("启发式规则推断失败：未找到可重复列表项容器")
        if best.validation_errors:
            raise SpecGenerationError(
                "启发式规则推断失败："
                + "; ".join(best.validation_errors)
            )
        logger.info(
            "Heuristic selected site_spec url=%s score=%.2f selectors=%s",
            sample.seed_url,
            best.score,
            best.spec.summary(),
        )
        return best.spec


def choose_best_candidate(candidates: list[SpecCandidate]) -> SpecCandidate | None:
    if not candidates:
        return None
    valid = [candidate for candidate in candidates if not candidate.validation_errors]
    if valid:
        return valid[0]
    return candidates[0]


def build_heuristic_spec_candidates(
    sample: CrawlSample,
    *,
    site_name: str | None,
    list_locator_hint: str | None = None,
) -> list[SpecCandidate]:
    soup = BeautifulSoup(sample.html, "html.parser")
    next_page_selector = infer_next_page_selector(soup)
    allowed_domains = infer_allowed_domains(sample)
    scope_root = resolve_locator_root(sample.html, list_locator_hint)
    item_groups = discover_item_groups(
        scope_root or soup,
        scope_root=scope_root,
        locator_hint=list_locator_hint,
    )
    if not item_groups and scope_root is not None:
        logger.warning(
            "Locator hint matched a node but no repeated item groups were found within it; falling back to full-page discovery url=%s locator=%s",
            sample.seed_url,
            list_locator_hint,
        )
        item_groups = discover_item_groups(soup)
    if not item_groups:
        raise SpecGenerationError("启发式规则推断失败：未找到可重复列表项容器")

    candidates: list[SpecCandidate] = []
    seen_specs: set[tuple[str, str, str, str | None, str | None]] = set()
    for group in item_groups[:12]:
        link_selectors = infer_link_selectors(group.nodes)[:2] or ["a"]
        title_selectors = infer_title_selectors(group.nodes, link_selectors)[:3]
        date_selectors = infer_date_selectors(group.nodes)[:3] or [None]
        for link_selector in link_selectors:
            title_pool = list(title_selectors)
            if link_selector not in title_pool:
                title_pool.append(link_selector)
            for title_selector in title_pool[:3]:
                for date_selector in date_selectors:
                    spec_key = (
                        group.selector,
                        title_selector,
                        link_selector,
                        date_selector,
                        next_page_selector,
                    )
                    if spec_key in seen_specs:
                        continue
                    seen_specs.add(spec_key)
                    spec = SiteSpec.model_validate(
                        {
                            "seed_url": sample.seed_url,
                            "site_name": site_name or sample.title,
                            "allowed_domains": allowed_domains,
                            "requires_js": False,
                            "wait_for": None,
                            "list_item_selector": group.selector,
                            "title_selector": title_selector,
                            "link_selector": link_selector,
                            "date_selector": date_selector,
                            "date_format": infer_date_format(group.nodes),
                            "timezone": "Asia/Shanghai",
                            "pagination_mode": "next_link" if next_page_selector else "none",
                            "next_page_selector": next_page_selector,
                            "max_pages_default": 10,
                            "url_join_mode": "auto",
                        }
                    )
                    candidate = evaluate_spec_candidate(
                        sample,
                        spec,
                        source=f"heuristic:{group.reason}",
                        base_group_score=group.score,
                    )
                    candidates.append(candidate)

    candidates.sort(
        key=lambda candidate: (
            bool(candidate.validation_errors),
            -candidate.score,
            len(candidate.spec.list_item_selector),
        )
    )
    return candidates


def infer_allowed_domains(sample: CrawlSample) -> list[str]:
    domains = {urlparse(sample.seed_url).netloc}
    for link in sample.links.get("internal", [])[:20]:
        if isinstance(link, dict):
            href = link.get("href") or link.get("url") or ""
        else:
            href = str(link)
        netloc = urlparse(href).netloc
        if netloc:
            domains.add(netloc)
    return sorted(domains)


def resolve_locator_root(html: str, locator_hint: str | None) -> Tag | None:
    if not locator_hint:
        return None
    soup = BeautifulSoup(html, "html.parser")
    locator = locator_hint.strip()
    if not locator:
        return None
    locator_kind = detect_locator_kind(locator)
    if locator_kind == "xpath_absolute":
        return find_node_by_simple_xpath(soup, locator)
    if locator_kind == "xpath_relative":
        return find_node_by_relative_xpath(soup, locator)
    try:
        return soup.select_one(locator)
    except Exception:  # noqa: BLE001
        return None


def find_node_by_simple_xpath(soup: BeautifulSoup, xpath: str) -> Tag | None:
    steps = [step for step in xpath.strip().split("/") if step]
    current: BeautifulSoup | Tag = soup
    for raw_step in steps:
        match = re.fullmatch(r"([a-zA-Z][\w:-]*)(?:\[(\d+)\])?", raw_step)
        if not match:
            return None
        tag_name = match.group(1).lower()
        index = int(match.group(2) or "1") - 1
        children = [
            child
            for child in current.find_all(tag_name, recursive=False)
            if isinstance(child, Tag)
        ]
        if index < 0 or index >= len(children):
            return None
        current = children[index]
    return current if isinstance(current, Tag) else None


def find_node_by_relative_xpath(soup: BeautifulSoup, xpath: str) -> Tag | None:
    expression = xpath.strip()
    if expression.startswith(".//"):
        expression = expression[3:]
    elif expression.startswith("//"):
        expression = expression[2:]
    else:
        expression = expression.lstrip("/")

    if not expression:
        return None

    current_nodes: list[BeautifulSoup | Tag] = [soup]
    for raw_step in [step for step in expression.split("/") if step]:
        parsed = parse_relative_xpath_step(raw_step)
        if parsed is None:
            return None
        tag_name, attrs, index = parsed
        matches: list[Tag] = []
        for current in current_nodes:
            matches.extend(find_matching_descendants(current, tag_name, attrs))
        if not matches:
            return None
        if index is not None:
            if index < 0 or index >= len(matches):
                return None
            current_nodes = [matches[index]]
        else:
            current_nodes = matches
    return current_nodes[0] if current_nodes else None


def parse_relative_xpath_step(
    raw_step: str,
) -> tuple[str, dict[str, str], int | None] | None:
    tag_match = re.match(r"^([a-zA-Z][\w:-]*)", raw_step)
    if not tag_match:
        return None
    tag_name = tag_match.group(1).lower()
    predicates = re.findall(r"\[([^\]]+)\]", raw_step)
    attrs: dict[str, str] = {}
    index: int | None = None
    for predicate in predicates:
        predicate = predicate.strip()
        if predicate.isdigit():
            index = int(predicate) - 1
            continue
        attr_match = re.fullmatch(
            r"""@([\w:-]+)\s*=\s*['"]([^'"]+)['"]""",
            predicate,
        )
        if attr_match is not None:
            attrs[attr_match.group(1).lower()] = attr_match.group(2)
            continue
        contains_match = re.fullmatch(
            r"""contains\(@([\w:-]+)\s*,\s*['"]([^'"]+)['"]\)""",
            predicate,
        )
        if contains_match is not None:
            attrs[f"contains:{contains_match.group(1).lower()}"] = contains_match.group(2)
            continue
        return None
    return tag_name, attrs, index


def find_matching_descendants(
    current: BeautifulSoup | Tag,
    tag_name: str,
    attrs: dict[str, str],
) -> list[Tag]:
    matches: list[Tag] = []
    for node in current.find_all(tag_name):
        if not isinstance(node, Tag):
            continue
        if all(xpath_attr_matches(node, key, value) for key, value in attrs.items()):
            matches.append(node)
    return matches


def xpath_attr_matches(node: Tag, key: str, value: str) -> bool:
    if key.startswith("contains:"):
        attr_name = key.split(":", 1)[1]
        actual = node.get(attr_name)
        if attr_name == "class":
            classes = actual if isinstance(actual, list) else str(actual or "").split()
            return value in classes or value in " ".join(classes)
        return value in str(actual or "")
    actual = node.get(key)
    if key == "class":
        classes = actual if isinstance(actual, list) else str(actual or "").split()
        return value in classes or " ".join(classes) == value
    return str(actual or "") == value


def discover_item_groups(
    soup: BeautifulSoup | Tag,
    *,
    scope_root: Tag | None = None,
    locator_hint: str | None = None,
) -> list[ItemGroupCandidate]:
    groups: list[ItemGroupCandidate] = []
    seen: set[str] = set()
    containers: list[Tag] = []
    if isinstance(soup, Tag) and soup.name in {"ul", "ol", "div", "section", "article", "main", "table", "tbody"}:
        containers.append(soup)
    containers.extend(
        soup.find_all(["ul", "ol", "div", "section", "article", "main", "table", "tbody"])
    )
    for container in containers:
        direct_children = [
            child for child in container.find_all(recursive=False) if isinstance(child, Tag)
        ]
        if len(direct_children) < 3:
            continue

        grouped: dict[str, list[Tag]] = {}
        for child in direct_children:
            grouped.setdefault(child.name, []).append(child)

        for tag_name, nodes in grouped.items():
            if tag_name in {"script", "style"} or len(nodes) < 3:
                continue
            if not any(find_primary_link(node) for node in nodes[:8]):
                continue
            selector = f"{anchored_css_path(container)} > {tag_name}"
            if selector in seen:
                continue
            score = score_item_group(nodes, selector=selector)
            if scope_root is not None:
                score += 20
            if locator_hint:
                score += 8
            groups.append(
                ItemGroupCandidate(
                    selector=selector,
                    nodes=nodes,
                    score=score,
                    reason=f"group:{selector}",
                )
            )
            seen.add(selector)

    if not groups:
        fallback = soup.select("li")
        if fallback:
            groups.append(
                ItemGroupCandidate(
                    selector="li",
                    nodes=fallback,
                    score=score_item_group(fallback, selector="li"),
                    reason="fallback:li",
                )
            )

    groups.sort(key=lambda group: (-group.score, len(group.selector)))
    return groups


def score_item_group(nodes: list[Tag], *, selector: str) -> float:
    sample_nodes = nodes[:12]
    count = len(sample_nodes) or 1
    link_hits = sum(1 for node in sample_nodes if find_primary_link(node))
    date_hits = sum(1 for node in sample_nodes if DATE_RE.search(node.get_text(" ", strip=True)))
    newsish_hrefs = sum(1 for node in sample_nodes if link_looks_like_article(find_primary_link(node)))
    text_lengths = [len(normalize_text(node.get_text(" ", strip=True))) for node in sample_nodes]
    avg_text_len = sum(text_lengths) / len(text_lengths) if text_lengths else 0
    score = 0.0
    score += min(len(nodes), 30)
    score += (link_hits / count) * 35
    score += (date_hits / count) * 35
    score += (newsish_hrefs / count) * 15
    if 12 <= avg_text_len <= 180:
        score += 12
    elif avg_text_len < 8:
        score -= 18
    score -= max(selector_depth(selector) - 3, 0) * 2
    if len(nodes) > 80:
        score -= 8
    return score


def infer_link_selectors(items: list[Tag]) -> list[str]:
    counter: Counter[str] = Counter()
    for item in items[:8]:
        for selector, weight in candidate_link_selectors_for_item(item):
            counter[selector] += weight
    return sort_ranked_selectors(counter) or ["a"]


def candidate_link_selectors_for_item(item: Tag) -> list[tuple[str, int]]:
    selectors: list[tuple[str, int]] = []
    if item.get("href"):
        selectors.append((":self", 12))
    direct_anchor = item.find("a", href=True, recursive=False)
    if direct_anchor is not None:
        selectors.append((best_relative_selector(item, direct_anchor), 10))
    anchor = item.find("a", href=True)
    if anchor is not None:
        selectors.append((best_relative_selector(item, anchor), 8))
    return dedupe_weighted_selectors(selectors)


def infer_title_selectors(items: list[Tag], link_selectors: list[str]) -> list[str]:
    counter: Counter[str] = Counter()
    preferred_link = link_selectors[0] if link_selectors else None
    for item in items[:8]:
        for selector, weight in candidate_title_selectors_for_item(item, preferred_link):
            counter[selector] += weight
    ranked = sort_ranked_selectors(counter)
    if preferred_link and preferred_link not in ranked:
        ranked.append(preferred_link)
    return ranked or [preferred_link or "a"]


def candidate_title_selectors_for_item(
    item: Tag, preferred_link: str | None
) -> list[tuple[str, int]]:
    selectors: list[tuple[str, int]] = []
    scored_nodes: list[tuple[int, Tag]] = []
    for node in item.find_all(True):
        text = normalize_text(node.get_text(" ", strip=True))
        if not text or DATE_RE.fullmatch(text) or len(text) < 6:
            continue
        score = 0
        if node.name in {"h1", "h2", "h3", "h4", "h5", "strong", "b"}:
            score += 18
        attrs = " ".join(
            [
                node.get("id", ""),
                " ".join(node.get("class", [])),
                node.get("title", ""),
            ]
        ).lower()
        if any(hint in attrs for hint in TITLE_HINTS):
            score += 25
        if DATE_RE.search(text):
            score -= 8
        text_length = len(text)
        if 8 <= text_length <= 80:
            score += 12
        elif text_length <= 120:
            score += 6
        else:
            score -= 6
        if score > 0:
            scored_nodes.append((score, node))

    scored_nodes.sort(
        key=lambda item: (
            -item[0],
            len(normalize_text(item[1].get_text(" ", strip=True))),
        )
    )
    for score, node in scored_nodes[:4]:
        selectors.append((best_relative_selector(item, node), score))

    if preferred_link:
        link_node = select_first(item, preferred_link)
        if link_node is not None:
            text = normalize_text(link_node.get_text(" ", strip=True))
            if 6 <= len(text) <= 100:
                selectors.append((preferred_link, 10))
    if item.get("title"):
        selectors.append((":self", 4))
    selectors.append((":self", 1))
    return dedupe_weighted_selectors(selectors)


def infer_date_selectors(items: list[Tag]) -> list[str | None]:
    counter: Counter[str | None] = Counter()
    for item in items[:8]:
        local: list[tuple[str | None, int]] = []
        for node in item.find_all(True):
            text = normalize_text(node.get_text(" ", strip=True))
            if not text:
                continue
            attrs = " ".join([node.get("id", ""), " ".join(node.get("class", []))]).lower()
            score = 0
            if DATE_RE.fullmatch(text):
                score += 18
            elif DATE_RE.search(text):
                score += 8
            if any(hint in attrs for hint in DATE_HINTS):
                score += 12
            if node.name in {"time", "em", "span"}:
                score += 3
            if score > 0 and DATE_RE.search(text):
                local.append((best_relative_selector(item, node), score))
        if not local and DATE_RE.search(item.get_text(" ", strip=True)):
            counter[None] += 2
        for selector, weight in dedupe_weighted_selectors(local):
            counter[selector] += weight

    if not counter:
        return [None]
    ranked = sorted(
        counter.items(),
        key=lambda item: (
            item[0] is None,
            -item[1],
            len(item[0] or ""),
        ),
    )
    return [selector for selector, _ in ranked]


def infer_date_format(items: list[Tag]) -> str:
    for item in items[:10]:
        text = item.get_text(" ", strip=True)
        match = DATE_RE.search(text)
        if not match:
            continue
        raw = match.group(0)
        if "年" in raw and "月" in raw and "日" in raw:
            return "auto"
        if "-" in raw:
            return "%Y-%m-%d"
        if "/" in raw:
            return "%Y/%m/%d"
        if "." in raw:
            return "%Y.%m.%d"
    return "auto"


def infer_next_page_selector(soup: BeautifulSoup) -> str | None:
    candidates: list[tuple[int, str]] = []
    for anchor in soup.select("a[href]"):
        text = normalize_text(anchor.get_text(" ", strip=True))
        href = (anchor.get("href") or "").strip()
        if not href or not NEXT_PAGE_RE.search(text):
            continue
        selector = best_absolute_selector(anchor)
        score = 10
        if "next" in " ".join(anchor.get("class", [])).lower():
            score += 6
        parent = anchor.parent if isinstance(anchor.parent, Tag) else None
        if parent is not None and parent.get("id"):
            score += 4
        candidates.append((score, selector))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (-item[0], len(item[1])))
    return candidates[0][1]


def evaluate_spec_candidate(
    sample: CrawlSample,
    spec: SiteSpec,
    *,
    source: str,
    base_group_score: float = 0.0,
) -> SpecCandidate:
    validation_errors = spec.validate_on_html(sample.html, sample.final_url)
    soup = BeautifulSoup(sample.html, "html.parser")
    try:
        nodes = soup.select(spec.list_item_selector)
    except Exception as exc:  # noqa: BLE001
        return SpecCandidate(
            spec=spec,
            score=-100.0,
            source=source,
            diagnostics={"selector_error": str(exc)},
            validation_errors=[str(exc)],
        )

    sample_nodes = nodes[:8]
    title_count = 0
    href_count = 0
    date_count = 0
    parsed_date_count = 0
    newsish_href_count = 0
    titles: list[str] = []
    samples: list[dict[str, Any]] = []

    for node in sample_nodes:
        title_el = select_first(node, spec.title_selector)
        link_el = select_first(node, spec.link_selector)
        date_el = select_first(node, spec.date_selector) if spec.date_selector else None
        raw_date = extract_date_text(date_el, node)
        title = ""
        href = ""
        if title_el is not None:
            title = extract_title_text(title_el, raw_date)
            if title:
                title_count += 1
                titles.append(title)
        if link_el is not None:
            href = (link_el.get("href") or "").strip()
            if href:
                href_count += 1
                if link_looks_like_article(link_el):
                    newsish_href_count += 1
        if raw_date:
            date_count += 1
            if parse_known_date(raw_date, spec.date_format):
                parsed_date_count += 1
        if len(samples) < 3:
            samples.append({"title": title, "href": href, "raw_date": raw_date})

    avg_title_len = (
        sum(len(title) for title in titles) / len(titles) if titles else 0.0
    )
    unique_title_ratio = len(set(titles)) / len(titles) if titles else 0.0
    score = base_group_score
    score += title_count * 10
    score += href_count * 10
    score += date_count * 4
    score += parsed_date_count * 8
    score += newsish_href_count * 4
    score += unique_title_ratio * 10
    if 8 <= avg_title_len <= 80:
        score += 12
    elif avg_title_len < 5:
        score -= 20
    elif avg_title_len > 140:
        score -= 8
    if spec.link_selector == ":self" and sample_nodes and sample_nodes[0].name == "a":
        score += 4
    score -= len(validation_errors) * 25
    score -= max(selector_depth(spec.title_selector) - 2, 0) * 1.5
    score -= max(selector_depth(spec.link_selector) - 2, 0) * 1.5
    score -= max(selector_depth(spec.date_selector or "") - 2, 0)
    diagnostics = {
        "node_count": len(nodes),
        "sample_count": len(sample_nodes),
        "title_count": title_count,
        "href_count": href_count,
        "date_count": date_count,
        "parsed_date_count": parsed_date_count,
        "newsish_href_count": newsish_href_count,
        "avg_title_length": round(avg_title_len, 2),
        "unique_title_ratio": round(unique_title_ratio, 2),
        "samples": samples,
        "quality_score": round(score, 2),
    }
    logger.debug(
        "Evaluated spec candidate url=%s source=%s score=%.2f diagnostics=%s errors=%s",
        sample.seed_url,
        source,
        score,
        diagnostics,
        validation_errors,
    )
    return SpecCandidate(
        spec=spec,
        score=score,
        source=source,
        diagnostics=diagnostics,
        validation_errors=validation_errors,
    )


def link_looks_like_article(link_el: Tag | None) -> bool:
    if link_el is None:
        return False
    href = (link_el.get("href") or "").strip().lower()
    if not href:
        return False
    return any(
        token in href
        for token in (".htm", ".html", "/info/", "/article/", "/content/", "/tzgg", "/gg")
    ) or bool(re.search(r"\d", href))


def find_primary_link(node: Tag) -> Tag | None:
    if node.get("href"):
        return node
    return node.find("a", href=True)


def sort_ranked_selectors(counter: Counter[Any]) -> list[Any]:
    return [
        selector
        for selector, _ in sorted(
            counter.items(),
            key=lambda item: (-item[1], len(str(item[0] or ""))),
        )
    ]


def dedupe_weighted_selectors(
    selectors: list[tuple[str | None, int]]
) -> list[tuple[str | None, int]]:
    best_weights: dict[str | None, int] = {}
    for selector, weight in selectors:
        current = best_weights.get(selector)
        if current is None or weight > current:
            best_weights[selector] = weight
    return list(best_weights.items())


def normalize_text(value: str) -> str:
    return " ".join(value.split())


def best_relative_selector(root: Tag, target: Tag) -> str:
    if target is root:
        return ":self"
    candidates = selector_candidates_for_target(root, target)
    for candidate in candidates:
        if selector_matches_target(root, target, candidate):
            return candidate
    return relative_css_path(root, target)


def selector_candidates_for_target(root: Tag, target: Tag) -> list[str]:
    candidates: list[str] = []
    simple = css_path(target)
    if simple:
        candidates.append(simple)

    parent = target.parent if isinstance(target.parent, Tag) else None
    if parent is not None and parent is not root:
        parent_simple = css_path(parent)
        if parent_simple:
            candidates.append(f"{parent_simple} > {simple}")

    full = relative_css_path(root, target)
    if full:
        candidates.append(full)

    unique: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    return unique


def selector_matches_target(root: Tag, target: Tag, selector: str) -> bool:
    try:
        matched = root.select(selector)
    except Exception:  # noqa: BLE001
        return False
    return len(matched) == 1 and matched[0] is target


def best_absolute_selector(node: Tag) -> str:
    if node.get("id"):
        return f"a#{node['id']}"
    return absolute_css_path(node)


def css_path(node: Tag) -> str:
    if node.get("id"):
        return f"#{node['id']}"
    parts = [node.name]
    classes = [cls for cls in node.get("class", []) if cls]
    if classes:
        parts.extend(f".{cls}" for cls in classes[:2])
    return "".join(parts)


def anchored_css_path(node: Tag) -> str:
    parts: list[str] = []
    current: Tag | None = node
    while current is not None and current.name != "[document]":
        parts.append(css_path(current))
        if current.get("id") or current.get("class"):
            break
        parent = current.parent
        current = parent if isinstance(parent, Tag) else None
    parts.reverse()
    return " > ".join(parts)


def absolute_css_path(node: Tag) -> str:
    parts: list[str] = []
    current: Tag | None = node
    while current is not None and current.name != "[document]":
        part = css_path(current)
        parent = current.parent if isinstance(current.parent, Tag) else None
        if parent is not None:
            siblings = [child for child in parent.find_all(current.name, recursive=False)]
            if len(siblings) > 1 and not current.get("id") and not current.get("class"):
                index = siblings.index(current) + 1
                part = f"{part}:nth-of-type({index})"
        parts.append(part)
        if current.get("id") or current.get("class"):
            break
        current = parent
    parts.reverse()
    return " > ".join(parts)


def selector_depth(selector: str) -> int:
    return selector.count(">") + 1 if selector else 0


def relative_css_path(root: Tag, target: Tag) -> str:
    parts: list[str] = []
    node = target
    while node is not None and node is not root:
        if not isinstance(node, Tag):
            break
        part = css_path(node)
        parent = node.parent if isinstance(node.parent, Tag) else None
        if parent is not None:
            siblings = [child for child in parent.find_all(node.name, recursive=False)]
            if len(siblings) > 1 and not node.get("id") and not node.get("class"):
                index = siblings.index(node) + 1
                part = f"{part}:nth-of-type({index})"
        parts.append(part)
        node = parent
    parts.reverse()
    return " > ".join(parts)
