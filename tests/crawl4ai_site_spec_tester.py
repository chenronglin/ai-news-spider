
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Crawl4AI site_spec discovery tester
==================================

用途：
1. 调 /html 获取列表页预处理 HTML
2. 调 /llm/job 生成 list_extraction 规则
3. 调 /crawl/job 用规则验证列表抽取
4. 取第一条 URL：
   - 如果是附件直链，则直接结束详情分析
   - 如果是 HTML 详情页，则继续：
     a) 调 /llm/job 生成 detail_extraction 规则
     b) 调 /crawl/job 抓详情页 markdown / links
5. 组装 site_spec，并把中间结果全部落盘，便于调试

依赖：
    pip install requests

示例：
    python crawl4ai_site_spec_tester.py \
        --base-url http://118.195.150.71:11235 \
        --list-url https://cmm.ncut.edu.cn/index/tzgg.htm \
        --provider openai/gpt-5-mini \
        --out-dir ./out
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import requests


DIRECT_FILE_EXTS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".rar", ".ppt", ".pptx"
}


class Crawl4AIError(RuntimeError):
    """Custom error for Crawl4AI client."""


def setup_logger(debug: bool = False) -> logging.Logger:
    level = logging.DEBUG if debug else logging.INFO
    logger = logging.getLogger("crawl4ai_tester")
    logger.setLevel(level)

    if logger.handlers:
        return logger

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def dump_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def absolutize(base_url: str, url: str) -> str:
    return urljoin(base_url, url)


def is_direct_file_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(path.endswith(ext) for ext in DIRECT_FILE_EXTS)


def looks_like_placeholder_selector(selector: str) -> bool:
    s = (selector or "").strip().lower()
    suspicious_tokens = [
        ".list-container",
        ".notification-item",
        ".notification-date",
        ".article-content",
        ".detail-content",
        ".news-list",
        ".news-item",
    ]
    return s in suspicious_tokens


def normalize_extracted_content(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return {}
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"raw_text": text}
    return {"raw_value": value}


def extract_llm_result_object(job_data: dict) -> dict:
    payload = job_data.get("result")
    if isinstance(payload, list):
        if not payload:
            raise Crawl4AIError(f"LLM job result is empty list: {job_data}")
        first = payload[0]
        if not isinstance(first, dict):
            raise Crawl4AIError(f"LLM job first result is not dict: {first}")
        if first.get("error") is True:
            raise Crawl4AIError(f"LLM job returned error=true: {first}")
        return first

    if isinstance(payload, dict):
        if payload.get("error") is True:
            raise Crawl4AIError(f"LLM job returned error=true: {payload}")
        return payload

    if isinstance(job_data.get("data"), dict):
        data = job_data["data"]
        if isinstance(data.get("extracted_content"), dict):
            return data["extracted_content"]

    raise Crawl4AIError(f"Unexpected LLM job result payload: {job_data}")


def extract_crawl_result_object(job_data: dict) -> dict:
    payload = job_data.get("result")
    if isinstance(payload, list):
        if not payload:
            raise Crawl4AIError(f"Crawl job result is empty list: {job_data}")
        first = payload[0]
        if not isinstance(first, dict):
            raise Crawl4AIError(f"Crawl job first result is not dict: {first}")
        return first

    if isinstance(payload, dict):
        return payload

    if isinstance(job_data.get("data"), dict):
        return job_data["data"]

    raise Crawl4AIError(f"Unexpected crawl job result payload: {job_data}")


def build_list_rule_prompt(locator_hint: Optional[str] = None) -> str:
    prompt = {
        "role": "高校通知公告列表页提取 CSS 规则助手",
        "task": "根据给定的列表页 HTML 提取规律，并输出准确匹配要素的 JSON 配置。",
        "requirements": {
            "fields": [
                "render",
                "list_extraction.strategy",
                "list_extraction.container",
                "list_extraction.item",
                "list_extraction.fields.title",
                "list_extraction.fields.url",
                "list_extraction.fields.date",
                "list_extraction.pagination"
            ],
            "allowed_values": {
                "render": ["static", "dynamic"],
                "list_extraction.strategy": ["css"],
                "list_extraction.fields.*.attr": ["text", "href"],
                "list_extraction.pagination.enabled": [True, False]
            },
            "rules": [
                "只返回一个符合 SCHEMA 格式的 JSON 对象，绝不要输出包含 Markdown 标记或其他多余的解释文本。",
                "所有 selector 必须使用真实解析 HTML 得到的 CSS selector，禁止编造虚假的占位符，比如 .list-container。",
                "必须使用通用的匹配规则提取。绝不能使用特定文章的长路径或 ID（例如禁止过度拟合地写 `a[href^=\"http...\"]`，不要被单篇文章带偏）。",
                "list_extraction.item 的选择器必须具备普适性，能匹配出当前页所有的列表行数据（比如结构类似 `ul.news_list > li` 这种泛用容器），而不是仅仅只命中唯一一条特定的记录。",
                "fields 内部的所有 selector 必须是相对于 item 的**内部相对路径**。如果数据就存在于 item 本身上，请直接使 selector 为空字符串 \"\"。",
                "如果没有检索到可靠的下一页标记，请将 pagination.enabled 置为 false，并且置空 next_page_selector。"
            ]
        }
    }
    if locator_hint:
        prompt["context"] = {
            "list_locator_hint": locator_hint,
            "instruction": f"用户提供了一个强烈建议的列表范围定位器：`{locator_hint}`。如果在页面中能找到该区域，请强烈优先仅在该区域的内部去挖掘可重复的 item 结构。如果它不是 CSS selector 而是 XPath，仅供您大致参考范围，你输出的时候仍然必须全部转化为具体的 CSS selector。"
        }
    return json.dumps(prompt, ensure_ascii=False, indent=2)


LIST_RULE_SCHEMA = {
    "render": "string",
    "list_extraction": {
        "strategy": "string",
        "container": "string",
        "item": "string",
        "fields": {
            "title": {"selector": "string", "attr": "string"},
            "url": {"selector": "string", "attr": "string"},
            "date": {"selector": "string", "attr": "string", "format": "string"},
        },
        "pagination": {
            "enabled": "boolean",
            "next_page_selector": "string",
        },
    },
}


def build_detail_rule_prompt() -> str:
    prompt = {
        "role": "高校通知公告详情页提取 CSS 规则助手",
        "task": "基于新闻详情页的 HTML 输出对应的配置结构 JSON，提取正文与附件规则。",
        "requirements": {
            "fields": [
                "detail_extraction.enabled",
                "detail_extraction.content_selector",
                "detail_extraction.attachments.enabled",
                "detail_extraction.attachments.selectors"
            ],
            "allowed_values": {
                "detail_extraction.enabled": [True, False],
                "detail_extraction.attachments.enabled": [True, False]
            },
            "rules": [
                "只返回 JSON 对象，不要包括 Markdown 标记等文字说明。",
                "提取规则必须只使用稳定的基于真实代码情况的 CSS selector，不要包含 nth-child 或任何仅凭纯文本或特定文章链接硬编码的选择器。",
                "attachments.selectors 请基于实际可能出现的扩展补充特征，比如经常覆盖到 `a[href$='.pdf']`, `a[href$='.doc']` 以及其他本站特征。",
                "如果页面没有出现附件，请将 attachments.enabled 设置为 false，并让 selectors 返回空数组。",
                "尽量避免臆测，如果页面正文没有特定的 articleId 或 article-content 就不要随意写上此类占位符。"
            ]
        }
    }
    return json.dumps(prompt, ensure_ascii=False, indent=2)


DETAIL_RULE_SCHEMA = {
    "detail_extraction": {
        "enabled": "boolean",
        "content_selector": "string",
        "attachments": {
            "enabled": "boolean",
            "selectors": ["string"],
        },
    }
}


def site_spec_list_to_crawl_schema(list_rule: dict) -> dict:
    le = list_rule["list_extraction"]
    fields = le["fields"]

    schema = {
        "name": "notice_list_items",
        "baseSelector": le["item"],
        "fields": [],
    }

    title_sel = fields["title"]["selector"]
    title_field = {
        "name": "title",
        "type": "text",
    }
    if title_sel and title_sel != ":self":
        title_field["selector"] = title_sel
    schema["fields"].append(title_field)

    url_sel = fields["url"]["selector"]
    url_field = {
        "name": "url",
        "type": "attribute",
        "attribute": "href",
    }
    if url_sel and url_sel != ":self":
        url_field["selector"] = url_sel
    schema["fields"].append(url_field)

    if "date" in fields:
        date_sel = fields["date"].get("selector", "")
        date_field = {
            "name": "date",
            "type": "text",
        }
        if date_sel and date_sel != ":self":
            date_field["selector"] = date_sel
        schema["fields"].append(date_field)

    return schema


def extract_list_items_from_job(job_data: dict, list_url: str) -> List[dict]:
    payload = extract_crawl_result_object(job_data)
    extracted = normalize_extracted_content(payload.get("extracted_content"))

    if isinstance(extracted, list):
        items = extracted
    elif isinstance(extracted, dict):
        if isinstance(extracted.get("items"), list):
            items = extracted["items"]
        elif isinstance(extracted.get("data"), list):
            items = extracted["data"]
        else:
            items = [extracted]
    else:
        items = []

    normalized = []
    for item in items:
        if not isinstance(item, dict):
            continue
        row = dict(item)
        if row.get("url"):
            row["url"] = absolutize(list_url, row["url"])
        normalized.append(row)
    return normalized


def score_list_rule_and_items(list_rule: dict, items: List[dict]) -> Dict[str, Any]:
    le = list_rule.get("list_extraction", {})
    item_selector = le.get("item", "")
    fields = le.get("fields", {})

    total = len(items)
    title_hit = sum(1 for x in items if str(x.get("title", "")).strip())
    url_hit = sum(1 for x in items if str(x.get("url", "")).strip())
    date_hit = sum(1 for x in items if str(x.get("date", "")).strip())

    score = 0
    reasons = []

    if total >= 5:
        score += 30
    else:
        reasons.append(f"抽取到的列表项太少：{total}")

    if total > 0 and title_hit / total >= 0.8:
        score += 25
    else:
        reasons.append(f"title 命中率偏低：{title_hit}/{total}")

    if total > 0 and url_hit / total >= 0.8:
        score += 25
    else:
        reasons.append(f"url 命中率偏低：{url_hit}/{total}")

    if total > 0 and date_hit / total >= 0.4:
        score += 10
    else:
        reasons.append(f"date 命中率偏低：{date_hit}/{total}")

    if not looks_like_placeholder_selector(item_selector):
        score += 10
    else:
        reasons.append(f"item selector 看起来像占位符：{item_selector}")

    for field_name, field_def in fields.items():
        selector = (field_def or {}).get("selector", "")
        if looks_like_placeholder_selector(selector):
            reasons.append(f"{field_name} selector 看起来像占位符：{selector}")

    return {
        "score": score,
        "passed": score >= 70,
        "metrics": {
            "total_items": total,
            "title_hit": title_hit,
            "url_hit": url_hit,
            "date_hit": date_hit,
        },
        "reasons": reasons,
    }


def build_site_spec(list_url: str, list_rule: dict, detail_rule: Optional[dict]) -> dict:
    return {
        "id": "spec_uuid",
        "version": 2,
        "status": "draft",
        "source": {
            "url": list_url,
            "type": "list_detail",
            "render": list_rule.get("render", "static"),
            "auth": None,
        },
        "list_extraction": {
            "strategy": "css",
            "container": list_rule["list_extraction"].get("container", ""),
            "item": list_rule["list_extraction"].get("item", ""),
            "fields": list_rule["list_extraction"].get("fields", {}),
            "pagination": list_rule["list_extraction"].get("pagination", {}),
        },
        "item_routing": {
            "direct_file_exts": sorted(DIRECT_FILE_EXTS),
            "direct_file_action": "emit_as_attachment_only",
            "html_action": "crawl_detail",
        },
        "detail_extraction": (
            detail_rule.get("detail_extraction", {})
            if detail_rule
            else {
                "enabled": True,
                "content_selector": "",
                "attachments": {"enabled": True, "selectors": []},
            }
        ),
        "dedup": {
            "strategy": "url",
            "window_days": 90,
        },
        "validation": {
            "min_list_items": 5,
            "title_required": True,
            "url_required": True,
            "date_parse_success_ratio": 0.4,
            "detail_min_markdown_length": 80,
        },
        "schedule": {
            "cron": "0 * * * *",
            "timezone": "Asia/Shanghai",
        },
    }


class Crawl4AIClient:
    def __init__(
        self,
        base_url: str,
        logger: logging.Logger,
        timeout: int = 120,
        api_token: Optional[str] = None,
        user_agent: str = "site-spec-builder/0.2",
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.logger = logger
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json, text/plain;q=0.9, */*;q=0.8",
                "User-Agent": user_agent,
            }
        )
        if api_token:
            self.session.headers["Authorization"] = f"Bearer {api_token}"

    def _safe_json(self, resp: requests.Response) -> Any:
        try:
            return resp.json()
        except ValueError:
            return resp.text

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Optional[dict] = None,
        timeout: Optional[int] = None,
    ) -> requests.Response:
        url = f"{self.base_url}{path}"
        self.logger.debug("HTTP %s %s", method.upper(), url)
        if json_body is not None:
            self.logger.debug("Request JSON: %s", json.dumps(json_body, ensure_ascii=False)[:2000])

        try:
            resp = self.session.request(
                method=method.upper(),
                url=url,
                json=json_body,
                timeout=timeout or self.timeout,
            )
        except requests.RequestException as e:
            raise Crawl4AIError(f"{method.upper()} {url} request failed: {e}") from e

        self.logger.debug("Response status: %s", resp.status_code)
        self.logger.debug("Response body: %s", resp.text[:2000])

        if not resp.ok:
            raise Crawl4AIError(
                f"{method.upper()} {url} failed: "
                f"status={resp.status_code}, body={resp.text[:1000]}"
            )
        return resp

    def health_check(self) -> Any:
        candidates = ["/health", "/"]
        for path in candidates:
            url = f"{self.base_url}{path}"
            try:
                resp = self.session.get(url, timeout=10)
                if resp.ok:
                    data = self._safe_json(resp)
                    self.logger.info("Health OK via %s", url)
                    self.logger.debug("Health payload: %s", data)
                    return data
            except requests.RequestException:
                continue
        self.logger.warning("Health check failed for %s", self.base_url)
        return None

    def get_html(self, url: str) -> dict:
        self.logger.info("Step 1/5: POST /html -> %s", url)
        resp = self._request("POST", "/html", json_body={"url": url})
        data = self._safe_json(resp)

        if isinstance(data, str):
            self.logger.info("/html returned plain text HTML, len=%s", len(data))
            return {"html": data}

        if isinstance(data, dict):
            html_len = len(data.get("html", "")) if isinstance(data.get("html"), str) else 0
            self.logger.info("/html returned JSON, html_len=%s", html_len)
            return data

        self.logger.warning("/html returned unexpected payload type: %s", type(data))
        return {"raw": data}

    def submit_llm_job(
        self,
        *,
        url: str,
        q: str,
        provider: Optional[str] = None,
        schema: Optional[dict] = None,
        cache: bool = False,
        temperature: Optional[float] = None,
        base_url_override: Optional[str] = None,
    ) -> dict:
        payload: Dict[str, Any] = {
            "url": url,
            "q": q,
            "cache": cache,
        }
        if provider:
            payload["provider"] = provider
        if schema is not None:
            payload["schema"] = json.dumps(schema, ensure_ascii=False)
        if temperature is not None:
            payload["temperature"] = temperature
        if base_url_override:
            payload["base_url"] = base_url_override

        self.logger.info("Submit LLM job: %s", url)
        resp = self._request("POST", "/llm/job", json_body=payload)
        data = self._safe_json(resp)
        if not isinstance(data, dict) or "task_id" not in data:
            raise Crawl4AIError(f"Unexpected /llm/job response: {data}")

        task_id = data["task_id"]
        self.logger.info("LLM task_id=%s", task_id)
        self.logger.info("LLM poll URL: %s/llm/job/%s", self.base_url, task_id)
        self.logger.debug("LLM submit response: %s", data)
        return data

    def submit_crawl_job(
        self,
        *,
        urls: List[str],
        extraction_schema: Optional[dict] = None,
        cache_mode: str = "bypass",
    ) -> dict:
        payload: Dict[str, Any] = {
            "urls": urls,
            "cache_mode": cache_mode,
        }

        if extraction_schema is not None:
            payload["extraction_strategy"] = {
                "type": "JsonCssExtractionStrategy",
                "schema": extraction_schema,
            }

        self.logger.info("Submit crawl job: urls=%s", urls)
        resp = self._request("POST", "/crawl/job", json_body=payload)
        data = self._safe_json(resp)
        if not isinstance(data, dict) or "task_id" not in data:
            raise Crawl4AIError(f"Unexpected /crawl/job response: {data}")

        task_id = data["task_id"]
        self.logger.info("Crawl task_id=%s", task_id)
        self.logger.info("Crawl poll URL: %s/crawl/job/%s", self.base_url, task_id)
        self.logger.debug("Crawl submit response: %s", data)
        return data

    def get_job(self, task_id: str) -> dict:
        if task_id.startswith("llm_"):
            candidates = [
                f"/llm/job/{task_id}",
                f"/crawl/job/{task_id}",
            ]
        elif task_id.startswith("crawl_"):
            candidates = [
                f"/crawl/job/{task_id}",
                f"/llm/job/{task_id}",
            ]
        else:
            candidates = [
                f"/llm/job/{task_id}",
                f"/crawl/job/{task_id}",
                f"/job/{task_id}",
            ]

        last_error = None

        for path in candidates:
            url = f"{self.base_url}{path}"
            try:
                self.logger.debug("Polling job URL: %s", url)
                resp = self.session.get(url, timeout=60)
                if resp.status_code == 404:
                    last_error = f"404 Not Found: {url}"
                    continue
                if not resp.ok:
                    last_error = f"{resp.status_code}: {url} -> {resp.text[:500]}"
                    continue

                data = self._safe_json(resp)
                if isinstance(data, dict):
                    self.logger.debug("Job response from %s: %s", url, json.dumps(data, ensure_ascii=False)[:2000])
                    return data
                last_error = f"Non-dict response from {url}: {data}"
            except requests.RequestException as e:
                last_error = f"{url} -> {e}"

        raise Crawl4AIError(
            f"All job status endpoints failed for task_id={task_id}. Last error: {last_error}"
        )

    def wait_job(
        self,
        task_id: str,
        *,
        poll_interval: float = 2.0,
        max_wait_seconds: int = 300,
    ) -> dict:
        self.logger.info("Waiting task: %s", task_id)
        started = time.time()

        while True:
            data = self.get_job(task_id)
            status = data.get("status")
            self.logger.info("Task %s status=%s", task_id, status)

            if status == "completed":
                return data

            if status == "failed":
                raise Crawl4AIError(
                    f"Job failed: task_id={task_id}, error={data.get('error') or data}"
                )

            if time.time() - started > max_wait_seconds:
                raise Crawl4AIError(
                    f"Job timeout: task_id={task_id}, last_status={status}, last_data={data}"
                )

            time.sleep(poll_interval)


def load_json(path: Path) -> Any:
    if not path.exists():
        raise Crawl4AIError(f"依赖的前置文件不存在，请先执行前置步骤: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def run_step_1_html(client: Crawl4AIClient, list_url: str, out_dir: Path) -> dict:
    client.logger.info("=== [Step 1] 获取列表页 HTML ===")
    html_data = client.get_html(list_url)
    dump_json(out_dir / "01_html.json", html_data)
    return html_data

def run_step_2_list_rule(
    client: Crawl4AIClient, list_url: str, out_dir: Path, llm_provider: str, llm_temperature: float, locator_hint: Optional[str] = None
) -> tuple[dict, dict]:
    client.logger.info("=== [Step 2] 提交 LLM 生成列表抽取规则 ===")
    list_rule_job = client.submit_llm_job(
        url=list_url,
        q=build_list_rule_prompt(locator_hint),
        provider=llm_provider,
        schema=LIST_RULE_SCHEMA,
        cache=False,
        temperature=llm_temperature,
    )
    list_rule_job_result = client.wait_job(list_rule_job["task_id"])
    dump_json(out_dir / "02_list_rule_job.json", list_rule_job_result)

    list_rule = extract_llm_result_object(list_rule_job_result)
    dump_json(out_dir / "03_list_rule.json", list_rule)

    if "list_extraction" not in list_rule:
        raise Crawl4AIError(f"LLM list_rule invalid: {list_rule}")

    list_schema = site_spec_list_to_crawl_schema(list_rule)
    dump_json(out_dir / "04_list_schema_for_crawl.json", list_schema)
    return list_rule, list_schema

def run_step_3_list_validation(
    client: Crawl4AIClient, list_url: str, list_schema: dict, list_rule: dict, out_dir: Path
) -> tuple[List[dict], dict]:
    client.logger.info("=== [Step 3] 验证列表级抓取 ===")
    crawl_list_job = client.submit_crawl_job(
        urls=[list_url],
        extraction_schema=list_schema,
        cache_mode="bypass",
    )
    crawl_list_job_result = client.wait_job(crawl_list_job["task_id"])
    dump_json(out_dir / "05_list_crawl_job.json", crawl_list_job_result)

    list_items = extract_list_items_from_job(crawl_list_job_result, list_url)
    dump_json(out_dir / "06_list_items.json", list_items)

    validation = score_list_rule_and_items(list_rule, list_items)
    dump_json(out_dir / "07_list_validation.json", validation)

    client.logger.info("List validation score=%s passed=%s", validation["score"], validation["passed"])
    if validation["reasons"]:
        for reason in validation["reasons"]:
            client.logger.warning("Validation note: %s", reason)

    if not list_items:
        raise Crawl4AIError(
            "列表规则验证失败：没有抽到任何 list items。"
            "请先检查 03_list_rule.json 和 05_list_crawl_job.json。"
        )
    return list_items, validation

def run_step_4_detail_rule(
    client: Crawl4AIClient, first_url: str, out_dir: Path, llm_provider: str, llm_temperature: float
) -> Optional[dict]:
    client.logger.info("=== [Step 4] 获取详情抽取规则 ===")
    if is_direct_file_url(first_url):
        client.logger.info("First URL is direct file, skip detail rule: %s", first_url)
        return None

    client.logger.info("Discover detail rule for first detail page -> %s", first_url)
    detail_rule_job = client.submit_llm_job(
        url=first_url,
        q=build_detail_rule_prompt(),
        provider=llm_provider,
        schema=DETAIL_RULE_SCHEMA,
        cache=False,
        temperature=llm_temperature,
    )
    detail_rule_job_result = client.wait_job(detail_rule_job["task_id"])
    dump_json(out_dir / "08_detail_rule_job.json", detail_rule_job_result)

    detail_rule = extract_llm_result_object(detail_rule_job_result)
    dump_json(out_dir / "09_detail_rule.json", detail_rule)
    return detail_rule

def run_step_5_detail_validation(client: Crawl4AIClient, first_url: str, out_dir: Path) -> dict:
    client.logger.info("=== [Step 5] 验证详情级抓取 ===")
    if is_direct_file_url(first_url):
        client.logger.info("First URL is direct file, skip detail crawl: %s", first_url)
        detail_sample = {
            "url": first_url,
            "item_type": "direct_file",
            "markdown": "",
            "links": {},
            "extracted_content": None,
        }
        dump_json(out_dir / "11_detail_sample.json", detail_sample)
        return detail_sample

    detail_crawl_job = client.submit_crawl_job(
        urls=[first_url],
        extraction_schema=None,
        cache_mode="bypass",
    )
    detail_crawl_job_result = client.wait_job(detail_crawl_job["task_id"])
    dump_json(out_dir / "10_detail_crawl_job.json", detail_crawl_job_result)

    detail_payload = extract_crawl_result_object(detail_crawl_job_result)
    detail_sample = {
        "url": first_url,
        "item_type": "html_detail",
        "markdown": detail_payload.get("markdown", ""),
        "links": detail_payload.get("links", {}),
        "extracted_content": detail_payload.get("extracted_content"),
    }
    dump_json(out_dir / "11_detail_sample.json", detail_sample)
    return detail_sample

def run_step_6_build_spec(
    client: Crawl4AIClient, list_url: str, list_rule: dict, detail_rule: Optional[dict], out_dir: Path
) -> dict:
    client.logger.info("=== [Step 6] 组装 site_spec ===")
    site_spec = build_site_spec(list_url, list_rule, detail_rule)
    dump_json(out_dir / "12_site_spec.json", site_spec)
    return site_spec


def discover_site_spec(
    client: Crawl4AIClient,
    *,
    list_url: str,
    out_dir: Path,
    llm_provider: str = "openai/gpt-5-mini",
    llm_temperature: float = 0.8,
    run_step: str = "all",
    locator_hint: Optional[str] = None,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    
    final_result: Dict[str, Any] = {}

    if run_step in ["all", "1"]:
        html_data = run_step_1_html(client, list_url, out_dir)
        final_result["html_sample"] = html_data

    if run_step in ["all", "2"]:
        list_rule, list_schema = run_step_2_list_rule(client, list_url, out_dir, llm_provider, llm_temperature, locator_hint)
        final_result["list_rule"] = list_rule
        final_result["list_schema_for_crawl"] = list_schema

    if run_step in ["all", "3"]:
        if run_step != "all":
            list_rule = load_json(out_dir / "03_list_rule.json")
            list_schema = load_json(out_dir / "04_list_schema_for_crawl.json")
        list_items, validation = run_step_3_list_validation(client, list_url, list_schema, list_rule, out_dir)
        final_result["list_items_sample"] = list_items[:5]
        final_result["list_validation"] = validation

    if run_step in ["all", "4"]:
        if run_step != "all":
            list_items = load_json(out_dir / "06_list_items.json")
            if not list_items:
                raise Crawl4AIError("列表项为空，无法继续后续步骤")
        first_url = list_items[0].get("url", "")
        if not first_url:
            raise Crawl4AIError(f"第一条列表项没有 url：{list_items[0]}")
        detail_rule = run_step_4_detail_rule(client, first_url, out_dir, llm_provider, llm_temperature)
        final_result["detail_rule"] = detail_rule

    if run_step in ["all", "5"]:
        if run_step != "all":
            list_items = load_json(out_dir / "06_list_items.json")
            first_url = list_items[0].get("url", "")
        detail_sample = run_step_5_detail_validation(client, first_url, out_dir)
        final_result["detail_sample"] = detail_sample

    if run_step in ["all", "6"]:
        if run_step != "all":
            list_rule = load_json(out_dir / "03_list_rule.json")
            try:
                detail_rule = load_json(out_dir / "09_detail_rule.json")
            except Exception:
                detail_rule = None
        site_spec = run_step_6_build_spec(client, list_url, list_rule, detail_rule, out_dir)
        final_result["site_spec"] = site_spec
        
        dump_json(out_dir / "13_final_result.json", final_result)

    return final_result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crawl4AI site_spec discovery tester")
    parser.add_argument("--base-url", required=True, help="Crawl4AI base url")
    parser.add_argument("--list-url", required=True, help="List page URL")
    parser.add_argument("--provider", default="openai/gpt-5-mini", help="LLM provider")
    parser.add_argument("--temperature", type=float, default=0.2, help="LLM temperature")
    parser.add_argument("--api-token", default=None, help="Optional auth token")
    parser.add_argument("--out-dir", default="./out", help="Directory to save debug files")
    parser.add_argument("--timeout", type=int, default=180, help="HTTP timeout")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--step", default="all", choices=["all", "1", "2", "3", "4", "5", "6"], help="Run specific step or all")
    parser.add_argument("--list-locator", default=None, help="人工提供的列表定位提示 (CSS/XPath)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logger = setup_logger(debug=args.debug)

    logger.info("Start site_spec discovery")
    logger.info("base_url=%s", args.base_url)
    logger.info("list_url=%s", args.list_url)
    logger.info("provider=%s", args.provider)
    logger.info("out_dir=%s", args.out_dir)
    logger.info("step=%s", args.step)
    if args.list_locator:
        logger.info("list_locator=%s", args.list_locator)

    client = Crawl4AIClient(
        base_url=args.base_url,
        logger=logger,
        timeout=args.timeout,
        api_token=args.api_token,
    )

    client.health_check()

    out_dir = Path(args.out_dir)

    try:
        result = discover_site_spec(
            client,
            list_url=args.list_url,
            out_dir=out_dir,
            llm_provider=args.provider,
            llm_temperature=args.temperature,
            run_step=args.step,
            locator_hint=args.list_locator,
        )
    except Exception as e:
        logger.exception("FAILED: %s", e)
        dump_json(out_dir / "99_error.json", {"error": str(e), "type": e.__class__.__name__})
        return 1

    logger.info("SUCCESS")
    
    if args.step in ["all", "6"]:
        logger.info("Final site_spec saved to: %s", out_dir / "12_site_spec.json")
    if args.step in ["all", "3"]:
        logger.info("List items sample saved to: %s", out_dir / "06_list_items.json")
    if args.step in ["all", "6"]:
        logger.info("Final merged result saved to: %s", out_dir / "13_final_result.json")

    if "site_spec" in result:
        print("\n===== site_spec =====")
        print(json.dumps(result["site_spec"], ensure_ascii=False, indent=2))

    if "list_validation" in result:
        print("\n===== list_validation =====")
        print(json.dumps(result["list_validation"], ensure_ascii=False, indent=2))

    if "list_items_sample" in result:
        print("\n===== list_items_sample =====")
        print(json.dumps(result["list_items_sample"], ensure_ascii=False, indent=2))

    if result.get("detail_sample"):
        print("\n===== detail_sample =====")
        print(json.dumps(result["detail_sample"], ensure_ascii=False, indent=2)[:4000])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
