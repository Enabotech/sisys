"""事务隔离级别 + 审计 UoW 测试

验证 AC-6: 事务隔离级别配置 + 审计专用 UoW
对应 Task 6 的 TDD 测试
"""

from __future__ import annotations

from unittest import mock

import pytest


class TestIsolationLevel:
    """验证隔离级别配置"""

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

    async def test_audit_uow_uses_serializable_isolation(self) -> None:
        """AuditUnitOfWork.begin() 应通过 get_session_with_isolation 创建 SERIALIZABLE 隔离级别的 session"""
        from src.infrastructure.messaging.unit_of_work.audit_unit_of_work import AuditUnitOfWork
        from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager

        mock_manager = mock.MagicMock(spec=PostgreSQLManager)
        mock_session = mock.AsyncMock()
        mock_session.begin = mock.AsyncMock()

        # 构造 get_session_with_isolation 返回的异步上下文管理器
        isolation_ctx = mock.AsyncMock()
        isolation_ctx.__aenter__ = mock.AsyncMock(return_value=mock_session)
        isolation_ctx.__aexit__ = mock.AsyncMock(return_value=False)
        mock_manager.get_session_with_isolation.return_value = isolation_ctx

        uow = AuditUnitOfWork(manager=mock_manager)
        await uow.begin()

        mock_manager.get_session_with_isolation.assert_called_once_with("SERIALIZABLE")
        mock_session.begin.assert_awaited_once()

    async def test_audit_uow_context_manager(self) -> None:
        """AuditUnitOfWork 应支持上下文管理器"""
        from src.infrastructure.messaging.unit_of_work.audit_unit_of_work import AuditUnitOfWork
        from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager

        mock_manager = mock.MagicMock(spec=PostgreSQLManager)
        mock_session = mock.AsyncMock()
        mock_session.begin = mock.AsyncMock()
        mock_session.commit = mock.AsyncMock()

        isolation_ctx = mock.AsyncMock()
        isolation_ctx.__aenter__ = mock.AsyncMock(return_value=mock_session)
        isolation_ctx.__aexit__ = mock.AsyncMock(return_value=False)
        mock_manager.get_session_with_isolation.return_value = isolation_ctx

        uow = AuditUnitOfWork(manager=mock_manager)

        async with uow:
            pass

        mock_session.commit.assert_awaited_once()
        isolation_ctx.__aexit__.assert_awaited_once()

    async def test_audit_uow_session_property_raises_before_begin(self) -> None:
        """AuditUnitOfWork.session 在 begin() 前应抛出 RuntimeError"""
        from src.infrastructure.messaging.unit_of_work.audit_unit_of_work import AuditUnitOfWork
        from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager

        mock_manager = mock.MagicMock(spec=PostgreSQLManager)
        uow = AuditUnitOfWork(manager=mock_manager)

        with pytest.raises(RuntimeError, match="Session not initialized"):
            _ = uow.session
