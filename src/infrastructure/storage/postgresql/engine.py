"""PostgreSQL 数据库引擎抽象层。

提供异步和同步引擎的懒初始化、健康检查和优雅关闭。
"""

from __future__ import annotations

import asyncio

from sqlalchemy import Engine, text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from src.infrastructure.config.postgresql import PostgreSQLConfig


class DatabaseEngine:
    """通用数据库引擎接口。

    支持异步(asyncpg)和同步(psycopg2)引擎的懒初始化。
    """

    def __init__(self, config: PostgreSQLConfig | None = None):
        """初始化 DatabaseEngine。

        Args:
            config: PostgreSQL 配置实例，如果为 None 则从环境变量加载
        """
        self._config = config or PostgreSQLConfig.from_env()
        self._async_engine: AsyncEngine | None = None
        self._sync_engine: Engine | None = None
        self._init_lock = asyncio.Lock()

    def _build_async_url(self) -> str:
        """构建异步引擎连接 URL。"""
        return (
            f"postgresql+asyncpg://{self._config.username}:{self._config.password}"
            f"@{self._config.host}:{self._config.port}/{self._config.database}"
        )

    def _build_sync_url(self) -> str:
        """构建同步引擎连接 URL。"""
        return (
            f"postgresql+psycopg2://{self._config.username}:{self._config.password}"
            f"@{self._config.host}:{self._config.port}/{self._config.database}"
        )

    def get_async_engine(self) -> AsyncEngine:
        """获取异步引擎实例（懒初始化）。

        Returns:
            SQLAlchemy AsyncEngine 实例
        """
        if self._async_engine is None:
            self._async_engine = create_async_engine(
                self._build_async_url(),
                pool_size=self._config.pool_size,
                max_overflow=self._config.max_overflow,
                pool_timeout=self._config.pool_timeout,
                pool_recycle=self._config.pool_recycle,
                echo=self._config.echo,
            )
        return self._async_engine

    def get_sync_engine(self) -> Engine:
        """获取同步引擎实例（懒初始化）。

        Returns:
            SQLAlchemy Engine 实例
        """
        if self._sync_engine is None:
            from sqlalchemy import create_engine

            self._sync_engine = create_engine(
                self._build_sync_url(),
                pool_size=self._config.pool_size,
                max_overflow=self._config.max_overflow,
                pool_timeout=self._config.pool_timeout,
                pool_recycle=self._config.pool_recycle,
                echo=self._config.echo,
            )
        return self._sync_engine

    async def health_check(self) -> bool:
        """执行健康检查。

        执行 SELECT 1 验证数据库连接可用。

        Returns:
            True 如果连接正常，否则 False
        """
        try:
            engine = self.get_async_engine()
            async with engine.connect() as conn:
                result = await conn.execute(text("SELECT 1"))
                return result.scalar() == 1
        except Exception:
            return False

    async def close(self) -> None:
        """关闭所有引擎连接。"""
        if self._async_engine is not None:
            await self._async_engine.dispose()
            self._async_engine = None
        if self._sync_engine is not None:
            self._sync_engine.dispose()
            self._sync_engine = None
