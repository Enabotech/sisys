"""智能命名 Pipeline 模块

使用 SmartNamingEngine 为文件生成智能名称

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import logging

from plugins.crawler.scrapy_engine.items import CrawledFileItem

logger = logging.getLogger(__name__)


class SmartNamingPipeline:
    """智能命名 Pipeline

    使用 SmartNamingEngine 为文件生成有意义的名称
    """

    def __init__(self):
        self._engine = None

    def open_spider(self):
        """Spider 启动时初始化命名引擎"""
        from plugins.crawler.core.naming.engine import SmartNamingEngine

        self._engine = SmartNamingEngine(
            max_length=200,
            conflict_strategy="append_hash",
        )

    def process_item(self, item: CrawledFileItem):
        """处理 Item：生成智能文件名

        Args:
            item: CrawledFileItem

        Returns:
            填充了 smart_name 和 naming_strategy_used 的 Item
        """
        candidate = self._engine.generate_name(
            metadata_title=item.get("metadata_title", ""),
            content_title=item.get("metadata_content_title", ""),
            page_title=item.get("page_title", ""),
            link_text=item.get("link_text", ""),
            url=item.get("url", ""),
            file_extension=item.get("file_extension", ""),
            author=item.get("metadata_author", ""),
        )

        item["smart_name"] = candidate.filename
        item["naming_strategy_used"] = candidate.strategy_name
        logger.debug(
            "命名完成: %s → %s (策略: %s)",
            item.get("file_name", ""),
            candidate.filename,
            candidate.strategy_name,
        )
        return item
