"""PostgreSQL UnitOfWork 单元测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.infrastructure.messaging.unit_of_work.postgresql_unit_of_work import (
    PostgreSQLUnitOfWork,
)
from src.infrastructure.storage.postgresql.session_context import reset_session, set_session


class TestPostgreSQLUnitOfWorkContextManager:
    """测试 PostgreSQLUnitOfWork 异步上下文管理器协议。"""

    @pytest.mark.asyncio
    async def test_aenter_calls_begin(self) -> None:
        """__aenter__ 应调用 begin()。"""
        mock_session = AsyncMock()
        token = set_session(mock_session)
        try:
            uow = PostgreSQLUnitOfWork()

            result = await uow.__aenter__()

            mock_session.begin.assert_awaited_once()
            assert result is uow
        finally:
            reset_session(token)

    @pytest.mark.asyncio
    async def test_aexit_commits_on_no_exception(self) -> None:
        """__aexit__ 无异常时应 commit 并 close。"""
        mock_session = AsyncMock()
        token = set_session(mock_session)
        try:
            uow = PostgreSQLUnitOfWork()

            await uow.__aexit__(None, None, None)

            mock_session.commit.assert_awaited_once()
            mock_session.close.assert_awaited_once()
            mock_session.rollback.assert_not_called()
        finally:
            reset_session(token)

    @pytest.mark.asyncio
    async def test_aexit_rollback_on_exception(self) -> None:
        """__aexit__ 有异常时应 rollback 并 close。"""
        mock_session = AsyncMock()
        token = set_session(mock_session)
        try:
            uow = PostgreSQLUnitOfWork()

            await uow.__aexit__(ValueError, ValueError("test"), None)

            mock_session.rollback.assert_awaited_once()
            mock_session.close.assert_awaited_once()
            mock_session.commit.assert_not_called()
        finally:
            reset_session(token)

    @pytest.mark.asyncio
    async def test_full_context_manager_cycle(self) -> None:
        """完整上下文管理器生命周期。"""
        mock_session = AsyncMock()
        token = set_session(mock_session)
        try:
            uow = PostgreSQLUnitOfWork()

            async with uow:
                pass

            mock_session.begin.assert_awaited_once()
            mock_session.commit.assert_awaited_once()
            mock_session.close.assert_awaited_once()
            mock_session.rollback.assert_not_called()
        finally:
            reset_session(token)

    @pytest.mark.asyncio
    async def test_full_context_manager_with_exception(self) -> None:
        """上下文管理器中发生异常时应 rollback。"""
        mock_session = AsyncMock()
        token = set_session(mock_session)
        try:
            uow = PostgreSQLUnitOfWork()

            try:
                async with uow:
                    raise RuntimeError("Test error")
            except RuntimeError:
                pass

            mock_session.begin.assert_awaited_once()
            mock_session.rollback.assert_awaited_once()
            mock_session.close.assert_awaited_once()
            mock_session.commit.assert_not_called()
        finally:
            reset_session(token)
