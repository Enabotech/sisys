"""Neo4j 客户端封装。

提供懒初始化、健康检查和优雅关闭功能。
"""

from __future__ import annotations

from neo4j import AsyncDriver, AsyncGraphDatabase

from src.domain.ports.connection_manager import ConnectionManager


class Neo4jClientWrapper(ConnectionManager):
    """Neo4j 异步客户端封装。

    支持懒初始化、健康检查和优雅关闭。
    """

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        username: str = "neo4j",
        password: str = "",
        database: str = "neo4j",
        max_connection_pool_size: int = 50,
        connection_timeout: float = 30.0,
        max_retry_time: float = 30.0,
    ):
        """初始化 Neo4j 客户端封装。

        Args:
            uri: Neo4j 服务地址
            username: 认证用户名
            password: 认证密码
            database: 数据库名称
            max_connection_pool_size: 最大连接池大小
            connection_timeout: 连接超时（秒）
            max_retry_time: 最大重试时间（秒）
        """
        self._uri = uri
        self._username = username
        self._password = password
        self._database = database
        self._max_connection_pool_size = max_connection_pool_size
        self._connection_timeout = connection_timeout
        self._max_retry_time = max_retry_time
        self._driver: AsyncDriver | None = None

    def _create_driver(self) -> AsyncDriver:
        """创建 Neo4j 异步驱动。

        Returns:
            AsyncDriver 实例
        """
        driver = AsyncGraphDatabase.driver(
            self._uri,
            auth=(self._username, self._password),
            max_connection_pool_size=self._max_connection_pool_size,
            connection_acquisition_timeout=self._connection_timeout,
        )
        return driver

    def get_async_driver(self) -> AsyncDriver:
        """获取异步驱动（懒初始化）。

        Returns:
            AsyncDriver 实例
        """
        if self._driver is None:
            self._driver = self._create_driver()
        return self._driver

    async def health_check(self) -> bool:
        """检查 Neo4j 服务是否可用。

        Returns:
            如果服务可用返回 True，否则返回 False
        """
        try:
            driver = self.get_async_driver()
            async with driver.session(database=self._database) as session:
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
