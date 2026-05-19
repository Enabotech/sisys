"""UnitOfWork Protocol 和实现测试。"""

from __future__ import annotations

from typing import Protocol

import pytest

from src.infrastructure.storage.postgresql.session_context import reset_session, set_session


class TestUnitOfWorkInterface:
    """UnitOfWork Protocol 接口测试。"""

    def test_unit_of_work_is_protocol(self):
        """UnitOfWork 应该是 Protocol。"""
        from src.domain.ports.unit_of_work import UnitOfWork

        assert issubclass(UnitOfWork, Protocol)

    def test_unit_of_work_has_begin_method(self):
        """UnitOfWork 应声明 begin() 方法。"""
        from src.domain.ports.unit_of_work import UnitOfWork

        assert hasattr(UnitOfWork, "begin")

    def test_unit_of_work_has_commit_method(self):
        """UnitOfWork 应声明 commit() 方法。"""
        from src.domain.ports.unit_of_work import UnitOfWork

        assert hasattr(UnitOfWork, "commit")

    def test_unit_of_work_has_rollback_method(self):
        """UnitOfWork 应声明 rollback() 方法。"""
        from src.domain.ports.unit_of_work import UnitOfWork

        assert hasattr(UnitOfWork, "rollback")

    def test_unit_of_work_has_no_close_method(self):
        """UnitOfWork 不应声明 close() 方法（由 Middleware 负责）。"""
        from src.domain.ports.unit_of_work import UnitOfWork

        assert not hasattr(UnitOfWork, "close")

    def test_unit_of_work_factory_protocol_exists(self):
        """UnitOfWorkFactory Protocol 应存在。"""
        from src.domain.ports.unit_of_work import UnitOfWorkFactory

        assert issubclass(UnitOfWorkFactory, Protocol)


class TestPostgreSQLUnitOfWork:
    """PostgreSQLUnitOfWork 实现测试。"""

    def test_postgresql_unit_of_work_can_be_instantiated(self):
        """PostgreSQLUnitOfWork 可实例化。"""
        from unittest import mock

        from src.infrastructure.messaging.unit_of_work.postgresql_unit_of_work import PostgreSQLUnitOfWork

        mock_session = mock.AsyncMock()
        token = set_session(mock_session)
        try:
            uow = PostgreSQLUnitOfWork()
            assert uow is not None
        finally:
            reset_session(token)

    @pytest.mark.asyncio
    async def test_begin_starts_transaction(self):
        """begin() 应启动事务。"""
        from unittest import mock

        from src.infrastructure.messaging.unit_of_work.postgresql_unit_of_work import PostgreSQLUnitOfWork

        mock_session = mock.AsyncMock()
        token = set_session(mock_session)
        try:
            uow = PostgreSQLUnitOfWork()

            await uow.begin()
            mock_session.begin.assert_called_once()
        finally:
            reset_session(token)

    @pytest.mark.asyncio
    async def test_commit_commits_transaction(self):
        """commit() 应提交事务。"""
        from unittest import mock

        from src.infrastructure.messaging.unit_of_work.postgresql_unit_of_work import PostgreSQLUnitOfWork

        mock_session = mock.AsyncMock()
        token = set_session(mock_session)
        try:
            uow = PostgreSQLUnitOfWork()

            await uow.commit()
            mock_session.commit.assert_called_once()
        finally:
            reset_session(token)

    @pytest.mark.asyncio
    async def test_rollback_rolls_back_transaction(self):
        """rollback() 应回滚事务。"""
        from unittest import mock

        from src.infrastructure.messaging.unit_of_work.postgresql_unit_of_work import PostgreSQLUnitOfWork

        mock_session = mock.AsyncMock()
        token = set_session(mock_session)
        try:
            uow = PostgreSQLUnitOfWork()

            await uow.rollback()
            mock_session.rollback.assert_called_once()
        finally:
            reset_session(token)

    @pytest.mark.asyncio
    async def test_context_manager_protocol(self):
        """UnitOfWork 应支持上下文管理器协议。"""
        from unittest import mock

        from src.infrastructure.messaging.unit_of_work.postgresql_unit_of_work import PostgreSQLUnitOfWork

        mock_session = mock.AsyncMock()
        token = set_session(mock_session)
        try:
            uow = PostgreSQLUnitOfWork()

            async with uow:
                pass
        finally:
            reset_session(token)
