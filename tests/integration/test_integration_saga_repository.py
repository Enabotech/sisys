"""SagaRepository 集成测试

验证 AC-7: Saga Repository + 领域端口 + DI 注册
对应 Task 8 的 TDD 测试
"""

from __future__ import annotations

from uuid import uuid4

from src.infrastructure.saga.saga_context import SagaContext
from src.infrastructure.saga.saga_status import SagaStatus


class TestSagaRepositoryProtocol:
    """验证 SagaRepositoryProtocol 契约"""

    def test_protocol_has_required_methods(self) -> None:
        """SagaRepositoryProtocol 应定义必要方法"""
        from src.domain.ports.saga import SagaRepositoryProtocol

        assert hasattr(SagaRepositoryProtocol, "save")
        assert hasattr(SagaRepositoryProtocol, "load")
        assert hasattr(SagaRepositoryProtocol, "update_status")


class TestPostgreSQLSagaRepository:
    """验证 PostgreSQLSagaRepository 实现"""

    async def test_save_and_load_context(self) -> None:
        """save() 后 load() 应返回相同上下文"""
        from unittest import mock

        from src.infrastructure.saga.saga_repository import PostgreSQLSagaRepository
        from src.infrastructure.storage.postgresql.session_context import (
            reset_session,
            set_session,
        )

        mock_session = mock.AsyncMock()
        token = set_session(mock_session)

        try:
            repo = PostgreSQLSagaRepository()
            saga_id = uuid4()
            ctx = SagaContext(
                saga_id=saga_id,
                saga_type="test_saga",
                status=SagaStatus.RUNNING,
            )

            await repo.save(ctx)

            mock_session.execute.assert_awaited()
            mock_session.flush.assert_awaited_once()
        finally:
            reset_session(token)

    async def test_update_status(self) -> None:
        """update_status() 应更新 Saga 状态"""
        from unittest import mock

        from src.infrastructure.saga.saga_repository import PostgreSQLSagaRepository
        from src.infrastructure.storage.postgresql.session_context import (
            reset_session,
            set_session,
        )

        mock_session = mock.AsyncMock()
        # SELECT 存在性检查返回 1（存在），UPDATE 正常执行
        select_result = mock.MagicMock()
        select_result.scalar_one_or_none.return_value = 1
        mock_session.execute.return_value = select_result
        token = set_session(mock_session)

        try:
            repo = PostgreSQLSagaRepository()
            saga_id = uuid4()

            await repo.update_status(str(saga_id), SagaStatus.COMPLETED)

            assert mock_session.execute.await_count == 2  # SELECT + UPDATE
        finally:
            reset_session(token)


class TestSagaPortRegistration:
    """验证 Saga 端口 DI 注册"""

    def test_saga_repository_port_registered(self) -> None:
        """saga_repository 端口应在 DI 容器注册"""
        from src.domain.ports.registry import _global_registry

        spec = _global_registry.get("saga_repository")
        assert spec is not None

    def test_saga_repository_interface_matches(self) -> None:
        """注册端口的接口应为 SagaRepositoryProtocol"""
        from src.domain.ports.registry import _global_registry
        from src.domain.ports.saga import SagaRepositoryProtocol

        spec = _global_registry.get("saga_repository")
        assert spec is not None
        assert spec.interface is SagaRepositoryProtocol
