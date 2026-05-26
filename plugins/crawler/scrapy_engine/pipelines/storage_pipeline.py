"""存储 Pipeline 模块

将文件存储到配置的存储后端

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import asyncio
import logging

from plugins.crawler.scrapy_engine.items import CrawledFileItem

logger = logging.getLogger(__name__)


class StoragePipeline:
    """存储 Pipeline

    将文件推送到配置的存储后端（本地/MinIO）
    """

    def __init__(self):
        self._storage = None

    def open_spider(self, spider):
        """Spider 启动时初始化存储"""
        from plugins.crawler.config.settings import CrawlerSettings
        from plugins.crawler.storage.local_storage import LocalStorage

        settings = CrawlerSettings()
        self._storage = LocalStorage(output_dir=settings.local_output_dir)

    def process_item(self, item: CrawledFileItem, spider):
        """处理 Item：存储文件

        Args:
            item: CrawledFileItem
            spider: Spider 实例

        Returns:
            存储完成的 Item
        """
        loop = asyncio.new_event_loop()
        try:
            object_path = loop.run_until_complete(
                self._storage.store_file(
                    file_name=item.get("smart_name", item.get("file_name", "")),
                    file_path=item.get("file_path", ""),
                    content_type=item.get("content_type", ""),
                    metadata={"task_id": item.get("task_id", "")},
                ),
            )
            logger.info("文件已存储: %s → %s", item.get("smart_name", ""), object_path)
        finally:
            loop.close()
        return item
