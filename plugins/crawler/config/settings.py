"""爬虫服务全局配置模块

使用 dataclass + from_env() 模式，不依赖 Pydantic
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class CrawlerSettings:
    """爬虫服务全局配置"""

    # ── 服务配置 ──
    host: str = ""  # 空字符串表示监听所有接口，等同于 0.0.0.0
    port: int = 8900

    # ── 爬取默认参数 ──
    max_depth: int = 3
    max_concurrent_requests: int = 8
    download_delay: float = 1.0
    download_timeout: int = 30
    max_files_per_task: int = 1000
    max_file_size_mb: int = 2048
    respect_robots_txt: bool = True
    retry_times: int = 3
    retry_http_codes: tuple[int, ...] = (500, 502, 503, 504, 408, 429)

    # ── 文件格式白名单 ──
    allowed_extensions: tuple[str, ...] = (
        "pdf",
        "txt",
        "doc",
        "docx",
        "ppt",
        "pptx",
        "xls",
        "xlsx",
        "csv",
        "jpeg",
        "jpg",
        "png",
        "gif",
        "md",
        "markdown",
        "zip",
        "tar",
        "gz",
        "bz2",
        # 视频
        "mp4",
        "avi",
        "mov",
        "mkv",
        "webm",
        "wmv",
        "flv",
        "m4v",
        "3gp",
        # 音频
        "mp3",
        "wav",
        "ogg",
        "flac",
        "aac",
        "wma",
        "m4a",
    )

    # ── 命名配置 ──
    max_filename_length: int = 200
    filename_conflict_strategy: str = "append_hash"

    # ── 中间件开关 ──
    enable_rate_limit: bool = True
    rate_limit_rps: float = 2.0
    enable_ua_rotation: bool = True
    enable_retry: bool = True

    # ── Playwright 浏览器模式 ──
    enable_browser: bool = False
    browser_concurrent_pages: int = 4
    browser_navigation_timeout_ms: int = 30000
    browser_headless: bool = True
    browser_proxy: str = ""

    # ── 认证配置 ──
    auth_storage_state_path: str = ""
    auth_headers: dict[str, str] = field(default_factory=dict)

    # ── 存储配置 ──
    storage_backend: str = "minio"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_bucket_prefix: str = "sisys"
    minio_secure: bool = False
    local_output_dir: str = "./crawl_output"

    # ── RabbitMQ 配置 ──
    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_exchange: str = "sisys.events"

    def to_scrapy_settings(self, user_agent: str | None = None) -> dict:
        """转换为 Scrapy CrawlerProcess 配置字典

        统一 CLI 和 Plugin 的配置来源，激活休眠中间件，
        仅在 enable_browser=True 时注入 Playwright 配置。

        Args:
            user_agent: 自定义 User-Agent 字符串，为 None 时使用 UA 轮换池中的随机值

        Returns:
            Scrapy 兼容的配置字典
        """
        settings: dict = {
            "BOT_NAME": "sisys_crawler",
            "SPIDER_MODULES": ["plugins.crawler.scrapy_engine.spiders"],
            "NEWSPIDER_MODULE": "plugins.crawler.scrapy_engine.spiders",
            "ROBOTSTXT_OBEY": self.respect_robots_txt,
            "CONCURRENT_REQUESTS": self.max_concurrent_requests,
            "DOWNLOAD_DELAY": self.download_delay,
            "DOWNLOAD_TIMEOUT": self.download_timeout,
            "LOG_LEVEL": "INFO",
            "ITEM_PIPELINES": {
                "plugins.crawler.scrapy_engine.pipelines.file_download_pipeline.FileDownloadPipeline": 100,
                "plugins.crawler.scrapy_engine.pipelines.format_detection_pipeline.FormatDetectionPipeline": 200,
                "plugins.crawler.scrapy_engine.pipelines.metadata_pipeline.MetadataPipeline": 300,
                "plugins.crawler.scrapy_engine.pipelines.smart_naming_pipeline.SmartNamingPipeline": 400,
                "plugins.crawler.scrapy_engine.pipelines.storage_pipeline.StoragePipeline": 500,
                "plugins.crawler.scrapy_engine.pipelines.notification_pipeline.NotificationPipeline": 600,
            },
        }

        if user_agent:
            settings["USER_AGENT"] = user_agent

        # ── 中间件（按需激活）──
        middlewares: dict[str, int] = {}
        if self.enable_rate_limit:
            middlewares["plugins.crawler.scrapy_engine.middlewares.rate_limit_middleware.RateLimitMiddleware"] = 400
            settings["RATE_LIMIT_RPS"] = self.rate_limit_rps
        if self.enable_ua_rotation:
            middlewares["plugins.crawler.scrapy_engine.middlewares.user_agent_middleware.UserAgentRotationMiddleware"] = 500
        if self.enable_retry:
            middlewares["plugins.crawler.scrapy_engine.middlewares.retry_middleware.RetryMiddleware"] = 550
            settings["RETRY_TIMES"] = self.retry_times
            settings["RETRY_HTTP_CODES"] = list(self.retry_http_codes)
        if middlewares:
            settings["DOWNLOADER_MIDDLEWARES"] = middlewares

        # ── Playwright 浏览器模式 ──
        if self.enable_browser:
            settings["TWISTED_REACTOR"] = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
            settings["DOWNLOAD_HANDLERS"] = {
                "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
                "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            }
            settings["PLAYWRIGHT_LAUNCH_OPTIONS"] = {
                "headless": self.browser_headless,
            }
            settings["PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT"] = self.browser_navigation_timeout_ms
            settings["PLAYWRIGHT_ABORT_REQUEST"] = (
                "plugins.crawler.scrapy_engine.middlewares.playwright_abort.should_abort_request"
            )
            if self.browser_proxy:
                proxy = {"server": self.browser_proxy}
                settings["PLAYWRIGHT_LAUNCH_OPTIONS"]["proxy"] = proxy

            # storageState 注入（需 enable_browser=True）
            if self.auth_storage_state_path:
                settings["PLAYWRIGHT_CONTEXT_ARGS"] = {
                    "storage_state": self.auth_storage_state_path,
                }

        # HTTP Header Auth 注入（适用所有模式）
        if self.auth_headers:
            settings["DEFAULT_REQUEST_HEADERS"] = dict(self.auth_headers)

        return settings

    @classmethod
    def from_env(cls) -> CrawlerSettings:
        """从环境变量加载配置（前缀 CRAWLER_）

        Returns:
            CrawlerSettings 实例
        """
        return cls(
            host=os.getenv("CRAWLER_HOST", ""),
            port=int(os.getenv("CRAWLER_PORT", "8900")),
            max_depth=int(os.getenv("CRAWLER_MAX_DEPTH", "3")),
            max_concurrent_requests=int(os.getenv("CRAWLER_MAX_CONCURRENT_REQUESTS", "8")),
            download_delay=float(os.getenv("CRAWLER_DOWNLOAD_DELAY", "1.0")),
            download_timeout=int(os.getenv("CRAWLER_DOWNLOAD_TIMEOUT", "30")),
            max_files_per_task=int(os.getenv("CRAWLER_MAX_FILES_PER_TASK", "1000")),
            max_file_size_mb=int(os.getenv("CRAWLER_MAX_FILE_SIZE_MB", "2048")),
            respect_robots_txt=os.getenv("CRAWLER_RESPECT_ROBOTS_TXT", "true").lower() == "true",
            retry_times=int(os.getenv("CRAWLER_RETRY_TIMES", "3")),
            storage_backend=os.getenv("CRAWLER_STORAGE_BACKEND", "minio"),
            minio_endpoint=os.getenv("CRAWLER_MINIO_ENDPOINT", "localhost:9000"),
            minio_access_key=os.getenv("CRAWLER_MINIO_ACCESS_KEY", ""),
            minio_secret_key=os.getenv("CRAWLER_MINIO_SECRET_KEY", ""),
            minio_bucket_prefix=os.getenv("CRAWLER_MINIO_BUCKET_PREFIX", "sisys"),
            minio_secure=os.getenv("CRAWLER_MINIO_SECURE", "false").lower() == "true",
            local_output_dir=os.getenv("CRAWLER_LOCAL_OUTPUT_DIR", "./crawl_output"),
            max_filename_length=int(os.getenv("CRAWLER_MAX_FILENAME_LENGTH", "200")),
            filename_conflict_strategy=os.getenv("CRAWLER_FILENAME_CONFLICT_STRATEGY", "append_hash"),
            rabbitmq_host=os.getenv("CRAWLER_RABBITMQ_HOST", "localhost"),
            rabbitmq_port=int(os.getenv("CRAWLER_RABBITMQ_PORT", "5672")),
            rabbitmq_exchange=os.getenv("CRAWLER_RABBITMQ_EXCHANGE", "sisys.events"),
            # 中间件开关
            enable_rate_limit=os.getenv("CRAWLER_ENABLE_RATE_LIMIT", "true").lower() == "true",
            rate_limit_rps=float(os.getenv("CRAWLER_RATE_LIMIT_RPS", "2.0")),
            enable_ua_rotation=os.getenv("CRAWLER_ENABLE_UA_ROTATION", "true").lower() == "true",
            enable_retry=os.getenv("CRAWLER_ENABLE_RETRY", "true").lower() == "true",
            # Playwright 浏览器模式
            enable_browser=os.getenv("CRAWLER_ENABLE_BROWSER", "false").lower() == "true",
            browser_concurrent_pages=int(os.getenv("CRAWLER_BROWSER_CONCURRENT_PAGES", "4")),
            browser_navigation_timeout_ms=int(os.getenv("CRAWLER_BROWSER_NAVIGATION_TIMEOUT_MS", "30000")),
            browser_headless=os.getenv("CRAWLER_BROWSER_HEADLESS", "true").lower() == "true",
            browser_proxy=os.getenv("CRAWLER_BROWSER_PROXY", ""),
            # 认证配置
            auth_storage_state_path=os.getenv("CRAWLER_AUTH_STORAGE_STATE_PATH", ""),
        )
