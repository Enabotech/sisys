"""Shared pytest configuration."""

import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

# Import all fixtures from fixtures.py for shared access
from tests.fixtures import *  # noqa: F403, F401

# Add project root to Python path so `src` can be imported
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session", autouse=True)
def _bootstrap_once() -> None:
    """Bootstrap the port registry once per test session."""
    from src.composition_root import bootstrap
    from tests.environments import get_test_env

    get_test_env()
    bootstrap()


# =============================================================================
# PostgreSQL Session Fixtures
# =============================================================================


def _create_mock_session() -> AsyncMock:
    """创建标准 mock AsyncSession（含常用方法预配置）"""
    session = AsyncMock(spec=AsyncSession)
    session.add = Mock()
    session.delete = Mock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.begin = AsyncMock()
    session.begin_nested = AsyncMock()
    session.in_transaction = Mock(return_value=True)
    session.execute = AsyncMock()
    return session


@pytest.fixture
async def pg_session() -> AsyncGenerator[AsyncMock, None]:
    """标准 PostgreSQL mock session fixture

    自动管理 ContextVar 生命周期，测试结束后自动清理
    替代分散在各测试文件中的 set_session()/reset_session() 手动管理

    用法::

        async def test_save(pg_session):
            repo = UserRepository()
            await repo.save(entity)
            pg_session.flush.assert_called()
    """
    from src.infrastructure.storage.postgresql.session_context import with_session

    mock = _create_mock_session()
    async with with_session(mock):
        yield mock


@asynccontextmanager
async def pg_session_context():
    """异步上下文管理器版本的 mock session（用于 fixture 链式组合）

    用法::

        @pytest.fixture
        async def user_repo(pg_session):
            async with pg_session_context() as session:
                yield UserRepository()
    """
    from src.infrastructure.storage.postgresql.session_context import with_session

    mock = _create_mock_session()
    async with with_session(mock):
        yield mock
