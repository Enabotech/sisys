"""文件下载 Pipeline 模块

验证已下载文件的基本信息

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import logging
import os

from plugins.crawler.scrapy_engine.items import CrawledFileItem

logger = logging.getLogger(__name__)


class FileDownloadPipeline:
    """文件下载验证 Pipeline

    验证文件已下载到临时目录且大小有效
    """

    def process_item(self, item: CrawledFileItem, spider):
        """处理 Item：验证文件下载

        Args:
            item: CrawledFileItem
            spider: Spider 实例

        Returns:
            验证通过的 Item

        Raises:
            DropItem: 文件不存在或大小为 0
        """
        file_path = item.get("file_path", "")
        if not file_path or not os.path.exists(file_path):
            from scrapy.exceptions import DropItem

            raise DropItem(f"文件不存在: {file_path}")

        actual_size = os.path.getsize(file_path)
        if actual_size == 0:
            from scrapy.exceptions import DropItem

            os.remove(file_path)
            raise DropItem(f"文件为空: {file_path}")

        item["file_size"] = actual_size
        return item
