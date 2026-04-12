from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class ApiError(BaseModel):
    detail: str = Field(description="错误说明文本。")


class PageMeta(BaseModel):
    page: int = Field(description="当前页码，从 1 开始。")
    page_size: int = Field(description="每页返回条数。")
    total: int = Field(description="符合条件的总记录数。")


class SiteSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int = Field(description="站点 ID。")
    name: str = Field(description="站点名称。")
    domain: str = Field(description="站点域名。")
    seed_url: str = Field(description="站点的新闻列表页种子 URL。")
    status: str = Field(description="站点状态，当前支持 `draft` 或 `active`。")
    approved_version_id: int | None = Field(
        default=None, description="当前正式版本 ID。未审批时为空。"
    )
    approved_version_no: int | None = Field(
        default=None, description="当前正式版本号。未审批时为空。"
    )
    notes: str | None = Field(default=None, description="站点备注或默认列表定位器。")
    created_at: str = Field(description="站点创建时间，UTC ISO 字符串。")
    last_run_at: str | None = Field(default=None, description="最近一次运行完成时间。")
    last_run_status: str | None = Field(default=None, description="最近一次运行状态。")
    recent_error: str | None = Field(default=None, description="最近一次运行错误信息。")
    article_count: int = Field(default=0, description="该站点累计入库文章数。")
    today_new_count: int = Field(default=0, description="今日新增文章数。")


class VersionSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int = Field(description="版本 ID。")
    site_id: int = Field(description="所属站点 ID。")
    version_no: int = Field(description="版本号，从 1 递增。")
    status: str = Field(description="版本状态，如 `draft`、`approved`、`rejected`。")
    feedback_text: str | None = Field(
        default=None, description="再次生成时记录的反馈文本或定位器。"
    )
    created_at: str = Field(description="版本创建时间。")
    spec_summary: dict[str, Any] = Field(
        default_factory=dict, description="规则摘要，便于快速查看核心 selector。"
    )
    latest_run_id: int | None = Field(
        default=None, description="该版本最近一次运行 ID。"
    )
    latest_run_status: str | None = Field(
        default=None, description="该版本最近一次运行状态。"
    )
    latest_run_finished_at: str | None = Field(
        default=None, description="该版本最近一次运行完成时间。"
    )


class RunSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int = Field(description="运行记录 ID。")
    site_id: int = Field(description="所属站点 ID。")
    site_name: str | None = Field(default=None, description="所属站点名称。")
    version_id: int = Field(description="运行时使用的版本 ID。")
    version_no: int | None = Field(default=None, description="运行时使用的版本号。")
    run_type: str = Field(description="运行类型，`preview` 或 `prod`。")
    status: str = Field(
        description="运行状态，常见为 `running`、`succeeded`、`failed`。"
    )
    started_at: str = Field(description="开始执行时间。")
    finished_at: str | None = Field(default=None, description="完成时间。")
    stop_reason: str | None = Field(default=None, description="运行停止原因。")
    items_found: int = Field(default=0, description="本次运行抽取到的总条数。")
    items_new: int = Field(default=0, description="本次运行新增条数。")
    items_duplicate: int = Field(default=0, description="本次运行命中的重复条数。")


class ArticleSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int = Field(description="文章记录 ID。")
    site_id: int = Field(description="所属站点 ID。")
    site_name: str | None = Field(default=None, description="所属站点名称。")
    title: str = Field(description="文章标题。")
    url: str = Field(description="原始文章 URL。")
    url_canonical: str = Field(description="标准化后的文章 URL，用于去重。")
    published_at: str | None = Field(default=None, description="发布时间，ISO 格式。")
    source_list_url: str = Field(description="该条记录来自哪个列表页。")
    first_seen_at: str = Field(description="首次发现时间。")
    last_seen_at: str = Field(description="最近一次发现时间。")
    run_id: int = Field(description="最近一次写入或更新该文章的运行 ID。")


class TaskSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int = Field(description="异步任务 ID。")
    task_type: str = Field(description="任务类型。")
    status: str = Field(
        description="任务状态，如 `pending`、`running`、`succeeded`、`failed`。"
    )
    params_json: dict[str, Any] = Field(default_factory=dict, description="任务入参。")
    result_json: dict[str, Any] = Field(
        default_factory=dict, description="任务执行结果。"
    )
    error_log: str = Field(default="", description="任务错误日志。无错误时为空字符串。")
    site_id: int | None = Field(default=None, description="关联站点 ID。")
    version_id: int | None = Field(default=None, description="关联版本 ID。")
    run_id: int | None = Field(default=None, description="关联运行 ID。")
    created_at: str = Field(description="任务创建时间。")
    started_at: str | None = Field(default=None, description="任务开始执行时间。")
    finished_at: str | None = Field(default=None, description="任务完成时间。")


class TaskDetail(TaskSummary):
    pass


class LatestVersionRun(BaseModel):
    id: int = Field(description="最近一次运行 ID。")
    run_type: str = Field(description="运行类型。")
    status: str = Field(description="运行状态。")
    started_at: str = Field(description="开始执行时间。")
    finished_at: str | None = Field(default=None, description="完成时间。")
    stop_reason: str | None = Field(default=None, description="停止原因。")
    items_found: int = Field(default=0, description="抽取总条数。")


class VersionDetail(BaseModel):
    id: int = Field(description="版本 ID。")
    site_id: int = Field(description="所属站点 ID。")
    version_no: int = Field(description="版本号。")
    status: str = Field(description="版本状态。")
    feedback_text: str | None = Field(
        default=None, description="再次生成时记录的反馈。"
    )
    created_at: str = Field(description="创建时间。")
    spec_json: dict[str, Any] = Field(
        default_factory=dict, description="完整规则 JSON。"
    )
    spec_summary: dict[str, Any] = Field(default_factory=dict, description="规则摘要。")
    script_code: str = Field(description="当前版本渲染出的候选执行脚本。")
    latest_run: LatestVersionRun | None = Field(
        default=None, description="该版本最近一次运行摘要。"
    )


class RunDetail(BaseModel):
    id: int = Field(description="运行记录 ID。")
    site_id: int = Field(description="所属站点 ID。")
    site_name: str = Field(description="所属站点名称。")
    seed_url: str = Field(description="站点种子 URL。")
    site_notes: str | None = Field(
        default=None, description="站点备注或默认列表定位器。"
    )
    version_id: int = Field(description="使用的版本 ID。")
    version_no: int = Field(description="使用的版本号。")
    version_status: str = Field(description="版本状态。")
    run_type: str = Field(description="运行类型，`preview` 或 `prod`。")
    status: str = Field(description="运行状态。")
    started_at: str = Field(description="开始执行时间。")
    finished_at: str | None = Field(default=None, description="完成时间。")
    error_log: str = Field(default="", description="运行日志或错误信息。")
    stats: dict[str, Any] = Field(default_factory=dict, description="运行统计信息。")
    result: dict[str, Any] = Field(
        default_factory=dict,
        description="运行结果，通常包含 `items`、`stats`、`debug`。",
    )
    spec_json: dict[str, Any] = Field(
        default_factory=dict, description="运行所用的完整规则。"
    )
    spec_summary: dict[str, Any] = Field(default_factory=dict, description="规则摘要。")


class SiteDetail(BaseModel):
    id: int = Field(description="站点 ID。")
    name: str = Field(description="站点名称。")
    domain: str = Field(description="站点域名。")
    seed_url: str = Field(description="新闻列表页种子 URL。")
    status: str = Field(description="站点状态。")
    approved_version_id: int | None = Field(
        default=None, description="当前正式版本 ID。"
    )
    notes: str | None = Field(default=None, description="站点备注或默认列表定位器。")
    created_at: str = Field(description="站点创建时间。")
    article_count: int = Field(default=0, description="站点累计入库文章数。")
    approved_version: VersionSummary | None = Field(
        default=None, description="当前正式版本摘要。"
    )
    latest_run: RunSummary | None = Field(
        default=None, description="最近一次运行摘要。"
    )
    recent_versions: list[VersionSummary] = Field(
        default_factory=list, description="最近 10 条版本记录。"
    )
    recent_runs: list[RunSummary] = Field(
        default_factory=list, description="最近 10 条运行记录。"
    )


class SiteListResponse(BaseModel):
    items: list[SiteSummary] = Field(description="站点列表。")
    page_meta: PageMeta = Field(description="分页信息。")


class VersionListResponse(BaseModel):
    items: list[VersionSummary] = Field(description="版本列表。")
    page_meta: PageMeta = Field(description="分页信息。")


class RunListResponse(BaseModel):
    items: list[RunSummary] = Field(description="运行记录列表。")
    page_meta: PageMeta = Field(description="分页信息。")


class ArticleListResponse(BaseModel):
    items: list[ArticleSummary] = Field(description="文章记录列表。")
    page_meta: PageMeta = Field(description="分页信息。")


class TaskListResponse(BaseModel):
    items: list[TaskSummary] = Field(description="异步任务列表。")
    page_meta: PageMeta = Field(description="分页信息。")


class HealthResponse(BaseModel):
    status: str = Field(description="服务整体状态。")
    database_ok: bool = Field(description="数据库连通性检查结果。")
    scheduler: dict[str, Any] | None = Field(
        default=None, description="调度器状态摘要。"
    )


class SystemInfo(BaseModel):
    llm_ready: bool = Field(
        description="是否已配置 LLM 所需的 `BASE_URL` 和 `API_KEY`。"
    )
    model_name: str = Field(description="当前用于规则生成的模型名称。")
    timezone: str = Field(description="系统运行时区。")
    scheduler_mode: str = Field(description="调度模式，`daily` 或 `hourly`。")
    scheduler_description: str = Field(description="调度模式的人类可读说明。")
    runtime_dir: str = Field(description="运行时脚本输出目录。")
    db_path: str = Field(description="SQLite 数据库路径。")


class SchedulerInfo(BaseModel):
    enabled: bool = Field(description="当前实例是否启用了调度器。")
    running: bool = Field(description="调度器是否正在运行。")
    job_id: str | None = Field(default=None, description="批处理任务的调度器内部 ID。")
    next_run_time: str | None = Field(default=None, description="下一次计划执行时间。")
    description: str | None = Field(default=None, description="调度策略说明。")
    mode: str | None = Field(default=None, description="调度模式。")


class SiteCreateRequest(BaseModel):
    seed_url: HttpUrl = Field(
        description="新闻列表页 URL，必须为绝对的 HTTP/HTTPS 地址。",
        examples=["https://example.com/news/list.htm"],
    )
    list_locator_hint: str | None = Field(
        default=None,
        description=(
            "列表定位器提示，可选。支持 CSS selector、相对 XPath、绝对 XPath，"
            "用于帮助系统更准确地定位新闻列表区域。"
        ),
        examples=[".news-list", "//div[@class='news-list']"],
    )


class SiteUpdateRequest(BaseModel):
    name: str | None = Field(default=None, description="新的站点名称。")
    notes: str | None = Field(default=None, description="新的备注或默认列表定位器。")
    status: Literal["draft", "active"] | None = Field(
        default=None, description="新的站点状态，只允许 `draft` 或 `active`。"
    )


class RegenerateVersionRequest(BaseModel):
    list_locator_hint: str = Field(
        description="重新生成规则时使用的列表定位器。该字段必填。",
        examples=[".news-list"],
    )


class TaskAcceptedResponse(BaseModel):
    task_id: int = Field(description="新创建的异步任务 ID。")
    task: TaskSummary = Field(description="任务摘要。")


class VersionApprovalResponse(BaseModel):
    version: VersionSummary = Field(description="已审批版本的摘要。")
    site: dict[str, Any] = Field(description="审批后站点的关键状态字段。")


class ProxyHtmlResponse(BaseModel):
    url: str = Field(description="请求时传入的原始 URL。")
    final_url: str = Field(description="实际抓取完成后的最终 URL。")
    html: str = Field(description="抓取到的 HTML 内容。")
    rendered_by: str = Field(description="HTML 的渲染来源。")
