"""Neo4j 客户端封装。

提供懒初始化、健康检查和优雅关闭功能。
"""

from __future__ import annotations

from neo4j import AsyncDriver, AsyncGraphDatabase

from src.domain.ports.connection_manager import ConnectionManager
from src.infrastructure.config.neo4j import Neo4jConfig


class Neo4jClientWrapper(ConnectionManager):
    """Neo4j 异步客户端封装。

    支持懒初始化、健康检查和优雅关闭。
    """

    def __init__(self, config: Neo4jConfig | None = None):
        """初始化 Neo4j 客户端封装。

        Args:
            config: Neo4j 配置实例，如果为 None 则从环境变量加载
        """
        self._config = config or Neo4jConfig.from_env()
        self._driver: AsyncDriver | None = None

    def _create_driver(self) -> AsyncDriver:
        """创建 Neo4j 异步驱动。

        Returns:
            AsyncDriver 实例
        """
        driver = AsyncGraphDatabase.driver(
            self._config.uri,
            auth=(self._config.username, self._config.password),
            max_connection_pool_size=self._config.max_connection_pool_size,
            connection_acquisition_timeout=self._config.connection_timeout,
        )
        return driver

    def get_client(self) -> AsyncDriver:
        """获取异步驱动（懒初始化）。

        Returns:
            AsyncDriver 实例
        """
        if self._driver is None:
            self._driver = self._create_driver()
        return self._driver

    def get_async_driver(self) -> AsyncDriver:
        """获取异步驱动（向后兼容）。

        Returns:
            AsyncDriver 实例
        """
        return self.get_client()

    async def health_check(self) -> bool:
        """检查 Neo4j 服务是否可用。

        Returns:
            如果服务可用返回 True，否则返回 False
        """
        try:
            driver = self.get_client()
            async with driver.session(database=self._config.database) as session:
                result = await session.run("RETURN 1")
                await result.single()
            return True
        except Exception:
            return False

    async def close(self) -> None:
        """关闭驱动连接。"""
        if self._driver is not None:
            await self._driver.close()
            self._driver = None
