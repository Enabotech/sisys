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

    def test_execute_signature(self) -> None:
        """验证 execute 方法签名"""
        method = getattr(SagaStep, "execute")
        sig = inspect.signature(method)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "context" in params

    def test_compensate_method_exists(self) -> None:
        assert hasattr(SagaStep, "compensate")
        method = getattr(SagaStep, "compensate")
        assert callable(method)
        assert inspect.iscoroutinefunction(method)

    def test_compensate_signature(self) -> None:
        """验证 compensate 方法签名"""
        method = getattr(SagaStep, "compensate")
        sig = inspect.signature(method)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "context" in params

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

    def test_noncompliant_missing_name(self) -> None:
        """缺少 name property 的子类型不被识别为 SagaStep"""

        class NoNameStep:
            async def execute(self, context):
                return context

            async def compensate(self, context):
                return context

        step = NoNameStep()
        assert not isinstance(step, SagaStep)

    def test_noncompliant_missing_compensate(self) -> None:
        """缺少 compensate 方法的子类型不被识别为 SagaStep"""

        class NoCompensate:
            @property
            def name(self) -> str:
                return "test"

            async def execute(self, context):
                return context

        step = NoCompensate()
        assert not isinstance(step, SagaStep)


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

    def test_save_signature(self) -> None:
        """验证 save 方法签名"""
        method = getattr(SagaRepositoryProtocol, "save")
        sig = inspect.signature(method)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "context" in params

    def test_load_method_exists(self) -> None:
        assert hasattr(SagaRepositoryProtocol, "load")
        method = getattr(SagaRepositoryProtocol, "load")
        assert callable(method)
        assert inspect.iscoroutinefunction(method)

    def test_load_signature(self) -> None:
        """验证 load 方法签名"""
        method = getattr(SagaRepositoryProtocol, "load")
        sig = inspect.signature(method)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "saga_id" in params

    def test_update_status_method_exists(self) -> None:
        assert hasattr(SagaRepositoryProtocol, "update_status")
        method = getattr(SagaRepositoryProtocol, "update_status")
        assert callable(method)
        assert inspect.iscoroutinefunction(method)

    def test_update_status_signature(self) -> None:
        """验证 update_status 方法签名"""
        method = getattr(SagaRepositoryProtocol, "update_status")
        sig = inspect.signature(method)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "saga_id" in params
        assert "status" in params

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

    def test_noncompliant_missing_load(self) -> None:
        """缺少 load 方法的不合规实现"""

        class BadRepo:
            async def save(self, context) -> None:
                pass

            async def update_status(self, saga_id: str, status) -> None:
                pass

        repo = BadRepo()
        assert not isinstance(repo, SagaRepositoryProtocol)

    def test_noncompliant_missing_save(self) -> None:
        """缺少 save 方法的不合规实现"""

        class NoSave:
            async def load(self, saga_id: str):
                return None

            async def update_status(self, saga_id: str, status) -> None:
                pass

        repo = NoSave()
        assert not isinstance(repo, SagaRepositoryProtocol)

    def test_noncompliant_missing_update_status(self) -> None:
        """缺少 update_status 方法的不合规实现"""

        class NoUpdate:
            async def save(self, context) -> None:
                pass

            async def load(self, saga_id: str):
                return None

        repo = NoUpdate()
        assert not isinstance(repo, SagaRepositoryProtocol)

    def test_load_return_type_accepts_none(self) -> None:
        """验证 load 返回类型允许 None（SagaContext | None）"""

        class OkNone:
            async def save(self, context) -> None:
                pass

            async def load(self, saga_id: str):
                return None

            async def update_status(self, saga_id: str, status) -> None:
                pass

        repo = OkNone()
        assert isinstance(repo, SagaRepositoryProtocol)

    def test_port_registered(self) -> None:
        """saga_repository 端口应在注册表中"""
        from src.domain.ports.registry import _global_registry

        spec = _global_registry.get("saga_repository")
        assert spec is not None, "saga_repository 端口未注册"
        assert spec.interface is SagaRepositoryProtocol


__all__ = ["TestSagaStepContract", "TestSagaRepositoryProtocolContract"]
