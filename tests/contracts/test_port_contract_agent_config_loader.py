"""Story 5.1: AgentConfigLoader 端口契约测试（11 维度）

参考样板：tests/contracts/test_port_contract_tool_execution_repository.py

11 维度测试方法名清单：
1. test_dimension_1_port_is_registered
2. test_dimension_2_port_name
3. test_dimension_3_port_version
4. test_dimension_4_port_interface_type
5. test_dimension_5_port_lifetime
6. test_dimension_6_port_owner
7. test_dimension_7_port_module
8. test_dimension_8_port_tags
9. test_dimension_9_impl_is_callable（9a 可调用 + 9b DummyResolver 实例化 isinstance）
10. test_dimension_10_implementation_has_required_methods
11. test_dimension_11_protocol_is_runtime_checkable
"""

from __future__ import annotations

from typing import Any

from src.application.ports.agent_config_loader import AgentConfigLoader
from src.domain.ports.registry import Lifetime


class _DummyResolver:
    """测试用最小 Resolver 占位符（agent_config_loader 工厂无外部依赖，零 resolve）。"""

    def resolve(self, name: str) -> Any:
        raise KeyError(f"未注册的端口: {name}")


class TestAgentConfigLoaderPortContract:
    """AgentConfigLoader 端口契约测试 11 维度"""

    PORT_NAME = "agent_config_loader"
    IMPL_CLS_NAME = "YamlAgentConfigLoader"
    MODULE_PATH = "src.infrastructure.agent_orch.yaml_agent_config_loader"
    EXPECTED_TAGS = ("agent", "config")
    EXPECTED_OWNER = "platform"
    REQUIRED_METHODS = ["load"]

    def _spec(self) -> Any:
        from src.domain.ports.registry import _global_registry

        return _global_registry.get(self.PORT_NAME)

    # 维度 1: 端口已注册
    def test_dimension_1_port_is_registered(self) -> None:
        assert self._spec() is not None, f"端口 {self.PORT_NAME} 未注册"

    # 维度 2: 端口名称
    def test_dimension_2_port_name(self) -> None:
        spec = self._spec()
        assert spec.name == self.PORT_NAME

    # 维度 3: 端口版本
    def test_dimension_3_port_version(self) -> None:
        spec = self._spec()
        assert spec.version == "v1.0.0"

    # 维度 4: interface 是 Protocol
    def test_dimension_4_port_interface_type(self) -> None:
        spec = self._spec()
        assert spec.interface is AgentConfigLoader

    # 维度 5: 生命周期
    def test_dimension_5_port_lifetime(self) -> None:
        spec = self._spec()
        assert spec.lifetime == Lifetime.SINGLETON

    # 维度 6: 端口 owner
    def test_dimension_6_port_owner(self) -> None:
        spec = self._spec()
        assert spec.owner == self.EXPECTED_OWNER

    # 维度 7: 实现模块路径
    def test_dimension_7_port_module(self) -> None:
        spec = self._spec()
        assert spec.module == self.MODULE_PATH

    # 维度 8: 端口 tags
    def test_dimension_8_port_tags(self) -> None:
        spec = self._spec()
        assert spec.tags == self.EXPECTED_TAGS

    # 维度 9a: impl 工厂可调用
    def test_dimension_9_impl_is_callable(self) -> None:
        spec = self._spec()
        assert callable(spec.impl)

    # 维度 9b: impl 工厂产出 isinstance Port
    def test_dimension_9b_impl_produces_port_instance(self) -> None:
        spec = self._spec()
        instance = spec.impl(_DummyResolver())
        assert isinstance(instance, AgentConfigLoader)
        assert type(instance).__name__ == self.IMPL_CLS_NAME

    # 维度 10: 实现类具备 REQUIRED_METHODS
    def test_dimension_10_implementation_has_required_methods(self) -> None:
        spec = self._spec()
        instance = spec.impl(_DummyResolver())
        for method in self.REQUIRED_METHODS:
            assert hasattr(instance, method), f"实现缺少方法: {method}"
            assert callable(getattr(instance, method)), f"方法不可调用: {method}"

    # 维度 11: Protocol runtime_checkable
    def test_dimension_11_protocol_is_runtime_checkable(self) -> None:
        spec = self._spec()
        instance = spec.impl(_DummyResolver())
        assert isinstance(instance, AgentConfigLoader)


__all__ = ["TestAgentConfigLoaderPortContract"]
