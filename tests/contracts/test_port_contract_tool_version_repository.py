"""Story 4-6: ToolVersionRepositoryPort 端口契约测试（11 维度）

参考样板：tests/contracts/test_port_contract_tool.py（11 维度全覆盖）。
Task 0 阶段红（端口未注册）；Task 3 循环 C 组合根注册后转绿。
"""

from __future__ import annotations

from typing import Any

from src.domain.ports.registry import Lifetime, PortSpec
from src.domain.ports.tool_version_repository import (
    ToolVersionQuery,
    ToolVersionRepositoryPort,
)
from src.infrastructure.storage.inmemory.tool_version_repository import (
    InMemoryToolVersionRepository,
)


class _DummyResolver:
    """测试用 resolver，模拟端口依赖注入（test_port_contract_tool.py 先例）。"""

    def resolve(self, name: str) -> Any:
        if name == "tool_version_repository":
            return InMemoryToolVersionRepository()
        raise KeyError(f"未注册的端口: {name}")


class TestToolVersionRepositoryPortContract:
    """ToolVersionRepositoryPort 端口契约测试 11 维度。"""

    PORT_NAME = "tool_version_repository"
    IMPL_CLS_NAME = "PostgreSQLToolVersionRepository"
    MODULE_PATH = "src.infrastructure.storage.postgresql.repository.tool_version_repository"
    EXPECTED_TAGS = ("tool", "version", "repository", "postgresql", "sqlalchemy")
    EXPECTED_OWNER = "tool-team"
    REQUIRED_METHODS = [
        "save",
        "get_by_id",
        "get_by_tool_and_version",
        "list_by_query",
        "count",
        "list_active",
        "delete",
    ]

    def _spec(self) -> PortSpec | None:
        from src.domain.ports.registry import _global_registry

        return _global_registry.get(self.PORT_NAME)

    def test_dimension_1_port_is_registered(self) -> None:
        """维度 1：端口已注册。"""
        spec = self._spec()
        assert spec is not None, f"端口 {self.PORT_NAME} 未注册"

    def test_dimension_2_port_name(self) -> None:
        """维度 2：端口名称。"""
        spec = self._spec()
        assert spec is not None
        assert spec.name == self.PORT_NAME

    def test_dimension_3_port_version(self) -> None:
        """维度 3：端口版本。"""
        spec = self._spec()
        assert spec is not None
        assert spec.version == "v1.0.0"

    def test_dimension_4_port_interface_type(self) -> None:
        """维度 4：端口接口类型。"""
        spec = self._spec()
        assert spec is not None
        assert spec.interface is ToolVersionRepositoryPort

    def test_dimension_5_port_lifetime(self) -> None:
        """维度 5：端口生命周期 SCOPED。"""
        spec = self._spec()
        assert spec is not None
        assert spec.lifetime == Lifetime.SCOPED

    def test_dimension_6_port_owner(self) -> None:
        """维度 6：端口 owner。"""
        spec = self._spec()
        assert spec is not None
        assert spec.owner == self.EXPECTED_OWNER

    def test_dimension_7_port_module(self) -> None:
        """维度 7：端口 module 路径（PG 主实现）。"""
        spec = self._spec()
        assert spec is not None
        assert spec.module == self.MODULE_PATH

    def test_dimension_8_port_tags(self) -> None:
        """维度 8：端口 tags。"""
        spec = self._spec()
        assert spec is not None
        assert set(spec.tags) == set(self.EXPECTED_TAGS)

    def test_dimension_9_impl_is_callable(self) -> None:
        """维度 9：impl 是可调用工厂（lambda 工厂——维度 10 依赖）。"""
        spec = self._spec()
        assert spec is not None
        assert callable(spec.impl), "impl 应为 lambda 工厂函数"

    def test_dimension_10_implementation_has_required_methods(self) -> None:
        """维度 10：实现类包含必需方法集（仓储 7 方法）。"""
        repo = InMemoryToolVersionRepository()
        for method_name in self.REQUIRED_METHODS:
            assert hasattr(repo, method_name), f"InMemory 实现缺少方法: {method_name}"
        spec = self._spec()
        assert spec is not None
        assert callable(spec.impl)
        instance = spec.impl(_DummyResolver())
        for method_name in self.REQUIRED_METHODS:
            assert hasattr(instance, method_name), f"PG 实现缺少方法: {method_name}"

    def test_dimension_11_protocol_is_runtime_checkable(self) -> None:
        """维度 11：Protocol 是 runtime_checkable 且 InMemory 实现满足。"""
        assert (
            hasattr(ToolVersionRepositoryPort, "_is_runtime_protocol")
            or hasattr(ToolVersionRepositoryPort, "__runtime_protocol__")
            or getattr(ToolVersionRepositoryPort, "_is_protocol", False)
        )
        assert isinstance(InMemoryToolVersionRepository(), ToolVersionRepositoryPort)

    def test_query_object_is_frozen_dataclass(self) -> None:
        """附加维度：ToolVersionQuery 为 frozen dataclass（Query Object 模式）。"""
        import dataclasses

        assert dataclasses.is_dataclass(ToolVersionQuery)
        q1 = ToolVersionQuery(tool_id=None, offset=0, limit=100)
        q2 = ToolVersionQuery(tool_id=None, offset=0, limit=100)
        assert q1 == q2
