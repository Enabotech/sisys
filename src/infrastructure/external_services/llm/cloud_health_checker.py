"""基础设施层云端模型健康检查模块

检查云端 LLM API 可用性，实现 HealthCheckPort

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import logging
import time

import httpx

from src.infrastructure.config.udmr import CloudModelConfig

logger = logging.getLogger(__name__)


class CloudHealthChecker:
    """云端模型健康检查器.

    实现 HealthCheckPort：
    - check(): 检查第一个 enabled 云端模型的 API 可用性
    - close(): 释放 HTTP 客户端资源

    支持 TTL 缓存避免每次路由都执行 HTTP 检查
    """

    def __init__(
        self,
        cloud_configs: list[CloudModelConfig],
        timeout: int = 600,
        cache_ttl: int = 300,
    ) -> None:
        self._cloud_configs = cloud_configs
        self._timeout = timeout
        self._cache_ttl = cache_ttl
        self._client: httpx.AsyncClient | None = None
        # 缓存: (result, timestamp)
        self._cache: tuple[bool, float] | None = None

    async def check(self) -> bool:
        """检查第一个 enabled 云端模型是否可用.

        使用 TTL 缓存避免频繁 HTTP 检查

        Returns:
            True 如果云端 API 可达，False 否则
        """
        # 检查缓存是否有效
        if self._cache is not None:
            cached_result, cached_time = self._cache
            if time.monotonic() - cached_time < self._cache_ttl:
                logger.debug("Health check cache hit: %s", cached_result)
                return cached_result

        # 找到第一个 enabled 的云端模型
        target: CloudModelConfig | None = None
        for cloud in self._cloud_configs:
            if cloud.enabled:
                target = cloud
                break

        if target is None:
            self._cache = (False, time.monotonic())
            return False

        try:
            result = await self._check_model_health(target)
            self._cache = (result, time.monotonic())
            return result
        except Exception:
            logger.exception("Health check failed for %s", target.model)
            self._cache = (False, time.monotonic())
            return False

    async def _check_model_health(self, cloud: CloudModelConfig) -> bool:
        """检查单个云端模型 API 是否可达.

        Args:
            cloud: 云端模型配置

        Returns:
            True 如果 API 返回成功状态码
        """
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)

        try:
            # 使用 HEAD 请求检查 API 可达性
            response = await self._client.head(cloud.endpoint)
            return response.status_code < 500
        except httpx.TimeoutException:
            logger.warning("Health check timeout for %s", cloud.model)
            return False
        except httpx.HTTPError:
            logger.warning("Health check failed for %s", cloud.model)
            return False

    async def close(self) -> None:
        """释放 HTTP 客户端资源."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        self._cache = None
