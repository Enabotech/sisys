"""Neo4j 客户端封装

提供健康检查和优雅关闭功能
"""

from __future__ import annotations

from neo4j import AsyncDriver, AsyncGraphDatabase

from src.domain.ports.connection_manager import ConnectionManager
from src.infrastructure.config.neo4j import Neo4jConfig


class Neo4jManager(ConnectionManager):
    """Neo4j 异步客户端封装

    支持构造函数注入驱动实例、健康检查和优雅关闭
    """

    def __init__(self, driver: AsyncDriver, *, database: str = "neo4j") -> None:
        """初始化 Neo4j 客户端封装

        Args:
            driver: Neo4j 异步驱动实例
            database: 默认数据库名称
        """
        self._driver: AsyncDriver = driver
        self._database = database

    @classmethod
    def from_config(cls, config: Neo4jConfig | None = None) -> Neo4jManager:
        """从配置创建封装实例（生产环境入口）

        Args:
            config: Neo4j 配置实例，如果为 None 则从环境变量加载

        Returns:
            Neo4jManager 实例
        """
        config = config or Neo4jConfig.from_env()
        driver = AsyncGraphDatabase.driver(
            config.uri,
            auth=(config.username, config.password),
            max_connection_pool_size=config.max_connection_pool_size,
            connection_acquisition_timeout=config.connection_timeout,
        )
        return cls(driver, database=config.database)

    def get_client(self) -> AsyncDriver:
        """获取异步驱动

        Returns:
            AsyncDriver 实例
        """
        return self._driver

    def get_async_driver(self) -> AsyncDriver:
        """获取异步驱动（向后兼容）

        Returns:
            AsyncDriver 实例
        """
        return self._driver

    async def health_check(self) -> bool:
        """检查 Neo4j 服务是否可用

        Returns:
            如果服务可用返回 True，否则返回 False
        """
        try:
            async with self._driver.session(database=self._database) as session:
                result = await session.run("RETURN 1")
                await result.single()
            return True
        except Exception:
            return False

    async def close(self) -> None:
        """关闭驱动连接。"""
        await self._driver.close()
