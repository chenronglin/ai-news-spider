from __future__ import annotations

from secrets import compare_digest
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import Response

from ai_news_spider.api.schemas import (
    ApiError,
    ArticleListResponse,
    ArticleSummary,
    HealthResponse,
    PageMeta,
    ProxyHtmlResponse,
    RegenerateVersionRequest,
    RunDetail,
    RunListResponse,
    RunSummary,
    SchedulerInfo,
    SiteCreateRequest,
    SiteDetail,
    SiteListResponse,
    SiteSummary,
    SiteUpdateRequest,
    SystemInfo,
    TaskAcceptedResponse,
    TaskDetail,
    TaskListResponse,
    TaskSummary,
    VersionApprovalResponse,
    VersionDetail,
    VersionListResponse,
    VersionSummary,
)
from ai_news_spider.services import ServiceContainer

API_TOKEN_HEADER_NAME = "X-API-Token"


def get_services(request: Request) -> ServiceContainer:
    return request.app.state.services


def require_api_token(
    request: Request,
    x_api_token: str | None = Header(default=None, alias=API_TOKEN_HEADER_NAME),
) -> None:
    configured_token = request.app.state.settings.api_token
    if not configured_token:
        raise HTTPException(status_code=503, detail="api token is not configured")
    if x_api_token is None or not compare_digest(x_api_token, configured_token):
        raise HTTPException(status_code=401, detail="invalid api token")


def build_page_meta(payload: dict) -> PageMeta:
    return PageMeta(
        page=payload["page"],
        page_size=payload["page_size"],
        total=payload["total"],
    )


def create_api_router() -> APIRouter:
    public_router = APIRouter(prefix="/api/v1")
    router = APIRouter(dependencies=[Depends(require_api_token)])

    @public_router.get(
        "/health",
        response_model=HealthResponse,
        tags=["系统"],
        summary="健康检查",
        description="检查当前服务实例、数据库连接和调度器的基本状态，用于部署后自检或探针监控。",
    )
    async def health(
        services: ServiceContainer = Depends(get_services),
    ) -> HealthResponse:
        return HealthResponse.model_validate(await services.system_service.health())

    @router.get(
        "/system/info",
        response_model=SystemInfo,
        tags=["系统"],
        summary="获取系统信息",
        description="返回当前后端实例的关键配置摘要，例如模型名、时区、调度模式、运行目录和数据库路径。",
    )
    async def system_info(
        services: ServiceContainer = Depends(get_services),
    ) -> SystemInfo:
        return SystemInfo.model_validate(services.system_service.system_info())

    @router.get(
        "/scheduler",
        response_model=SchedulerInfo,
        tags=["调度"],
        summary="查看调度器状态",
        description="查看 APScheduler 是否启用、是否正在运行、批处理任务 ID 和下次计划执行时间。",
    )
    async def scheduler_info(
        services: ServiceContainer = Depends(get_services),
    ) -> SchedulerInfo:
        return SchedulerInfo.model_validate(services.system_service.scheduler_info())

    @router.post(
        "/scheduler/run-now",
        response_model=TaskAcceptedResponse,
        status_code=status.HTTP_202_ACCEPTED,
        tags=["调度"],
        summary="立即触发批量正式运行",
        description=(
            "为所有已审批站点创建一个 `run_all_sites_prod` 异步任务。"
            "接口不会同步等待执行完成，调用后请轮询任务状态。"
        ),
    )
    async def scheduler_run_now(
        services: ServiceContainer = Depends(get_services),
    ) -> TaskAcceptedResponse:
        task = await services.task_service.enqueue_run_all_sites_prod()
        return TaskAcceptedResponse(
            task_id=task["id"], task=TaskSummary.model_validate(task)
        )

    @router.get(
        "/tools/proxy/html",
        response_model=ProxyHtmlResponse,
        tags=["调试工具"],
        summary="代理抓取页面 HTML",
        description=(
            "使用服务端抓取指定 URL 的 HTML 内容，可选传入 `wait_for`。"
            "该接口主要用于选择器调试、页面结构检查和前端联调。"
        ),
        responses={400: {"model": ApiError}, 502: {"model": ApiError}},
    )
    async def proxy_html(
        request: Request,
        url: str = Query(
            description="需要抓取的目标 URL，必须为绝对的 HTTP/HTTPS 地址。"
        ),
        wait_for: str | None = Query(
            default=None,
            description="可选的页面等待条件，会直接透传给 Crawl4AI。",
        ),
    ) -> ProxyHtmlResponse:
        parsed = urlparse(url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise HTTPException(
                status_code=400,
                detail="url must be an absolute http/https URL",
            )
        crawler = request.app.state.crawler
        try:
            html, _, _, final_url = await crawler.fetch_html(
                url,
                requires_js=True,
                wait_for=wait_for,
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=502, detail=f"proxy fetch failed: {exc}"
            ) from exc
        return ProxyHtmlResponse(
            url=url,
            final_url=final_url,
            html=html,
            rendered_by="crawl4ai",
        )

    @router.get(
        "/sites",
        response_model=SiteListResponse,
        tags=["站点"],
        summary="获取站点列表",
        description="分页查询站点摘要，可按站点状态和关键词过滤，便于前端做站点管理页。",
    )
    async def list_sites(
        status: str | None = Query(
            default=None,
            description="按站点状态过滤，例如 `draft` 或 `active`。",
        ),
        keyword: str | None = Query(
            default=None,
            description="按站点名称、域名或种子 URL 进行模糊搜索。",
        ),
        page: int = Query(default=1, ge=1, description="页码，从 1 开始。"),
        page_size: int = Query(
            default=20,
            ge=1,
            le=100,
            description="每页条数，最大 100。",
        ),
        services: ServiceContainer = Depends(get_services),
    ) -> SiteListResponse:
        payload = await services.site_service.list_sites(
            status=status,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
        return SiteListResponse(
            items=[SiteSummary.model_validate(item) for item in payload["items"]],
            page_meta=build_page_meta(payload),
        )

    @router.post(
        "/sites",
        response_model=TaskAcceptedResponse,
        status_code=status.HTTP_202_ACCEPTED,
        tags=["站点"],
        summary="创建站点并生成预览任务",
        description=(
            "根据新闻列表页 URL 创建或复用站点，并异步执行“抓样本页、生成规则、预览运行”整条链路。"
            "调用成功后返回任务 ID，需要再轮询任务结果获取 `site_id`、`version_id` 和 `run_id`。"
        ),
        responses={400: {"model": ApiError}},
    )
    async def create_site(
        body: SiteCreateRequest,
        services: ServiceContainer = Depends(get_services),
    ) -> TaskAcceptedResponse:
        task = await services.task_service.enqueue_create_site_preview(
            seed_url=str(body.seed_url),
            list_locator_hint=body.list_locator_hint,
        )
        return TaskAcceptedResponse(
            task_id=task["id"], task=TaskSummary.model_validate(task)
        )

    @router.get(
        "/sites/{site_id}",
        response_model=SiteDetail,
        tags=["站点"],
        summary="获取站点详情",
        description=(
            "返回单个站点的聚合详情，包括站点主信息、当前正式版本、最近一次运行、"
            "最近 10 条版本记录和最近 10 条运行记录。"
        ),
        responses={404: {"model": ApiError}},
    )
    async def get_site(
        site_id: int,
        services: ServiceContainer = Depends(get_services),
    ) -> SiteDetail:
        payload = await services.site_service.get_site_detail(site_id)
        if not payload:
            raise HTTPException(status_code=404, detail="site not found")
        return SiteDetail.model_validate(payload)

    @router.patch(
        "/sites/{site_id}",
        response_model=SiteSummary,
        tags=["站点"],
        summary="更新站点信息",
        description="更新站点名称、备注或状态。当前仅允许将状态设置为 `draft` 或 `active`。",
        responses={404: {"model": ApiError}, 400: {"model": ApiError}},
    )
    async def update_site(
        site_id: int,
        body: SiteUpdateRequest,
        services: ServiceContainer = Depends(get_services),
    ) -> SiteSummary:
        try:
            updated = await services.site_service.update_site(
                site_id,
                name=body.name,
                notes=body.notes,
                status=body.status,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not updated:
            raise HTTPException(status_code=404, detail="site not found")
        listing = await services.site_service.list_sites(page=1, page_size=100)
        summary = next(
            (item for item in listing["items"] if item["id"] == site_id), None
        )
        if summary is None:
            raise HTTPException(status_code=404, detail="site not found")
        return SiteSummary.model_validate(summary)

    @router.delete(
        "/sites/{site_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        tags=["站点"],
        summary="删除站点",
        description="删除指定站点及其关联的版本、运行、文章、反馈和任务记录。",
        responses={404: {"model": ApiError}},
    )
    async def delete_site(
        site_id: int,
        services: ServiceContainer = Depends(get_services),
    ) -> Response:
        deleted = await services.site_service.delete_site(site_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="site not found")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.get(
        "/sites/{site_id}/versions",
        response_model=VersionListResponse,
        tags=["站点"],
        summary="获取站点版本列表",
        description="分页查询指定站点下的规则版本记录，通常用于版本管理页或审批历史查看。",
        responses={404: {"model": ApiError}},
    )
    async def list_site_versions(
        site_id: int,
        page: int = Query(default=1, ge=1, description="页码，从 1 开始。"),
        page_size: int = Query(
            default=20,
            ge=1,
            le=100,
            description="每页条数，最大 100。",
        ),
        services: ServiceContainer = Depends(get_services),
    ) -> VersionListResponse:
        if not await services.site_service.get_site_detail(site_id):
            raise HTTPException(status_code=404, detail="site not found")
        payload = await services.version_service.list_versions_for_site(
            site_id,
            page=page,
            page_size=page_size,
        )
        return VersionListResponse(
            items=[VersionSummary.model_validate(item) for item in payload["items"]],
            page_meta=build_page_meta(payload),
        )

    @router.get(
        "/sites/{site_id}/runs",
        response_model=RunListResponse,
        tags=["站点"],
        summary="获取站点运行记录",
        description="分页查询指定站点下的 preview/prod 运行记录，可按运行类型和状态过滤。",
        responses={404: {"model": ApiError}},
    )
    async def list_site_runs(
        site_id: int,
        run_type: str | None = Query(
            default=None,
            description="按运行类型过滤，常见值为 `preview` 或 `prod`。",
        ),
        status: str | None = Query(
            default=None,
            description="按运行状态过滤，例如 `succeeded` 或 `failed`。",
        ),
        page: int = Query(default=1, ge=1, description="页码，从 1 开始。"),
        page_size: int = Query(
            default=20,
            ge=1,
            le=100,
            description="每页条数，最大 100。",
        ),
        services: ServiceContainer = Depends(get_services),
    ) -> RunListResponse:
        if not await services.site_service.get_site_detail(site_id):
            raise HTTPException(status_code=404, detail="site not found")
        payload = await services.run_service.list_runs(
            site_id=site_id,
            run_type=run_type,
            status=status,
            page=page,
            page_size=page_size,
        )
        return RunListResponse(
            items=[RunSummary.model_validate(item) for item in payload["items"]],
            page_meta=build_page_meta(payload),
        )

    @router.get(
        "/articles",
        response_model=ArticleListResponse,
        tags=["结果表"],
        summary="全局查询结果表记录",
        description=(
            "分页查询 `article_item` 结果表，可按站点 ID、运行 ID、标题模糊、通用关键词、"
            "来源列表页和发布时间区间进行过滤。适用于跨站点汇总检索。"
        ),
    )
    async def list_articles(
        site_id: int | None = Query(default=None, description="按站点 ID 过滤。"),
        run_id: int | None = Query(default=None, description="按运行 ID 过滤。"),
        title: str | None = Query(
            default=None,
            description="按标题模糊匹配，适合输入文章标题片段。",
        ),
        keyword: str | None = Query(
            default=None,
            description="通用模糊搜索，同时匹配标题、URL、标准化 URL 和来源列表页。",
        ),
        source_list_url: str | None = Query(
            default=None,
            description="按来源列表页 URL 模糊过滤。",
        ),
        published_from: str | None = Query(
            default=None,
            description="发布时间下界，建议使用 ISO 时间字符串。",
        ),
        published_to: str | None = Query(
            default=None,
            description="发布时间上界，建议使用 ISO 时间字符串。",
        ),
        page: int = Query(default=1, ge=1, description="页码，从 1 开始。"),
        page_size: int = Query(
            default=20,
            ge=1,
            le=100,
            description="每页条数，最大 100。",
        ),
        services: ServiceContainer = Depends(get_services),
    ) -> ArticleListResponse:
        payload = await services.article_service.list_articles(
            site_id=site_id,
            run_id=run_id,
            title=title,
            keyword=keyword,
            source_list_url=source_list_url,
            published_from=published_from,
            published_to=published_to,
            page=page,
            page_size=page_size,
        )
        return ArticleListResponse(
            items=[ArticleSummary.model_validate(item) for item in payload["items"]],
            page_meta=build_page_meta(payload),
        )

    @router.post(
        "/sites/{site_id}/runs",
        response_model=TaskAcceptedResponse,
        status_code=status.HTTP_202_ACCEPTED,
        tags=["站点"],
        summary="触发站点正式运行",
        description=(
            "为指定站点创建一个 `run_site_prod` 异步任务。"
            "仅当站点已经存在正式版本时，该任务才会成功执行。"
        ),
        responses={404: {"model": ApiError}},
    )
    async def run_site(
        site_id: int,
        services: ServiceContainer = Depends(get_services),
    ) -> TaskAcceptedResponse:
        if not await services.site_service.get_site_detail(site_id):
            raise HTTPException(status_code=404, detail="site not found")
        task = await services.task_service.enqueue_run_site_prod(site_id=site_id)
        return TaskAcceptedResponse(
            task_id=task["id"], task=TaskSummary.model_validate(task)
        )

    @router.get(
        "/versions/{version_id}",
        response_model=VersionDetail,
        tags=["版本"],
        summary="获取版本详情",
        description="查看某个规则版本的完整内容，包括 `spec_json`、脚本代码和最近一次运行摘要。",
        responses={404: {"model": ApiError}},
    )
    async def get_version(
        version_id: int,
        services: ServiceContainer = Depends(get_services),
    ) -> VersionDetail:
        payload = await services.version_service.get_version_detail(version_id)
        if not payload:
            raise HTTPException(status_code=404, detail="version not found")
        return VersionDetail.model_validate(payload)

    @router.post(
        "/versions/{version_id}/regenerate",
        response_model=TaskAcceptedResponse,
        status_code=status.HTTP_202_ACCEPTED,
        tags=["版本"],
        summary="重新生成版本并自动预览",
        description=(
            "基于新的列表定位器重新生成一个规则版本，并自动触发一次 preview run。"
            "接口返回任务 ID，执行完成后可从任务结果中拿到新的版本 ID 和运行 ID。"
        ),
        responses={404: {"model": ApiError}, 400: {"model": ApiError}},
    )
    async def regenerate_version(
        version_id: int,
        body: RegenerateVersionRequest,
        services: ServiceContainer = Depends(get_services),
    ) -> TaskAcceptedResponse:
        if not await services.version_service.get_version_detail(version_id):
            raise HTTPException(status_code=404, detail="version not found")
        task = await services.task_service.enqueue_regenerate_version_preview(
            version_id=version_id,
            list_locator_hint=body.list_locator_hint,
        )
        return TaskAcceptedResponse(
            task_id=task["id"], task=TaskSummary.model_validate(task)
        )

    @router.post(
        "/versions/{version_id}/approve",
        response_model=VersionApprovalResponse,
        tags=["版本"],
        summary="审批版本为正式版本",
        description=(
            "将指定版本设置为站点当前正式版本，并把该站点状态切换为 `active`。"
            "审批成功后会同步刷新调度器的批处理任务。"
        ),
        responses={404: {"model": ApiError}},
    )
    async def approve_version(
        version_id: int,
        services: ServiceContainer = Depends(get_services),
    ) -> VersionApprovalResponse:
        if not await services.version_service.get_version_detail(version_id):
            raise HTTPException(status_code=404, detail="version not found")
        payload = await services.version_service.approve_version(version_id)
        return VersionApprovalResponse(
            version=VersionSummary.model_validate(payload["version"]),
            site=payload["site"],
        )

    @router.get(
        "/runs",
        response_model=RunListResponse,
        tags=["运行记录"],
        summary="获取运行记录列表",
        description="全局分页查询运行记录，可按站点、版本、运行类型和运行状态过滤。",
    )
    async def list_runs(
        site_id: int | None = Query(default=None, description="按站点 ID 过滤。"),
        version_id: int | None = Query(default=None, description="按版本 ID 过滤。"),
        run_type: str | None = Query(
            default=None,
            description="按运行类型过滤，常见值为 `preview` 或 `prod`。",
        ),
        status: str | None = Query(
            default=None,
            description="按运行状态过滤，例如 `succeeded` 或 `failed`。",
        ),
        page: int = Query(default=1, ge=1, description="页码，从 1 开始。"),
        page_size: int = Query(
            default=20,
            ge=1,
            le=100,
            description="每页条数，最大 100。",
        ),
        services: ServiceContainer = Depends(get_services),
    ) -> RunListResponse:
        payload = await services.run_service.list_runs(
            site_id=site_id,
            version_id=version_id,
            run_type=run_type,
            status=status,
            page=page,
            page_size=page_size,
        )
        return RunListResponse(
            items=[RunSummary.model_validate(item) for item in payload["items"]],
            page_meta=build_page_meta(payload),
        )

    @router.get(
        "/runs/{run_id}",
        response_model=RunDetail,
        tags=["运行记录"],
        summary="获取运行详情",
        description=(
            "查看单次运行的完整详情，包含统计信息、抽取结果、调试信息、错误日志以及本次运行使用的规则摘要。"
        ),
        responses={404: {"model": ApiError}},
    )
    async def get_run(
        run_id: int,
        services: ServiceContainer = Depends(get_services),
    ) -> RunDetail:
        payload = await services.run_service.get_run_detail(run_id)
        if not payload:
            raise HTTPException(status_code=404, detail="run not found")
        return RunDetail.model_validate(payload)

    @router.get(
        "/tasks",
        response_model=TaskListResponse,
        tags=["异步任务"],
        summary="获取任务列表",
        description="分页查询异步任务，可按任务类型、任务状态和站点 ID 过滤。",
    )
    async def list_tasks(
        task_type: str | None = Query(default=None, description="按任务类型过滤。"),
        status: str | None = Query(default=None, description="按任务状态过滤。"),
        site_id: int | None = Query(default=None, description="按关联站点 ID 过滤。"),
        page: int = Query(default=1, ge=1, description="页码，从 1 开始。"),
        page_size: int = Query(
            default=20,
            ge=1,
            le=100,
            description="每页条数，最大 100。",
        ),
        services: ServiceContainer = Depends(get_services),
    ) -> TaskListResponse:
        payload = await services.task_service.list_tasks(
            task_type=task_type,
            status=status,
            site_id=site_id,
            page=page,
            page_size=page_size,
        )
        return TaskListResponse(
            items=[TaskSummary.model_validate(item) for item in payload["items"]],
            page_meta=build_page_meta(payload),
        )

    @router.get(
        "/tasks/{task_id}",
        response_model=TaskDetail,
        tags=["异步任务"],
        summary="获取任务详情",
        description="查看单个异步任务的当前状态、入参、结果、错误信息和关联资源 ID。",
        responses={404: {"model": ApiError}},
    )
    async def get_task(
        task_id: int,
        services: ServiceContainer = Depends(get_services),
    ) -> TaskDetail:
        payload = await services.task_service.get_task(task_id)
        if not payload:
            raise HTTPException(status_code=404, detail="task not found")
        return TaskDetail.model_validate(payload)

    @router.post(
        "/tasks/{task_id}/cancel",
        response_model=TaskDetail,
        tags=["异步任务"],
        summary="取消待执行任务",
        description="取消一个仍处于 `pending` 状态的异步任务。当前不支持取消正在执行的任务。",
        responses={404: {"model": ApiError}, 409: {"model": ApiError}},
    )
    async def cancel_task(
        task_id: int,
        services: ServiceContainer = Depends(get_services),
    ) -> TaskDetail:
        existing = await services.task_service.get_task(task_id)
        if not existing:
            raise HTTPException(status_code=404, detail="task not found")
        payload = await services.task_service.cancel_task(task_id)
        if payload is None:
            raise HTTPException(
                status_code=409, detail="only pending tasks can be cancelled"
            )
        return TaskDetail.model_validate(payload)

    public_router.include_router(router)
    return public_router
