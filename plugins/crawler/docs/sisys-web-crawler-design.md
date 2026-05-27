# SISYS Web Crawler 详细设计方案

> 版本：2.0 | 日期：2026-05-27 | 作者：agimtech

---

## 目录

1. [背景与目标](#1-背景与目标)
2. [整体架构](#2-整体架构)
3. [目录结构](#3-目录结构)
4. [核心接口设计](#4-核心接口设计)
5. [Scrapy 工程设计](#5-scrapy-工程设计)
6. [智能命名策略](#6-智能命名策略)
7. [配置管理](#7-配置管理)
8. [运行模式](#8-运行模式)
9. [依赖变更](#9-依赖变更)
10. [SISYS 侧集成点](#10-sisys-侧集成点)
11. [测试策略](#11-测试策略)
12. [实施阶段](#12-实施阶段)
13. [验证方案](#13-验证方案)
14. [Playwright 浏览器模式](#14-playwright-浏览器模式)
15. [登录态爬取](#15-登录态爬取)

---

## 1. 背景与目标

### 1.1 背景

SISYS 是面向企业高管的 AI 驱动战略规划与决策智能平台。平台需要从外部网站爬取文件（pdf/txt/doc/docx/ppt/pptx/xls/xlsx/csv/jpeg/png/gif/markdown/zip/tar/mp4/avi/mov/mkv/webm/wmv/flv/mp3/wav/flac/ogg）作为战略规划的数据输入源

### 1.2 设计目标

| 目标 | 说明 |
|------|------|
| 独立性 | Crawler 作为独立微服务运行，可脱离 SISYS 独立启动、测试、部署 |
| 解耦 | 零反向依赖 SISYS 源码，通过 REST API + RabbitMQ 通信 |
| 可扩展 | 文件格式处理器可运行时注册，支持自定义扩展 |
| 智能命名 | 爬取文件根据元数据/标题/内容特征自动命名 |
| 合规 | 遵守 robots.txt，支持请求限速和 UA 轮换 |
| 反爬绕过 | Playwright 浏览器模式绕过 WAF/反爬检测（Cloudflare/Akamai） |
| 登录态支持 | 通过 Playwright storageState 注入登录态，爬取需认证的内容 |

### 1.3 设计决策

- **独立微服务模式**：Crawler 运行为独立进程，通过 HTTP REST API 接收 SISYS 任务，通过 MinIO S3 API 推送文件，通过 RabbitMQ 发布事件
- **Scrapy 技术栈**：使用 Scrapy 作为爬虫引擎，利用其成熟的 Spider/Pipeline/Middleware 体系
- **无 Prefect 调度**：仅支持手动触发（CLI/API），后续按需扩展定时调度

### 1.4 核心原则

- **独立性**：Crawler 可脱离 SISYS 独立启动、测试、部署
- **合约通信**：通过 REST API（SISYS → Crawler）+ RabbitMQ 事件（Crawler → SISYS）
- **共享存储**：通过 MinIO S3 API 直推文件，SISYS 通过对象路径读取
- **无 Prefect 调度**：仅支持手动触发（CLI/API），后续按需扩展

---

## 2. 整体架构

### 2.1 架构拓扑

```
┌─────────────────────────────────────────────────────────┐
│  SISYS Core (独立进程)                                    │
│                                                          │
│  src/domain/ports/crawler_client.py  # HTTP 客户端端口     │
│  src/infrastructure/crawler/         # HTTP 适配器实现     │
│  src/interfaces/api/crawler.py       # 对外暴露 API 路由   │
│  SISYS EventSubscriber              # 订阅 CrawlCompleted │
│         │                                                │
│    HTTP │ (提交任务/查询状态)                               │
│         ▼                                                │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  Crawler Service (独立进程)                               │
│                                                          │
│  plugins/crawler/                                        │
│  ├── api.py          # FastAPI 应用 (REST API 入口)       │
│  ├── core/           # 领域层 (命名策略/格式注册表/实体)    │
│  ├── scrapy_engine/  # Scrapy Spider/Pipeline/Middleware  │
│  ├── storage/        # 存储层 (MinIO S3 / 本地文件系统)    │
│  ├── messaging/      # RabbitMQ 事件发布                  │
│  └── cli.py          # Typer CLI 入口                     │
└─────────────────────────────────────────────────────────┘
         │                          │
    S3 API │ (推送文件)    RabbitMQ │ (发布事件)
         ▼                          ▼
┌──────────────┐         ┌──────────────────┐
│  MinIO (L4)  │         │  RabbitMQ        │
│  共享对象存储  │         │  sisys.events.*  │
└──────────────┘         └──────────────────┘
```

### 2.2 通信方式

| 方向 | 协议 | 用途 |
|------|------|------|
| SISYS → Crawler | HTTP REST API | 提交爬取任务、查询状态、取消任务 |
| Crawler → MinIO | S3 API | 推送爬取到的文件 |
| Crawler → RabbitMQ | AMQP | 发布 CrawlCompleted / CrawlFailed 事件 |
| Crawler 自身 | Typer CLI | 开发调试独立运行 |

### 2.3 数据流

```
[SISYS API POST /api/v1/crawler/tasks]
    → SISYS CrawlerClientPort (HTTP 适配器)
    → Crawler Service API POST /tasks
    → CrawlerPlugin.start_crawl(task)
    → Scrapy DomainSpider 爬取网页 → 发现文件链接
    → Pipeline 链：下载 → 格式识别 → 元数据提取 → 智能命名
    → MinIOStorage.store_file() → S3 API → MinIO (bucket: sisys-crawled)
    → RabbitMQPublisher.publish(CrawlCompleted)
    → SISYS EventSubscriber 收到事件 → 触发下游处理
```

### 2.4 Crawler 内部分层

Crawler 插件内部延续六边形架构风格，保持与 SISYS 一致的设计哲学：

```
plugins/crawler/
├── core/           ← 领域层：命名策略、格式注册表、实体（零外部依赖）
├── storage/        ← 基础设施层：存储端口实现（MinIO / 本地）
├── messaging/      ← 基础设施层：事件发布实现（RabbitMQ / 控制台）
├── scrapy_engine/  ← 基础设施层：Scrapy 引擎封装
├── api.py          ← 接口层：FastAPI REST API
└── cli.py          ← 接口层：Typer CLI
```

---

## 3. 目录结构

### 3.1 Crawler 插件目录

```
plugins/crawler/
  __init__.py                              # 导出版本信息
  plugin.py                                # CrawlerPlugin 生命周期管理
  api.py                                   # FastAPI 应用入口

  config/
    __init__.py
    settings.py                            # CrawlerSettings (@dataclass + from_env())

  core/
    __init__.py
    entities.py                            # CrawlTask, CrawlResult, CrawledFile
    value_objects.py                       # FileFormat, CrawlStatus, NamingCandidate
    naming/
      __init__.py
      engine.py                            # SmartNamingEngine
      strategies.py                        # 命名策略链
      sanitizer.py                         # FilenameSanitizer
      metadata_extractor.py                # 统一元数据提取门面
    format/
      __init__.py
      registry.py                          # FileFormatHandlerRegistry
      base.py                              # FileFormatHandler Protocol
      handlers/
        __init__.py
        pdf_handler.py                     # pypdf（已有）
        office_handler.py                  # python-docx（已有）/ python-pptx（新增）/ openpyxl（已有）
        text_handler.py                    # txt/csv/markdown
        image_handler.py                   # jpeg/png/gif — Pillow（已有）
        archive_handler.py                 # zip/tar
        audio_handler.py                   # mp3/wav/ogg/flac — tinytag
        video_handler.py                   # mp4/avi/mov/mkv — ffprobe

  scrapy_engine/
    __init__.py
    items.py                               # CrawledFileItem / CrawledPageItem
    spiders/
      __init__.py
      domain_spider.py                     # DomainSpider — 域名递归爬取
      sitemap_spider.py                    # SitemapSpider — 基于 sitemap.xml
    pipelines/
      __init__.py
      file_download_pipeline.py            # 文件下载到临时目录
      format_detection_pipeline.py         # MIME magic 格式识别
      metadata_pipeline.py                 # 元数据提取（调 FileFormatHandlerRegistry）
      smart_naming_pipeline.py             # 智能命名（调 SmartNamingEngine）
      storage_pipeline.py                  # 存储推送（调 storage 层）
      notification_pipeline.py             # 事件发布（调 messaging 层）
    middlewares/
      __init__.py
      rate_limit_middleware.py             # 域名级别令牌桶限速
      user_agent_middleware.py             # UA 池随机轮换
      retry_middleware.py                  # 指数退避重试
      playwright_abort.py                 # Playwright 资源过滤（中止图片/字体/CSS/媒体）
    extensions/
      __init__.py
      stats_extension.py                   # 爬取统计采集

  storage/
    __init__.py
    base.py                                # StoragePort Protocol
    minio_storage.py                       # MinIO S3 存储（生产）
    local_storage.py                       # 本地文件系统（开发/调试）

  messaging/
    __init__.py
    base.py                                # EventPublisher Protocol
    rabbitmq_publisher.py                  # RabbitMQ 事件发布（生产）
    console_publisher.py                   # 控制台日志（开发/调试）

  cli.py                                   # Typer CLI 入口

  docs/
    sisys-web-crawler-design.md            # 本设计文档

tests/
  unit/                                    # 单元测试
  integration/                             # 集成测试
```

### 3.2 SISYS 侧新增文件

在 `src/` 下新增以下文件，用于接入 Crawler Service：

| 文件路径 | 说明 |
|---------|------|
| `src/domain/ports/crawler_client.py` | CrawlerClientPort Protocol（HTTP 客户端端口） |
| `src/infrastructure/crawler/__init__.py` | 包初始化 |
| `src/infrastructure/crawler/http_crawler_client.py` | HttpCrawlerClient 适配器实现 |
| `src/interfaces/api/crawler.py` | 对外暴露的 API 路由（转发到 Crawler Service） |

---

## 4. 核心接口设计

### 4.1 Crawler Service REST API

Crawler Service 暴露以下 REST API 端点：

| 方法 | 路径 | 说明 | 请求 | 响应 |
|------|------|------|------|------|
| POST | `/tasks` | 提交爬取任务 | CrawlTaskRequest | `{ task_id: str }` |
| GET | `/tasks/{task_id}` | 查询任务状态 | — | CrawlTaskStatus |
| DELETE | `/tasks/{task_id}` | 取消任务 | — | `{ cancelled: bool }` |
| GET | `/tasks` | 列出任务 | `?status=running` | `list[CrawlTaskStatus]` |
| GET | `/formats` | 列出支持的文件格式 | — | `{ formats: list[str] }` |
| GET | `/health` | 健康检查 | — | `{ status: "healthy" }` |

#### 提交任务请求体

```json
{
  "domains": ["example.com"],
  "seed_urls": ["https://example.com/resources"],
  "follow_subdomains": true,
  "max_depth": 3,
  "allowed_extensions": ["pdf", "docx", "xlsx"],
  "url_patterns": {
    "include": ["/resources/", "/reports/"],
    "exclude": ["/login", "/admin"]
  },
  "max_files": 500,
  "download_delay": 2.0,
  "use_browser": false,
  "auth_storage_state_path": null,
  "auth_headers": null
}
```

#### 任务状态响应

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "domains": ["example.com"],
  "files_crawled": 42,
  "files_failed": 3,
  "total_size_bytes": 104857600,
  "started_at": "2026-05-26T10:00:00Z",
  "completed_at": null
}
```

**任务状态枚举**：`pending` → `running` → `completed` | `failed` | `cancelled`

### 4.2 Crawler 内部 Protocol

Crawler 插件内部通过 Protocol 定义抽象接口，支持多种实现替换：

```python
# plugins/crawler/storage/base.py

class StoragePort(Protocol):
    """存储抽象端口 — MinIO 或本地文件系统"""

    async def store_file(
        self,
        file_name: str,
        file_path: str,
        content_type: str,
        metadata: dict,
    ) -> str:
        """存储文件，返回对象路径"""
        ...

    async def file_exists(self, file_name: str) -> bool:
        """检查文件是否已存在"""
        ...
```

```python
# plugins/crawler/messaging/base.py

class EventPublisher(Protocol):
    """事件发布抽象端口 — RabbitMQ 或控制台"""

    async def publish_crawl_completed(self, result: CrawlResult) -> None:
        """发布爬取完成事件"""
        ...

    async def publish_crawl_failed(self, task_id: str, error: str) -> None:
        """发布爬取失败事件"""
        ...

    async def publish_file_crawled(self, file_info: CrawledFile) -> None:
        """发布单文件爬取完成事件"""
        ...
```

### 4.3 SISYS 侧端口

SISYS 通过 `CrawlerClientPort` 调用 Crawler Service，遵循六边形架构的端口/适配器模式：

```python
# src/domain/ports/crawler_client.py

from typing import Protocol, runtime_checkable


@runtime_checkable
class CrawlerClientPort(Protocol):
    """Crawler HTTP 客户端端口

    SISYS 通过此端口与 Crawler Service 通信
    """

    async def submit_task(
        self,
        domains: list[str],
        seed_urls: list[str] | None = None,
        allowed_extensions: list[str] | None = None,
        max_depth: int = 3,
        follow_subdomains: bool = True,
        max_files: int = 1000,
        download_delay: float = 1.0,
    ) -> str:
        """提交爬取任务，返回 task_id"""
        ...

    async def get_task_status(self, task_id: str) -> dict:
        """查询任务状态"""
        ...

    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        ...

    async def list_supported_formats(self) -> list[str]:
        """列出 Crawler 支持的文件格式"""
        ...
```

**HTTP 适配器实现**：

```python
# src/infrastructure/crawler/http_crawler_client.py

import httpx


class HttpCrawlerClient:
    """通过 HTTP 调用 Crawler Service 的适配器"""

    def __init__(self, base_url: str, timeout: float = 30.0):
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout)

    async def submit_task(
        self,
        domains: list[str],
        seed_urls: list[str] | None = None,
        allowed_extensions: list[str] | None = None,
        max_depth: int = 3,
        follow_subdomains: bool = True,
        max_files: int = 1000,
        download_delay: float = 1.0,
    ) -> str:
        payload = {
            "domains": domains,
            "seed_urls": seed_urls or [],
            "allowed_extensions": allowed_extensions or [],
            "max_depth": max_depth,
            "follow_subdomains": follow_subdomains,
            "max_files": max_files,
            "download_delay": download_delay,
        }
        resp = await self._client.post("/tasks", json=payload)
        resp.raise_for_status()
        return resp.json()["task_id"]

    async def get_task_status(self, task_id: str) -> dict:
        resp = await self._client.get(f"/tasks/{task_id}")
        resp.raise_for_status()
        return resp.json()

    async def cancel_task(self, task_id: str) -> bool:
        resp = await self._client.delete(f"/tasks/{task_id}")
        resp.raise_for_status()
        return resp.json()["cancelled"]

    async def list_supported_formats(self) -> list[str]:
        resp = await self._client.get("/formats")
        resp.raise_for_status()
        return resp.json()["formats"]

    async def close(self) -> None:
        await self._client.aclose()
```

### 4.4 RabbitMQ 事件契约

Crawler Service 直接发布到 RabbitMQ exchange `sisys.events`，routing key 遵循 SISYS 命名规范

#### CrawlCompleted 事件

```json
{
  "event_type": "CrawlCompleted",
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2026-05-26T10:30:00Z",
  "source": "crawler-service",
  "schema_version": "1.0.0",
  "aggregate_type": "CrawlTask",
  "payload": {
    "task_id": "uuid",
    "domain": "example.com",
    "files_count": 42,
    "total_size_bytes": 104857600,
    "duration_seconds": 180.5,
    "storage_bucket": "sisys-raw-documents-default",
    "storage_path_prefix": "crawled/{task_id}/"
  }
}
```

**routing_key**: `sisys.events.reliable.crawl_completed`

#### CrawlFailed 事件

```json
{
  "event_type": "CrawlFailed",
  "event_id": "...",
  "timestamp": "2026-05-26T10:30:00Z",
  "source": "crawler-service",
  "payload": {
    "task_id": "uuid",
    "domain": "example.com",
    "error_message": "Connection timeout after 3 retries",
    "files_crawled_before_failure": 12
  }
}
```

**routing_key**: `sisys.events.reliable.crawl_failed`

#### FileCrawled 事件（单文件级别）

```json
{
  "event_type": "FileCrawled",
  "source": "crawler-service",
  "payload": {
    "task_id": "uuid",
    "file_name": "2024 Annual Report.pdf",
    "original_url": "https://example.com/reports/2024-annual-report.pdf",
    "file_size_bytes": 2097152,
    "content_type": "application/pdf",
    "naming_strategy": "metadata_title",
    "storage_path": "crawled/{task_id}/2024 Annual Report.pdf"
  }
}
```

**routing_key**: `sisys.events.reliable.file_crawled`

### 4.5 MinIO 存储路径约定

Crawler 推送文件到 MinIO 的路径规范：

```
bucket: sisys-raw-documents-{tenant_id}
path:   crawled/{task_id}/{smart_name}.{ext}
```

示例：

```
sisys-raw-documents-default/
  crawled/550e8400-e29b-41d4-a716-446655440000/
    2024 Annual Report.pdf
    Q3 Financial Summary.xlsx
    Product Roadmap 2025.pptx
    crawl_a1b2c3d4e5f67890.txt
```

SISYS 侧通过 L4ObjectPort 直接读取这些路径

---

## 5. Scrapy 工程设计

### 5.1 Spider 设计

#### DomainSpider — 核心域名递归爬取

**特性**：

| 特性 | 说明 |
|------|------|
| 多种子域名 | 支持同时指定多个域名 |
| 子域名跟踪 | `follow_subdomains=True` 自动发现并跟踪子域名 |
| 深度控制 | 可配置 `max_depth`（默认 3） |
| 文件类型过滤 | 扩展名白名单 + MIME 校验 |
| URL 模式过滤 | 支持 include/exclude 路径模式 |
| 上下文传递 | 页面标题、链接锚文本注入 `response.meta` |

**核心逻辑**：

```python
class DomainSpider(scrapy.Spider):
    """域名递归爬取 Spider"""

    name = "domain"

    def __init__(
        self,
        task_id: str = "",
        domains: tuple[str, ...] = (),
        seed_urls: tuple[str, ...] = (),
        allowed_extensions: tuple[str, ...] = (),
        max_depth: int = 3,
        follow_subdomains: bool = True,
        use_browser: bool = False,
    ):
        super().__init__()
        self.task_id = task_id
        self.domains = domains
        self.seed_urls = seed_urls
        self.allowed_extensions = set(ext.lower().lstrip(".") for ext in allowed_extensions)
        self.max_depth = max_depth
        self.follow_subdomains = follow_subdomains
        self.use_browser = use_browser

    async def start(self):
        """生成初始请求（Scrapy 2.16+ async start API）"""
        urls = self.seed_urls if self.seed_urls else tuple(f"https://{d}" for d in self.domains)
        for url in urls:
            meta = {"depth": 0, "page_title": "", "parent_url": ""}
            if self.use_browser:
                meta["playwright"] = True
            yield scrapy.Request(url=url, callback=self.parse, meta=meta)

    def parse(self, response):
        depth = response.meta.get("depth", 0)
        page_title = response.css("title::text").get("").strip()

        for link in response.css("a[href]"):
            href = link.css("::attr(href)").get()
            link_text = link.css("::text").get("").strip()
            if not href:
                continue

            url = urljoin(response.url, href)

            if self._is_target_file(url):
                yield scrapy.Request(
                    url,
                    callback=self.parse_file,
                    meta={
                        "parent_url": response.url,
                        "page_title": page_title,
                        "link_text": link_text,
                        "depth": depth,
                        "playwright": False,  # 文件下载不走浏览器
                    },
                    dont_filter=True,
                )
            elif self._should_follow(url, depth):
                meta = {
                    "depth": depth + 1,
                    "page_title": page_title,
                    "parent_url": response.url,
                }
                if self.use_browser:
                    meta["playwright"] = True
                yield scrapy.Request(url, callback=self.parse, meta=meta)

    def parse_file(self, response):
        """处理文件下载响应，生成 CrawledFileItem"""
        # ... 保存到临时路径并填充 item
        yield item

    def _is_target_file(self, url: str) -> bool:
        """判断 URL 是否指向目标文件（扩展名白名单匹配）"""
        path = urlparse(url).path.lower()
        ext = os.path.splitext(path)[1].lstrip(".")
        return ext in self.allowed_extensions

    def _should_follow(self, url: str, current_depth: int) -> bool:
        """判断 URL 是否应继续爬取"""
        if current_depth >= self.max_depth:
            return False
        parsed = urlparse(url)
        domain = parsed.hostname or ""
        # 子域名检查
        if self.follow_subdomains:
            return any(
                domain == d or domain.endswith(f".{d}")
                for d in self.seed_domains
            )
        return domain in self.seed_domains
```

#### SitemapSpider — 基于 sitemap.xml 的快速发现

适合有 `sitemap.xml` 的结构化站点，直接解析 sitemap 中的 URL 列表，效率高于页面递归

### 5.2 Item 定义

```python
class CrawledFileItem(scrapy.Item):
    """爬取文件 Item — 在 Pipeline 链中逐步填充"""

    # 文件基础信息（FileDownloadPipeline 填充）
    url = scrapy.Field()                    # 下载 URL
    file_path = scrapy.Field()              # 本地临时路径
    file_name = scrapy.Field()              # 原始文件名（URL 推导）
    file_size = scrapy.Field()              # 字节数
    content_type = scrapy.Field()           # MIME 类型
    file_extension = scrapy.Field()         # 扩展名

    # 格式检测结果（FormatDetectionPipeline 填充）
    detected_format = scrapy.Field()        # 实际检测到的格式

    # 元数据（MetadataPipeline 填充）
    metadata_title = scrapy.Field()         # 文件元数据中的标题
    metadata_author = scrapy.Field()        # 文件元数据中的作者
    metadata_created = scrapy.Field()       # 创建日期
    metadata_extra = scrapy.Field()         # 其他元数据 dict

    # 命名结果（SmartNamingPipeline 填充）
    smart_name = scrapy.Field()             # 最终智能文件名
    naming_strategy_used = scrapy.Field()   # 使用的命名策略名

    # 来源上下文（Spider 注入）
    parent_url = scrapy.Field()             # 来源页面 URL
    page_title = scrapy.Field()             # 来源页面标题
    link_text = scrapy.Field()              # 链接锚文本
    depth = scrapy.Field()                  # 爬取深度
    task_id = scrapy.Field()                # 任务 ID
```

### 5.3 Pipeline 处理链

CrawledFileItem 按顺序流经 6 个 Pipeline，每个职责单一：

> **Scrapy 2.16 注意**：Pipeline 的 `process_item()` 和 `open_spider()` 不再接收 `spider` 参数。
> `StoragePipeline` 和 `NotificationPipeline` 的 `process_item()` 为 `async` 方法，直接 `await` 异步存储/事件发布操作，无需 `asyncio.new_event_loop()`。

```
CrawledFileItem
    │
    ▼
┌─────────────────────────┐
│ 1. FileDownloadPipeline  │  下载文件到临时目录
│    (FilesPipeline 扩展)  │  填充: file_path, file_size, content_type
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│ 2. FormatDetectionPipe   │  MIME magic 检测真实格式
│    (不信任扩展名)         │  填充: detected_format
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│ 3. MetadataPipeline      │  通过 FileFormatHandlerRegistry
│    (元数据提取)           │  提取文件元数据
│                          │  填充: metadata_title, metadata_author, ...
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│ 4. SmartNamingPipeline   │  调用 SmartNamingEngine
│    (智能命名)             │  按优先级链选择最佳文件名
│                          │  填充: smart_name, naming_strategy_used
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│ 5. StoragePipeline       │  通过 StoragePort 推送文件
│    (存储推送)             │  MinIO S3 或本地文件系统
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│ 6. NotificationPipeline  │  通过 EventPublisher 发布事件
│    (事件通知)             │  CrawlCompleted / FileCrawled
└─────────────────────────┘
```

### 5.4 Middleware

| Middleware | 职责 | 配置项 | 激活状态 |
|------------|------|--------|---------|
| RateLimitMiddleware | 域名级别令牌桶限速，保证请求间隔 | `CRAWLER_DOWNLOAD_DELAY` | 默认激活 |
| UserAgentRotationMiddleware | UA 池随机轮换，避免被封 | `CRAWLER_USER_AGENT_POOL` | 默认激活 |
| RetryMiddleware | 指数退避重试（429/5xx） | `CRAWLER_RETRY_TIMES`, `CRAWLER_RETRY_HTTP_CODES` | 默认激活 |
| Scrapy ROBOTSTXT_OBEY | robots.txt 遵守（内置） | `CRAWLER_RESPECT_ROBOTS_TXT` | 内置 |
| PlaywrightAbort | 中止无关浏览器子请求（图片/字体/CSS/媒体） | `PLAYWRIGHT_ABORT_REQUEST` | `--browser` 时激活 |

> **中间件激活机制**：`CrawlerSettings.to_scrapy_settings()` 根据 `enable_rate_limit`、`enable_ua_rotation`、`enable_retry` 三个开关动态构建 `DOWNLOADER_MIDDLEWARES` 字典，注入到 Scrapy settings。

### 5.5 格式处理器注册表

通过 Protocol 定义格式处理器接口，支持运行时注册自定义处理器：

```python
# plugins/crawler/core/format/base.py

class FileFormatHandler(Protocol):
    """文件格式处理器协议

    每种文件格式实现此接口，提供元数据提取和格式识别能力
    """

    @property
    def supported_extensions(self) -> list[str]:
        """支持的文件扩展名列表"""
        ...

    @property
    def supported_mime_types(self) -> list[str]:
        """支持的 MIME 类型列表"""
        ...

    def can_handle(self, file_path: str, mime_type: str) -> bool:
        """判断是否能处理该文件"""
        ...

    def extract_metadata(self, file_path: str) -> FileMetadata:
        """提取文件元数据（标题、作者、创建日期等）"""
        ...
```

```python
# plugins/crawler/core/format/registry.py

class FileFormatHandlerRegistry:
    """文件格式处理器注册表"""

    def __init__(self):
        self._handlers: dict[str, FileFormatHandler] = {}

    def register(self, handler: FileFormatHandler) -> None:
        """注册格式处理器（按扩展名索引）"""
        for ext in handler.supported_extensions:
            self._handlers[ext.lower()] = handler

    def get_handler(self, extension: str) -> FileFormatHandler | None:
        """按扩展名获取处理器"""
        return self._handlers.get(extension.lower())

    def detect_format(self, file_path: str, mime_type: str) -> FileFormatHandler | None:
        """自动检测文件格式并返回对应处理器"""
        for handler in set(self._handlers.values()):
            if handler.can_handle(file_path, mime_type):
                return handler
        return None

    def register_default_handlers(self) -> None:
        """注册内置默认处理器"""
        self.register(PdfFormatHandler())       # pypdf
        self.register(OfficeDocHandler())       # python-docx + python-pptx + openpyxl
        self.register(TextFormatHandler())      # txt, csv, markdown
        self.register(ImageFormatHandler())     # jpeg, png, gif (Pillow)
        self.register(ArchiveFormatHandler())   # zip, tar
        self.register(AudioFormatHandler())     # tinytag
        self.register(VideoFormatHandler())     # ffprobe
```

**扩展新格式**：

```python
# 用户自定义格式处理器示例
class EpubFormatHandler:
    @property
    def supported_extensions(self) -> list[str]:
        return ["epub"]

    def can_handle(self, file_path: str, mime_type: str) -> bool:
        return mime_type == "application/epub+zip" or file_path.endswith(".epub")

    def extract_metadata(self, file_path: str) -> FileMetadata:
        # ... epub 元数据提取逻辑
        return FileMetadata(title="...", author="...")

# 注册
registry.register(EpubFormatHandler())
```

---

## 6. 智能命名策略

### 6.1 命名优先级链

SmartNamingEngine 按优先级生成多个候选名称，选择置信度最高者：

| 优先级 | 策略名 | 置信度 | 来源 | 示例 |
|--------|--------|--------|------|------|
| 1 | metadata_title | 0.95 | 文件内嵌元数据 | PDF /Title → `2024 Annual Report.pdf` |
| 2 | content_title | 0.90 | 文档内容推导 | PDF 大纲 → `第一章 绪论.pdf`；DOCX Heading → `战略规划报告.pdf` |
| 3 | page_title | 0.80 | HTML `<title>` | `产品中心 - XX公司` → `产品中心 - XX公司.pdf` |
| 4 | link_text | 0.65 | `<a>` 锚文本 | `下载年度报告` → `下载年度报告.pdf` |
| 5 | url_derived | 0.45 | URL 路径推导 | `/reports/2024-annual-report.pdf` → `2024 Annual Report.pdf` |
| 6 | content_hash | 0.10 | URL 内容哈希 | `crawl_a1b2c3d4e5f67890.pdf` |

### 6.2 SmartNamingEngine 核心逻辑

```python
@dataclass
class NamingCandidate:
    """命名候选"""
    filename: str
    strategy_name: str
    confidence: float      # 0.0 ~ 1.0
    source: str            # 来源描述


class SmartNamingEngine:
    """智能命名引擎

    按优先级链生成多个候选名称，选择最佳候选
    """

    def __init__(self, settings: CrawlerSettings):
        self._sanitizer = FilenameSanitizer(settings.max_filename_length)
        self._conflict_strategy = settings.filename_conflict_strategy
        self._seen_names: dict[str, int] = {}  # 去重计数器

    def generate_name(
        self,
        metadata_title: str | None = None,
        page_title: str | None = None,
        link_text: str | None = None,
        url: str | None = None,
        file_extension: str = "",
        author: str = "",
    ) -> list[NamingCandidate]:
        """生成命名候选列表（按优先级排序）"""
        candidates = []

        # 策略 1: 文件元数据标题
        if metadata_title and metadata_title.strip():
            name = self._sanitizer.sanitize(metadata_title.strip(), file_extension)
            candidates.append(NamingCandidate(name, "metadata_title", 0.95, ...))

        # 策略 2: 页面标题 + 上下文
        if page_title and page_title.strip():
            base = page_title.strip()
            if author:
                base = f"{base} - {author}"
            name = self._sanitizer.sanitize(base, file_extension)
            candidates.append(NamingCandidate(name, "page_title", 0.80, ...))

        # 策略 3: 链接锚文本
        if link_text and len(link_text.strip()) > 2:
            name = self._sanitizer.sanitize(link_text.strip(), file_extension)
            candidates.append(NamingCandidate(name, "link_text", 0.65, ...))

        # 策略 4: URL 路径推导
        if url:
            derived = self._derive_from_url(url, file_extension)
            if derived:
                candidates.append(NamingCandidate(derived, "url_derived", 0.45, ...))

        # 策略 5: 内容哈希（兜底）
        if url:
            hash_name = self._hash_fallback(url, file_extension)
            candidates.append(NamingCandidate(hash_name, "content_hash", 0.10, ...))

        return candidates

    def select_best(self, candidates: list[NamingCandidate]) -> NamingCandidate:
        """选择最佳候选并处理冲突"""
        if not candidates:
            raise ValueError("无可用命名候选")

        chosen = max(candidates, key=lambda c: c.confidence)
        chosen.filename = self._resolve_conflict(chosen.filename)
        return chosen
```

### 6.3 元数据提取方案

各文件格式的元数据提取策略和依赖库：

| 格式 | 依赖库 | 提取字段 | 状态 |
|------|--------|----------|------|
| PDF | pypdf | /Title, /Author, /Subject, /Creator | 已有依赖 |
| DOCX | python-docx | core_properties.title, author, created | 已有依赖 |
| PPTX | python-pptx | presentation.title, author, subject | **新增依赖** |
| XLSX | openpyxl | workbook.properties.title, creator | 已有依赖 |
| TXT/MD/CSV | 标准库 | 首行非空文本截取（最多 100 字符） | 标准库 |
| JPEG/PNG | Pillow | EXIF ImageDescription, DocumentName | 已有依赖 |
| ZIP | 标准库 zipfile | 内部文件名列表 | 标准库 |
| TAR | 标准库 tarfile | 内部文件名列表 | 标准库 |
| GIF | Pillow | 无显著元数据，降级到策略 2-5 | 已有依赖 |
| Video | ffprobe | title, artist, duration, codec, resolution | **新增依赖** |
| Audio | tinytag | title, artist, album, duration | **新增依赖** |

### 6.4 文件名清洗

FilenameSanitizer 处理以下场景：

| 场景 | 输入 | 输出 |
|------|------|------|
| 非法字符 | `Report: Q3/2024 <Draft>` | `Report_ Q3_2024 _Draft_.pdf` |
| 连续空格 | `Annual   Report` | `Annual Report.pdf` |
| Windows 保留名 | `CON` | `_CON.pdf` |
| 超长文件名 | 300 字符标题 | 截取前 200 字符（含扩展名） |
| 首尾空白/点 | ` Report.pdf ` | `Report.pdf` |

### 6.5 冲突处理

| 策略 | 行为 | 示例 |
|------|------|------|
| append_hash（默认） | 追加 8 位短哈希（SHA-256 前 8 位） | `Report.pdf` → `Report_a1b2c3d4.pdf` |
| append_counter | 追加递增计数器 | `Report.pdf` → `Report (2).pdf` |
| overwrite | 覆盖同名文件 | `Report.pdf` → `Report.pdf`（覆盖） |

---

## 7. 配置管理

### 7.1 CrawlerSettings

Crawler 拥有独立配置，使用 `@dataclass` + `from_env()` 类方法管理（不使用 Pydantic BaseSettings，保持 core 层零外部依赖），支持环境变量覆盖（前缀 `CRAWLER_`）：

```python
@dataclass
class CrawlerSettings:
    """爬虫服务全局配置"""

    # ── 服务配置 ──
    host: str = ""                                  # 监听地址（空字符串等价于 0.0.0.0）
    port: int = 8900                                # 监听端口

    # ── 爬取默认参数 ──
    max_depth: int = 3                              # 最大递归深度
    max_concurrent_requests: int = 8                # 并发请求数
    download_delay: float = 1.0                     # 请求间隔（秒）
    download_timeout: int = 30                      # 下载超时（秒）
    max_files_per_task: int = 1000                  # 单任务最大文件数
    max_file_size_mb: int = 2048                    # 单文件大小上限（MB）
    respect_robots_txt: bool = True                 # 遵守 robots.txt
    retry_times: int = 3                            # 重试次数
    retry_http_codes: tuple[int, ...] = (500, 502, 503, 504, 408, 429)

    # ── 文件格式白名单 ──
    allowed_extensions: tuple[str, ...] = (
        "pdf", "txt", "doc", "docx", "ppt", "pptx",
        "xls", "xlsx", "csv", "jpeg", "jpg", "png", "gif",
        "md", "markdown", "zip", "tar", "gz", "bz2",
        # 视频
        "mp4", "avi", "mov", "mkv", "webm", "wmv", "flv", "m4v", "3gp",
        # 音频
        "mp3", "wav", "ogg", "flac", "aac", "wma", "m4a",
    )

    # ── 命名配置 ──
    max_filename_length: int = 200                  # 文件名最大长度
    filename_conflict_strategy: str = "append_hash"  # 冲突策略

    # ── 存储配置 ──
    storage_backend: str = "minio"                  # minio | local
    minio_endpoint: str = "localhost:9000"           # MinIO 端点
    minio_access_key: str = ""                       # MinIO access key
    minio_secret_key: str = ""                       # MinIO secret key
    minio_bucket_prefix: str = "sisys"              # bucket 前缀
    minio_secure: bool = False                       # 是否使用 HTTPS
    local_output_dir: str = "./crawl_output"         # 本地输出目录

    # ── RabbitMQ 配置 ──
    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_exchange: str = "sisys.events"

    # ── Playwright 浏览器模式 ──
    enable_browser: bool = False                          # 启用 Playwright 浏览器渲染
    browser_concurrent_pages: int = 4                    # 浏览器并发页面数
    browser_navigation_timeout_ms: int = 30000           # 页面加载超时（毫秒）
    browser_headless: bool = True                        # 无头模式
    browser_proxy: str = ""                              # pragma: allowlist secret 浏览器代理（如 http://user:pass@proxy:8080）

    # ── 中间件开关 ──
    enable_rate_limit: bool = True                       # 限速中间件
    rate_limit_rps: float = 1.0                          # 每秒请求数
    enable_ua_rotation: bool = True                      # UA 轮换中间件
    enable_retry: bool = True                            # 重试中间件

    # ── 登录态配置 ──
    auth_storage_state_path: str = ""                    # Playwright storageState JSON 文件路径
    auth_headers: dict[str, str] = field(default_factory=dict)  # 额外请求头（如 Authorization）

    @classmethod
    def from_env(cls) -> CrawlerSettings:
        """从环境变量加载配置（前缀 CRAWLER_）"""
        ...

    def to_scrapy_settings(self, user_agent: str | None = None) -> dict:
        """生成完整 Scrapy settings dict

        根据配置动态注入：
        - 基础配置（BOT_NAME、SPIDER_MODULES、ITEM_PIPELINES）
        - DOWNLOADER_MIDDLEWARES（根据开关动态构建）
        - Playwright 配置（仅 enable_browser=True 时注入）
        - 登录态配置（auth_storage_state_path / auth_headers）

        Args:
            user_agent: 自定义 User-Agent，为 None 时不设置（交给 UA 轮换中间件）

        Returns:
            完整的 Scrapy settings dict，可直接传给 CrawlerProcess
        """
        ...
```

### 7.2 环境变量示例

```bash
# .env.crawler
CRAWLER_HOST=
CRAWLER_PORT=8900
CRAWLER_MAX_DEPTH=3
CRAWLER_MAX_CONCURRENT_REQUESTS=8
CRAWLER_DOWNLOAD_DELAY=1.0
CRAWLER_STORAGE_BACKEND=minio
CRAWLER_MINIO_ENDPOINT=localhost:9000
CRAWLER_MINIO_ACCESS_KEY=<your-access-key>
CRAWLER_MINIO_SECRET_KEY=<your-secret-key>
CRAWLER_RABBITMQ_HOST=localhost
CRAWLER_RABBITMQ_PORT=5672

# Playwright 浏览器模式
CRAWLER_ENABLE_BROWSER=false
CRAWLER_BROWSER_CONCURRENT_PAGES=4
CRAWLER_BROWSER_HEADLESS=true
CRAWLER_BROWSER_PROXY=

# 登录态爬取
CRAWLER_AUTH_STORAGE_STATE_PATH=
```

### 7.3 任务配置（YAML）

可通过 YAML 文件预定义爬取任务，适合重复性爬取场景：

```yaml
# plugins/crawler/config/tasks/example_task.yaml
task:
  name: "目标站点文件爬取"
  description: "爬取指定站点的公开文件资源"

target:
  domains:
    - "example.com"
  seed_urls:
    - "https://example.com/resources"
    - "https://example.com/reports"
  follow_subdomains: true

limits:
  max_depth: 3
  max_concurrent_requests: 4
  download_delay: 2.0
  max_files: 500
  max_file_size_mb: 100
  timeout: 60

filters:
  allowed_extensions:
    - pdf
    - docx
    - xlsx
    - pptx
    - txt
  url_patterns:
    include:
      - "/resources/"
      - "/reports/"
      - "/downloads/"
    exclude:
      - "/login"
      - "/admin"
      - "/api/"

naming:
  max_filename_length: 200
  conflict_strategy: "append_hash"

advanced:
  respect_robots_txt: true
  retry_times: 3
  user_agent_rotation: true
```

使用方式：

```bash
# CLI 方式
poetry run crawler crawl --task config/tasks/example_task.yaml

# API 方式
curl -X POST http://localhost:8900/tasks -d @config/tasks/example_task.yaml
```

---

## 8. 运行模式

### 8.1 CLI 独立模式

开发调试和一次性爬取的首选方式，零外部依赖（MinIO/RabbitMQ 均可选）：

```bash
# 基础用法 — 爬取指定域名，文件存到本地（默认遵守 robots.txt）
poetry run crawler crawl -d example.com -o ./crawl_output

# 高级用法 — 指定文件格式、深度、种子 URL
poetry run crawler crawl \
    -d example.com \
    -s "https://example.com/resources" \
    --formats pdf,docx,xlsx \
    --depth 5 \
    --output ./reports

# 忽略 robots.txt（需显式指定）
poetry run crawler crawl -d example.com --formats pdf --no-obey-robots

# Playwright 浏览器模式 — 绕过 WAF/反爬检测
poetry run crawler crawl -d www.tsmc.com --formats pdf --depth 2 \
    --browser --no-obey-robots

# 登录态爬取 — 注入 Playwright storageState
poetry run crawler crawl -d protected.example.com --formats pdf \
    --browser --auth-storage-state ./auth.json

# Header Auth — API Token 认证
poetry run crawler crawl -d api.example.com \
    --auth-header "Authorization=Bearer xxx" --formats pdf

# 从任务配置文件启动
poetry run crawler crawl --task config/tasks/example_task.yaml
```

**存储**：本地文件系统（`LocalStorage`）
**事件**：控制台日志（`ConsolePublisher`）

### 8.2 服务模式

生产部署模式，Crawler 作为独立 FastAPI 服务运行：

```bash
# 启动 Crawler 服务
poetry run crawler serve --port 8900

# 使用 uvicorn 启动（生产推荐）
uvicorn plugins.crawler.api:app --host 0.0.0.0 --port 8900 --workers 1
```

**存储**：MinIO S3（`MinIOStorage`）
**事件**：RabbitMQ（`RabbitMQPublisher`）

SISYS 通过 `CrawlerClientPort`（HTTP 适配器）调用 Crawler Service，无需共享进程

### 8.3 模式对比

| 维度 | CLI 独立 | 服务模式 |
|------|---------|---------|
| 入口 | `poetry run crawler crawl ...` | `poetry run crawler serve` |
| 存储 | 本地文件系统 | MinIO S3 |
| 事件 | 控制台日志 | RabbitMQ |
| 任务管理 | 无（同步执行） | 支持查询/取消/列表 |
| 并发任务 | 1 | 多任务并行 |
| 适用场景 | 开发调试、一次性爬取 | 生产部署、SISYS 集成 |

---

## 9. 依赖变更

### 9.1 pyproject.toml 新增依赖

| 依赖 | 版本 | 用途 | 归属 |
|------|------|------|------|
| scrapy | ^2.11 | 爬虫引擎 | Crawler 插件 |
| scrapy-playwright | ^0.0.46 | Playwright 浏览器集成（反爬/WAF 绕过） | Crawler 插件 |
| python-pptx | ^1.0 | PPT/PPTX 元数据提取 | Crawler 插件 |
| httpx | ^0.27 | SISYS 侧 HTTP 客户端 | SISYS Core |
| tinytag | ^2.2 | 音频元数据提取 | Crawler 插件 |
| ffmpeg-python | ^0.2 | 视频元数据提取（ffprobe 封装） | Crawler 插件 |

> **注意**：安装 scrapy-playwright 后需执行 `poetry run playwright install chromium` 安装浏览器内核。

### 9.2 已有可复用依赖

以下依赖已在 pyproject.toml 中存在，可直接复用：

| 依赖 | 用途 |
|------|------|
| pypdf | PDF 元数据提取（PyPDF2 后继） |
| python-docx | DOCX 元数据提取 |
| openpyxl | XLSX 元数据提取 |
| pillow | 图片 EXIF 提取 |
| typer | CLI 入口 |
| pydantic | 配置管理 / 数据验证 |
| fastapi | Crawler Service API |
| uvicorn | ASGI 服务器 |

---

## 10. SISYS 侧集成点

### 10.1 DI 端口注册

在 `src/composition_root.py` 中注册 Crawler 客户端端口：

```python
# composition_root.py 新增

from src.domain.ports.crawler_client import CrawlerClientPort
from src.infrastructure.crawler.http_crawler_client import HttpCrawlerClient

register_port(
    name="crawler_client",
    version="v1.0.0",
    interface=CrawlerClientPort,
    impl=lambda resolver: HttpCrawlerClient(
        base_url=os.getenv("CRAWLER_SERVICE_URL", "http://localhost:8900"),
    ),
    module="src.infrastructure.crawler.http_crawler_client",
    lifetime=Lifetime.SINGLETON,
    owner="crawler-team",
    tags=("crawler", "client"),
)
```

### 10.2 API 路由

在 `src/interfaces/api/crawler.py` 中对外暴露爬虫管理 API：

```python
from fastapi import APIRouter
from src.domain.ports.resolver import get_resolver
from src.domain.ports.crawler_client import CrawlerClientPort

router = APIRouter(prefix="/api/v1/crawler", tags=["crawler"])


@router.post("/tasks")
async def create_crawl_task(request: CrawlTaskRequest):
    """提交爬取任务"""
    client: CrawlerClientPort = get_resolver().resolve("crawler_client")
    task_id = await client.submit_task(CrawlTaskSpec(**request.model_dump()))
    return {"task_id": task_id, "status": "submitted"}


@router.get("/tasks/{task_id}")
async def get_crawl_status(task_id: str):
    """查询爬取任务状态"""
    client: CrawlerClientPort = get_resolver().resolve("crawler_client")
    status = await client.get_task_status(task_id)
    return status


@router.delete("/tasks/{task_id}")
async def cancel_crawl_task(task_id: str):
    """取消爬取任务"""
    client: CrawlerClientPort = get_resolver().resolve("crawler_client")
    cancelled = await client.cancel_task(task_id)
    return {"task_id": task_id, "cancelled": cancelled}


@router.get("/formats")
async def list_supported_formats():
    """列出支持的文件格式"""
    client: CrawlerClientPort = get_resolver().resolve("crawler_client")
    formats = await client.list_supported_formats()
    return {"formats": formats}
```

### 10.3 事件通道注册

在 `configs/event_channels.yaml` 中新增爬虫事件通道：

```yaml
# Crawler 事件
CrawlCompleted:
    redis_channel: "sisys:rt:crawl_completed"
    rabbitmq_routing_key: "sisys.events.reliable.crawl_completed"
    delivery_mode: "reliable"
    description: "爬取任务完成"

CrawlFailed:
    redis_channel: "sisys:rt:crawl_failed"
    rabbitmq_routing_key: "sisys.events.reliable.crawl_failed"
    delivery_mode: "reliable"
    description: "爬取任务失败"

FileCrawled:
    redis_channel: "sisys:rt:file_crawled"
    rabbitmq_routing_key: "sisys.events.reliable.file_crawled"
    delivery_mode: "reliable"
    description: "单文件爬取完成"
```

同时在 `src/infrastructure/messaging/channel_router.py` 的 `ChannelRouter.DEFAULT_MAPPINGS` 中同步新增对应条目：

```python
"CrawlCompleted": ChannelMapping(
    event_type="CrawlCompleted",
    redis_channel="sisys:rt:crawl_completed",
    rabbitmq_routing_key="sisys.events.reliable.crawl_completed",
    delivery_mode=DeliveryMode.RELIABLE,
    description="爬取任务完成",
),
"CrawlFailed": ChannelMapping(
    event_type="CrawlFailed",
    redis_channel="sisys:rt:crawl_failed",
    rabbitmq_routing_key="sisys.events.reliable.crawl_failed",
    delivery_mode=DeliveryMode.RELIABLE,
    description="爬取任务失败",
),
"FileCrawled": ChannelMapping(
    event_type="FileCrawled",
    redis_channel="sisys:rt:file_crawled",
    rabbitmq_routing_key="sisys.events.reliable.file_crawled",
    delivery_mode=DeliveryMode.RELIABLE,
    description="单文件爬取完成",
),
```

### 10.4 集成文件清单

SISYS 侧需要修改/新增的文件汇总：

| 操作 | 文件路径 | 说明 |
|------|---------|------|
| 新增 | `src/domain/ports/crawler_client.py` | CrawlerClientPort Protocol |
| 新增 | `src/infrastructure/crawler/__init__.py` | 包初始化 |
| 新增 | `src/infrastructure/crawler/http_crawler_client.py` | HTTP 适配器实现 |
| 新增 | `src/interfaces/api/crawler.py` | API 路由 |
| 修改 | `src/composition_root.py` | 注册 crawler_client 端口 |
| 修改 | `configs/event_channels.yaml` | 新增 3 个事件通道 |
| 修改 | `src/infrastructure/messaging/channel_router.py` | DEFAULT_MAPPINGS 新增 3 条 |
| 新增 | `tests/contracts/test_port_contract_crawler.py` | 契约测试 |

---

## 11. 测试策略

### 11.1 Crawler 插件测试

| 层次 | 对象 | 关键场景 | 依赖 |
|------|------|---------|------|
| 单元 | SmartNamingEngine | 优先级链正确、metadata_title 优先于 page_title | 无 |
| 单元 | SmartNamingEngine | 同名文件 append_hash/append_counter 冲突处理 | 无 |
| 单元 | FilenameSanitizer | 超长文件名截断、保留名前缀加下划线、非法字符替换 | 无 |
| 单元 | FileFormatHandlerRegistry | 注册/查找/自动检测、未知格式返回 None | 无 |
| 单元 | PdfFormatHandler | 有元数据 PDF 提取 /Title、无元数据 PDF 返回空 | pypdf2 |
| 单元 | OfficeDocHandler | DOCX/PPTX/XLSX 元数据提取 | python-docx, python-pptx, openpyxl |
| 单元 | CrawlerSettings | 环境变量覆盖、默认值正确 | pydantic |
| 集成 | Pipeline 全链路 | fake_server fixture 模拟目标站点，验证完整流经 | scrapy, aiohttp |
| 集成 | MinIOStorage | S3 API 推送文件并验证路径、file_exists 正确判断 | minio |
| 集成 | RabbitMQPublisher | 事件发布并验证 routing key / payload 结构 | aio-pika |
| 集成 | FastAPI endpoints | httpx.AsyncClient 测试 API 端点响应 | fastapi, httpx |
| 集成 | DomainSpider | fake_server fixture 提供多类型文件链接 | scrapy |

### 11.2 SISYS 侧测试

| 层次 | 对象 | 关键场景 |
|------|------|---------|
| 契约 | CrawlerClientPort | 方法签名包含所有必需参数 |
| 契约 | CrawlerClientPort | 端口已注册到 PortRegistry、元数据完整 |
| 集成 | HttpCrawlerClient | 正确构造 HTTP 请求、处理错误响应 |
| 集成 | API 路由 | 转发到 Crawler Service 并返回响应 |

### 11.3 端到端测试

| 场景 | 步骤 |
|------|------|
| SISYS → Crawler 完整流程 | 提交任务 → 文件爬取 → 存入 MinIO → SISYS 订阅事件 |
| 格式扩展验证 | 注册自定义 FileFormatHandler → 爬取 → 验证元数据提取 |
| 错误恢复 | 爬取中断 → 重启 → 验证状态恢复 |

### 11.4 测试覆盖率要求

| 层次 | 最低覆盖率 |
|------|-----------|
| Crawler core（命名/格式/实体） | ≥90% |
| Crawler storage + messaging | ≥80% |
| Crawler scrapy_engine | ≥70% |
| SISYS 侧集成代码 | ≥85% |

---

## 12. 实施阶段

### 12.1 阶段规划

| 阶段 | 内容 | 产出 | 预计工期 |
|------|------|------|---------|
| P1 | 核心实体 + 命名引擎 + 格式注册表 + 元数据提取 | `core/*` | 3 天 |
| P2 | 存储层（MinIO / 本地）+ 事件发布层（RabbitMQ / 控制台） | `storage/*`, `messaging/*` | 2 天 |
| P3 | Scrapy Spider + Pipeline + Middleware | `scrapy_engine/*` | 3 天 |
| P4 | FastAPI 应用 + 插件生命周期 + CLI | `api.py`, `plugin.py`, `cli.py` | 2 天 |
| P5 | SISYS 侧：HTTP 客户端端口 + 适配器 + API 路由 | `src/domain/ports/crawler_client.py`, `src/infrastructure/crawler/*` | 1 天 |
| P6 | SISYS 侧：事件通道配置 + DI 注册 | `event_channels.yaml`, `composition_root.py` | 0.5 天 |
| P7 | 全链路测试 | `tests/` | 2 天 |

**总计**：约 13.5 个工作日

### 12.2 并行策略

```
P1 (核心层) ──────┐
                  ├── P3 (Scrapy) ──┐
P2 (基础设施层) ──┘                  ├── P4 (API/CLI) ──┐
                                                       ├── P7 (测试)
P5 (SISYS 集成) ──────────────────────────────────────┘
P6 (事件配置)  ──┘
```

- **P1 + P2** 可并行开发（无交叉依赖）
- **P5 + P6** 可与 P1-P4 并行开发（SISYS 侧与 Crawler 侧零耦合）
- **P7** 必须在 P1-P6 全部完成后执行

---

## 13. 验证方案

### 13.1 CLI 独立验证

```bash
# 1. 安装依赖
poetry install

# 2. 本地爬取测试（已验证：成功爬取 243 个文件，2.9GB）
poetry run crawler crawl -d www.huawei.com -s https://www.huawei.com/cn/ -o ./test_output --formats pdf,txt --depth 1

# 3. 验证输出
ls -la ./test_output/
# 预期：文件已按智能命名规则存储，中文标题正确提取

# 4. 验证命名策略
# 预期：优先使用元数据标题，次用页面标题，最后用 URL 推导或哈希
# 冲突时自动追加 SHA-256 前 8 位：探索智能世界 - 华为_ac4f30cf.pdf

# 5. 忽略 robots.txt（需显式指定）
poetry run crawler crawl -d example.com --formats pdf --no-obey-robots
```

### 13.2 服务模式验证

```bash
# 1. 启动 Crawler 服务
poetry run crawler serve --port 8900

# 2. 健康检查
curl http://localhost:8900/health
# 预期：{"status": "healthy"}

# 3. 查询支持的格式
curl http://localhost:8900/formats
# 预期：{"formats": ["pdf", "txt", "doc", ...]}

# 4. 提交爬取任务
curl -X POST http://localhost:8900/tasks \
  -H "Content-Type: application/json" \
  -d '{"domains": ["example.com"], "allowed_extensions": ["pdf"], "max_depth": 2}'
# 预期：{"task_id": "..."}

# 5. 查询任务状态
curl http://localhost:8900/tasks/{task_id}
# 预期：{"task_id": "...", "status": "running", ...}
```

### 13.3 SISYS 集成验证

```bash
# 1. 启动 MinIO + RabbitMQ + SISYS + Crawler Service

# 2. 通过 SISYS API 提交任务
curl -X POST http://localhost:8000/api/v1/crawler/tasks \
  -H "Content-Type: application/json" \
  -d '{"domains": ["example.com"], "formats": ["pdf", "docx"]}'

# 3. 验证文件存储
# 检查 MinIO bucket: sisys-raw-documents-default
# 路径: crawled/{task_id}/*.pdf

# 4. 验证事件发布
# 检查 RabbitMQ queue: sisys.events.reliable.crawl_completed
```

### 13.4 质量门禁

```bash
# 代码质量
poetry run ruff check plugins/crawler/ src/domain/ports/crawler_client.py src/infrastructure/crawler/
poetry run ruff format plugins/crawler/ src/domain/ports/crawler_client.py src/infrastructure/crawler/
poetry run mypy plugins/crawler/ src/domain/ports/crawler_client.py src/infrastructure/crawler/

# 测试
poetry run pytest tests/ -v --cov=plugins/crawler --cov-report=term-missing

# 覆盖率门禁
# Crawler core ≥90%
# 整体 ≥80%
```

---

## 附录 A：关键文件路径索引

### Crawler 插件侧

| 类别 | 文件路径 | 说明 |
|------|---------|------|
| 服务入口 | `plugins/crawler/api.py` | FastAPI 应用 |
| CLI 入口 | `plugins/crawler/cli.py` | Typer CLI |
| 生命周期 | `plugins/crawler/plugin.py` | CrawlerPlugin 主类 |
| 配置 | `plugins/crawler/config/settings.py` | CrawlerSettings |
| 命名引擎 | `plugins/crawler/core/naming/engine.py` | SmartNamingEngine |
| 命名清洗 | `plugins/crawler/core/naming/sanitizer.py` | FilenameSanitizer |
| 格式注册表 | `plugins/crawler/core/format/registry.py` | FileFormatHandlerRegistry |
| 格式基类 | `plugins/crawler/core/format/base.py` | FileFormatHandler Protocol |
| PDF 处理 | `plugins/crawler/core/format/handlers/pdf_handler.py` | PDF 元数据提取 |
| Office 处理 | `plugins/crawler/core/format/handlers/office_handler.py` | DOCX/PPTX/XLSX 元数据提取 |
| 存储端口 | `plugins/crawler/storage/base.py` | StoragePort Protocol |
| MinIO 存储 | `plugins/crawler/storage/minio_storage.py` | MinIO S3 实现 |
| 本地存储 | `plugins/crawler/storage/local_storage.py` | 本地文件系统实现 |
| 事件端口 | `plugins/crawler/messaging/base.py` | EventPublisher Protocol |
| RabbitMQ | `plugins/crawler/messaging/rabbitmq_publisher.py` | RabbitMQ 事件发布 |
| Spider | `plugins/crawler/scrapy_engine/spiders/domain_spider.py` | 域名递归爬取（含混合模式） |
| Pipeline | `plugins/crawler/scrapy_engine/pipelines/*.py` | 6 个 Pipeline |
| Playwright 过滤 | `plugins/crawler/scrapy_engine/middlewares/playwright_abort.py` | 浏览器资源过滤 |

### SISYS 侧

| 类别 | 文件路径 | 说明 |
|------|---------|------|
| 端口定义 | `src/domain/ports/crawler_client.py` | CrawlerClientPort Protocol |
| HTTP 适配器 | `src/infrastructure/crawler/http_crawler_client.py` | HttpCrawlerClient |
| API 路由 | `src/interfaces/api/crawler.py` | 对外暴露路由 |
| 组合根 | `src/composition_root.py` | 端口注册 |
| 事件通道 | `configs/event_channels.yaml` | 事件通道配置 |
| 通道路由 | `src/infrastructure/messaging/channel_router.py` | DEFAULT_MAPPINGS |

---

## 14. Playwright 浏览器模式

### 14.1 背景

爬取 TSMC 等部署 WAF（Cloudflare/Akamai）的站点时，Scrapy 纯 HTTP 请求被 403 拒绝。即使设置了 Chrome User-Agent，WAF 仍通过 TLS 指纹和 JS 执行能力检测识别爬虫。

**解决方案**：scrapy-playwright 混合模式 — 页面请求走 Playwright（完整浏览器），文件下载走原生 HTTP（快）。

### 14.2 混合模式设计

scrapy-playwright 的 `ScrapyPlaywrightDownloadHandler` 继承默认 handler，只有 `meta["playwright"] = True` 的请求才走浏览器，其余走原生 HTTP：

```
┌─────────────────────────────────────────────────┐
│  DomainSpider                                    │
│                                                  │
│  ┌──────────────┐     ┌───────────────────────┐ │
│  │ 页面链接      │     │ 文件链接               │ │
│  │ meta:         │     │ meta:                  │ │
│  │  playwright:  │     │  playwright: False     │ │
│  │    True/False │     │  (始终原生 HTTP)        │ │
│  └──────┬───────┘     └───────────┬───────────┘ │
│         │                         │              │
│    ┌────▼─────────────────────────▼────┐         │
│    │  ScrapyPlaywrightDownloadHandler  │         │
│    │  (继承默认 handler)                │         │
│    │                                    │         │
│    │  playwright=True → 浏览器渲染      │         │
│    │  其他          → 原生 HTTP 请求    │         │
│    └────────────────────────────────────┘         │
└─────────────────────────────────────────────────┘
```

### 14.3 配置项

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|---------|--------|------|
| `enable_browser` | `CRAWLER_ENABLE_BROWSER` | `False` | 启用 Playwright 浏览器模式 |
| `browser_concurrent_pages` | `CRAWLER_BROWSER_CONCURRENT_PAGES` | `4` | 浏览器并发页面数 |
| `browser_navigation_timeout_ms` | — | `30000` | 页面加载超时（毫秒） |
| `browser_headless` | `CRAWLER_BROWSER_HEADLESS` | `True` | 无头模式 |
| `browser_proxy` | `CRAWLER_BROWSER_PROXY` | `""` | 浏览器代理 |

### 14.4 资源过滤策略

通过 `PLAYWRIGHT_ABORT_REQUEST` 配置项，中止无关浏览器子请求以加速页面加载：

```python
# plugins/crawler/scrapy_engine/middlewares/playwright_abort.py

_ABORT_RESOURCE_TYPES = frozenset({
    "image",      # 图片（jpg/png/gif/svg/webp）
    "font",       # 字体（woff/woff2/ttf/eot）
    "stylesheet", # CSS 样式表
    "media",      # 视频/音频（mp4/mp3/wav）
})

def should_abort_request(request) -> bool:
    """中止无关资源请求（图片/字体/CSS/媒体），加速页面加载"""
    return request.resource_type in _ABORT_RESOURCE_TYPES
```

### 14.5 Scrapy Settings 注入

`CrawlerSettings.to_scrapy_settings()` 在 `enable_browser=True` 时动态注入以下配置：

```python
{
    "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
    "DOWNLOAD_HANDLERS": {
        "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    },
    "PLAYWRIGHT_LAUNCH_OPTIONS": {
        "headless": True,
    },
    "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 30000,
    "PLAYWRIGHT_ABORT_REQUEST": "plugins.crawler.scrapy_engine.middlewares.playwright_abort.should_abort_request",
}
```

### 14.6 使用示例

**CLI 方式**：

```bash
# 浏览器模式爬取 WAF 站点
poetry run crawler crawl -d www.tsmc.com --formats pdf --depth 2 \
    --browser --no-obey-robots

# 浏览器模式 + 代理
poetry run crawler crawl -d example.com --formats pdf \
    --browser --browser-proxy "http://proxy:8080"
```

**API 方式**：

```bash
curl -X POST http://localhost:8900/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "domains": ["www.tsmc.com"],
    "allowed_extensions": ["pdf"],
    "use_browser": true,
    "max_depth": 2
  }'
```

### 14.7 配置统一：to_scrapy_settings()

`CrawlerSettings.to_scrapy_settings()` 方法统一生成 Scrapy settings dict，消除 `cli.py` 和 `plugin.py` 中各自维护的内联 dict。

**注入逻辑**：

| 配置来源 | 注入内容 |
|---------|---------|
| 基础配置 | `BOT_NAME`、`SPIDER_MODULES`、`ROBOTSTXT_OBEY`、`CONCURRENT_REQUESTS`、`DOWNLOAD_DELAY` |
| ITEM_PIPELINES | 6 个管道（始终注入） |
| `enable_rate_limit=True` | `RateLimitMiddleware`（优先级 400） |
| `enable_ua_rotation=True` | `UserAgentRotationMiddleware`（优先级 500） |
| `enable_retry=True` | `RetryMiddleware`（优先级 550） |
| `enable_browser=True` | `TWISTED_REACTOR`、`DOWNLOAD_HANDLERS`、`PLAYWRIGHT_*` 配置 |
| `user_agent` 参数 | `USER_AGENT` |

### 14.8 同步修复：休眠中间件

`cli.py` 和 `plugin.py` 原先使用内联 dict 创建 `CrawlerProcess`，未引用 `scrapy_engine/settings.py` 中定义的 `DOWNLOADER_MIDDLEWARES`，导致以下三个中间件从未生效：

- `RateLimitMiddleware` — 域名级别令牌桶限速
- `UserAgentRotationMiddleware` — UA 池随机轮换
- `RetryMiddleware` — 指数退避重试

通过 `to_scrapy_settings()` 统一生成 settings dict，三个中间件已默认激活。

---

## 15. 登录态爬取

### 15.1 价值分析

登录态爬取解锁三类高价值场景：

| 场景 | 典型目标 | 价值 |
|------|---------|------|
| 付费墙/订阅内容 | 研报平台（Bloomberg、Gartner）、学术论文（IEEE、ACM）、行业数据库 | 高价值专业内容 |
| 个性化内容 | 用户偏好定制的新闻流、推荐系统结果、账户专属文档 | 个性化数据源 |
| 表单后内容 | 需注册才能访问的下载链接、会员专区资源 | 受保护资源 |

> **价值估算**：企业级爬虫场景中，约 30-40% 的高价值目标需要登录态访问。

### 15.2 业界最佳实践对比

| 方案 | 适用场景 | 优点 | 缺点 |
|------|---------|------|------|
| **Playwright storageState** | 复杂登录（验证码/2FA/MFA） | 最可靠，支持任意认证流程 | 需手动执行一次登录 |
| Scrapy FormRequest.from_response() | 简单表单登录 | 自动化程度高 | 不支持 JS 渲染、验证码 |
| Cookie 注入 | 已有 cookie（浏览器导出） | 最简单 | Cookie 过期需手动更新 |
| HTTP Header Auth | API Token / Bearer | 标准化，易管理 | 仅适用于 API 端点 |

**推荐方案**：Playwright `storageState` 作为主路径，覆盖 95%+ 场景。

### 15.3 storageState 格式

Playwright `context.storage_state()` 导出的 JSON 包含 cookies + localStorage + IndexedDB：

```json
{
  "cookies": [
    {
      "name": "sessionid",
      "value": "abc123",
      "domain": ".example.com",
      "path": "/",
      "expires": 1735689600,
      "httpOnly": true,
      "secure": true,
      "sameSite": "Lax"
    }
  ],
  "origins": [
    {
      "origin": "https://example.com",
      "localStorage": [
        {"name": "auth_token", "value": "eyJhbGciOiJIUzI1NiIs..."}
      ]
    }
  ]
}
```

**导出方式**：

1. **Playwright GUI**：在 Playwright Inspector 中登录目标站点后执行 `context.storage_state(path="auth.json")`
2. **Playwright 脚本**：

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://example.com/login")
    # 手动或自动执行登录操作...
    page.fill("#username", "user@example.com")
    page.fill("#password", "password123")
    page.click("button[type=submit]")
    page.wait_for_url("**/dashboard")
    # 导出登录态
    context.storage_state(path="auth.json")
    browser.close()
```

### 15.4 配置项

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|---------|--------|------|
| `auth_storage_state_path` | `CRAWLER_AUTH_STORAGE_STATE_PATH` | `""` | Playwright storageState JSON 文件路径 |
| `auth_headers` | — | `{}` | 额外请求头（如 `{"Authorization": "Bearer xxx"}`） |

### 15.5 设计实现

#### 配置注入

`CrawlerSettings.to_scrapy_settings()` 根据认证配置动态注入：

```python
# Playwright storageState 注入（需要 enable_browser=True）
if self.enable_browser and self.auth_storage_state_path:
    settings["PLAYWRIGHT_CONTEXT_ARGS"] = {
        "storage_state": self.auth_storage_state_path,
    }

# HTTP Header Auth 注入
if self.auth_headers:
    settings.setdefault("DEFAULT_REQUEST_HEADERS", {}).update(self.auth_headers)
```

#### 实体扩展

`CrawlTask` 新增字段：

```python
@dataclass(frozen=True)
class CrawlTask:
    # ... 现有字段 ...
    use_browser: bool = False
    auth_storage_state_path: str = ""
    auth_headers: dict[str, str] = field(default_factory=dict)
```

#### CLI 参数

```bash
# 登录态爬取（Playwright storageState）
poetry run crawler crawl -d protected.example.com --formats pdf \
    --browser --auth-storage-state ./auth.json

# Header Auth（API Token）
poetry run crawler crawl -d api.example.com \
    --auth-header "Authorization=Bearer xxx" --formats pdf
```

#### API 请求

```json
{
  "domains": ["protected.example.com"],
  "allowed_extensions": ["pdf"],
  "use_browser": true,
  "auth_storage_state_path": "/path/to/auth.json"
}
```

### 15.6 安全注意事项

| 措施 | 说明 |
|------|------|
| **文件权限** | storageState 文件应设置 `chmod 600`（仅所有者可读写） |
| **日志脱敏** | `auth_storage_state_path` 在日志中仅显示路径；`auth_headers` 中的 `Authorization` 值脱敏显示 |
| **API 响应过滤** | `CrawlTask` 序列化到响应时，`auth_*` 字段不返回或返回 `***` |
| **凭证轮换** | 建议 storageState 文件定期更新，避免长期有效凭证暴露 |
| **`.gitignore`** | 确保 `auth.json`、`*.storage-state.json` 等凭证文件被 gitignore |

### 15.7 数据流

```
用户提供 auth.json（Playwright storageState）
    │
    ▼
CLI / API 传入 auth_storage_state_path
    │
    ▼
CrawlTask.auth_storage_state_path → CrawlerSettings.auth_storage_state_path
    │
    ▼
to_scrapy_settings() 注入 PLAYWRIGHT_CONTEXT_ARGS
    │
    ▼
scrapy-playwright 创建浏览器上下文时加载 storageState
    │
    ▼
浏览器上下文自动携带 cookies + localStorage → 认证通过
    │
    ▼
DomainSpider 正常爬取受保护页面 → 发现并下载文件
```
