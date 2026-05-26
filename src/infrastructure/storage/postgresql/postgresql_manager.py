"""基础设施层 PostgreSQL 引擎管理模块

提供异步和同步引擎的懒初始化、健康检查和优雅关闭
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import Engine, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from src.domain.ports.connection_manager import ConnectionManager
from src.infrastructure.config.postgresql import PostgreSQLConfig

_ISOLATION_LEVELS = {"SERIALIZABLE", "REPEATABLE READ", "READ COMMITTED", "READ UNCOMMITTED"}


class PostgreSQLManager(ConnectionManager):
    """PostgreSQL 数据库引擎管理器，支持异步和同步引擎的懒初始化

    Attributes:
        _config: PostgreSQL 连接配置
        _async_engine: 异步引擎实例（懒初始化）
        _sync_engine: 同步引擎实例（懒初始化）
        _init_lock: 异步初始化锁
        _async_session_maker: 异步会话工厂
    """

    def __init__(self, config: PostgreSQLConfig | None = None):
        """初始化 PostgreSQLManager

        Args:
            config: PostgreSQL 配置实例，如果为 None 则从环境变量加载
        """
        self._config = config or PostgreSQLConfig.from_env()
        self._async_engine: AsyncEngine | None = None
        self._sync_engine: Engine | None = None
        self._init_lock = asyncio.Lock()
        self._async_session_maker: async_sessionmaker[AsyncSession] | None = None

    def _build_async_url(self) -> str:
        """构建异步引擎连接 URL（asyncpg 驱动）

        Returns:
            异步连接 URL 字符串
        """
        return (
            f"postgresql+asyncpg://{self._config.username}:{self._config.password}"
            f"@{self._config.host}:{self._config.port}/{self._config.database}"
        )

    def _build_sync_url(self) -> str:
        """构建同步引擎连接 URL（psycopg2 驱动）

        Returns:
            同步连接 URL 字符串
        """
        return (
            f"postgresql+psycopg2://{self._config.username}:{self._config.password}"
            f"@{self._config.host}:{self._config.port}/{self._config.database}"
        )

    def get_client(self) -> AsyncEngine:
        """获取异步引擎实例（ConnectionManager 统一接口）

        Returns:
            SQLAlchemy AsyncEngine 实例
        """
        return self.get_async_engine()

    def get_async_engine(self) -> AsyncEngine:
        """获取异步引擎实例（懒初始化）

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
        """获取同步引擎实例（懒初始化）

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
        """执行健康检查

        执行 SELECT 1 验证数据库连接可用

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
        """关闭所有引擎连接"""
        if self._async_engine is not None:
            await self._async_engine.dispose()
            self._async_engine = None
        if self._sync_engine is not None:
            self._sync_engine.dispose()
            self._sync_engine = None

    @asynccontextmanager
    async def get_async_session(self) -> AsyncIterator[AsyncSession]:
        """获取异步会话上下文管理器

        Returns:
            AsyncSession 实例作为异步上下文管理器
        """
        if self._async_session_maker is None:
            self._async_session_maker = async_sessionmaker(
                bind=self.get_async_engine(),
                class_=AsyncSession,
                expire_on_commit=False,
            )
        async with self._async_session_maker() as session:
            yield session

    @asynccontextmanager
    async def get_session_with_isolation(self, isolation_level: str) -> AsyncIterator[AsyncSession]:
        """获取指定隔离级别的异步会话

        Args:
            isolation_level: 隔离级别（SERIALIZABLE, REPEATABLE READ, READ COMMITTED, READ UNCOMMITTED）

        Yields:
            AsyncSession 实例

        Raises:
            ValueError: 隔离级别不支持
        """
        if isolation_level.upper() not in _ISOLATION_LEVELS:
            raise ValueError(f"Unsupported isolation level: {isolation_level}. Must be one of {_ISOLATION_LEVELS}")

        maker = async_sessionmaker(
            bind=self.get_async_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            isolation_level=isolation_level.upper(),
        )
        async with maker() as session:
            yield session
