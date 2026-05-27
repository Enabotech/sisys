"""Scrapy 引擎默认设置模块

定义 Scrapy 爬虫的默认配置，作为参考文档。
实际运行时配置由 CrawlerSettings.to_scrapy_settings() 生成。
"""

from __future__ import annotations

BOT_NAME = "sisys_crawler"
SPIDER_MODULES = ["plugins.crawler.scrapy_engine.spiders"]
NEWSPIDER_MODULE = "plugins.crawler.scrapy_engine.spiders"

ROBOTSTXT_OBEY = True

CONCURRENT_REQUESTS = 8
DOWNLOAD_DELAY = 1.0
DOWNLOAD_TIMEOUT = 30

ITEM_PIPELINES = {
    "plugins.crawler.scrapy_engine.pipelines.file_download_pipeline.FileDownloadPipeline": 100,
    "plugins.crawler.scrapy_engine.pipelines.format_detection_pipeline.FormatDetectionPipeline": 200,
    "plugins.crawler.scrapy_engine.pipelines.metadata_pipeline.MetadataPipeline": 300,
    "plugins.crawler.scrapy_engine.pipelines.smart_naming_pipeline.SmartNamingPipeline": 400,
    "plugins.crawler.scrapy_engine.pipelines.storage_pipeline.StoragePipeline": 500,
    "plugins.crawler.scrapy_engine.pipelines.notification_pipeline.NotificationPipeline": 600,
}

DOWNLOADER_MIDDLEWARES = {
    "plugins.crawler.scrapy_engine.middlewares.rate_limit_middleware.RateLimitMiddleware": 400,
    "plugins.crawler.scrapy_engine.middlewares.user_agent_middleware.UserAgentRotationMiddleware": 500,
    "plugins.crawler.scrapy_engine.middlewares.retry_middleware.RetryMiddleware": 550,
}

RATE_LIMIT_RPS = 2.0
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]

USER_AGENT = "SISYS Crawler/0.1.0"

LOG_LEVEL = "INFO"

# ── Playwright 浏览器模式配置（仅 enable_browser=True 时生效）──
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}

PLAYWRIGHT_LAUNCH_OPTIONS = {
    "headless": True,
}

PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 30000

PLAYWRIGHT_ABORT_REQUEST = "plugins.crawler.scrapy_engine.middlewares.playwright_abort.should_abort_request"
