"""基础设施层 Crawler HTTP 客户端适配器模块

使用 httpx.AsyncClient 实现 CrawlerClientPort，调用 Crawler Service 的 REST API。
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class HttpCrawlerClient:
    """Crawler HTTP 客户端适配器

    使用 httpx.AsyncClient 调用 Crawler Service 的 REST API。
    实现 CrawlerClientPort 端口接口。
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
    ) -> None:
        """初始化 HTTP Crawler 客户端

        Args:
            base_url: Crawler Service 的基础 URL
            timeout: HTTP 请求超时时间（秒），默认 30.0
        """
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """获取或创建 HTTP 客户端实例

        Returns:
            httpx.AsyncClient 实例
        """
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def close(self) -> None:
        """关闭 HTTP 客户端，释放资源"""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

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

        Raises:
            httpx.HTTPError: HTTP 请求失败时抛出
        """
        client = await self._get_client()

        payload: dict[str, Any] = {
            "domains": domains,
            "max_depth": max_depth,
            "follow_subdomains": follow_subdomains,
            "max_files": max_files,
            "download_delay": download_delay,
        }

        if seed_urls is not None:
            payload["seed_urls"] = seed_urls
        if allowed_extensions is not None:
            payload["allowed_extensions"] = allowed_extensions

        response = await client.post(
            f"{self._base_url}/api/v1/tasks",
            json=payload,
        )
        response.raise_for_status()

        data: dict[str, Any] = response.json()
        task_id: str = str(data.get("task_id", ""))
        logger.info("Submitted crawler task: %s", task_id)
        return task_id

    async def get_task_status(self, task_id: str) -> dict:
        """查询任务状态

        Args:
            task_id: 任务 ID

        Returns:
            任务状态信息字典

        Raises:
            httpx.HTTPError: HTTP 请求失败时抛出
        """
        client = await self._get_client()

        response = await client.get(
            f"{self._base_url}/api/v1/tasks/{task_id}",
        )
        response.raise_for_status()

        data: dict[str, Any] = response.json()
        logger.debug("Task %s status: %s", task_id, data.get("status"))
        return data

    async def cancel_task(self, task_id: str) -> bool:
        """取消任务

        Args:
            task_id: 任务 ID

        Returns:
            True 如果取消成功，False 否则

        Raises:
            httpx.HTTPError: HTTP 请求失败时抛出
        """
        client = await self._get_client()

        response = await client.delete(
            f"{self._base_url}/api/v1/tasks/{task_id}",
        )

        if response.status_code == 200:
            logger.info("Cancelled crawler task: %s", task_id)
            return True

        logger.warning("Failed to cancel task %s: status %d", task_id, response.status_code)
        return False

    async def list_supported_formats(self) -> list[str]:
        """列出支持的文件格式

        Returns:
            支持的文件格式列表

        Raises:
            httpx.HTTPError: HTTP 请求失败时抛出
        """
        client = await self._get_client()

        response = await client.get(
            f"{self._base_url}/api/v1/formats",
        )
        response.raise_for_status()

        data = response.json()
        formats: list[str] = data.get("formats", [])
        logger.debug("Supported formats: %s", formats)
        return formats
