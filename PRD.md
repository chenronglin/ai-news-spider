## 新闻列表爬虫生成与审核平台

用户输入列表页 URL → 系统抓取样本页 → AI 生成站点适配脚本 → 执行预览 → 人工确认 → 保存为正式版 → 每天定时运行正式版 → 重复即停 → 后续再接内容详情抓取规则。

## 5 个子系统：

1. **爬虫生成器**
   输入一个新闻列表页 URL，AI 产出一个“候选版” Python3 爬虫。

2. **统一执行框架**
   所有爬虫都必须服从统一模板，不允许 AI 自己乱写数据库逻辑、日志逻辑、去重逻辑。

3. **人工审核台**
   预览运行结果，人工判断是否正确。

4. **正式版调度器**
   每天执行一次正式版脚本，命中重复或超出 10 天窗口就停止。

5. **后续业务扩展层**
   按规则挑选部分文章，再去抓详情与做后处理。

这里面最关键的一点是：

**AI 生成的不是“整个系统”，而只是“站点适配代码”。**


### 技术选型

* **FastAPI + Jinja2**：做一个简单 Web 界面
* **Crawl4AI**：负责列表页抓取、动态 JS 页面处理、结构化提取
* **SQLite**：第一版足够，小规模、单机内部工具非常合适
* **APScheduler**：每天定时跑正式版
* **Python subprocess / 独立 runner 进程**：执行 AI 生成的候选脚本，避免把 Web 进程带崩


### 系统分层

**A. Web 层**
负责输入 URL、展示结果、收集人工反馈。

**B. AI 生成层**
负责把样本页面分析成站点规则，再填充到固定模板里，生成候选脚本。

**C. Runner 执行层**
负责安全执行候选脚本，拿到标准输出，统一入库、去重、记录日志。

**D. 调度层**
只运行“已审核通过”的正式版本脚本。


## 设计原则：AI 不直接写“自由脚本”

不要让 AI 直接生成这种东西：

* 自己连数据库
* 自己决定表结构
* 自己决定日志格式
* 自己决定停止规则
* 自己决定如何去重



### 技术方案

**AI 先生成 `site_spec.json`，再由模板引擎生成 Python 脚本**

AI 只输出：

* 列表项选择器
* 标题选择器
* 链接选择器
* 日期选择器
* 下一页选择器 / 翻页方式
* 是否需要执行 JS
* 日期格式解析规则
* URL 补全规则

然后系统把这个 spec 填到固定模板里。


## Crawl4AI 用法

项目场景是“新闻列表页”，通常有两类：

1. **静态翻页**
   URL 翻页、分页链接、下一页按钮 href

2. **动态翻页**
   JS 加载更多、局部刷新、滚动加载

Crawl4AI 对这两类都能覆盖：它有 `AsyncWebCrawler`、`BrowserConfig`、`CrawlerRunConfig`，支持 JS 执行、动态页面交互、CSS/XPath 提取；同时可以直接抽取页面 links。对于结构稳定页面，官方推荐用 `JsonCssExtractionStrategy` 做可重复、低成本的结构化提取；如果页面非常不规则，再考虑 LLM 参与。([Crawl4AI Documentation][1])


### 生成流程

1. 用户提交 URL
2. 系统先用 Crawl4AI 抓第一页 HTML / Markdown / links
3. AI 分析页面结构，生成 `site_spec`
4. 用模板生成候选脚本
5. 运行候选脚本，试爬前 2~3 页
6. 展示结果给用户人工确认
7. 用户确认正确后，保存为正式版本
8. 定时任务每天运行正式版本


## 正式版脚本必须满足的统一规范

### 输入

Runner 给脚本传入：

* `seed_url`
* `site_id`
* `max_days=10`
* `max_pages`
* `run_type=preview|prod`
* `last_seen_checkpoint`
* `db_readonly_context`（可选，不建议脚本自己写库）

### 输出

脚本只能返回标准结构：

```json
{
  "items": [
    {
      "title": "xxx",
      "url": "https://example.com/news/123",
      "published_at": "2026-04-10T08:30:00+08:00",
      "source_list_url": "https://example.com/news?page=2"
    }
  ],
  "stats": {
    "pages_crawled": 2,
    "items_found": 34,
    "items_new": 12,
    "items_duplicate": 22,
    "stop_reason": "duplicate_hit"
  },
  "debug": {
    "next_page_trace": "...",
    "date_parse_errors": []
  }
}
```

### 严格限制

* 脚本 **不负责入库**
* 脚本 **不负责去重**
* 脚本 **不负责调度**
* 脚本 **不负责审批状态变更**

这些都交给 Runner。


## 去重与停止策略

### 去重键

数据库里对每条新闻建立唯一键：

* 首选：`(site_id, canonical_url)`
* 备选：`(site_id, title_hash, published_at)`

因为新闻站最稳定的标识通常是文章 URL。

### 正式运行停止规则

每天正式跑时，按顺序抓列表页：

* 如果某页里的数据 **全部已存在**，直接停止
* 如果抓到的发布时间 **已经早于当前时间往前 10 天**，停止
* 如果页面没有发布时间字段，就用“连续重复页”或“最大页数”停止
* 建议再加一个保险：`max_pages=30`

这能确保：

* 不重复扫太多旧页
* 不做无用功
* 数据库天然无重复


## 人工审核流程

把审核做成 **强制闸门**：

### 审计流程

* 状态：`draft`
* 只能人工触发运行预览
* 预览只跑前 2~3 页
* 前端展示：

  * 标题
  * URL
  * 发布时间
  * 来源列表页
  * 页码
  * 停止原因
  * 错误日志

### 审核动作

用户有两个按钮：

* **保存为正式版本**
* **再次生成爬虫**

如果点“再次生成爬虫”，要求输入错误描述，比如：

* 标题抓错了，抓成了栏目名
* 翻页失败，第二页没抓到
* 发布时间为空
* URL 抓到了跳转链接，不是真实文章链接

然后系统把：

* 原始 URL
* 上次候选脚本
* 预览结果
* 错误日志
* 人工错误描述

一起喂给 AI 再生成下一版。

这样迭代几轮后，命中率会明显提升。


## Web 界面设计

### 页面 1：生成页

字段：

* 目标 URL
* 站点名称（可自动识别域名）
* 备注（可选）

按钮：

* 生成爬虫

### 页面 2：预览结果页

展示：

* 候选脚本版本号
* 执行状态
* 抽取结果表格
* 日志
* 停止原因
* AI 推断出的规则摘要

按钮：

* 保存为正式版本
* 再次生成爬虫

输入框：

* 错误描述

### 页面 3：站点管理页

展示：

* 站点列表
* 当前正式版本
* 上次运行时间
* 今日新增数量
* 最近错误
* 手工执行一次



## 数据库设计

### 1. `crawl_site`

记录站点

* `id`
* `name`
* `domain`
* `seed_url`
* `status`
* `approved_version_id`
* `created_at`

### 2. `crawler_version`

记录每次 AI 生成的脚本版本

* `id`
* `site_id`
* `version_no`
* `status` (`draft` / `approved` / `rejected`)
* `spec_json`
* `script_code`
* `feedback_text`
* `created_at`

### 3. `crawl_run`

记录每次执行

* `id`
* `site_id`
* `version_id`
* `run_type` (`preview` / `prod`)
* `status`
* `stats_json`
* `error_log`
* `started_at`
* `finished_at`

### 4. `article_item`

新闻列表结果表

* `id`
* `site_id`
* `title`
* `url`
* `url_canonical`
* `published_at`
* `source_list_url`
* `first_seen_at`
* `last_seen_at`
* `run_id`

唯一索引：

* `unique(site_id, url_canonical)`

### 5. `regen_feedback`

人工反馈表

* `id`
* `site_id`
* `version_id`
* `run_id`
* `feedback_text`
* `created_at`

### 6. `business_rule`

后续扩展用

* `id`
* `site_id`
* `rule_type`
* `rule_json`
* `enabled`

---

## 后续“抓详情”的扩展方式

**不要把详情抓取混到第一阶段**。

### 第一段：列表采集

只负责：

* 标题
* URL
* 发布时间
* 来源页

### 第二段：规则选中后抓详情

规则可以是：

* 包含关键词：AI / 芯片 / 并购
* 来自特定栏目
* 发布时间在最近 24 小时
* 标题匹配正则

命中后再进入 `detail_fetch_job`：

* 抓正文
* 提取摘要
* 分类
* 入向量库 / 推送消息 / 业务处理
