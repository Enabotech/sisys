"""Story 4.1b: 端口契约测试 — data_source_resolver 应用层端口

验证 data_source_resolver 端口的注册、版本、接口、生命周期、owner/tags/module 元数据，
以及 DataSourceResolverService 实现类的 required_methods 与 Protocol runtime_checkable 属性。

遵循项目标准 11 维度契约测试模式（范本 tests/contracts/test_port_contract_tool.py）。
"""

from __future__ import annotations

from typing import Any

from src.application.ports.data_source_resolver import DataSourceResolverPort
from src.domain.ports.registry import Lifetime, _global_registry


class _StubCache:
    """L1CachePort 最小桩（仅满足契约测试实例化）。"""

    async def get(self, key: str) -> str | None:
        return None

    async def set(self, key: str, value: str, ttl: int | None = None) -> bool:
        return True

    async def delete(self, key: str) -> bool:
        return True

    async def exists(self, key: str) -> bool:
        return False

    async def delete_pattern(self, pattern: str) -> int:
        return 0

    async def set_with_ttl(self, key: str, value: str, ttl: int) -> bool:
        return True

    async def set_nx(self, key: str, value: str, ttl: int) -> bool:
        return True

    async def eval(self, script: str, keys: list[str], args: list[str]) -> Any:
        return None


class _DummyResolver:
    """测试用最小 Resolver 占位符。

    data_source_resolver 工厂需要 resolver.resolve_optional('data_source_*')
    聚合适配器 + resolver.resolve('redis_adapter') 缓存 + 事件总线，
    本测试提供最小可工作桩。
    """

    def resolve(self, name: str) -> Any:
        if name == "redis_adapter":
            return _StubCache()
        raise KeyError(name)

    def resolve_optional(self, name: str, **_kwargs: Any) -> Any:
        if name == "redis_adapter":
            return _StubCache()
        return None  # data_source_* 适配器未注册时优雅降级为空集合


class TestDataSourceResolverPortContract:
    """data_source_resolver 端口契约（11 维度全覆盖）."""

    PORT_NAME = "data_source_resolver"
    IMPL_CLS_NAME = "DataSourceResolverService"
    MODULE_PATH = "src.application.services.data_source_resolver"
    EXPECTED_TAGS = ("data-source", "resolver", "service")
    EXPECTED_OWNER = "tool-team"
    REQUIRED_METHODS = ["fetch", "fetch_many"]

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
        """维度 4：PortSpec.interface 是 DataSourceResolverPort Protocol."""
        spec = self._spec()
        assert spec is not None
        assert spec.interface is DataSourceResolverPort

    def test_dimension_5_port_lifetime(self) -> None:
        """维度 5：PortSpec.lifetime 为 SINGLETON（无状态编排服务）."""
        spec = self._spec()
        assert spec is not None
        assert spec.lifetime == Lifetime.SINGLETON

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
        assert isinstance(instance, DataSourceResolverPort)

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
        """维度 11：Protocol 是 @runtime_checkable（isinstance 行为）."""
        from src.application.services.data_source_resolver import DataSourceResolverService

        service = DataSourceResolverService(adapters={}, cache=_StubCache())
        assert isinstance(service, DataSourceResolverPort)
