"""Qdrant 客户端封装。

提供懒初始化、健康检查和优雅关闭功能。
"""

from __future__ import annotations

from qdrant_client import AsyncQdrantClient

from src.domain.ports.connection_manager import ConnectionManager


class QdrantClientWrapper(ConnectionManager):
    """Qdrant 异步客户端封装。

    支持懒初始化、健康检查和优雅关闭。
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6333,
        grpc_port: int = 6334,
        api_key: str | None = None,
        https: bool = False,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        """初始化 Qdrant 客户端封装。

        Args:
            host: Qdrant 服务主机地址
            port: REST API 端口
            grpc_port: gRPC API 端口
            api_key: API 认证密钥（可选）
            https: 是否使用 HTTPS 连接
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
        """
        self._host = host
        self._port = port
        self._grpc_port = grpc_port
        self._api_key = api_key
        self._https = https
        self._timeout = timeout
        self._max_retries = max_retries
        self._client: AsyncQdrantClient | None = None

    def _create_client(self) -> AsyncQdrantClient:
        """创建 Qdrant 异步客户端。

        Returns:
            AsyncQdrantClient 实例
        """
        return AsyncQdrantClient(
            host=self._host,
            port=self._port,
            grpc_port=self._grpc_port,
            api_key=self._api_key,
            https=self._https,
            timeout=int(self._timeout) if self._timeout else None,
            prefer_grpc=False,
        )

    def get_async_client(self) -> AsyncQdrantClient:
        """获取异步客户端（懒初始化）。

        Returns:
            AsyncQdrantClient 实例
        """
        if self._client is None:
            self._client = self._create_client()
        return self._client

    async def health_check(self) -> bool:
        """检查 Qdrant 服务是否可用。

        Returns:
            如果服务可用返回 True，否则返回 False
        """
        try:
            client = self.get_async_client()
            collections = await client.get_collections()
            return collections is not None
        except Exception:
            return False

    async def close(self) -> None:
        """关闭客户端连接。"""
        if self._client is not None:
            await self._client.close()
            self._client = None
