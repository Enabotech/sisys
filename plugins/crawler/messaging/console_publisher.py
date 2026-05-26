"""控制台日志事件发布实现模块

开发/调试用，将事件输出到日志

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import logging

from plugins.crawler.core.entities import CrawledFile, CrawlResult

logger = logging.getLogger(__name__)


class ConsolePublisher:
    """控制台日志事件发布（开发/调试用）"""

    async def publish_crawl_completed(self, result: CrawlResult) -> None:
        """发布爬取完成事件到日志

        Args:
            result: 爬取结果
        """
        logger.info(
            "Crawl completed: task_id=%s, files=%d, size=%d bytes",
            result.task_id,
            len(result.files),
            result.total_size_bytes,
        )

    async def publish_crawl_failed(self, task_id: str, error: str) -> None:
        """发布爬取失败事件到日志

        Args:
            task_id: 任务 ID
            error: 错误信息
        """
        logger.error("Crawl failed: task_id=%s, error=%s", task_id, error)

    async def publish_file_crawled(self, file_info: CrawledFile) -> None:
        """发布单文件爬取完成事件到日志

        Args:
            file_info: 爬取到的文件信息
        """
        logger.info(
            "File crawled: name=%s, url=%s, size=%d",
            file_info.smart_name,
            file_info.url,
            file_info.file_size,
        )
