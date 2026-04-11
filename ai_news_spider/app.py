from __future__ import annotations

from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from ai_news_spider.config import Settings
from ai_news_spider.crawler import CrawlClient
from ai_news_spider.db import Database
from ai_news_spider.llm import OpenAISiteSpecGenerator, SiteSpecGenerator
from ai_news_spider.runner import CandidateRunner
from ai_news_spider.scheduler import CrawlScheduler
from ai_news_spider.services import SpiderService


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
    service = SpiderService(settings, db, crawler, spec_generator, runner)
    templates = Jinja2Templates(
        directory=str(settings.base_dir / "ai_news_spider" / "templates")
    )

    scheduler = None
    if with_scheduler:
        scheduler = CrawlScheduler(settings, db, service.run_all_sites)
        service.scheduler = scheduler

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await db.init()
        if scheduler:
            scheduler.start()
            await scheduler.refresh_jobs()
        try:
            yield
        finally:
            if scheduler:
                scheduler.shutdown()

    app = FastAPI(title="AI News Spider", lifespan=lifespan)
    app.state.settings = settings
    app.state.service = service
    app.state.templates = templates

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "llm_ready": bool(settings.base_url and settings.api_key),
                "model_name": settings.model_name,
                "scheduler_description": settings.scheduler_description(),
            },
        )

    @app.get("/tools/url-selector", response_class=HTMLResponse)
    async def url_selector(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "url_selector.html",
            {
                "proxy_endpoint": str(request.url_for("proxy_html")),
            },
        )

    @app.get("/api/proxy/html", response_class=JSONResponse)
    async def proxy_html(url: str, wait_for: str | None = None) -> JSONResponse:
        parsed = urlparse(url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return JSONResponse(
                {"error": "url must be an absolute http/https URL"},
                status_code=400,
            )
        try:
            html, _, _, final_url = await crawler.fetch_html(
                url,
                requires_js=True,
                wait_for=wait_for,
            )
            return JSONResponse(
                {
                    "url": url,
                    "final_url": final_url,
                    "html": html,
                    "rendered_by": "crawl4ai",
                }
            )
        except Exception as exc:  # noqa: BLE001
            return JSONResponse(
                {"error": f"proxy fetch failed: {exc}"},
                status_code=502,
            )

    @app.post("/sites")
    async def create_site(request: Request) -> Response:
        form = await request.form()
        seed_url = str(form.get("seed_url", "")).strip()
        list_locator_hint = str(form.get("list_locator_hint", "")).strip() or None
        try:
            run_id = await service.create_site_and_preview(
                seed_url,
                list_locator_hint=list_locator_hint,
            )
            return RedirectResponse(url=f"/runs/{run_id}", status_code=303)
        except Exception as exc:  # noqa: BLE001
            return templates.TemplateResponse(
                request,
                "index.html",
                {
                    "error": str(exc),
                    "llm_ready": bool(settings.base_url and settings.api_key),
                    "model_name": settings.model_name,
                    "scheduler_description": settings.scheduler_description(),
                },
                status_code=400,
            )

    @app.get("/runs/{run_id}", response_class=HTMLResponse)
    async def run_detail(request: Request, run_id: int) -> HTMLResponse:
        detail = await service.get_run_detail(run_id)
        return templates.TemplateResponse(request, "run.html", {"run": detail})

    @app.post("/versions/{version_id}/approve")
    async def approve_version(version_id: int) -> RedirectResponse:
        await service.approve_version(version_id)
        return RedirectResponse(url="/sites", status_code=303)

    @app.post("/versions/{version_id}/regenerate")
    async def regenerate_version(request: Request, version_id: int) -> RedirectResponse:
        form = await request.form()
        list_locator_hint = str(form.get("list_locator_hint", "")).strip()
        run_id = await service.regenerate_version(version_id, list_locator_hint)
        return RedirectResponse(url=f"/runs/{run_id}", status_code=303)

    @app.get("/sites", response_class=HTMLResponse)
    async def sites(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "sites.html",
            {"sites": await service.list_sites()},
        )

    @app.post("/sites/{site_id}/run")
    async def run_site(site_id: int) -> RedirectResponse:
        run_id = await service.run_site(site_id, run_type="prod")
        return RedirectResponse(url=f"/runs/{run_id}", status_code=303)

    return app
