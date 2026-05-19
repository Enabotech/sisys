"""PostgreSQL UnitOfWork 单元测试"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.infrastructure.messaging.unit_of_work.postgresql_unit_of_work import (
    PostgreSQLUnitOfWork,
)
from src.infrastructure.storage.postgresql.session_context import reset_session, set_session


class TestUowManagedContextVar:
    """测试 UoW 管理标记的 ContextVar 机制"""

    def test_default_is_not_managed(self) -> None:
        """默认情况下 UoW 未管理事务"""
        from src.infrastructure.storage.postgresql.session_context import is_uow_managed

        assert is_uow_managed() is False

    def test_mark_uow_managed_sets_true(self) -> None:
        """mark_uow_managed(True) 设置管理标记"""
        from src.infrastructure.storage.postgresql.session_context import (
            is_uow_managed,
            mark_uow_managed,
            reset_uow_managed,
        )

        token = mark_uow_managed(True)
        try:
            assert is_uow_managed() is True
        finally:
            reset_uow_managed(token)

    def test_mark_uow_managed_resets_correctly(self) -> None:
        """reset_uow_managed 恢复先前状态"""
        from src.infrastructure.storage.postgresql.session_context import (
            is_uow_managed,
            mark_uow_managed,
            reset_uow_managed,
        )

        token = mark_uow_managed(True)
        reset_uow_managed(token)
        assert is_uow_managed() is False

    @pytest.mark.asyncio
    async def test_aexit_marks_uow_managed(self) -> None:
        """__aexit__ 完成后标记 UoW 已管理"""
        from src.infrastructure.storage.postgresql.session_context import is_uow_managed

        mock_session = AsyncMock()
        token = set_session(mock_session)
        try:
            uow = PostgreSQLUnitOfWork()

            async with uow:
                pass

            assert is_uow_managed() is True
        finally:
            reset_session(token)

    @pytest.mark.asyncio
    async def test_aenter_does_not_mark_uow_managed(self) -> None:
        """__aenter__ 不应标记 UoW 已管理（仅在 __aexit__ 后标记）"""
        from src.infrastructure.storage.postgresql.session_context import is_uow_managed

        mock_session = AsyncMock()
        token = set_session(mock_session)
        try:
            uow = PostgreSQLUnitOfWork()

            await uow.__aenter__()

            assert is_uow_managed() is False
        finally:
            reset_session(token)


class TestPostgreSQLUnitOfWorkInstanceIsolation:
    """测试 PostgreSQLUnitOfWork 实例级标志位隔离"""

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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
