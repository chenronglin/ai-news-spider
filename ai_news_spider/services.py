from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable
from urllib.parse import urlparse

from ai_news_spider.config import Settings
from ai_news_spider.crawler import CrawlClient
from ai_news_spider.db import Database
from ai_news_spider.llm import SiteSpecGenerator
from ai_news_spider.models import RunInput, RunnerResult, SiteSpec
from ai_news_spider.runner import CandidateRunner

logger = logging.getLogger(__name__)

TASK_CREATE_SITE_PREVIEW = "create_site_preview"
TASK_REGENERATE_VERSION_PREVIEW = "regenerate_version_preview"
TASK_RUN_SITE_PROD = "run_site_prod"
TASK_RUN_ALL_SITES_PROD = "run_all_sites_prod"
TASK_FETCH_ARTICLE_DETAILS = "fetch_article_details"

TASK_PENDING = "pending"
TASK_RUNNING = "running"
TASK_SUCCEEDED = "succeeded"
TASK_FAILED = "failed"
TASK_CANCELLED = "cancelled"

SITE_STATUSES = {"draft", "active"}
TASK_TYPES = {
    TASK_CREATE_SITE_PREVIEW,
    TASK_REGENERATE_VERSION_PREVIEW,
    TASK_RUN_SITE_PROD,
    TASK_RUN_ALL_SITES_PROD,
    TASK_FETCH_ARTICLE_DETAILS,
}


def parse_json_field(payload: str | None, *, fallback: Any) -> Any:
    if not payload:
        return fallback
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return fallback


def summarize_spec(spec_json: dict[str, Any]) -> dict[str, Any]:
    expected_fields = (
        "site_name",
        "requires_js",
        "list_item_selector",
        "title_selector",
        "link_selector",
        "date_selector",
        "pagination_mode",
        "next_page_selector",
        "max_pages_default",
        "detail_enabled",
        "detail_requires_js",
        "detail_wait_for",
    )
    return {
        field: spec_json.get(field) for field in expected_fields if field in spec_json
    }


@dataclass(slots=True)
class ServiceContainer:
    site_service: "SiteService"
    version_service: "VersionService"
    run_service: "RunService"
    article_service: "ArticleService"
    detail_service: "DetailService"
    task_service: "TaskService"
    system_service: "SystemService"
    task_executor: "TaskExecutor"


class GenerationService:
    def __init__(
        self,
        *,
        crawler: CrawlClient,
        db: Database,
        spec_generator: SiteSpecGenerator,
        runner: CandidateRunner,
        run_service: "RunService",
    ) -> None:
        self.crawler = crawler
        self.db = db
        self.spec_generator = spec_generator
        self.runner = runner
        self.run_service = run_service

    async def create_site_preview(
        self,
        seed_url: str,
        *,
        list_locator_hint: str | None = None,
    ) -> dict[str, Any]:
        logger.info(
            "Create site preview workflow start seed_url=%s list_locator_hint=%s",
            seed_url,
            list_locator_hint,
        )
        site: dict[str, Any] | None = None
        version: dict[str, Any] | None = None
        try:
            sample = await self.crawler.fetch_sample(seed_url)
            site_name = sample.title.strip() or sample.final_url
            site = await self.db.upsert_site(seed_url, site_name, list_locator_hint)
            version = await self.db.create_version(site["id"])
            spec = await self.spec_generator.generate(
                sample,
                site_name=site_name,
                list_locator_hint=list_locator_hint,
            )
            script_code = self.runner.render_script(spec)
            await self.db.update_version_assets(
                version["id"],
                spec_json=spec.model_dump(mode="json"),
                script_code=script_code,
            )
            version = await self.db.get_version(version["id"])
            run_result = await self.run_service.run_version(
                site,
                version,
                run_type="preview",
            )
            return {
                "site_id": site["id"],
                "version_id": version["id"],
                "run_id": run_result["run_id"],
                "status": run_result["status"],
                "error_log": run_result.get("error_log", ""),
            }
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Create site preview workflow failed seed_url=%s", seed_url
            )
            fallback_name = urlparse(seed_url).netloc
            if site is None:
                site = await self.db.upsert_site(
                    seed_url, fallback_name, list_locator_hint
                )
            if version is None:
                version = await self.db.create_version(site["id"])
            await self.db.update_version_assets(
                version["id"],
                spec_json={"generation_error": str(exc)},
                script_code="",
            )
            run_result = await self.run_service.record_failed_run(
                site["id"],
                version["id"],
                run_type="preview",
                stop_reason="generation_failed",
                error_log=str(exc),
            )
            return {
                "site_id": site["id"],
                "version_id": version["id"],
                "run_id": run_result["run_id"],
                "status": TASK_FAILED,
                "error_log": str(exc),
            }

    async def regenerate_version_preview(
        self,
        version_id: int,
        *,
        list_locator_hint: str,
    ) -> dict[str, Any]:
        logger.info(
            "Regenerate version preview workflow start version_id=%s list_locator_hint=%s",
            version_id,
            list_locator_hint,
        )
        if not list_locator_hint.strip():
            raise RuntimeError("再次生成时必须填写列表定位器。")

        previous_version = await self.db.get_version(version_id)
        if not previous_version:
            raise RuntimeError("版本不存在。")
        site = await self.db.get_site(previous_version["site_id"])
        latest_run = await self.db.latest_run_for_version(version_id)
        locator_hint = list_locator_hint.strip()
        await self.db.update_site_notes(site["id"], locator_hint)
        await self.db.record_feedback(
            site["id"],
            version_id,
            latest_run["id"] if latest_run else None,
            locator_hint,
        )
        new_version = await self.db.create_version(
            site["id"],
            feedback_text=locator_hint,
        )
        try:
            sample = await self.crawler.fetch_sample(site["seed_url"])
            previous_spec = parse_json_field(previous_version["spec_json"], fallback={})
            previous_run_result = (
                parse_json_field(latest_run["result_json"], fallback={})
                if latest_run
                else None
            )
            spec = await self.spec_generator.generate(
                sample,
                site_name=site["name"],
                list_locator_hint=locator_hint,
                feedback=locator_hint,
                previous_spec=previous_spec,
                previous_run_result=previous_run_result,
            )
            script_code = self.runner.render_script(spec)
            await self.db.update_version_assets(
                new_version["id"],
                spec_json=spec.model_dump(mode="json"),
                script_code=script_code,
            )
            new_version = await self.db.get_version(new_version["id"])
            run_result = await self.run_service.run_version(
                site,
                new_version,
                run_type="preview",
            )
            return {
                "site_id": site["id"],
                "version_id": new_version["id"],
                "run_id": run_result["run_id"],
                "status": run_result["status"],
                "error_log": run_result.get("error_log", ""),
            }
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Regenerate version preview workflow failed version_id=%s", version_id
            )
            await self.db.update_version_assets(
                new_version["id"],
                spec_json={"generation_error": str(exc)},
                script_code="",
            )
            run_result = await self.run_service.record_failed_run(
                site["id"],
                new_version["id"],
                run_type="preview",
                stop_reason="generation_failed",
                error_log=str(exc),
            )
            return {
                "site_id": site["id"],
                "version_id": new_version["id"],
                "run_id": run_result["run_id"],
                "status": TASK_FAILED,
                "error_log": str(exc),
            }


class RunService:
    def __init__(
        self,
        *,
        db: Database,
        runner: CandidateRunner,
    ) -> None:
        self.db = db
        self.runner = runner

    async def record_failed_run(
        self,
        site_id: int,
        version_id: int,
        *,
        run_type: str,
        stop_reason: str,
        error_log: str,
    ) -> dict[str, Any]:
        run = await self.db.create_run(site_id, version_id, run_type)
        error_result = RunnerResult()
        error_result.stats.stop_reason = stop_reason
        await self.db.complete_run(
            run["id"],
            status=TASK_FAILED,
            stats_json=error_result.stats.model_dump(mode="json"),
            result_json=error_result.model_dump(mode="json"),
            error_log=error_log,
        )
        return {
            "site_id": site_id,
            "version_id": version_id,
            "run_id": run["id"],
            "status": TASK_FAILED,
            "error_log": error_log,
        }

    async def run_site(self, site_id: int, *, run_type: str = "prod") -> dict[str, Any]:
        site = await self.db.get_site(site_id)
        if not site:
            raise RuntimeError("站点不存在。")
        version = await self.db.get_approved_version_for_site(site_id)
        if version is None:
            raise RuntimeError("当前站点还没有已审核通过的正式版本。")
        return await self.run_version(site, version, run_type=run_type)

    async def run_all_sites(self) -> dict[str, Any]:
        sites = await self.db.list_approved_sites()
        logger.info("Run all approved sites batch start site_count=%s", len(sites))
        run_ids: list[int] = []
        succeeded_count = 0
        failed_count = 0
        for site in sites:
            try:
                result = await self.run_site(site["id"], run_type="prod")
                run_ids.append(result["run_id"])
                if result["status"] == TASK_SUCCEEDED:
                    succeeded_count += 1
                else:
                    failed_count += 1
            except Exception:  # noqa: BLE001
                logger.exception(
                    "Run approved site failed in batch site_id=%s", site["id"]
                )
                failed_count += 1
        logger.info(
            "Run all approved sites batch completed site_count=%s succeeded=%s failed=%s",
            len(sites),
            succeeded_count,
            failed_count,
        )
        return {
            "site_count": len(sites),
            "succeeded_count": succeeded_count,
            "failed_count": failed_count,
            "run_ids": run_ids,
        }

    async def run_version(
        self,
        site: dict[str, Any],
        version: dict[str, Any],
        *,
        run_type: str,
    ) -> dict[str, Any]:
        logger.info(
            "Run version start site_id=%s version_id=%s run_type=%s",
            site["id"],
            version["id"],
            run_type,
        )
        run = await self.db.create_run(site["id"], version["id"], run_type)
        try:
            spec_data = parse_json_field(version["spec_json"], fallback={})
            spec = SiteSpec.model_validate(spec_data)
            max_days = 3650 if run_type == "preview" else 10
            max_pages = 3 if run_type == "preview" else 30
            checkpoint = (
                []
                if run_type == "preview"
                else await self.db.get_existing_canonical_urls(site["id"])
            )
            payload = RunInput(
                seed_url=site["seed_url"],
                site_id=site["id"],
                max_days=max_days,
                max_pages=max_pages,
                run_type=run_type,
                last_seen_checkpoint=checkpoint,
            ).model_dump(mode="json")
            execution = await self.runner.run(spec, payload)
            result = RunnerResult.model_validate(execution.result)
            if run_type == "prod":
                inserted, duplicated = await self.db.upsert_article_items(
                    site["id"],
                    run["id"],
                    [item.model_dump(mode="json") for item in result.items],
                )
                result.stats.items_new = inserted
                result.stats.items_duplicate = duplicated
            await self.db.complete_run(
                run["id"],
                status=TASK_SUCCEEDED,
                stats_json=result.stats.model_dump(mode="json"),
                result_json=result.model_dump(mode="json"),
                error_log=execution.stderr,
            )
            return {
                "site_id": site["id"],
                "version_id": version["id"],
                "run_id": run["id"],
                "status": TASK_SUCCEEDED,
                "error_log": execution.stderr,
            }
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Run version failed site_id=%s version_id=%s run_type=%s",
                site["id"],
                version["id"],
                run_type,
            )
            error_result = RunnerResult()
            error_result.stats.stop_reason = "run_failed"
            await self.db.complete_run(
                run["id"],
                status=TASK_FAILED,
                stats_json=error_result.stats.model_dump(mode="json"),
                result_json=error_result.model_dump(mode="json"),
                error_log=str(exc),
            )
            return {
                "site_id": site["id"],
                "version_id": version["id"],
                "run_id": run["id"],
                "status": TASK_FAILED,
                "error_log": str(exc),
            }

    async def list_runs(
        self,
        *,
        site_id: int | None = None,
        version_id: int | None = None,
        run_type: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        rows, total, current_page, current_page_size = await self.db.list_runs(
            site_id=site_id,
            version_id=version_id,
            run_type=run_type,
            status=status,
            page=page,
            page_size=page_size,
        )
        return {
            "items": [self._serialize_run_summary(row) for row in rows],
            "total": total,
            "page": current_page,
            "page_size": current_page_size,
        }

    async def get_run_detail(self, run_id: int) -> dict[str, Any]:
        detail = await self.db.get_run_detail(run_id)
        if not detail:
            return {}
        stats = parse_json_field(detail.get("stats_json"), fallback={})
        result = parse_json_field(detail.get("result_json"), fallback={})
        spec_json = parse_json_field(detail.get("spec_json"), fallback={})
        return {
            "id": detail["id"],
            "site_id": detail["site_id"],
            "site_name": detail["site_name"],
            "seed_url": detail["seed_url"],
            "site_notes": detail["site_notes"],
            "version_id": detail["version_id"],
            "version_no": detail["version_no"],
            "version_status": detail["version_status"],
            "run_type": detail["run_type"],
            "status": detail["status"],
            "started_at": detail["started_at"],
            "finished_at": detail["finished_at"],
            "error_log": detail["error_log"],
            "stats": stats,
            "result": result,
            "spec_json": spec_json,
            "spec_summary": summarize_spec(spec_json),
        }

    def _serialize_run_summary(self, row: dict[str, Any]) -> dict[str, Any]:
        stats = parse_json_field(row.get("stats_json"), fallback={})
        return {
            "id": row["id"],
            "site_id": row["site_id"],
            "site_name": row.get("site_name"),
            "version_id": row["version_id"],
            "version_no": row.get("version_no"),
            "run_type": row["run_type"],
            "status": row["status"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "stop_reason": stats.get("stop_reason"),
            "items_found": stats.get("items_found", 0),
            "items_new": stats.get("items_new", 0),
            "items_duplicate": stats.get("items_duplicate", 0),
        }


class SiteService:
    def __init__(
        self,
        *,
        db: Database,
        run_service: RunService,
    ) -> None:
        self.db = db
        self.run_service = run_service

    async def list_sites(
        self,
        *,
        status: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        rows, total, current_page, current_page_size = await self.db.list_sites(
            status=status,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
        return {
            "items": [self._serialize_site_summary(row) for row in rows],
            "total": total,
            "page": current_page,
            "page_size": current_page_size,
        }

    async def get_site_detail(self, site_id: int) -> dict[str, Any]:
        site = await self.db.get_site(site_id)
        if not site:
            return {}
        approved_version = await self.db.get_approved_version_for_site(site_id)
        latest_run = await self.db.get_latest_run_for_site(site_id)
        versions = await self.db.list_versions_for_site(site_id, page=1, page_size=10)
        runs = await self.run_service.list_runs(site_id=site_id, page=1, page_size=10)
        article_count = await self.db.count_articles_for_site(site_id)
        return {
            "id": site["id"],
            "name": site["name"],
            "domain": site["domain"],
            "seed_url": site["seed_url"],
            "status": site["status"],
            "approved_version_id": site["approved_version_id"],
            "notes": site["notes"],
            "created_at": site["created_at"],
            "article_count": article_count,
            "approved_version": (
                VersionService.serialize_version_summary(approved_version)
                if approved_version
                else None
            ),
            "latest_run": (
                self.run_service._serialize_run_summary(latest_run)
                if latest_run
                else None
            ),
            "recent_versions": [
                VersionService.serialize_version_summary(row) for row in versions[0]
            ],
            "recent_runs": runs["items"],
        }

    async def update_site(
        self,
        site_id: int,
        *,
        name: str | None = None,
        notes: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        if status is not None and status not in SITE_STATUSES:
            raise RuntimeError("site status 仅支持 draft 或 active。")
        updated = await self.db.update_site(
            site_id,
            name=name,
            notes=notes,
            status=status,
        )
        return updated

    def _serialize_site_summary(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "domain": row["domain"],
            "seed_url": row["seed_url"],
            "status": row["status"],
            "approved_version_id": row["approved_version_id"],
            "approved_version_no": row.get("approved_version_no"),
            "notes": row["notes"],
            "created_at": row["created_at"],
            "last_run_at": row.get("last_run_at"),
            "last_run_status": row.get("last_run_status"),
            "recent_error": row.get("recent_error"),
            "article_count": row.get("article_count", 0),
            "today_new_count": row.get("today_new_count", 0),
        }


class VersionService:
    def __init__(
        self,
        *,
        db: Database,
        scheduler_refresh: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self.db = db
        self.scheduler_refresh = scheduler_refresh

    async def list_versions_for_site(
        self,
        site_id: int,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        (
            rows,
            total,
            current_page,
            current_page_size,
        ) = await self.db.list_versions_for_site(
            site_id,
            page=page,
            page_size=page_size,
        )
        return {
            "items": [self.serialize_version_summary(row) for row in rows],
            "total": total,
            "page": current_page,
            "page_size": current_page_size,
        }

    async def get_version_detail(self, version_id: int) -> dict[str, Any]:
        version = await self.db.get_version(version_id)
        if not version:
            return {}
        latest_run = await self.db.latest_run_for_version(version_id)
        spec_json = parse_json_field(version.get("spec_json"), fallback={})
        return {
            "id": version["id"],
            "site_id": version["site_id"],
            "version_no": version["version_no"],
            "status": version["status"],
            "feedback_text": version["feedback_text"],
            "created_at": version["created_at"],
            "spec_json": spec_json,
            "spec_summary": summarize_spec(spec_json),
            "script_code": version["script_code"],
            "latest_run": self._serialize_latest_run(latest_run),
        }

    async def approve_version(self, version_id: int) -> dict[str, Any]:
        version = await self.db.approve_version(version_id)
        if self.scheduler_refresh:
            await self.scheduler_refresh()
        site = await self.db.get_site(version["site_id"])
        return {
            "version": self.serialize_version_summary(version),
            "site": {
                "id": site["id"],
                "status": site["status"],
                "approved_version_id": site["approved_version_id"],
            },
        }

    @staticmethod
    def serialize_version_summary(version: dict[str, Any]) -> dict[str, Any]:
        if not version:
            return {}
        spec_json = parse_json_field(version.get("spec_json"), fallback={})
        return {
            "id": version["id"],
            "site_id": version["site_id"],
            "version_no": version["version_no"],
            "status": version["status"],
            "feedback_text": version.get("feedback_text"),
            "created_at": version["created_at"],
            "spec_summary": summarize_spec(spec_json),
            "latest_run_id": version.get("latest_run_id"),
            "latest_run_status": version.get("latest_run_status"),
            "latest_run_finished_at": version.get("latest_run_finished_at"),
        }

    def _serialize_latest_run(
        self, latest_run: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        if latest_run is None:
            return None
        stats = parse_json_field(latest_run.get("stats_json"), fallback={})
        return {
            "id": latest_run["id"],
            "run_type": latest_run["run_type"],
            "status": latest_run["status"],
            "started_at": latest_run["started_at"],
            "finished_at": latest_run["finished_at"],
            "stop_reason": stats.get("stop_reason"),
            "items_found": stats.get("items_found", 0),
        }


class ArticleService:
    def __init__(self, *, db: Database) -> None:
        self.db = db

    async def list_articles(
        self,
        *,
        site_id: int | None = None,
        run_id: int | None = None,
        title: str | None = None,
        keyword: str | None = None,
        source_list_url: str | None = None,
        detail_status: str | None = None,
        published_from: str | None = None,
        published_to: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        (
            rows,
            total,
            current_page,
            current_page_size,
        ) = await self.db.list_articles(
            site_id=site_id,
            run_id=run_id,
            title=title,
            keyword=keyword,
            source_list_url=source_list_url,
            detail_status=detail_status,
            published_from=published_from,
            published_to=published_to,
            page=page,
            page_size=page_size,
        )
        return {
            "items": [self._serialize_article(row) for row in rows],
            "total": total,
            "page": current_page,
            "page_size": current_page_size,
        }

    async def list_articles_for_site(
        self,
        site_id: int,
        *,
        run_id: int | None = None,
        title: str | None = None,
        published_from: str | None = None,
        published_to: str | None = None,
        keyword: str | None = None,
        source_list_url: str | None = None,
        detail_status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        (
            rows,
            total,
            current_page,
            current_page_size,
        ) = await self.db.list_articles_for_site(
            site_id,
            run_id=run_id,
            title=title,
            published_from=published_from,
            published_to=published_to,
            keyword=keyword,
            source_list_url=source_list_url,
            detail_status=detail_status,
            page=page,
            page_size=page_size,
        )
        return {
            "items": [self._serialize_article(row) for row in rows],
            "total": total,
            "page": current_page,
            "page_size": current_page_size,
        }

    def _serialize_article(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "site_id": row["site_id"],
            "site_name": row.get("site_name"),
            "title": row["title"],
            "url": row["url"],
            "url_canonical": row["url_canonical"],
            "published_at": row["published_at"],
            "source_list_url": row["source_list_url"],
            "first_seen_at": row["first_seen_at"],
            "last_seen_at": row["last_seen_at"],
            "run_id": row["run_id"],
            "detail_status": row.get("detail_status") or "none",
            "detail_requested_at": row.get("detail_requested_at"),
            "detail_fetched_at": row.get("detail_fetched_at"),
            "detail_error": row.get("detail_error") or "",
            "has_detail": bool(row.get("has_detail")),
        }


class DetailService:
    def __init__(
        self,
        *,
        db: Database,
        crawler: CrawlClient,
    ) -> None:
        self.db = db
        self.crawler = crawler

    async def mark_articles_pending(
        self,
        article_ids: list[int],
        *,
        force_refetch: bool = False,
    ) -> dict[str, Any]:
        article_ids = [int(article_id) for article_id in article_ids]
        if not article_ids:
            raise RuntimeError("article_ids 不能为空。")
        result = await self.db.mark_articles_detail_pending(
            article_ids,
            force_refetch=force_refetch,
        )
        result["requested_count"] = len(article_ids)
        return result

    async def validate_pending_articles(
        self,
        article_ids: list[int],
    ) -> list[int]:
        normalized_ids = [int(article_id) for article_id in article_ids]
        if not normalized_ids:
            raise RuntimeError("article_ids 不能为空。")
        pending_ids = await self.db.get_pending_detail_article_ids(normalized_ids)
        if not pending_ids:
            raise RuntimeError("没有处于 pending 状态的文章可用于详情抓取。")
        return pending_ids

    async def get_article_detail(self, article_id: int) -> dict[str, Any]:
        detail = await self.db.get_article_detail(article_id)
        if not detail or not detail.get("content_html"):
            return {}
        return {
            "article_id": detail["article_id"],
            "site_id": detail["site_id"],
            "site_name": detail["site_name"],
            "title": detail["title"],
            "source_url": detail["source_url"],
            "final_url": detail["final_url"],
            "detail_status": detail["detail_status"],
            "detail_requested_at": detail["detail_requested_at"],
            "detail_fetched_at": detail["detail_fetched_at"],
            "detail_error": detail["detail_error"],
            "content_html": detail["content_html"],
            "content_markdown": detail["content_markdown"],
            "fetched_at": detail["fetched_at"],
            "updated_at": detail["updated_at"],
        }

    async def fetch_article_details(
        self,
        *,
        article_ids: list[int],
        force_refetch: bool = False,
    ) -> dict[str, Any]:
        running_ids = await self.db.mark_articles_detail_running(article_ids)
        if not running_ids:
            return {
                "article_ids": article_ids,
                "processed_count": 0,
                "succeeded_count": 0,
                "failed_count": 0,
                "skipped_ids": article_ids,
                "succeeded_ids": [],
                "failed_ids": [],
                "status": TASK_SUCCEEDED,
            }

        articles = await self.db.get_article_items_by_ids(running_ids)
        site_specs: dict[int, SiteSpec] = {}
        succeeded_ids: list[int] = []
        failed_ids: list[int] = []
        skipped_ids: list[int] = []

        for article in articles:
            article_id = int(article["id"])
            current_status = article.get("detail_status") or "none"
            if current_status == "succeeded" and not force_refetch:
                skipped_ids.append(article_id)
                continue

            site_id = int(article["site_id"])
            if site_id not in site_specs:
                version = await self.db.get_approved_version_for_site(site_id)
                if version is None:
                    await self.db.mark_article_detail_failed(
                        article_id,
                        "站点没有可用的正式版本，无法抓取详情页。",
                    )
                    failed_ids.append(article_id)
                    continue
                spec = SiteSpec.model_validate(
                    parse_json_field(version["spec_json"], fallback={})
                )
                site_specs[site_id] = spec

            spec = site_specs[site_id]
            if not spec.detail_enabled:
                await self.db.mark_article_detail_failed(
                    article_id,
                    "当前版本未启用详情页抓取。",
                )
                failed_ids.append(article_id)
                continue

            try:
                html, markdown, final_url = await self.crawler.fetch_detail_content(
                    article["url"],
                    requires_js=bool(spec.detail_requires_js),
                    wait_for=spec.detail_wait_for,
                )
                await self.db.upsert_article_detail(
                    article_item_id=article_id,
                    site_id=site_id,
                    source_url=article["url"],
                    final_url=final_url,
                    content_html=html,
                    content_markdown=markdown,
                )
                await self.db.mark_article_detail_succeeded(article_id)
                succeeded_ids.append(article_id)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Fetch article detail failed article_id=%s", article_id)
                await self.db.mark_article_detail_failed(article_id, str(exc))
                failed_ids.append(article_id)

        status = TASK_FAILED if failed_ids and not succeeded_ids else TASK_SUCCEEDED
        return {
            "article_ids": article_ids,
            "processed_count": len(running_ids),
            "succeeded_count": len(succeeded_ids),
            "failed_count": len(failed_ids),
            "skipped_ids": skipped_ids,
            "succeeded_ids": succeeded_ids,
            "failed_ids": failed_ids,
            "status": status,
        }


class TaskService:
    def __init__(
        self,
        *,
        db: Database,
        generation_service: GenerationService,
        run_service: RunService,
        detail_service: DetailService,
    ) -> None:
        self.db = db
        self.generation_service = generation_service
        self.run_service = run_service
        self.detail_service = detail_service
        self._wakeup: Callable[[], None] | None = None

    def bind_wakeup(self, callback: Callable[[], None]) -> None:
        self._wakeup = callback

    def notify(self) -> None:
        if self._wakeup is not None:
            self._wakeup()

    async def prepare_for_startup(self) -> None:
        await self.db.reset_running_tasks_to_pending()

    async def enqueue_create_site_preview(
        self,
        *,
        seed_url: str,
        list_locator_hint: str | None = None,
    ) -> dict[str, Any]:
        task = await self.db.create_task(
            task_type=TASK_CREATE_SITE_PREVIEW,
            params_json={
                "seed_url": seed_url,
                "list_locator_hint": list_locator_hint,
            },
        )
        self.notify()
        return self.serialize_task(task)

    async def enqueue_regenerate_version_preview(
        self,
        *,
        version_id: int,
        list_locator_hint: str,
    ) -> dict[str, Any]:
        task = await self.db.create_task(
            task_type=TASK_REGENERATE_VERSION_PREVIEW,
            params_json={"list_locator_hint": list_locator_hint},
            version_id=version_id,
        )
        self.notify()
        return self.serialize_task(task)

    async def enqueue_run_site_prod(self, *, site_id: int) -> dict[str, Any]:
        task = await self.db.create_task(
            task_type=TASK_RUN_SITE_PROD,
            params_json={},
            site_id=site_id,
        )
        self.notify()
        return self.serialize_task(task)

    async def enqueue_run_all_sites_prod(self) -> dict[str, Any]:
        task = await self.db.create_task(
            task_type=TASK_RUN_ALL_SITES_PROD,
            params_json={},
        )
        self.notify()
        return self.serialize_task(task)

    async def enqueue_fetch_article_details(
        self,
        *,
        article_ids: list[int],
        force_refetch: bool = False,
    ) -> dict[str, Any]:
        task = await self.db.create_task(
            task_type=TASK_FETCH_ARTICLE_DETAILS,
            params_json={
                "article_ids": [int(article_id) for article_id in article_ids],
                "force_refetch": bool(force_refetch),
            },
        )
        self.notify()
        return self.serialize_task(task)

    async def claim_next_task(self) -> dict[str, Any] | None:
        task = await self.db.claim_next_task()
        return self.serialize_task(task) if task else None

    async def execute_claimed_task(self, task: dict[str, Any]) -> dict[str, Any]:
        task_id = task["id"]
        task_type = task["task_type"]
        params = task["params_json"]
        try:
            if task_type == TASK_CREATE_SITE_PREVIEW:
                result = await self.generation_service.create_site_preview(
                    params["seed_url"],
                    list_locator_hint=params.get("list_locator_hint"),
                )
            elif task_type == TASK_REGENERATE_VERSION_PREVIEW:
                result = await self.generation_service.regenerate_version_preview(
                    task["version_id"],
                    list_locator_hint=params["list_locator_hint"],
                )
            elif task_type == TASK_RUN_SITE_PROD:
                result = await self.run_service.run_site(
                    task["site_id"], run_type="prod"
                )
            elif task_type == TASK_RUN_ALL_SITES_PROD:
                result = await self.run_service.run_all_sites()
            elif task_type == TASK_FETCH_ARTICLE_DETAILS:
                result = await self.detail_service.fetch_article_details(
                    article_ids=params.get("article_ids", []),
                    force_refetch=bool(params.get("force_refetch", False)),
                )
            else:
                raise RuntimeError(f"unsupported task type: {task_type}")

            if result.get("status") == TASK_FAILED:
                stored = await self.db.mark_task_failed(
                    task_id,
                    error_log=result.get("error_log", "task failed"),
                    result_json=result,
                    site_id=result.get("site_id"),
                    version_id=result.get("version_id"),
                    run_id=result.get("run_id"),
                )
                return self.serialize_task(stored)

            stored = await self.db.mark_task_succeeded(
                task_id,
                result_json=result,
                site_id=result.get("site_id"),
                version_id=result.get("version_id"),
                run_id=result.get("run_id"),
            )
            return self.serialize_task(stored)
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Task execution failed task_id=%s task_type=%s", task_id, task_type
            )
            stored = await self.db.mark_task_failed(
                task_id,
                error_log=str(exc),
                result_json={},
            )
            return self.serialize_task(stored)

    async def list_tasks(
        self,
        *,
        task_type: str | None = None,
        status: str | None = None,
        site_id: int | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        rows, total, current_page, current_page_size = await self.db.list_tasks(
            task_type=task_type,
            status=status,
            site_id=site_id,
            page=page,
            page_size=page_size,
        )
        return {
            "items": [self.serialize_task(row) for row in rows],
            "total": total,
            "page": current_page,
            "page_size": current_page_size,
        }

    async def get_task(self, task_id: int) -> dict[str, Any]:
        task = await self.db.get_task(task_id)
        return self.serialize_task(task) if task else {}

    async def cancel_task(self, task_id: int) -> dict[str, Any] | None:
        task = await self.db.cancel_task(task_id)
        return self.serialize_task(task) if task else None

    def serialize_task(self, task: dict[str, Any] | None) -> dict[str, Any]:
        if not task:
            return {}
        return {
            "id": task["id"],
            "task_type": task["task_type"],
            "status": task["status"],
            "params_json": parse_json_field(task.get("params_json"), fallback={}),
            "result_json": parse_json_field(task.get("result_json"), fallback={}),
            "error_log": task["error_log"],
            "site_id": task.get("site_id"),
            "version_id": task.get("version_id"),
            "run_id": task.get("run_id"),
            "created_at": task["created_at"],
            "started_at": task.get("started_at"),
            "finished_at": task.get("finished_at"),
        }


class SystemService:
    def __init__(
        self,
        *,
        settings: Settings,
        db: Database,
        scheduler,
    ) -> None:
        self.settings = settings
        self.db = db
        self.scheduler = scheduler

    async def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "database_ok": await self.db.ping(),
            "scheduler": self.scheduler.get_info() if self.scheduler else None,
        }

    def system_info(self) -> dict[str, Any]:
        return {
            "llm_ready": bool(self.settings.base_url and self.settings.api_key),
            "model_name": self.settings.model_name,
            "timezone": self.settings.timezone,
            "scheduler_mode": self.settings.scheduler_mode,
            "scheduler_description": self.settings.scheduler_description(),
            "runtime_dir": str(self.settings.runtime_dir),
            "db_path": str(self.settings.db_path),
        }

    def scheduler_info(self) -> dict[str, Any]:
        if self.scheduler is None:
            return {
                "enabled": False,
                "running": False,
                "job_id": None,
                "next_run_time": None,
                "description": None,
            }
        return self.scheduler.get_info()


class TaskExecutor:
    def __init__(
        self,
        *,
        task_service: TaskService,
        poll_interval: float = 0.5,
    ) -> None:
        self.task_service = task_service
        self.poll_interval = poll_interval
        self._worker: asyncio.Task[None] | None = None
        self._stopped = False
        self._wake_event = asyncio.Event()
        self.task_service.bind_wakeup(self.wake)

    async def start(self) -> None:
        self._stopped = False
        await self.task_service.prepare_for_startup()
        self._worker = asyncio.create_task(self._run_loop())
        self.wake()

    async def stop(self) -> None:
        self._stopped = True
        self.wake()
        if self._worker is not None:
            self._worker.cancel()
            try:
                await self._worker
            except asyncio.CancelledError:
                pass
            self._worker = None

    def wake(self) -> None:
        self._wake_event.set()

    async def _run_loop(self) -> None:
        while not self._stopped:
            task = await self.task_service.claim_next_task()
            if task is None:
                self._wake_event.clear()
                try:
                    await asyncio.wait_for(
                        self._wake_event.wait(),
                        timeout=self.poll_interval,
                    )
                except TimeoutError:
                    continue
                continue
            await self.task_service.execute_claimed_task(task)


def build_services(
    *,
    settings: Settings,
    db: Database,
    crawler: CrawlClient,
    spec_generator: SiteSpecGenerator,
    runner: CandidateRunner,
    scheduler,
) -> ServiceContainer:
    run_service = RunService(db=db, runner=runner)
    detail_service = DetailService(db=db, crawler=crawler)
    generation_service = GenerationService(
        crawler=crawler,
        db=db,
        spec_generator=spec_generator,
        runner=runner,
        run_service=run_service,
    )
    task_service = TaskService(
        db=db,
        generation_service=generation_service,
        run_service=run_service,
        detail_service=detail_service,
    )
    version_service = VersionService(
        db=db,
        scheduler_refresh=scheduler.refresh_jobs if scheduler else None,
    )
    site_service = SiteService(db=db, run_service=run_service)
    article_service = ArticleService(db=db)
    system_service = SystemService(settings=settings, db=db, scheduler=scheduler)
    task_executor = TaskExecutor(task_service=task_service)
    return ServiceContainer(
        site_service=site_service,
        version_service=version_service,
        run_service=run_service,
        article_service=article_service,
        detail_service=detail_service,
        task_service=task_service,
        system_service=system_service,
        task_executor=task_executor,
    )
