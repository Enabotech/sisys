"""Saga 端口契约测试

验证 SagaStep 和 SagaRepositoryProtocol 的结构化子类型合规性。
"""

from __future__ import annotations

import inspect

from src.domain.ports.saga import SagaRepositoryProtocol, SagaStep


class TestSagaStepContract:
    """测试 SagaStep Protocol 端口契约"""

    def test_protocol_is_runtime_checkable(self) -> None:
        assert hasattr(SagaStep, "_is_runtime_protocol")
        assert SagaStep._is_runtime_protocol is True  # type: ignore[attr-defined]

    def test_name_property_exists(self) -> None:
        assert hasattr(SagaStep, "name")

    def test_execute_method_exists(self) -> None:
        assert hasattr(SagaStep, "execute")
        method = getattr(SagaStep, "execute")
        assert callable(method)
        assert inspect.iscoroutinefunction(method)

    def test_compensate_method_exists(self) -> None:
        assert hasattr(SagaStep, "compensate")
        method = getattr(SagaStep, "compensate")
        assert callable(method)
        assert inspect.iscoroutinefunction(method)

    def test_compliant_implementation(self) -> None:
        class MockStep:
            @property
            def name(self) -> str:
                return "test_step"

            async def execute(self, context):
                return context

            async def compensate(self, context):
                return context

        step = MockStep()
        assert isinstance(step, SagaStep)


class TestSagaRepositoryProtocolContract:
    """测试 SagaRepositoryProtocol 端口契约"""

    def test_protocol_is_runtime_checkable(self) -> None:
        assert hasattr(SagaRepositoryProtocol, "_is_runtime_protocol")
        assert SagaRepositoryProtocol._is_runtime_protocol is True  # type: ignore[attr-defined]

    def test_save_method_exists(self) -> None:
        assert hasattr(SagaRepositoryProtocol, "save")
        method = getattr(SagaRepositoryProtocol, "save")
        assert callable(method)
        assert inspect.iscoroutinefunction(method)

    def test_load_method_exists(self) -> None:
        assert hasattr(SagaRepositoryProtocol, "load")
        method = getattr(SagaRepositoryProtocol, "load")
        assert callable(method)
        assert inspect.iscoroutinefunction(method)

    def test_update_status_method_exists(self) -> None:
        assert hasattr(SagaRepositoryProtocol, "update_status")
        method = getattr(SagaRepositoryProtocol, "update_status")
        assert callable(method)
        assert inspect.iscoroutinefunction(method)

    def test_compliant_implementation(self) -> None:
        class MockRepo:
            async def save(self, context) -> None:
                pass

            async def load(self, saga_id: str):
                return None

            async def update_status(self, saga_id: str, status) -> None:
                pass

        repo = MockRepo()
        assert isinstance(repo, SagaRepositoryProtocol)


__all__ = ["TestSagaStepContract", "TestSagaRepositoryProtocolContract"]
