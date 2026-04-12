from __future__ import annotations

import pytest

from ai_news_spider.crawler import CrawlClient
from ai_news_spider.db import Database
from ai_news_spider.llm import HeuristicSiteSpecGenerator
from ai_news_spider.runner import CandidateRunner
from ai_news_spider.services import (
    TASK_PENDING,
    TASK_RUN_ALL_SITES_PROD,
    build_services,
)


@pytest.mark.asyncio
async def test_task_service_can_cancel_pending_task(settings, fixture_map) -> None:
    settings.ensure_directories()
    db = Database(settings.db_path)
    await db.init()
    services = build_services(
        settings=settings,
        db=db,
        crawler=CrawlClient(),
        spec_generator=HeuristicSiteSpecGenerator(),
        runner=CandidateRunner(settings),
        scheduler=None,
    )

    task = await services.task_service.enqueue_run_all_sites_prod()
    cancelled = await services.task_service.cancel_task(task["id"])

    assert cancelled is not None
    assert cancelled["status"] == "cancelled"


@pytest.mark.asyncio
async def test_task_service_prepare_for_startup_requeues_running_tasks(
    settings, fixture_map
) -> None:
    settings.ensure_directories()
    db = Database(settings.db_path)
    await db.init()
    services = build_services(
        settings=settings,
        db=db,
        crawler=CrawlClient(),
        spec_generator=HeuristicSiteSpecGenerator(),
        runner=CandidateRunner(settings),
        scheduler=None,
    )

    await db.create_task(task_type=TASK_RUN_ALL_SITES_PROD, params_json={})
    claimed = await db.claim_next_task()
    assert claimed is not None
    assert claimed["status"] == "running"

    await services.task_service.prepare_for_startup()
    task = await services.task_service.get_task(claimed["id"])

    assert task["status"] == TASK_PENDING
