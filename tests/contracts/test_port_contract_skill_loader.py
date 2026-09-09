"""Story 4.1a: SkillLoader 端口契约测试（11 维度）

参考样板：tests/contracts/test_port_contract_tool.py（11 维度全覆盖）

11 维度测试方法名清单：
1. test_dimension_1_port_is_registered
2. test_dimension_2_port_name
3. test_dimension_3_port_version
4. test_dimension_4_port_interface_type
5. test_dimension_5_port_lifetime
6. test_dimension_6_port_owner
7. test_dimension_7_port_module
8. test_dimension_8_port_tags
9. test_dimension_9_impl_is_callable
10. test_dimension_10_implementation_has_required_methods
11. test_dimension_11_protocol_is_runtime_checkable
"""

from __future__ import annotations

from typing import Any

from src.application.ports.skill_loader import SkillLoaderPort
from src.domain.ports.registry import Lifetime, PortSpec


class _DummyResolver:
    """测试用最小 Resolver 占位符。"""

    def resolve(self, name: str) -> Any:
        raise KeyError(f"未注册的端口: {name}")


class TestSkillLoaderPortContract:
    """SkillLoaderPort 端口契约测试 11 维度"""

    PORT_NAME = "skill_loader"
    IMPL_CLS_NAME = "InMemorySkillLoader"
    MODULE_PATH = "src.application.skills.loader"
    EXPECTED_TAGS = ("skills", "loader", "inmemory")
    EXPECTED_OWNER = "tool-team"
    REQUIRED_METHODS = [
        "load_metadata",
        "load_sop",
        "load_references",
        "load_script",
        "match_by_capability",
        "match_by_tag",
        "match_by_trigger",
    ]

    def _spec(self) -> PortSpec | None:
        from src.domain.ports.registry import _global_registry

        return _global_registry.get(self.PORT_NAME)

    def test_dimension_1_port_is_registered(self) -> None:
        """维度 1：端口已注册。"""
        spec = self._spec()
        assert spec is not None, f"端口 {self.PORT_NAME} 未注册"

    def test_dimension_2_port_name(self) -> None:
        """维度 2：端口 name 正确。"""
        spec = self._spec()
        assert spec is not None
        assert spec.name == self.PORT_NAME

    def test_dimension_3_port_version(self) -> None:
        """维度 3：端口 version 非空。"""
        spec = self._spec()
        assert spec is not None
        assert spec.version, f"端口 {self.PORT_NAME} 缺少 version"

    def test_dimension_4_port_interface_type(self) -> None:
        """维度 4：端口 interface 是 Protocol 类。"""
        spec = self._spec()
        assert spec is not None
        assert spec.interface is SkillLoaderPort

    def test_dimension_5_port_lifetime(self) -> None:
        """维度 5：端口 lifetime 为 SCOPED。"""
        spec = self._spec()
        assert spec is not None
        assert spec.lifetime == Lifetime.SCOPED

    def test_dimension_6_port_owner(self) -> None:
        """维度 6：端口 owner 为 tool-team。"""
        spec = self._spec()
        assert spec is not None
        assert spec.owner == self.EXPECTED_OWNER

    def test_dimension_7_port_module(self) -> None:
        """维度 7：端口 module 路径正确。"""
        spec = self._spec()
        assert spec is not None
        assert spec.module == self.MODULE_PATH

    def test_dimension_8_port_tags(self) -> None:
        """维度 8：端口 tags 匹配。"""
        spec = self._spec()
        assert spec is not None
        assert spec.tags == self.EXPECTED_TAGS

    def test_dimension_9_impl_is_callable(self) -> None:
        """维度 9a：impl 工厂可调用。"""
        spec = self._spec()
        assert spec is not None
        assert callable(spec.impl)

    def test_dimension_9_impl_factory_produces_port_instance(self) -> None:
        """维度 9b：impl 工厂产出正确类型的实例。"""
        spec = self._spec()
        assert spec is not None
        instance = spec.impl(_DummyResolver())
        assert isinstance(instance, SkillLoaderPort), f"{self.IMPL_CLS_NAME} 未实现 SkillLoaderPort"

    def test_dimension_10_implementation_has_required_methods(self) -> None:
        """维度 10：实现类包含所有必需方法。"""
        spec = self._spec()
        assert spec is not None
        instance = spec.impl(_DummyResolver())

        for method_name in self.REQUIRED_METHODS:
            assert hasattr(instance, method_name), f"{self.IMPL_CLS_NAME} 缺少方法: {method_name}"
            assert callable(getattr(instance, method_name)), f"{self.IMPL_CLS_NAME}.{method_name} 不可调用"

    def test_dimension_11_protocol_is_runtime_checkable(self) -> None:
        """维度 11：Protocol 是 runtime_checkable，isinstance 校验通过。"""
        spec = self._spec()
        assert spec is not None
        instance = spec.impl(_DummyResolver())
        assert isinstance(instance, SkillLoaderPort)
