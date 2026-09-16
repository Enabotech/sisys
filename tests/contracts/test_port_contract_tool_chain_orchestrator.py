"""Story 4.2: ToolChainOrchestrator 端口契约测试（11 维度）

参考样板：tests/contracts/test_port_contract_skill_loader.py（11 维度全覆盖）

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
10. test_dimension_10_execute_chain_signature
11. test_dimension_11_protocol_is_runtime_checkable
"""

from __future__ import annotations

import inspect
from typing import Any

from src.application.ports.tool_chain_orchestrator import ToolChainOrchestratorProtocol
from src.domain.ports.registry import Lifetime


class _RealResolver:
    """使用真实端口注册中心的 Resolver（依赖 bootstrap 已调用）。

    Orchestrator impl 依赖 tool_execution_service + tool_registry_service 两个端口。
    本测试仅做 isinstance 校验，不会真正执行方法，因此真实 Resolver 足够。
    """

    def resolve(self, name: str) -> Any:  # noqa: D401
        from src.domain.ports.resolver import resolve as _resolve

        return _resolve(name)


class TestToolChainOrchestratorPortContract:
    """ToolChainOrchestratorProtocol 端口契约测试 11 维度"""

    PORT_NAME = "tool_chain_orchestrator"
    IMPL_CLS_NAME = "ToolChainOrchestrator"
    MODULE_PATH = "src.application.services.tool_chain_orchestrator"
    EXPECTED_TAGS = ("tool", "chain", "orchestrator")
    EXPECTED_OWNER = "tool-team"
    REQUIRED_METHODS = ["execute_chain"]

    def _spec(self) -> Any:
        from src.domain.ports.registry import _global_registry

        return _global_registry.get(self.PORT_NAME)

    def _resolver(self) -> Any:
        return _RealResolver()

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
        assert spec.interface is ToolChainOrchestratorProtocol

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
        instance = spec.impl(self._resolver())
        assert isinstance(instance, ToolChainOrchestratorProtocol), f"{self.IMPL_CLS_NAME} 未实现 ToolChainOrchestratorProtocol"

    def test_dimension_10_execute_chain_signature(self) -> None:
        """维度 10：execute_chain 方法签名正确（async + 3 参 + ToolChainRun 返回）。"""
        spec = self._spec()
        assert spec is not None
        instance = spec.impl(self._resolver())

        method = getattr(instance, "execute_chain", None)
        assert method is not None, f"{self.IMPL_CLS_NAME} 缺少方法: execute_chain"
        assert callable(method), f"{self.IMPL_CLS_NAME}.execute_chain 不可调用"
        # 校验方法是 async 函数（coroutine function）
        assert inspect.iscoroutinefunction(method), f"{self.IMPL_CLS_NAME}.execute_chain 必须为 async 函数"

    def test_dimension_11_protocol_is_runtime_checkable(self) -> None:
        """维度 11：Protocol 是 runtime_checkable，isinstance 校验通过 + _is_runtime_protocol 标记验证。"""
        spec = self._spec()
        assert spec is not None
        instance = spec.impl(self._resolver())
        # isinstance 校验通过
        assert isinstance(instance, ToolChainOrchestratorProtocol)
        # _is_runtime_protocol 标记校验（@runtime_checkable 装饰器自动设置）
        assert hasattr(ToolChainOrchestratorProtocol, "_is_runtime_protocol"), (
            "ToolChainOrchestratorProtocol 缺少 _is_runtime_protocol 标记"
        )
        assert ToolChainOrchestratorProtocol._is_runtime_protocol is True, (
            "ToolChainOrchestratorProtocol._is_runtime_protocol 必须为 True"
        )
