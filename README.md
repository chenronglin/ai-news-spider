# AI News Spider

基于 FastAPI、Crawl4AI、OpenAI 兼容接口和 SQLite 的新闻列表采集后端服务。

当前版本已经调整为**前后端分离**架构：应用只提供 `/api/v1` JSON API，不再以内置 Jinja 页面作为主入口。当前公开接口聚焦“新闻列表页规则生成、预览、审批、正式运行、批量调度”这一段流程，前端可以通过异步任务轮询直接接入。

## 项目简介

不同高校或机构网站的新闻列表结构差异较大，直接让 LLM 猜 selector 稳定性不够。当前实现采用：

- 页面样本抓取
- 列表定位器提示
- 启发式候选规则生成
- LLM 选择或修正规则
- 预览运行
- 人工审批
- 正式运行与批处理调度

核心能力：

- 输入新闻列表页 URL，自动抓取样本页面
- 支持列表定位器提示，兼容 CSS selector、相对 XPath、绝对 XPath
- 自动生成列表规则 `site_spec`
- 自动执行预览运行
- 审批通过后将版本设为正式版本
- 正式运行与定时调度直接使用数据库中的规则，不再依赖 LLM
- 提供统一的异步任务 API，适合前端轮询接入
- 数据层和服务层已经预留文章详情抓取能力

当前公开 API 不包含：

- 摘要、分类、标签、推送
- 用户认证与权限系统

说明：

- 代码中已经包含 `article_detail`、`detail_status` 和 `fetch_article_details` 相关服务能力，但当前版本尚未开放对应的公开 API 路由。

## 当前架构

- API 框架：FastAPI
- 存储：SQLite
- 抓取：Crawl4AI + 静态 HTML 优先
- 规则生成：OpenAI 兼容接口
- 调度：APScheduler
- 依赖管理：uv

当前应用是 API-only 后端，主要分层如下：

- [main.py](/Users/moses/Developer/ai-news-spider/main.py)：启动入口
- [ai_news_spider/app.py](/Users/moses/Developer/ai-news-spider/ai_news_spider/app.py)：应用组装、生命周期、异常处理
- [ai_news_spider/api/routes.py](/Users/moses/Developer/ai-news-spider/ai_news_spider/api/routes.py)：`/api/v1` 路由
- [ai_news_spider/api/schemas.py](/Users/moses/Developer/ai-news-spider/ai_news_spider/api/schemas.py)：请求/响应 DTO
- [ai_news_spider/services.py](/Users/moses/Developer/ai-news-spider/ai_news_spider/services.py)：站点、版本、运行、任务、系统服务与任务执行器
- [ai_news_spider/llm.py](/Users/moses/Developer/ai-news-spider/ai_news_spider/llm.py)：规则生成、候选评分、定位器解析
- [ai_news_spider/runtime.py](/Users/moses/Developer/ai-news-spider/ai_news_spider/runtime.py)：列表执行时的抽取逻辑
- [ai_news_spider/db.py](/Users/moses/Developer/ai-news-spider/ai_news_spider/db.py)：SQLite 访问层
- [ai_news_spider/scheduler.py](/Users/moses/Developer/ai-news-spider/ai_news_spider/scheduler.py)：批量调度器

## 处理流程

### 1. 创建站点并生成预览

1. 调用 `POST /api/v1/sites`
2. 服务创建异步任务 `create_site_preview`
3. 后台抓取样本页并生成规则版本
4. 自动执行一次 preview run
5. 前端轮询 `GET /api/v1/tasks/{task_id}` 获取 `site_id / version_id / run_id`
6. 通过 `GET /api/v1/runs/{run_id}` 查看预览结果

### 2. 再次生成

1. 调用 `POST /api/v1/versions/{version_id}/regenerate`
2. 服务创建异步任务 `regenerate_version_preview`
3. 后台基于新的定位器重新生成版本并自动跑预览
4. 前端轮询任务结果并查看新的 `run_id`

### 3. 审批正式版本

1. 调用 `POST /api/v1/versions/{version_id}/approve`
2. 当前版本切换为站点正式版本
3. 站点状态更新为 `active`
4. 调度器刷新批处理任务

### 4. 正式运行与批处理

- 单站正式运行：`POST /api/v1/sites/{site_id}/runs`
- 批量正式运行：`POST /api/v1/scheduler/run-now`

这两类操作都会先创建异步任务，再由后台执行器串行消费。

重要说明：

- LLM 只用于生成或重新生成列表规则
- 正式运行不依赖 LLM
- 正式运行默认最多 30 页、时间窗口 10 天
- 预览运行默认最多 3 页
- 正式运行去重键为 `(site_id, url_canonical)`

## 异步任务机制

系统内置单进程、单并发的持久化任务队列，任务数据写入 `async_task` 表。

支持的任务类型：

- `create_site_preview`
- `regenerate_version_preview`
- `run_site_prod`
- `run_all_sites_prod`
- `fetch_article_details`（当前仅服务层/任务层预留，未开放公开 API）

任务状态：

- `pending`
- `running`
- `succeeded`
- `failed`
- `cancelled`

设计说明：

- API 对耗时写操作统一返回 `202 Accepted`
- 响应中包含 `task_id`
- 前端通过 `GET /api/v1/tasks/{task_id}` 轮询结果
- 只有 `pending` 任务支持取消
- 应用重启时会把 `running` 任务重置回 `pending`
- 当前并发固定为 1，避免 SQLite、Crawl4AI、子进程 runner 之间互相争抢

## 运行要求

- Python：`>=3.13`
- 依赖管理：`uv`

安装依赖：

```bash
uv sync
```

## 配置方式

系统默认从项目根目录 `.env` 读取配置。建议先复制模板：

```bash
cp .env.example .env
```

然后编辑 `.env`：

```dotenv
HOST=127.0.0.1
PORT=8000
TIMEZONE=Asia/Shanghai
LOG_LEVEL=INFO

BASE_URL=https://yunwu.ai
API_KEY=your-api-key
MODEL_NAME=gpt-5-mini

SCHEDULER_MODE=daily
SCHEDULER_HOUR=9
SCHEDULER_MINUTE=0
SCHEDULER_INTERVAL_HOURS=1
```

说明：

- `BASE_URL=https://yunwu.ai` 会自动归一化为 `https://yunwu.ai/v1`
- `.env` 配置会在启动时自动加载
- 如果同名系统环境变量已存在，系统环境变量优先

调度支持两种模式。

每天一次：

```dotenv
SCHEDULER_MODE=daily
SCHEDULER_HOUR=9
SCHEDULER_MINUTE=0
```

按小时执行：

```dotenv
SCHEDULER_MODE=hourly
SCHEDULER_INTERVAL_HOURS=1
SCHEDULER_MINUTE=0
```

例如每 3 小时一次：

```dotenv
SCHEDULER_MODE=hourly
SCHEDULER_INTERVAL_HOURS=3
SCHEDULER_MINUTE=15
```

## 启动方式

```bash
uv run main.py
```

启动后可访问：

- [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)
- [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health)

## API 概览

### 系统与调试

- `GET /api/v1/health`
- `GET /api/v1/system/info`
- `GET /api/v1/scheduler`
- `POST /api/v1/scheduler/run-now`
- `GET /api/v1/tools/proxy/html?url=...&wait_for=...`

### 站点管理

- `GET /api/v1/sites`
- `POST /api/v1/sites`
- `GET /api/v1/sites/{site_id}`
- `PATCH /api/v1/sites/{site_id}`
- `GET /api/v1/sites/{site_id}/versions`
- `GET /api/v1/sites/{site_id}/runs`
- `POST /api/v1/sites/{site_id}/runs`

### 版本管理

- `GET /api/v1/versions/{version_id}`
- `POST /api/v1/versions/{version_id}/regenerate`
- `POST /api/v1/versions/{version_id}/approve`

### 运行记录

- `GET /api/v1/runs`
- `GET /api/v1/runs/{run_id}`

### 结果表

- `GET /api/v1/articles`

### 异步任务

- `GET /api/v1/tasks`
- `GET /api/v1/tasks/{task_id}`
- `POST /api/v1/tasks/{task_id}/cancel`

列表接口统一支持：

- `page`，默认 `1`
- `page_size`，默认 `20`，最大 `100`

部分接口支持额外过滤条件：

- `/sites`：`status`、`keyword`
- `/sites/{site_id}/runs`：`run_type`、`status`
- `/runs`：`site_id`、`version_id`、`run_type`、`status`
- `/api/v1/articles`：`site_id`、`run_id`、`title`、`keyword`、`source_list_url`、`published_from`、`published_to`
- `/tasks`：`task_type`、`status`、`site_id`

## 快速调用示例

### 1. 创建站点并生成预览

```bash
curl -X POST http://127.0.0.1:8000/api/v1/sites \
  -H "Content-Type: application/json" \
  -d '{
    "seed_url": "https://example.com/list.htm",
    "list_locator_hint": ".news-list"
  }'
```

典型返回：

```json
{
  "task_id": 1,
  "task": {
    "id": 1,
    "task_type": "create_site_preview",
    "status": "pending"
  }
}
```

### 2. 轮询任务结果

```bash
curl http://127.0.0.1:8000/api/v1/tasks/1
```

任务完成后，`result_json` 中会包含：

```json
{
  "site_id": 1,
  "version_id": 1,
  "run_id": 1,
  "status": "succeeded",
  "error_log": ""
}
```

### 3. 查看预览结果

```bash
curl http://127.0.0.1:8000/api/v1/runs/1
```

`RunDetail` 中会包含：

- `stats`
- `result.items`
- `result.debug`
- `error_log`
- `spec_summary`
- `spec_json`

### 4. 审批版本

```bash
curl -X POST http://127.0.0.1:8000/api/v1/versions/1/approve
```

### 5. 触发正式运行

```bash
curl -X POST http://127.0.0.1:8000/api/v1/sites/1/runs
```

## 运行结果 JSON 结构

执行器标准输出结构如下：

```json
{
  "items": [
    {
      "title": "示例标题",
      "url": "https://example.com/info/1.htm",
      "published_at": "2026-03-12T00:00:00+08:00",
      "source_list_url": "https://example.com/list.htm"
    }
  ],
  "stats": {
    "pages_crawled": 1,
    "items_found": 20,
    "items_new": 20,
    "items_duplicate": 0,
    "stop_reason": "no_next_page"
  },
  "debug": {
    "spec_summary": {},
    "selected_item_count_per_page": [],
    "next_page_trace": [],
    "date_parse_errors": []
  }
}
```

## 数据目录

- 数据库文件：`data/app.db`
- 运行时脚本目录：`data/runtime/`

## 数据库字典

数据库文件为 [data/app.db](/Users/moses/Developer/ai-news-spider/data/app.db)。

### `crawl_site`

站点主表。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | INTEGER | 主键 |
| `name` | TEXT | 站点名称 |
| `domain` | TEXT | 种子 URL 域名 |
| `seed_url` | TEXT | 列表页 URL，唯一 |
| `status` | TEXT | 站点状态，常见为 `draft` / `active` |
| `approved_version_id` | INTEGER | 当前正式版本 ID |
| `notes` | TEXT | 当前保存的列表定位器 |
| `created_at` | TEXT | 创建时间，UTC ISO 字符串 |

### `crawler_version`

站点规则版本表。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | INTEGER | 主键 |
| `site_id` | INTEGER | 所属站点 ID |
| `version_no` | INTEGER | 版本号，从 1 递增 |
| `status` | TEXT | `draft` / `approved` / `rejected` |
| `spec_json` | TEXT | 规则 JSON |
| `script_code` | TEXT | 根据规则渲染出的候选执行脚本 |
| `feedback_text` | TEXT | 再次生成时输入的反馈文本或定位器 |
| `created_at` | TEXT | 创建时间 |

### `crawl_run`

每次预览或正式运行的执行记录。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | INTEGER | 主键 |
| `site_id` | INTEGER | 站点 ID |
| `version_id` | INTEGER | 本次运行使用的规则版本 |
| `run_type` | TEXT | `preview` 或 `prod` |
| `status` | TEXT | `running` / `succeeded` / `failed` |
| `stats_json` | TEXT | 统计信息 JSON |
| `result_json` | TEXT | 抽取结果 JSON |
| `error_log` | TEXT | 运行日志或错误信息 |
| `started_at` | TEXT | 开始时间 |
| `finished_at` | TEXT | 结束时间 |

### `article_item`

正式运行入库的文章列表项。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | INTEGER | 主键 |
| `site_id` | INTEGER | 站点 ID |
| `title` | TEXT | 标题 |
| `url` | TEXT | 原始文章 URL |
| `url_canonical` | TEXT | 标准化 URL，用于去重 |
| `published_at` | TEXT | 发布时间，ISO 格式，可为空 |
| `source_list_url` | TEXT | 该条记录来自哪个列表页 |
| `first_seen_at` | TEXT | 首次发现时间 |
| `last_seen_at` | TEXT | 最近一次发现时间 |
| `run_id` | INTEGER | 最近一次写入或更新该记录的运行 ID |
| `detail_status` | TEXT | 详情抓取状态，默认 `none`，常见值有 `pending` / `running` / `succeeded` / `failed` |
| `detail_requested_at` | TEXT | 最近一次请求抓取详情的时间 |
| `detail_fetched_at` | TEXT | 最近一次成功抓取详情的时间 |
| `detail_error` | TEXT | 最近一次详情抓取失败信息，默认空字符串 |

唯一约束：

- `(site_id, url_canonical)`

### `article_detail`

文章详情正文表。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | INTEGER | 主键 |
| `article_item_id` | INTEGER | 关联的文章列表项 ID，唯一 |
| `site_id` | INTEGER | 站点 ID |
| `source_url` | TEXT | 抓取详情时使用的原始文章 URL |
| `final_url` | TEXT | 详情页最终落地 URL |
| `content_html` | TEXT | 原始 HTML 正文 |
| `content_markdown` | TEXT | 转换后的 Markdown 正文 |
| `fetched_at` | TEXT | 本次详情内容抓取时间 |
| `updated_at` | TEXT | 最近一次更新详情内容的时间 |

### `regen_feedback`

再次生成记录表。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | INTEGER | 主键 |
| `site_id` | INTEGER | 站点 ID |
| `version_id` | INTEGER | 来源规则版本 ID |
| `run_id` | INTEGER | 来源运行 ID，可为空 |
| `feedback_text` | TEXT | 当前实现中主要保存再次生成时输入的定位器 |
| `created_at` | TEXT | 创建时间 |

### `async_task`

异步任务表。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | INTEGER | 主键 |
| `task_type` | TEXT | 任务类型 |
| `status` | TEXT | `pending` / `running` / `succeeded` / `failed` / `cancelled` |
| `params_json` | TEXT | 任务输入参数 |
| `result_json` | TEXT | 任务结果 JSON |
| `error_log` | TEXT | 错误信息 |
| `site_id` | INTEGER | 关联站点 ID，可为空 |
| `version_id` | INTEGER | 关联版本 ID，可为空 |
| `run_id` | INTEGER | 关联运行 ID，可为空 |
| `created_at` | TEXT | 创建时间 |
| `started_at` | TEXT | 开始执行时间 |
| `finished_at` | TEXT | 完成时间 |

## `site_spec` 字段说明

当前列表规则结构如下：

| 字段 | 说明 |
| --- | --- |
| `seed_url` | 列表页种子地址 |
| `site_name` | 站点名称 |
| `allowed_domains` | 允许采集的域名列表 |
| `requires_js` | 是否需要浏览器渲染 |
| `wait_for` | 页面等待条件，可为空 |
| `list_item_selector` | 列表项根节点 selector |
| `title_selector` | 标题 selector |
| `link_selector` | 链接 selector，支持 `:self` |
| `date_selector` | 日期 selector，可为空 |
| `date_format` | 日期格式，通常为 `auto` |
| `timezone` | 时区 |
| `pagination_mode` | `next_link` 或 `none` |
| `next_page_selector` | 下一页 selector，可为空 |
| `max_pages_default` | 建议最大页数 |
| `url_join_mode` | URL 拼接模式 |
| `detail_enabled` | 是否启用详情页抓取 |
| `detail_requires_js` | 详情页是否需要浏览器渲染，默认继承 `requires_js` |
| `detail_wait_for` | 详情页等待条件，默认继承 `wait_for` |

## 常用命令

启动项目：

```bash
uv run main.py
```

代码检查：

```bash
uv run ruff check .
```

格式化：

```bash
uv run ruff format .
```

测试：

```bash
uv run pytest
```

## 当前已知限制

- 当前公开 API 仍聚焦列表页采集，尚未开放详情抓取接口
- 某些极端模板仍然需要人工提供更准确的列表定位器
- 页面结构变化后，需要重新生成并重新审批版本
- 当前不包含认证、授权与多用户审计
- 当前任务执行器是单进程单并发设计，适合单机内部工具场景
