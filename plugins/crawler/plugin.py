"""Crawler 插件主类模块

管理爬虫生命周期：安装、激活、启动、查询、取消
"""

from __future__ import annotations

import asyncio
import logging

from scrapy.crawler import CrawlerProcess

from plugins.crawler.config.settings import CrawlerSettings
from plugins.crawler.core.entities import CrawlResult, CrawlTask
from plugins.crawler.core.format.registry import FileFormatHandlerRegistry
from plugins.crawler.core.naming.engine import SmartNamingEngine
from plugins.crawler.core.naming.metadata_extractor import MetadataExtractor
from plugins.crawler.core.value_objects import CrawlStatus
from plugins.crawler.messaging.base import EventPublisher
from plugins.crawler.storage.base import StoragePort

logger = logging.getLogger(__name__)


class CrawlerPlugin:
    """Crawler 插件主类 — 管理爬虫生命周期

    Attributes:
        _settings: 全局配置
        _format_registry: 文件格式注册表
        _naming_engine: 智能命名引擎
        _metadata_extractor: 元数据提取器
        _storage: 存储端口
        _publisher: 事件发布端口
        _tasks: 任务状态字典
        _active_crawler: 活跃的 Scrapy 进程
    """

    def __init__(self, settings: CrawlerSettings | None = None):
        """初始化 Crawler 插件

        Args:
            settings: 爬虫配置，为 None 时使用默认值
        """
        self._settings = settings or CrawlerSettings()
        self._format_registry = FileFormatHandlerRegistry()
        self._naming_engine = SmartNamingEngine(
            max_length=self._settings.max_filename_length,
            conflict_strategy=self._settings.filename_conflict_strategy,
        )
        self._metadata_extractor = MetadataExtractor(self._format_registry)
        self._storage: StoragePort | None = None
        self._publisher: EventPublisher | None = None
        self._tasks: dict[str, CrawlResult] = {}
        self._active_crawler: CrawlerProcess | None = None

    def install(self) -> None:
        """安装插件 — 注册默认格式处理器"""
        self._format_registry.register_default_handlers()
        logger.info("Crawler 插件已安装")

    def activate(self, storage: StoragePort, publisher: EventPublisher) -> None:
        """激活插件 — 注入存储和事件发布端口

        Args:
            storage: 存储端口实现
            publisher: 事件发布端口实现
        """
        self._storage = storage
        self._publisher = publisher
        logger.info("Crawler 插件已激活")

    def start_crawl(self, task: CrawlTask) -> str:
        """启动爬取任务

        Args:
            task: 爬取任务实体

        Returns:
            任务 ID
        """
        result = CrawlResult(task_id=task.task_id)
        result.mark_running()
        self._tasks[task.task_id] = result

        extensions = task.allowed_extensions or self._settings.allowed_extensions

        settings = CrawlerSettings(
            respect_robots_txt=self._settings.respect_robots_txt,
            max_concurrent_requests=self._settings.max_concurrent_requests,
            download_delay=task.download_delay,
            download_timeout=self._settings.download_timeout,
            enable_browser=task.use_browser,
            browser_concurrent_pages=self._settings.browser_concurrent_pages,
            browser_navigation_timeout_ms=self._settings.browser_navigation_timeout_ms,
            browser_headless=self._settings.browser_headless,
            browser_proxy=self._settings.browser_proxy,
            auth_storage_state_path=task.auth_storage_state_path,
            auth_headers=task.auth_headers,
            local_output_dir=self._settings.local_output_dir,
        )
        scrapy_settings = settings.to_scrapy_settings()
        scrapy_settings["CRAWL_OUTPUT_DIR"] = self._settings.local_output_dir

        process = CrawlerProcess(settings=scrapy_settings)

        process.crawl(
            "domain",
            task_id=task.task_id,
            domains=task.domains,
            seed_urls=task.seed_urls,
            allowed_extensions=extensions,
            max_depth=task.max_depth,
            follow_subdomains=task.follow_subdomains,
            use_browser=task.use_browser,
            storage_state_path=task.auth_storage_state_path,
        )

        import threading

        def _run_crawler() -> None:
            process.start()
            self._tasks[task.task_id].mark_completed()
            if self._publisher:
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(
                        self._publisher.publish_crawl_completed(self._tasks[task.task_id]),
                    )
                finally:
                    loop.close()

        thread = threading.Thread(target=_run_crawler, daemon=True)
        thread.start()

        logger.info("爬取任务已启动: %s", task.task_id)
        return task.task_id

    def get_task_status(self, task_id: str) -> CrawlResult | None:
        """查询任务状态

        Args:
            task_id: 任务 ID

        Returns:
            爬取结果，不存在时返回 None
        """
        return self._tasks.get(task_id)

    def cancel_task(self, task_id: str) -> bool:
        """取消任务

        Args:
            task_id: 任务 ID

        Returns:
            是否成功取消
        """
        result = self._tasks.get(task_id)
        if result is None:
            return False

        if result.status in (CrawlStatus.COMPLETED, CrawlStatus.FAILED, CrawlStatus.CANCELLED):
            return False

        result.mark_cancelled()
        logger.info("任务已取消: %s", task_id)
        return True

    def list_tasks(self) -> list[CrawlResult]:
        """列出所有任务

        Returns:
            所有爬取结果列表
        """
        return list(self._tasks.values())

    def list_supported_formats(self) -> list[str]:
        """列出支持的文件格式

        Returns:
            排序后的扩展名列表
        """
        return self._format_registry.supported_extensions_list()
