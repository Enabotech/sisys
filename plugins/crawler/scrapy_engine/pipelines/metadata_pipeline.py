"""元数据提取 Pipeline 模块

从文件中提取元数据（标题、作者等）

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import logging

from plugins.crawler.scrapy_engine.items import CrawledFileItem

logger = logging.getLogger(__name__)


class MetadataPipeline:
    """元数据提取 Pipeline

    使用 MetadataExtractor 从文件中提取元数据
    """

    def __init__(self):
        self._extractor = None

    def open_spider(self):
        """Spider 启动时初始化元数据提取器"""
        from plugins.crawler.core.format.registry import FileFormatHandlerRegistry
        from plugins.crawler.core.naming.metadata_extractor import MetadataExtractor

        registry = FileFormatHandlerRegistry()
        registry.register_default_handlers()
        self._extractor = MetadataExtractor(registry)

    def process_item(self, item: CrawledFileItem):
        """处理 Item：提取文件元数据

        Args:
            item: CrawledFileItem

        Returns:
            填充了元数据字段的 Item
        """
        file_path = item.get("file_path", "")
        extension = item.get("file_extension", "")
        content_type = item.get("content_type", "")

        metadata = self._extractor.extract(file_path, extension, content_type)

        item["metadata_title"] = metadata.title
        item["metadata_content_title"] = metadata.content_title
        item["metadata_author"] = metadata.author
        item["metadata_created"] = metadata.created
        return item
