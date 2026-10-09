"""Story 4.7: 端口契约测试 — 错误案例库仓储

验证 error_case_repository 端口的注册、版本、接口、生命周期、owner/tags/module
元数据，以及 PostgreSQLErrorCaseRepository 实现类的 required_methods 与
Protocol runtime_checkable 属性（InMemory 实现供单测/验收装配）。

遵循项目标准 11 维度契约测试模式（与 test_port_contract_tool.py 样板对齐）。
"""

from __future__ import annotations

from typing import Any

from src.domain.ports.error_case_repository import ErrorCaseRepositoryPort
from src.domain.ports.registry import Lifetime, _global_registry


class _DummyResolver:
    """测试用最小 Resolver 占位符（error_case_repository 工厂零依赖——解析任意名即抛）。"""

    def resolve(self, name: str) -> Any:
        raise KeyError(name)


class TestErrorCaseRepositoryPortContract:
    """error_case_repository 端口契约（11 维度全覆盖）."""

    PORT_NAME = "error_case_repository"
    IMPL_CLS_NAME = "PostgreSQLErrorCaseRepository"
    MODULE_PATH = "src.infrastructure.storage.postgresql.repository.error_case_repository"
    EXPECTED_TAGS = ("tool", "repository", "feedback")
    EXPECTED_OWNER = "tool-team"
    REQUIRED_METHODS = [
        "get_by_natural_key",
        "record_case",
    ]

    def _spec(self) -> Any:
        return _global_registry.get(self.PORT_NAME)

    def test_dimension_1_port_is_registered(self) -> None:
        """维度 1：端口已注册."""
        spec = self._spec()
        assert spec is not None, f"端口 {self.PORT_NAME} 未注册"

    def test_dimension_2_port_name(self) -> None:
        """维度 2：PortSpec.name 正确."""
        spec = self._spec()
        assert spec is not None
        assert spec.name == self.PORT_NAME

    def test_dimension_3_port_version(self) -> None:
        """维度 3：PortSpec.version 为 v1.0.0."""
        spec = self._spec()
        assert spec is not None
        assert spec.version == "v1.0.0"

    def test_dimension_4_port_interface_type(self) -> None:
        """维度 4：PortSpec.interface 是 ErrorCaseRepositoryPort Protocol."""
        spec = self._spec()
        assert spec is not None
        assert spec.interface is ErrorCaseRepositoryPort

    def test_dimension_5_port_lifetime(self) -> None:
        """维度 5：PortSpec.lifetime 为 SCOPED."""
        spec = self._spec()
        assert spec is not None
        assert spec.lifetime == Lifetime.SCOPED

    def test_dimension_6_port_owner(self) -> None:
        """维度 6：PortSpec.owner 为 tool-team."""
        spec = self._spec()
        assert spec is not None
        assert spec.owner == self.EXPECTED_OWNER

    def test_dimension_7_port_module(self) -> None:
        """维度 7：PortSpec.module 指向正确实现模块."""
        spec = self._spec()
        assert spec is not None
        assert spec.module == self.MODULE_PATH

    def test_dimension_8_port_tags(self) -> None:
        """维度 8：PortSpec.tags 元数据完整."""
        spec = self._spec()
        assert spec is not None
        assert spec.tags == self.EXPECTED_TAGS

    def test_dimension_9_impl_is_callable(self) -> None:
        """维度 9：spec.impl 是可调用工厂."""
        spec = self._spec()
        assert spec is not None
        assert callable(spec.impl), "impl 应为 lambda 工厂函数"

    def test_dimension_9_impl_factory_produces_port_instance(self) -> None:
        """维度 9（续）：工厂产出满足 Protocol（runtime_checkable isinstance 校验）."""
        spec = self._spec()
        assert spec is not None
        instance = spec.impl(_DummyResolver())
        assert isinstance(instance, ErrorCaseRepositoryPort)

    def test_dimension_10_implementation_has_required_methods(self) -> None:
        """维度 10：实现类包含所有必需方法."""
        import importlib

        spec = self._spec()
        assert spec is not None
        assert spec.module
        mod = importlib.import_module(spec.module)
        impl_cls = getattr(mod, self.IMPL_CLS_NAME, None)
        assert impl_cls is not None
        for method in self.REQUIRED_METHODS:
            assert hasattr(impl_cls, method), f"缺少方法: {method}"
            assert callable(getattr(impl_cls, method)), f"方法不可调用: {method}"

    def test_dimension_11_protocol_is_runtime_checkable(self) -> None:
        """维度 11：Protocol 是 @runtime_checkable（InMemory 实现 isinstance 校验）."""
        from src.infrastructure.storage.inmemory.error_case_repository import (
            InMemoryErrorCaseRepository,
        )

        repo = InMemoryErrorCaseRepository()
        assert isinstance(repo, ErrorCaseRepositoryPort)

    def test_extra_query_object_is_frozen(self) -> None:
        """附加维度：EvolutionLogQuery 同款 frozen Query Object 决策规则印证（多字段+分页）。

        error_case_repository 按 CLAUDE.md 端口参数决策规则仅两个方法
        （单字段检索 get_by_natural_key + 命令型 record_case 直接参数），
        无 Query Object——本测试锁定「不设 search_by_signature」的 V1 语义
        （多案例加权检索登记 deferred-work）。
        """
        import inspect

        methods = [m for m in dir(ErrorCaseRepositoryPort) if not m.startswith("_")]
        assert "get_by_natural_key" in methods
        assert "record_case" in methods
        assert "search_by_signature" not in methods, "V1 不设 search_by_signature（deferred-work）"
        sig = inspect.signature(ErrorCaseRepositoryPort.get_by_natural_key)
        assert "error_signature" in sig.parameters
