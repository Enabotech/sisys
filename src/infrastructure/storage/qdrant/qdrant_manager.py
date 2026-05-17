"""基础设施层 Qdrant 客户端管理模块

提供 Qdrant 异步客户端的懒初始化、健康检查和优雅关闭功能

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from qdrant_client import AsyncQdrantClient

from src.domain.ports.connection_manager import ConnectionManager
from src.infrastructure.config.qdrant import QdrantConfig


class QdrantManager(ConnectionManager):
    """Qdrant 异步客户端封装

    支持懒初始化、健康检查和优雅关闭
    """

    def __init__(self, config: QdrantConfig | None = None):
        """初始化 Qdrant 客户端封装

        Args:
            config: Qdrant 配置实例，如果为 None 则从环境变量加载
        """
        self._config = config or QdrantConfig.from_env()
        self._client: AsyncQdrantClient | None = None

    def _create_client(self) -> AsyncQdrantClient:
        """创建 Qdrant 异步客户端

        Returns:
            AsyncQdrantClient 实例
        """
        return AsyncQdrantClient(
            host=self._config.host,
            port=self._config.port,
            grpc_port=self._config.grpc_port,
            api_key=self._config.api_key,
            https=self._config.https,
            timeout=int(self._config.timeout) if self._config.timeout else None,
            prefer_grpc=False,
        )

    def get_client(self) -> AsyncQdrantClient:
        """获取异步客户端（懒初始化）

        Returns:
            AsyncQdrantClient 实例
        """
        if self._client is None:
            self._client = self._create_client()
        return self._client

    def get_async_client(self) -> AsyncQdrantClient:
        """获取异步客户端（向后兼容）

        Returns:
            AsyncQdrantClient 实例
        """
        return self.get_client()

    async def health_check(self) -> bool:
        """检查 Qdrant 服务是否可用

        Returns:
            如果服务可用返回 True，否则返回 False
        """
        try:
            client = self.get_client()
            collections = await client.get_collections()
            return collections is not None
        except Exception:
            return False

    async def close(self) -> None:
        """关闭客户端连接"""
        if self._client is not None:
            await self._client.close()
            self._client = None
