"""格式检测 Pipeline 模块

基于扩展名和 MIME 类型检测文件格式

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import logging

from plugins.crawler.scrapy_engine.items import CrawledFileItem

logger = logging.getLogger(__name__)


class FormatDetectionPipeline:
    """格式检测 Pipeline

    使用 FileFormatHandlerRegistry 检测文件格式
    """

    def __init__(self):
        self._registry = None

    def open_spider(self, spider):
        """Spider 启动时初始化注册表"""
        from plugins.crawler.core.format.registry import FileFormatHandlerRegistry

        self._registry = FileFormatHandlerRegistry()
        self._registry.register_default_handlers()

    def process_item(self, item: CrawledFileItem, spider):
        """处理 Item：检测文件格式

        Args:
            item: CrawledFileItem
            spider: Spider 实例

        Returns:
            填充了 detected_format 的 Item
        """
        extension = item.get("file_extension", "")
        content_type = item.get("content_type", "")
        file_path = item.get("file_path", "")

        handler = self._registry.get_handler(extension)
        if handler is None and content_type:
            handler = self._registry.detect_format(file_path, content_type)

        item["detected_format"] = extension if handler else "unknown"
        return item
