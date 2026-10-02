"""Story 4.5: red_blue_debate_service 端口契约测试

11 维度契约验证（新式模式，参考样板 test_port_contract_tool_chain_orchestrator.py）：
1. 端口已注册 2. 端口名 3. 版本 4. 接口类型 5. 生命周期 6. owner
7. module 8. tags 9. impl 可调用 9b. 工厂产出端口实例 10. 方法签名 11. runtime_checkable
"""

from __future__ import annotations

import inspect
from typing import Any

from src.application.ports.red_blue_debate_service import RedBlueDebateServicePort
from src.application.services.red_blue_debate_service import RedBlueDebateService
from src.domain.ports.registry import _global_registry

PORT_NAME = "red_blue_debate_service"
IMPL_CLS_NAME = "RedBlueDebateService"
MODULE_PATH = "src.application.services.red_blue_debate_service"
EXPECTED_TAGS = ("debate", "service")
EXPECTED_OWNER = "tool-team"
REQUIRED_METHODS = ["run_debate", "get_debate_result"]


class _RealResolver:
    """真实 resolver 代理（工厂依赖解析用）"""

    def resolve(self, name: str) -> Any:
        from src.domain.ports.resolver import resolve

        return resolve(name)

    def resolve_optional(self, name: str) -> Any:
        return None


class TestRedBlueDebateServicePortContract:
    """red_blue_debate_service 端口 11 维度契约。"""

    def _spec(self) -> Any:
        return _global_registry.get(PORT_NAME)

    def _resolver(self) -> _RealResolver:
        return _RealResolver()

    def test_dimension_1_port_is_registered(self) -> None:
        """维度 1：端口已在组合根注册。"""
        assert self._spec() is not None

    def test_dimension_2_port_name(self) -> None:
        """维度 2：端口名精确匹配。"""
        assert self._spec().name == PORT_NAME

    def test_dimension_3_port_version(self) -> None:
        """维度 3：版本 v1.0.0。"""
        assert self._spec().version == "v1.0.0"

    def test_dimension_4_port_interface_type(self) -> None:
        """维度 4：interface 为 RedBlueDebateServicePort。"""
        assert self._spec().interface is RedBlueDebateServicePort

    def test_dimension_5_port_lifetime(self) -> None:
        """维度 5：生命周期 SCOPED。"""
        from src.domain.ports.registry import Lifetime

        assert self._spec().lifetime is Lifetime.SCOPED

    def test_dimension_6_port_owner(self) -> None:
        """维度 6：owner 为 tool-team。"""
        assert self._spec().owner == EXPECTED_OWNER

    def test_dimension_7_port_module(self) -> None:
        """维度 7：module 路径精确。"""
        assert self._spec().module == MODULE_PATH

    def test_dimension_8_port_tags(self) -> None:
        """维度 8：tags 含 debate/service。"""
        assert set(EXPECTED_TAGS).issubset(set(self._spec().tags))

    def test_dimension_9_impl_is_callable(self) -> None:
        """维度 9：impl 为 lambda 工厂（可调用非类）。"""
        impl = self._spec().impl
        assert callable(impl) and not isinstance(impl, type)

    def test_dimension_9b_impl_factory_produces_port_instance(self) -> None:
        """维度 9b：工厂产出真实服务实例且满足端口协议。"""
        instance = self._spec().impl(resolver=self._resolver())
        assert isinstance(instance, RedBlueDebateService)
        assert isinstance(instance, RedBlueDebateServicePort)

    def test_dimension_10_required_methods_signature(self) -> None:
        """维度 10：REQUIRED_METHODS 两方法存在且为 async。"""
        for method_name in REQUIRED_METHODS:
            method = getattr(RedBlueDebateService, method_name, None)
            assert method is not None, f"缺少方法 {method_name}"
            assert inspect.iscoroutinefunction(method), f"{method_name} 应为 async"

    def test_dimension_11_protocol_is_runtime_checkable(self) -> None:
        """维度 11：端口协议 runtime_checkable（结构匹配 stub 的 isinstance 行为验证）。"""

        class _PortStub:
            async def run_debate(self, topic: Any, context: Any) -> Any:
                """协议方法桩"""

            async def get_debate_result(self, debate_id: Any) -> Any:
                """协议方法桩"""

        # 非 runtime_checkable 的 Protocol 对 isinstance 抛 TypeError；
        # 结构匹配实例通过判定即证明 @runtime_checkable 生效
        assert isinstance(_PortStub(), RedBlueDebateServicePort)

    def test_port_spec_10_fields_complete(self) -> None:
        """PortSpec 10 字段元数据完整性。"""
        spec = self._spec()
        from dataclasses import fields

        from src.domain.ports.registry import PortSpec

        expected_fields = {f.name for f in fields(PortSpec)}
        actual_fields = {f.name for f in fields(type(spec))}
        assert expected_fields == actual_fields
        assert spec.compatibility == ()
        assert spec.deprecated is False
