from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import urlparse

from ai_news_spider.config import Settings
from ai_news_spider.crawler import CrawlClient
from ai_news_spider.db import Database
from ai_news_spider.llm import SiteSpecGenerator
from ai_news_spider.models import RunInput, RunnerResult, SiteSpec
from ai_news_spider.runner import CandidateRunner

logger = logging.getLogger(__name__)


class SpiderService:
    def __init__(
        self,
        settings: Settings,
        db: Database,
        crawler: CrawlClient,
        spec_generator: SiteSpecGenerator,
        runner: CandidateRunner,
    ) -> None:
        self.settings = settings
        self.db = db
        self.crawler = crawler
        self.spec_generator = spec_generator
        self.runner = runner
        self.scheduler = None

    async def create_site_and_preview(
        self,
        seed_url: str,
        *,
        list_locator_hint: str | None = None,
    ) -> int:
        logger.info(
            "Create site and preview start seed_url=%s list_locator_hint=%s",
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
            logger.info("Generated candidate version site_id=%s version_id=%s", site["id"], version["id"])
            return await self.run_version(site, version, run_type="preview")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Create site and preview failed seed_url=%s", seed_url)
            if site is None:
                site = await self.db.upsert_site(
                    seed_url, urlparse(seed_url).netloc, list_locator_hint
                )
            if version is None:
                version = await self.db.create_version(site["id"])
            await self.db.update_version_assets(
                version["id"],
                spec_json={"generation_error": str(exc)},
                script_code="",
            )
            run = await self.db.create_run(site["id"], version["id"], "preview")
            error_result = RunnerResult()
            error_result.stats.stop_reason = "generation_failed"
            await self.db.complete_run(
                run["id"],
                status="failed",
                stats_json=error_result.stats.model_dump(mode="json"),
                result_json=error_result.model_dump(mode="json"),
                error_log=str(exc),
            )
            return run["id"]

    async def regenerate_version(self, version_id: int, list_locator_hint: str) -> int:
        logger.info(
            "Regenerate version start version_id=%s list_locator_hint=%s",
            version_id,
            list_locator_hint,
        )
        if not list_locator_hint.strip():
            raise RuntimeError("再次生成时必须填写列表定位器。")
        version = await self.db.get_version(version_id)
        site = await self.db.get_site(version["site_id"])
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
            site["id"], feedback_text=locator_hint
        )
        try:
            sample = await self.crawler.fetch_sample(site["seed_url"])
            previous_spec = json.loads(version["spec_json"])
            previous_run_result = latest_run and json.loads(latest_run["result_json"])
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
            logger.info("Regenerated candidate version site_id=%s version_id=%s", site["id"], new_version["id"])
            return await self.run_version(site, new_version, run_type="preview")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Regenerate version failed version_id=%s", version_id)
            await self.db.update_version_assets(
                new_version["id"],
                spec_json={"generation_error": str(exc)},
                script_code="",
            )
            run = await self.db.create_run(site["id"], new_version["id"], "preview")
            error_result = RunnerResult()
            error_result.stats.stop_reason = "generation_failed"
            await self.db.complete_run(
                run["id"],
                status="failed",
                stats_json=error_result.stats.model_dump(mode="json"),
                result_json=error_result.model_dump(mode="json"),
                error_log=str(exc),
            )
            return run["id"]

    async def run_site(self, site_id: int, run_type: str = "prod") -> int:
        logger.info("Run site start site_id=%s run_type=%s", site_id, run_type)
        site = await self.db.get_site(site_id)
        version = await self.db.get_approved_version_for_site(site_id)
        if version is None:
            raise RuntimeError("当前站点还没有已审核通过的正式版本。")
        return await self.run_version(site, version, run_type=run_type)

    async def run_all_sites(self) -> None:
        sites = await self.db.list_approved_sites()
        logger.info("Run all approved sites batch start site_count=%s", len(sites))
        for site in sites:
            try:
                await self.run_site(site["id"], run_type="prod")
            except Exception:  # noqa: BLE001
                logger.exception("Run approved site failed in batch site_id=%s", site["id"])
        logger.info("Run all approved sites batch completed site_count=%s", len(sites))

    async def run_version(
        self, site: dict[str, Any], version: dict[str, Any], *, run_type: str
    ) -> int:
        logger.info(
            "Run version start site_id=%s version_id=%s run_type=%s",
            site["id"],
            version["id"],
            run_type,
        )
        spec_data = json.loads(version["spec_json"])
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

        run = await self.db.create_run(site["id"], version["id"], run_type)
        try:
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
                status="succeeded",
                stats_json=result.stats.model_dump(mode="json"),
                result_json=result.model_dump(mode="json"),
                error_log=execution.stderr,
            )
            logger.info(
                "Run version succeeded run_id=%s items_found=%s stop_reason=%s",
                run["id"],
                result.stats.items_found,
                result.stats.stop_reason,
            )
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
                status="failed",
                stats_json=error_result.stats.model_dump(mode="json"),
                result_json=error_result.model_dump(mode="json"),
                error_log=str(exc),
            )
        return run["id"]

    async def approve_version(self, version_id: int) -> None:
        version = await self.db.approve_version(version_id)
        if self.scheduler:
            await self.scheduler.refresh_jobs()
        return version

    async def get_run_detail(self, run_id: int) -> dict[str, Any]:
        return await self.db.get_run_detail(run_id)

    async def list_sites(self) -> list[dict[str, Any]]:
        return await self.db.list_site_summaries()
