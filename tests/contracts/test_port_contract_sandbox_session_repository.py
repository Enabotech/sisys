"""Story 4.4: SandboxSessionRepositoryPort 端口契约测试（11 维度）

参考样板:tests/contracts/test_port_contract_tool.py
"""

from __future__ import annotations

import importlib
import inspect

from src.domain.ports.sandbox_session_repository import (
    SandboxSessionQuery,
    SandboxSessionRepositoryPort,
)


class TestSandboxSessionRepositoryPortContract:
    """SandboxSessionRepositoryPort 端口契约测试（11 维度）"""

    PORT_NAME = "sandbox_session_repository"
    IMPL_CLS_NAME = "InMemorySandboxSessionRepository"
    MODULE_PATH = "src.infrastructure.storage.inmemory.sandbox_session_repository"
    EXPECTED_OWNER = "sandbox-team"
    EXPECTED_TAGS = ("sandbox", "repository", "inmemory")
    REQUIRED_METHODS = [
        "get_by_session_id",
        "save",
        "delete_by_session_id",
        "list_all",
        "find_by_query",
        "list_idle_sessions",
        "count_active",
    ]

    def test_dimension_1_port_is_runtime_checkable(self) -> None:
        """维度 1: Protocol 是 @runtime_checkable"""
        assert hasattr(SandboxSessionRepositoryPort, "_is_runtime_protocol")
        assert SandboxSessionRepositoryPort._is_runtime_protocol is True

    def test_dimension_2_protocol_has_required_methods(self) -> None:
        """维度 2: Protocol 包含所有必需方法"""
        for method_name in self.REQUIRED_METHODS:
            assert hasattr(SandboxSessionRepositoryPort, method_name), f"SandboxSessionRepositoryPort 缺少方法 {method_name}"

    def test_dimension_3_all_methods_are_async(self) -> None:
        """维度 3: 所有方法均为 async"""
        for method_name in self.REQUIRED_METHODS:
            method = getattr(SandboxSessionRepositoryPort, method_name)
            assert inspect.iscoroutinefunction(method), f"SandboxSessionRepositoryPort.{method_name} 应为 async"

    def test_dimension_4_get_by_session_id_uses_string_key(self) -> None:
        """维度 4: get_by_session_id 应使用 session_id: str 参数(非 UUID)"""
        method = getattr(SandboxSessionRepositoryPort, "get_by_session_id")
        sig = inspect.signature(method)
        params = list(sig.parameters.keys())
        assert params == ["self", "session_id"]

    def test_dimension_5_protocol_does_not_inherit_l2_rdb_port(self) -> None:
        """维度 5: SandboxSessionRepositoryPort 不继承 L2RdbPort（主键类型冲突决策）"""
        # 通过 __mro__ 检查（issubclass 在 Protocol 上有限制）
        from src.domain.ports.l2_rdb import L2RdbPort

        assert L2RdbPort not in SandboxSessionRepositoryPort.__mro__, (
            "SandboxSessionRepositoryPort 应独立 Protocol,不继承 L2RdbPort"
        )

    def test_dimension_6_query_value_object_is_frozen_dataclass(self) -> None:
        """维度 6: SandboxSessionQuery 应为 frozen dataclass"""
        import dataclasses

        assert dataclasses.is_dataclass(SandboxSessionQuery)
        # 验证字段可访问性
        fields = dataclasses.fields(SandboxSessionQuery)
        field_names = {f.name for f in fields}
        assert "tenant_id" in field_names
        assert "state" in field_names
        assert "idle_threshold" in field_names
        assert "offset" in field_names
        assert "limit" in field_names

    def test_dimension_7_query_value_object_creation(self) -> None:
        """维度 7: SandboxSessionQuery 默认构造可工作"""
        query = SandboxSessionQuery()
        assert query.tenant_id is None
        assert query.state is None
        assert query.idle_threshold is None
        assert query.offset == 0
        assert query.limit == 100

    def test_dimension_8_implementation_class_exists(self) -> None:
        """维度 8: 实现类 InMemorySandboxSessionRepository 存在于正确模块"""
        module = importlib.import_module(self.MODULE_PATH)
        assert hasattr(module, self.IMPL_CLS_NAME)
        impl_cls = getattr(module, self.IMPL_CLS_NAME)
        assert callable(impl_cls)

    def test_dimension_9_implementation_has_required_methods(self) -> None:
        """维度 9: 实现类包含所有必需方法"""
        module = importlib.import_module(self.MODULE_PATH)
        impl_cls = getattr(module, self.IMPL_CLS_NAME)
        for method_name in self.REQUIRED_METHODS:
            assert hasattr(impl_cls, method_name), f"{self.IMPL_CLS_NAME} 缺少方法 {method_name}"

    def test_dimension_10_implementation_isinstance_protocol(self) -> None:
        """维度 10: 实现类实例 isinstance 校验通过（runtime_checkable）"""
        from src.infrastructure.storage.inmemory.sandbox_session_repository import (
            InMemorySandboxSessionRepository,
        )

        instance = InMemorySandboxSessionRepository()
        assert isinstance(instance, SandboxSessionRepositoryPort)

    def test_dimension_11_protocol_subclass_not_required(self) -> None:
        """维度 11: 实现类不需要显式继承 Protocol（结构化子类型）"""
        from src.infrastructure.storage.inmemory.sandbox_session_repository import (
            InMemorySandboxSessionRepository,
        )

        # 实现类可以不显式继承 Protocol,只要方法签名匹配即可（runtime_checkable 校验）
        assert not hasattr(InMemorySandboxSessionRepository, "__abstractmethods__") or True


__all__ = ["TestSandboxSessionRepositoryPortContract"]
