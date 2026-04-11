# AI News Spider

基于 FastAPI、Crawl4AI、OpenAI 兼容接口和 SQLite 的高校新闻列表采集系统。  
当前版本只实现“第一段：列表采集”，目标是把一个新闻列表页快速变成可审核、可复用、可调度的正式采集规则。

## 项目简介

系统解决的问题是：不同高校网站模板差异很大，纯靠 LLM 直接猜 selector 容易不稳定。当前实现采用“页面样本 + 列表定位器提示 + 启发式候选 + LLM 选择/修正 + 人工审核”的流程，尽量把规则生成做稳。

核心能力：

- 输入一个新闻列表页 URL，自动抓取样本页面
- 支持用户补充“列表定位器”作为启发，支持 CSS selector、相对 XPath、绝对 XPath
- 自动生成列表规则 `site_spec`
- 自动跑预览，展示抽取结果
- 人工确认后保存为正式版本
- 正式版本入库后，后续执行直接使用数据库中的规则，不再依赖 LLM
- 支持手工执行和定时批量调度

当前不包含：

- 文章详情页正文抓取
- 摘要、分类、打标签
- 消息推送、向量库、知识库

## 技术架构

- Web 框架：FastAPI + Jinja2
- 存储：SQLite
- 抓取：Crawl4AI + 静态 HTML 优先
- 规则生成：OpenAI 兼容接口
- 调度：APScheduler
- 依赖管理：uv

主要模块：

- [main.py](/Users/moses/Developer/ai-news-spider/main.py)：启动入口
- [ai_news_spider/app.py](/Users/moses/Developer/ai-news-spider/ai_news_spider/app.py)：Web 路由
- [ai_news_spider/services.py](/Users/moses/Developer/ai-news-spider/ai_news_spider/services.py)：业务编排
- [ai_news_spider/llm.py](/Users/moses/Developer/ai-news-spider/ai_news_spider/llm.py)：规则生成、候选评分、定位器解析
- [ai_news_spider/runtime.py](/Users/moses/Developer/ai-news-spider/ai_news_spider/runtime.py)：列表执行时的抽取逻辑
- [ai_news_spider/db.py](/Users/moses/Developer/ai-news-spider/ai_news_spider/db.py)：SQLite 访问层
- [ai_news_spider/scheduler.py](/Users/moses/Developer/ai-news-spider/ai_news_spider/scheduler.py)：批量调度器

## 处理流程

1. 用户在首页输入 `目标 URL`，可选输入 `列表定位器`
2. 系统抓取样本页，自动读取页面 `<title>` 作为站点名称
3. 后台根据页面样本和定位器生成多个规则候选
4. LLM 在候选基础上选择或修正规则
5. 自动执行 3 页预览
6. 用户在 `/runs/{id}` 页面确认结果
7. 点击“保存为正式版本”后，规则写入正式版本
8. 后续手工执行和定时调度都直接使用已保存规则

重要说明：

- LLM 只用于生成候选规则或重新生成
- 正式运行不依赖 LLM
- 正式运行使用数据库中的 `spec_json` 和 `script_code`

## 运行要求

- Python：`>=3.13`
- 依赖管理：`uv`

安装依赖：

```bash
uv sync
```

## 配置方式

系统默认从项目根目录 `.env` 文件读取配置。  
建议先复制模板文件：

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

系统会自动把 `BASE_URL=https://yunwu.ai` 归一化成 `https://yunwu.ai/v1`。

说明：

- `.env` 中的配置会在启动时自动加载
- 如果同名系统环境变量已经存在，系统环境变量优先级更高

调度配置支持两种模式。

每天一次：

```dotenv
SCHEDULER_MODE=daily
SCHEDULER_HOUR=9
SCHEDULER_MINUTE=0
```

每小时一次或每 N 小时一次：

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
uv run python main.py
```

启动后访问：

- [http://127.0.0.1:8000](http://127.0.0.1:8000)

## 使用说明

### 1. 生成并预览

首页填写：

- `目标 URL`：新闻列表页地址
- `列表定位器（可选）`：用于帮助系统更准确定位列表区域

`列表定位器` 支持：

- CSS selector，例如 `.class-list`
- 相对 XPath，例如 `//div[@class='class-list']`
- 绝对 XPath，例如 `/html[1]/body[1]/div[4]/div[1]/div[1]/div[2]`

推荐优先使用 CSS selector。  
如果你有浏览器插件，建议直接把插件提供的 selector/XPath 填进这个输入框。

### 2. 审核预览结果

生成后系统会跳转到 `/runs/{id}` 页面，展示：

- 规则摘要
- 抽取结果

可执行两个动作：

- `保存为正式版本`
- `再次生成爬虫`

再次生成时：

- `列表定位器` 为必填项
- 新定位器会写回站点配置，后续继续作为默认提示使用

### 3. 正式运行

在站点管理页 `/sites` 可以：

- 查看已创建站点
- 手工触发正式运行

正式运行默认策略：

- 最多 30 页
- 时间窗口 10 天
- 去重键：`(site_id, url_canonical)`

### 4. 定时调度

系统启动后只注册 1 个批处理定时任务。  
到点后批量读取所有已审批站点，并逐个执行正式采集。

当前实现不是“每站点一个定时任务”，而是“一个批处理任务处理所有站点”。

## 规则保存机制

生成成功后，规则会保存到数据库。  
审核通过后，后续执行直接使用数据库中的规则，不需要再次调用 LLM。

规则保存位置：

- 表：`crawler_version`
- 字段：`spec_json`
- 字段：`script_code`

正式版本关联位置：

- 表：`crawl_site`
- 字段：`approved_version_id`

换句话说：

- 新建站点时，LLM 参与生成
- 再次生成时，LLM 再参与一次
- 正式运行和调度执行时，不使用 LLM

## 数据目录

- 数据库文件：`data/app.db`
- 运行时文件目录：`data/runtime/`

## 数据库字典

数据库为 SQLite，文件路径为 [data/app.db](/Users/moses/Developer/ai-news-spider/data/app.db)。

### `crawl_site`

站点主表。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | INTEGER | 主键 |
| `name` | TEXT | 站点名称，首次创建时自动取页面 title |
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
| `status` | TEXT | 版本状态，常见为 `draft` / `approved` / `rejected` |
| `spec_json` | TEXT | 规则 JSON，核心字段即 `site_spec` |
| `script_code` | TEXT | 根据规则渲染出的候选执行脚本 |
| `feedback_text` | TEXT | 再次生成时使用的定位器或反馈文本 |
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

唯一约束：

- `(site_id, url_canonical)`

### `regen_feedback`

再次生成记录表。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | INTEGER | 主键 |
| `site_id` | INTEGER | 站点 ID |
| `version_id` | INTEGER | 来源规则版本 ID |
| `run_id` | INTEGER | 来源运行 ID，可为空 |
| `feedback_text` | TEXT | 当前实现里主要保存再次生成时输入的列表定位器 |
| `created_at` | TEXT | 创建时间 |

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

## API 接口说明

当前接口主要服务于 Web 页面，返回 HTML 页面或 303 跳转，不是纯 JSON API。

### `GET /`

首页，展示“第一段：列表采集”表单。

### `POST /sites`

创建站点、生成候选规则并立即跑预览。

表单字段：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `seed_url` | 是 | 列表页 URL |
| `list_locator_hint` | 否 | 列表定位器，支持 CSS/XPath |

成功行为：

- 返回 `303`
- 跳转到 `/runs/{run_id}`

### `GET /runs/{run_id}`

查看一次运行的详情页，包含：

- 规则摘要
- 抽取结果
- 保存正式版按钮
- 再次生成表单

### `POST /versions/{version_id}/approve`

将当前版本批准为正式版本。

成功行为：

- 返回 `303`
- 跳转到 `/sites`

### `POST /versions/{version_id}/regenerate`

基于新的列表定位器重新生成规则并预览。

表单字段：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `list_locator_hint` | 是 | 再次生成时使用的列表定位器 |

成功行为：

- 返回 `303`
- 跳转到新的 `/runs/{run_id}`

### `GET /sites`

站点管理页，展示：

- 站点名称
- 当前状态
- 正式版本号
- 最近运行时间
- 今日新增数
- 最近错误

### `POST /sites/{site_id}/run`

手工触发一次正式运行。

成功行为：

- 返回 `303`
- 跳转到新的 `/runs/{run_id}`

## 运行结果 JSON 结构

执行器标准输出结构：

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

## 常用命令

启动项目：

```bash
uv run python main.py
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

- 当前只支持列表页采集，不采详情正文
- 某些极端模板仍然可能需要人工提供更准确的“列表定位器”
- 线上页面结构变更后，需要重新生成并审核新规则
