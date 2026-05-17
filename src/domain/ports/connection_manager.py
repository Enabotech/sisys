"""SISYS 领域层连接管理器端口模块

定义所有异步存储连接管理器（PostgreSQL、Qdrant、Neo4j、Redis）
的统一契约。每个管理器拥有连接池，提供健康检查与优雅关闭

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ConnectionManager(Protocol):
    """统一异步连接生命周期契约

    所有异步存储包装器（PostgreSQLManager、QdrantManager、
    Neo4jManager、RedisConnectionManager）通过结构化子类型满足此协议
    """

    async def health_check(self) -> bool:
        """检查底层连接是否健康

        Returns:
            连接存活返回 True，否则返回 False
        """
        ...

    async def close(self) -> None:
        """关闭连接池并释放所有资源"""
        ...

    def get_client(self) -> Any:
        """获取底层客户端实例

        可选：暴露客户端的实现应重写此方法
        默认抛出 NotImplementedError

        Returns:
            底层客户端实例（如 aioredis.Redis、AsyncEngine）

        Raises:
            NotImplementedError: 实现未暴露客户端时抛出
        """
        raise NotImplementedError(
            f"{type(self).__name__}.get_client() is not implemented. This ConnectionManager does not expose a client instance."
        )
