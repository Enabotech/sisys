"""事件发布抽象端口模块

定义 EventPublisher 协议，抽象事件发布行为

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from plugins.crawler.core.entities import CrawledFile, CrawlResult


@runtime_checkable
class EventPublisher(Protocol):
    """事件发布抽象端口

    定义爬取事件的统一发布接口
    """

    async def publish_crawl_completed(self, result: CrawlResult) -> None:
        """发布爬取完成事件

        Args:
            result: 爬取结果
        """
        ...

    async def publish_crawl_failed(self, task_id: str, error: str) -> None:
        """发布爬取失败事件

        Args:
            task_id: 任务 ID
            error: 错误信息
        """
        ...

    async def publish_file_crawled(self, file_info: CrawledFile) -> None:
        """发布单文件爬取完成事件

        Args:
            file_info: 爬取到的文件信息
        """
        ...
