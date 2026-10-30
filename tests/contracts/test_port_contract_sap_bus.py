"""sap_bus 端口契约测试——Story 5.11 组合根注册 11 维度门禁。

模板：test_port_contract_agent_checkpoint.py（11 维度 + _DummyResolver 分发替身 +
REQUIRED_METHODS 常量）；追加降级防护维度：依赖缺失 → ConfigurationError（fail-fast
非降级——DC-12，与 5.6/5.8/5.9 可选依赖 resolve_optional→None 降级族相反裁定）。

Run with:
    poetry run pytest tests/contracts/test_port_contract_sap_bus.py -v
"""

from __future__ import annotations

from typing import Any

import pytest

from src.domain.ports.registry import Lifetime, _global_registry

PORT_NAME = "sap_bus"
IMPL_CLS_NAME = "InProcessSAPBus"
MODULE_PATH = "src.interfaces.sap.bus"
EXPECTED_TAGS = ("agent", "sap", "collaboration")
EXPECTED_OWNER = "platform"
REQUIRED_METHODS = ["send", "subscribe", "wait_for_response", "close"]


class _FakeBlackboard:
    """零 IO 黑板 Fake（分发替身依赖——duck-typing PublicBlackboard 最小面）。"""

    async def post(
        self,
        conversation_id: str,
        agent_id: str,
        content: dict[str, Any],
        confidence: float = 1.0,
        citations: list[str] | None = None,
    ) -> int:
        """桩 post。"""
        return 1

    async def get(self, conversation_id: str) -> list[dict[str, Any]]:
        """桩 get。"""
        return []


class _FakeGuard:
    """零 IO 守卫 Fake（分发替身依赖——duck-typing IsolationGuardPort 最小面）。"""

    async def ensure_agent_access(self, actor_agent_id: Any, target_agent_id: Any, resource: Any, operation: Any) -> None:
        """放行桩。"""


class _DummyResolver:
    """零 IO 依赖分发替身（分发 sap_bus 工厂 lambda 消费的 public_blackboard/isolation_guard_service 端口名）."""

    def resolve(self, name: str) -> Any:
        if name == "public_blackboard":
            return _FakeBlackboard()
        if name == "isolation_guard_service":
            return _FakeGuard()
        raise KeyError(f"未注册的端口: {name}")

    def resolve_optional(self, name: str) -> Any:
        return None


class _MissingDepsResolver:
    """缺依赖分发替身（resolve 一律 KeyError——fail-fast 翻译载体）."""

    def resolve(self, name: str) -> Any:
        raise KeyError(f"Port not registered: {name}")

    def resolve_optional(self, name: str) -> Any:
        return None


class TestSAPBusPortContract:
    """sap_bus 端口契约 11 维度 + fail-fast 降级防护。"""

    def _spec(self) -> Any:
        spec = _global_registry.get(PORT_NAME)
        assert spec is not None, f"端口 {PORT_NAME} 未注册（bootstrap 后应可达）"
        return spec

    def test_dimension_1_port_is_registered(self) -> None:
        """维度 1：端口已注册（bootstrap 后可达）。"""
        assert self._spec() is not None

    def test_dimension_2_port_name(self) -> None:
        """维度 2：端口名 sap_bus。"""
        assert self._spec().name == PORT_NAME

    def test_dimension_3_port_version(self) -> None:
        """维度 3：版本 v1.0.0（端口契约基线——Epic 9 演进走 contract_gate）。"""
        assert self._spec().version == "v1.0.0"

    def test_dimension_4_interface_is_sap_bus(self) -> None:
        """维度 4：interface 是 SAPBus Protocol。"""
        from src.interfaces.sap.bus import SAPBus

        assert self._spec().interface is SAPBus

    def test_dimension_5_lifetime_singleton(self) -> None:
        """维度 5：SINGLETON（有状态总线——订阅表+correlation 索引+优先级队列跨调用共享）。"""
        assert self._spec().lifetime == Lifetime.SINGLETON

    def test_dimension_6_owner(self) -> None:
        """维度 6：owner=platform。"""
        assert self._spec().owner == EXPECTED_OWNER

    def test_dimension_7_module_path(self) -> None:
        """维度 7：module 路径。"""
        assert self._spec().module == MODULE_PATH

    def test_dimension_8_tags(self) -> None:
        """维度 8：tags 三元组。"""
        assert self._spec().tags == EXPECTED_TAGS

    def test_dimension_9a_impl_is_callable(self) -> None:
        """维度 9a：impl 是可调用 lambda。"""
        assert callable(self._spec().impl)

    def test_dimension_9b_impl_yields_port_instance(self) -> None:
        """维度 9b：Dummy 分发两依赖 → impl 产出 InProcessSAPBus 实例。"""
        from src.interfaces.sap.bus import SAPBus

        instance = self._spec().impl(_DummyResolver())
        assert isinstance(instance, SAPBus)
        assert type(instance).__name__ == IMPL_CLS_NAME

    def test_dimension_10_methods_present(self) -> None:
        """维度 10：REQUIRED_METHODS 四方法存在且可调用。"""
        instance = self._spec().impl(_DummyResolver())
        for method in REQUIRED_METHODS:
            assert hasattr(instance, method), f"方法缺失: {method}"
            assert callable(getattr(instance, method)), f"方法不可调用: {method}"

    def test_dimension_11_runtime_checkable(self) -> None:
        """维度 11：runtime_checkable Protocol 判别。"""
        from src.interfaces.sap.bus import SAPBus

        instance = self._spec().impl(_DummyResolver())
        assert isinstance(instance, SAPBus)

    def test_fail_fast_configuration_error_on_missing_deps(self) -> None:
        """降级防护：依赖缺失 → ConfigurationError（fail-fast 非 None 降级——DC-12 三元组翻译）。"""
        from src.domain.exceptions import ConfigurationError

        impl = self._spec().impl
        assert callable(impl)
        with pytest.raises(ConfigurationError) as exc_info:
            impl(_MissingDepsResolver())
        assert exc_info.value.code == "EXCEPTION_101"
        assert exc_info.value.cause is not None, "翻译应保留 cause 链（from e）"
