"""事务隔离级别 + 审计 UoW 测试

验证 AC-6: 事务隔离级别配置 + 审计专用 UoW
对应 Task 6 的 TDD 测试
"""

from __future__ import annotations

from unittest import mock

import pytest


class TestIsolationLevel:
    """验证隔离级别配置"""

    @pytest.mark.asyncio
    async def test_get_session_with_serializable_isolation(self) -> None:
        """get_session_with_isolation('SERIALIZABLE') 应创建 SERIALIZABLE 隔离级别的 session"""
        from src.infrastructure.config.postgresql import PostgreSQLConfig
        from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager

        config = PostgreSQLConfig(
            host="localhost",
            port=5432,
            username="postgres",
            password="postgres",  # pragma: allowlist secret
            database="sisys",
        )
        manager = PostgreSQLManager(config)
        manager._async_engine = mock.AsyncMock()

        with mock.patch(
            "src.infrastructure.storage.postgresql.postgresql_manager.async_sessionmaker",
        ) as mock_maker:
            mock_session = mock.AsyncMock()
            mock_maker.return_value.return_value.__aenter__ = mock.AsyncMock(return_value=mock_session)
            mock_maker.return_value.return_value.__aexit__ = mock.AsyncMock(return_value=False)

            async with manager.get_session_with_isolation("SERIALIZABLE") as session:
                assert session is mock_session

            call_kwargs = mock_maker.call_args[1]
            assert call_kwargs["isolation_level"] == "SERIALIZABLE"

    @pytest.mark.asyncio
    async def test_get_session_with_repeatable_read_isolation(self) -> None:
        """get_session_with_isolation('REPEATABLE READ') 应创建 REPEATABLE READ 隔离级别的 session"""
        from src.infrastructure.config.postgresql import PostgreSQLConfig
        from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager

        config = PostgreSQLConfig(
            host="localhost",
            port=5432,
            username="postgres",
            password="postgres",  # pragma: allowlist secret
            database="sisys",
        )
        manager = PostgreSQLManager(config)
        manager._async_engine = mock.AsyncMock()

        with mock.patch(
            "src.infrastructure.storage.postgresql.postgresql_manager.async_sessionmaker",
        ) as mock_maker:
            mock_session = mock.AsyncMock()
            mock_maker.return_value.return_value.__aenter__ = mock.AsyncMock(return_value=mock_session)
            mock_maker.return_value.return_value.__aexit__ = mock.AsyncMock(return_value=False)

            async with manager.get_session_with_isolation("REPEATABLE READ") as session:
                assert session is mock_session

            call_kwargs = mock_maker.call_args[1]
            assert call_kwargs["isolation_level"] == "REPEATABLE READ"


class TestAuditUnitOfWork:
    """验证审计专用 UoW"""

    @pytest.mark.asyncio
    async def test_audit_uow_uses_serializable_isolation(self) -> None:
        """AuditUnitOfWork 应使用 SERIALIZABLE 隔离级别"""
        from src.infrastructure.messaging.unit_of_work.audit_unit_of_work import AuditUnitOfWork

        mock_session = mock.AsyncMock()
        mock_session.get_transaction = mock.MagicMock(return_value=None)

        uow = AuditUnitOfWork(session=mock_session)

        assert uow._isolation_level == "SERIALIZABLE"

    @pytest.mark.asyncio
    async def test_audit_uow_begin_sets_isolation(self) -> None:
        """AuditUnitOfWork.begin() 应设置 SERIALIZABLE 隔离级别"""
        from src.infrastructure.messaging.unit_of_work.audit_unit_of_work import AuditUnitOfWork

        mock_session = mock.AsyncMock()
        mock_session.begin = mock.AsyncMock()
        mock_session.execute = mock.AsyncMock()

        uow = AuditUnitOfWork(session=mock_session)
        await uow.begin()

        mock_session.execute.assert_called()
        call_args = mock_session.execute.call_args[0][0]
        assert "SERIALIZABLE" in str(call_args)

    @pytest.mark.asyncio
    async def test_audit_uow_context_manager(self) -> None:
        """AuditUnitOfWork 应支持上下文管理器"""
        from src.infrastructure.messaging.unit_of_work.audit_unit_of_work import AuditUnitOfWork

        mock_session = mock.AsyncMock()
        mock_session.begin = mock.AsyncMock()
        mock_session.commit = mock.AsyncMock()
        mock_session.execute = mock.AsyncMock()

        uow = AuditUnitOfWork(session=mock_session)

        async with uow:
            pass

        mock_session.commit.assert_awaited_once()
