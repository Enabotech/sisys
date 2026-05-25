"""PostgreSQL UnitOfWork 单元测试"""

from __future__ import annotations

from unittest.mock import AsyncMock

from src.infrastructure.messaging.unit_of_work.postgresql_unit_of_work import (
    PostgreSQLUnitOfWork,
)
from src.infrastructure.storage.postgresql.session_context import reset_session, set_session


class TestPostgreSQLUnitOfWorkInstanceIsolation:
    """测试 PostgreSQLUnitOfWork 实例级标志位隔离"""

    async def test_two_instances_have_independent_state(self) -> None:
        """两个实例的 _committed/_rolled_back 状态完全独立"""
        mock_session = AsyncMock()
        token = set_session(mock_session)
        try:
            uow1 = PostgreSQLUnitOfWork()
            uow2 = PostgreSQLUnitOfWork()

            await uow1.commit()

            assert uow1._committed is True
            assert uow2._committed is False
        finally:
            reset_session(token)

    async def test_two_instances_rollback_isolation(self) -> None:
        """一个实例 rollback 不影响另一个实例"""
        mock_session = AsyncMock()
        token = set_session(mock_session)
        try:
            uow1 = PostgreSQLUnitOfWork()
            uow2 = PostgreSQLUnitOfWork()

            await uow1.rollback()

            assert uow1._rolled_back is True
            assert uow2._rolled_back is False
        finally:
            reset_session(token)

    async def test_new_instance_has_clean_state(self) -> None:
        """新创建的实例标志位均为 False"""
        mock_session = AsyncMock()
        token = set_session(mock_session)
        try:
            uow = PostgreSQLUnitOfWork()
            assert uow._committed is False
            assert uow._rolled_back is False
        finally:
            reset_session(token)


class TestPostgreSQLUnitOfWorkContextManager:
    """测试 PostgreSQLUnitOfWork 异步上下文管理器协议"""

    async def test_aenter_calls_begin(self) -> None:
        """__aenter__ 应调用 begin()"""
        mock_session = AsyncMock()
        token = set_session(mock_session)
        try:
            uow = PostgreSQLUnitOfWork()

            result = await uow.__aenter__()

            mock_session.begin.assert_awaited_once()
            assert result is uow
        finally:
            reset_session(token)

    async def test_aexit_commits_on_no_exception(self) -> None:
        """__aexit__ 无异常时应 commit 但不 close"""
        mock_session = AsyncMock()
        token = set_session(mock_session)
        try:
            uow = PostgreSQLUnitOfWork()

            await uow.__aexit__(None, None, None)

            mock_session.commit.assert_awaited_once()
            mock_session.close.assert_not_called()
            mock_session.rollback.assert_not_called()
        finally:
            reset_session(token)

    async def test_aexit_rollback_on_exception(self) -> None:
        """__aexit__ 有异常时应 rollback 但不 close"""
        mock_session = AsyncMock()
        token = set_session(mock_session)
        try:
            uow = PostgreSQLUnitOfWork()

            await uow.__aexit__(ValueError, ValueError("test"), None)

            mock_session.rollback.assert_awaited_once()
            mock_session.close.assert_not_called()
            mock_session.commit.assert_not_called()
        finally:
            reset_session(token)

    async def test_full_context_manager_cycle(self) -> None:
        """完整上下文管理器生命周期（不 close）"""
        mock_session = AsyncMock()
        token = set_session(mock_session)
        try:
            uow = PostgreSQLUnitOfWork()

            async with uow:
                pass

            mock_session.begin.assert_awaited_once()
            mock_session.commit.assert_awaited_once()
            mock_session.close.assert_not_called()
            mock_session.rollback.assert_not_called()
        finally:
            reset_session(token)

    async def test_full_context_manager_with_exception(self) -> None:
        """上下文管理器中发生异常时应 rollback（不 close）"""
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
            mock_session.close.assert_not_called()
            mock_session.commit.assert_not_called()
        finally:
            reset_session(token)

    async def test_aexit_does_not_close_session(self) -> None:
        """__aexit__ 不应调用 session.close()"""
        mock_session = AsyncMock()
        token = set_session(mock_session)
        try:
            uow = PostgreSQLUnitOfWork()

            async with uow:
                pass

            mock_session.close.assert_not_called()
        finally:
            reset_session(token)
