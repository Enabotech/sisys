"""领域层 Crawler HTTP 客户端端口模块

定义 CrawlerClientPort 协议，作为 SISYS 核心侧与 Crawler Service 之间的契约接口。
遵循六边形架构：领域层零外部依赖，仅使用 typing.Protocol 定义抽象端口。

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class CrawlerClientPort(Protocol):
    """Crawler HTTP 客户端端口

    定义与 Crawler Service 交互的抽象接口，
    包括任务提交、状态查询、任务取消、格式列表等操作。
    所有 Crawler HTTP 客户端实现必须实现此端口。
    """

    async def submit_task(
        self,
        domains: list[str],
        seed_urls: list[str] | None = None,
        allowed_extensions: list[str] | None = None,
        max_depth: int = 3,
        follow_subdomains: bool = True,
        max_files: int = 1000,
        download_delay: float = 1.0,
    ) -> str:
        """提交爬取任务

        Args:
            domains: 目标域名列表
            seed_urls: 种子 URL 列表（可选）
            allowed_extensions: 允许的文件扩展名列表（可选）
            max_depth: 最大爬取深度，默认 3
            follow_subdomains: 是否跟随子域名，默认 True
            max_files: 最大文件下载数，默认 1000
            download_delay: 下载延迟秒数，默认 1.0

        Returns:
            任务 ID 字符串
        """

    async def get_task_status(self, task_id: str) -> dict:
        """查询任务状态

        Args:
            task_id: 任务 ID

        Returns:
            任务状态信息字典
        """

    async def cancel_task(self, task_id: str) -> bool:
        """取消任务

        Args:
            task_id: 任务 ID

        Returns:
            True 如果取消成功，False 否则
        """

    async def list_supported_formats(self) -> list[str]:
        """列出支持的文件格式

        Returns:
            支持的文件格式列表
        """
