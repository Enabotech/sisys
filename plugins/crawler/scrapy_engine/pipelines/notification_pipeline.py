"""通知 Pipeline 模块

发布文件爬取完成事件

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import logging

from plugins.crawler.scrapy_engine.items import CrawledFileItem

logger = logging.getLogger(__name__)


class NotificationPipeline:
    """通知 Pipeline

    发布文件爬取完成事件到消息总线
    """

    def __init__(self):
        self._publisher = None

    def open_spider(self):
        """Spider 启动时初始化事件发布器"""
        from plugins.crawler.messaging.console_publisher import ConsolePublisher

        self._publisher = ConsolePublisher()

    async def process_item(self, item: CrawledFileItem):
        """处理 Item：发布文件爬取事件

        Args:
            item: CrawledFileItem

        Returns:
            发布完成的 Item
        """
        from plugins.crawler.core.entities import CrawledFile

        file_info = CrawledFile(
            url=item.get("url", ""),
            file_path=item.get("file_path", ""),
            file_name=item.get("file_name", ""),
            file_size=item.get("file_size", 0),
            content_type=item.get("content_type", ""),
            file_extension=item.get("file_extension", ""),
            smart_name=item.get("smart_name", ""),
            naming_strategy=item.get("naming_strategy_used", ""),
            task_id=item.get("task_id", ""),
            parent_url=item.get("parent_url", ""),
            page_title=item.get("page_title", ""),
            link_text=item.get("link_text", ""),
            depth=item.get("depth", 0),
            metadata_title=item.get("metadata_title", ""),
            metadata_author=item.get("metadata_author", ""),
        )

        await self._publisher.publish_file_crawled(file_info)
        return item
