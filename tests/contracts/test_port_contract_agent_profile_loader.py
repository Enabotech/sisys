"""agent_profile_loader 端口契约测试（Story 5-2 — Agent 身份档案加载）

11 维度契约断言（维度清单同 5-1 agent_repository 契约测试先例）：
已注册/name/version/interface 是 Protocol/lifetime/owner/module/tags/
impl 工厂 9a+9b/REQUIRED_METHODS/runtime_checkable。

DummyResolver 零依赖直构（MarkdownAgentProfileLoader 构造零参、无连接——
维度仅验证实例化与方法面，不触真实档案读取）。

Run with:
    poetry run pytest tests/contracts/test_port_contract_agent_profile_loader.py -v
"""

from __future__ import annotations

from typing import Any


class _DummyResolver:
    """测试用最小 Resolver 占位符（agent_profile_loader 工厂零依赖直构）。"""

    def resolve(self, name: str) -> Any:
        raise KeyError(f"未注册的端口: {name}")


class TestAgentProfileLoaderPortContract:
    """agent_profile_loader 端口契约测试 11 维度。"""

    PORT_NAME = "agent_profile_loader"
    IMPL_CLS_NAME = "MarkdownAgentProfileLoader"
    MODULE_PATH = "src.infrastructure.agent_orch.markdown_agent_profile_loader"
    EXPECTED_TAGS = ("agent", "profile")
    EXPECTED_OWNER = "platform"
    REQUIRED_METHODS = ["load"]

    def _spec(self) -> Any:
        from src.domain.ports.registry import _global_registry

        return _global_registry.get(self.PORT_NAME)

    # 维度 1: 端口已注册
    def test_dimension_1_port_registered(self) -> None:
        assert self._spec() is not None, f"端口 {self.PORT_NAME} 未注册"

    # 维度 2: 端口名称
    def test_dimension_2_port_name(self) -> None:
        assert self._spec().name == self.PORT_NAME

    # 维度 3: 版本
    def test_dimension_3_version(self) -> None:
        assert self._spec().version == "v1.0.0"

    # 维度 4: interface 是 Protocol
    def test_dimension_4_interface_is_protocol(self) -> None:
        from src.application.ports.agent_profile_loader import AgentProfileLoader

        assert self._spec().interface is AgentProfileLoader

    # 维度 5: 生命周期
    def test_dimension_5_lifetime(self) -> None:
        from src.domain.ports.registry import Lifetime

        assert self._spec().lifetime == Lifetime.SINGLETON

    # 维度 6: owner
    def test_dimension_6_owner(self) -> None:
        assert self._spec().owner == self.EXPECTED_OWNER

    # 维度 7: 实现模块路径
    def test_dimension_7_module_path(self) -> None:
        assert self._spec().module == self.MODULE_PATH

    # 维度 8: tags
    def test_dimension_8_tags(self) -> None:
        assert self._spec().tags == self.EXPECTED_TAGS

    # 维度 9a: impl 是可调用工厂
    def test_dimension_9a_impl_callable(self) -> None:
        assert callable(self._spec().impl)

    # 维度 9b: impl 工厂产出端口实例
    def test_dimension_9b_impl_produces_port_instance(self) -> None:
        from src.application.ports.agent_profile_loader import AgentProfileLoader

        instance = self._spec().impl(_DummyResolver())
        assert isinstance(instance, AgentProfileLoader)
        assert type(instance).__name__ == self.IMPL_CLS_NAME

    # 维度 10: 实现具备必需方法
    def test_dimension_10_implementation_has_required_methods(self) -> None:
        instance = self._spec().impl(_DummyResolver())
        for method in self.REQUIRED_METHODS:
            assert hasattr(instance, method), f"实现缺少方法: {method}"
            assert callable(getattr(instance, method)), f"方法不可调用: {method}"

    # 维度 11: runtime_checkable isinstance 校验
    def test_dimension_11_runtime_checkable(self) -> None:
        from src.application.ports.agent_profile_loader import AgentProfileLoader

        instance = self._spec().impl(_DummyResolver())
        assert isinstance(instance, AgentProfileLoader)


__all__ = ["TestAgentProfileLoaderPortContract"]
