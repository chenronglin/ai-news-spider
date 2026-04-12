from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ai_news_spider.api.routes import create_api_router
from ai_news_spider.config import Settings
from ai_news_spider.crawler import CrawlClient
from ai_news_spider.db import Database
from ai_news_spider.llm import OpenAISiteSpecGenerator, SiteSpecGenerator
from ai_news_spider.runner import CandidateRunner
from ai_news_spider.scheduler import CrawlScheduler
from ai_news_spider.services import ServiceContainer, build_services

OPENAPI_TAGS = [
    {
        "name": "系统",
        "description": "服务健康检查、系统配置摘要等全局信息接口。",
    },
    {
        "name": "调度",
        "description": "查看调度器状态，或手动触发全站批量正式运行。",
    },
    {
        "name": "调试工具",
        "description": "调试页面抓取和选择器定位时使用的辅助接口。",
    },
    {
        "name": "站点",
        "description": "站点的创建、更新、详情查看，以及站点下版本、运行记录、文章列表等接口。",
    },
    {
        "name": "版本",
        "description": "规则版本详情、重新生成和审批相关接口。",
    },
    {
        "name": "结果表",
        "description": "对 `article_item` 结果表进行单站或跨站查询、过滤和分页的接口。",
    },
    {
        "name": "运行记录",
        "description": "预览运行和正式运行的列表与详情接口。",
    },
    {
        "name": "异步任务",
        "description": "异步任务的创建结果查询、列表查看和取消操作。",
    },
]


def build_app(
    *,
    settings: Settings | None = None,
    db: Database | None = None,
    spec_generator: SiteSpecGenerator | None = None,
    with_scheduler: bool = True,
) -> FastAPI:
    settings = settings or Settings.from_env()
    settings.ensure_directories()
    db = db or Database(settings.db_path)
    crawler = CrawlClient()
    spec_generator = spec_generator or OpenAISiteSpecGenerator(settings)
    runner = CandidateRunner(settings)

    scheduler = None
    if with_scheduler:
        scheduler = CrawlScheduler(
            settings,
            db,
            run_prod_batch=None,
        )

    services: ServiceContainer = build_services(
        settings=settings,
        db=db,
        crawler=crawler,
        spec_generator=spec_generator,
        runner=runner,
        scheduler=scheduler,
    )
    if scheduler is not None:
        scheduler.run_prod_batch = services.task_service.enqueue_run_all_sites_prod

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await db.init()
        if scheduler:
            scheduler.start()
            await scheduler.refresh_jobs()
        await services.task_executor.start()
        try:
            yield
        finally:
            await services.task_executor.stop()
            if scheduler:
                scheduler.shutdown()

    app = FastAPI(
        title="AI News Spider API",
        summary="新闻列表采集与规则生成后端接口",
        description=(
            "这是一个面向前后端分离架构的新闻列表采集后端服务。"
            "系统支持站点创建、规则生成、预览运行、版本审批、正式运行、批量调度和异步任务轮询。"
            "\n\n"
            "推荐测试流程："
            "\n"
            "1. 调用 `POST /api/v1/sites` 创建站点并生成预览任务。"
            "\n"
            "2. 轮询 `GET /api/v1/tasks/{task_id}` 获取 `site_id`、`version_id`、`run_id`。"
            "\n"
            "3. 使用 `GET /api/v1/runs/{run_id}` 查看预览结果。"
            "\n"
            "4. 如果规则合适，调用 `POST /api/v1/versions/{version_id}/approve` 审批为正式版本。"
            "\n"
            "5. 使用 `POST /api/v1/sites/{site_id}/runs` 或 `POST /api/v1/scheduler/run-now` 触发正式运行。"
            "\n\n"
            "耗时写操作统一采用异步任务机制，接口会返回 `202 Accepted` 和任务 ID。"
        ),
        version="1.0.0",
        openapi_tags=OPENAPI_TAGS,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.settings = settings
    app.state.db = db
    app.state.crawler = crawler
    app.state.services = services
    app.include_router(create_api_router())

    @app.exception_handler(RuntimeError)
    async def runtime_error_handler(_, exc: RuntimeError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    return app
