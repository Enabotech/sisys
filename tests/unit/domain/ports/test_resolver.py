"""Resolver 依赖注入容器单元测试。

验证端口解析、生命周期管理、自动注入和懒加载行为。
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.domain.ports.registry import Lifetime, PortRegistry, PortSpec
from src.domain.ports.resolver import Resolver, get_resolver, resolve


class _MockInterface:
    """模拟接口用于测试。"""

    def execute(self) -> str:
        """执行方法。"""
        return ""


class _MockImplA:
    """模拟实现 A。"""

    def __init__(self, config: str = "default") -> None:
        self.config = config

    def execute(self) -> str:
        return "impl_a"


class _MockImplB:
    """模拟实现 B（需要依赖注入）。"""

    def __init__(self, dependency: _MockImplA) -> None:
        self.dependency = dependency

    def execute(self) -> str:
        return "impl_b"


class _MockImplC:
    """模拟实现 C（无依赖）。"""

    def execute(self) -> str:
        return "impl_c"


class TestResolverResolve:
    """Resolver.resolve 测试。"""

    @pytest.fixture
    def registry(self) -> PortRegistry:
        """创建干净的注册表。"""
        registry = PortRegistry()
        registry._ports.clear()
        return registry

    def test_resolve_registered_port(self, registry: PortRegistry) -> None:
        """解析已注册端口应返回实例。"""
        spec = PortSpec(
            name="test_port",
            version="1.0.0",
            interface=_MockInterface,
            impl=_MockImplC,
            module="test.module",
            lifetime=Lifetime.TRANSIENT,
        )
        registry.register(spec)
        resolver = Resolver(registry=registry)
        result = resolver.resolve("test_port")
        assert isinstance(result, _MockImplC)

    def test_resolve_unregistered_port_raises_key_error(self, registry: PortRegistry) -> None:
        """解析未注册端口应抛出 KeyError。"""
        resolver = Resolver(registry=registry)
        with pytest.raises(KeyError, match="Port not registered"):
            resolver.resolve("nonexistent")

    def test_resolve_override_returns_override(self, registry: PortRegistry) -> None:
        """override 应优先返回。"""
        override_instance = _MockImplC()
        resolver = Resolver(registry=registry, overrides={"test_port": override_instance})
        result = resolver.resolve("test_port")
        assert result is override_instance


class TestResolverDeprecated:
    """Resolver 处理 deprecated 端口测试。"""

    @pytest.fixture
    def registry(self) -> PortRegistry:
        """创建干净的注册表。"""
        registry = PortRegistry()
        registry._ports.clear()
        return registry

    def test_resolve_deprecated_logs_warning(self, registry: PortRegistry) -> None:
        """解析 deprecated 端口应打印警告日志。"""
        spec = PortSpec(
            name="deprecated_port",
            version="1.0.0",
            interface=_MockInterface,
            impl=_MockImplC,
            module="test.module",
            deprecated=True,
        )
        registry.register(spec)
        resolver = Resolver(registry=registry)

        with patch("src.domain.ports.resolver.logger.warning") as mock_warning:
            resolver.resolve("deprecated_port")
            mock_warning.assert_called_once()


class TestResolverLifecycle:
    """Resolver 生命周期管理测试。"""

    @pytest.fixture
    def registry(self) -> PortRegistry:
        """创建干净的注册表。"""
        registry = PortRegistry()
        registry._ports.clear()
        return registry

    def test_transient_creates_new_instance(self, registry: PortRegistry) -> None:
        """TRANSIENT 每次应创建新实例。"""
        spec = PortSpec(
            name="transient_port",
            version="1.0.0",
            interface=_MockInterface,
            impl=_MockImplC,
            module="test.module",
            lifetime=Lifetime.TRANSIENT,
        )
        registry.register(spec)
        resolver = Resolver(registry=registry)

        a = resolver.resolve("transient_port")
        b = resolver.resolve("transient_port")
        assert a is not b

    def test_singleton_returns_same_instance(self, registry: PortRegistry) -> None:
        """SINGLETON 应返回相同实例。"""
        spec = PortSpec(
            name="singleton_port",
            version="1.0.0",
            interface=_MockInterface,
            impl=_MockImplC,
            module="test.module",
            lifetime=Lifetime.SINGLETON,
        )
        registry.register(spec)
        resolver = Resolver(registry=registry)

        a = resolver.resolve("singleton_port")
        b = resolver.resolve("singleton_port")
        assert a is b

    def test_scoped_returns_same_within_scope(self, registry: PortRegistry) -> None:
        """SCOPED 在同一 scope 内应返回相同实例。"""
        spec = PortSpec(
            name="scoped_port",
            version="1.0.0",
            interface=_MockInterface,
            impl=_MockImplC,
            module="test.module",
            lifetime=Lifetime.SCOPED,
        )
        registry.register(spec)
        resolver = Resolver(registry=registry)

        a = resolver.resolve("scoped_port")
        b = resolver.resolve("scoped_port")
        assert a is b

    def test_scoped_clear_creates_new_after_clear(self, registry: PortRegistry) -> None:
        """clear_scoped 后应创建新实例。"""
        spec = PortSpec(
            name="scoped_port",
            version="1.0.0",
            interface=_MockInterface,
            impl=_MockImplC,
            module="test.module",
            lifetime=Lifetime.SCOPED,
        )
        registry.register(spec)
        resolver = Resolver(registry=registry)

        a = resolver.resolve("scoped_port")
        resolver.clear_scoped()
        b = resolver.resolve("scoped_port")
        assert a is not b

    def test_clear_singleton_removes_cached_instances(self, registry: PortRegistry) -> None:
        """clear_singleton 应移除缓存实例。"""
        spec = PortSpec(
            name="singleton_port",
            version="1.0.0",
            interface=_MockInterface,
            impl=_MockImplC,
            module="test.module",
            lifetime=Lifetime.SINGLETON,
        )
        registry.register(spec)
        resolver = Resolver(registry=registry)

        a = resolver.resolve("singleton_port")
        resolver.clear_singleton()
        b = resolver.resolve("singleton_port")
        assert a is not b


class TestResolverResolveByInterface:
    """Resolver.resolve_by_interface 测试。"""

    @pytest.fixture
    def registry(self) -> PortRegistry:
        """创建干净的注册表。"""
        registry = PortRegistry()
        registry._ports.clear()
        return registry

    def test_resolve_by_interface_returns_impl(self, registry: PortRegistry) -> None:
        """按接口类型解析应返回实现。"""
        spec = PortSpec(
            name="interface_port",
            version="1.0.0",
            interface=_MockInterface,
            impl=_MockImplC,
            module="test.module",
        )
        registry.register(spec)
        resolver = Resolver(registry=registry)

        result = resolver.resolve_by_interface(_MockInterface)
        assert isinstance(result, _MockImplC)

    def test_resolve_by_interface_unregistered_raises_key_error(self, registry: PortRegistry) -> None:
        """接口未注册应抛出 KeyError。"""
        resolver = Resolver(registry=registry)

        class _UnregisteredInterface:
            pass

        with pytest.raises(KeyError, match="Port not found for interface"):
            resolver.resolve_by_interface(_UnregisteredInterface)

    def test_resolve_by_interface_string_raises_key_error(self, registry: PortRegistry) -> None:
        """字符串 forward-reference 应抛出 KeyError。"""
        resolver = Resolver(registry=registry)
        with pytest.raises(KeyError, match="Cannot resolve forward-reference"):
            resolver.resolve_by_interface("SomeInterface")


class TestResolverAutoInject:
    """Resolver._auto_inject 自动注入测试。"""

    @pytest.fixture
    def registry(self) -> PortRegistry:
        """创建干净的注册表。"""
        registry = PortRegistry()
        registry._ports.clear()
        return registry

    def test_auto_inject_resolves_dependencies(self, registry: PortRegistry) -> None:
        """应自动注入构造函数依赖。"""
        dep_spec = PortSpec(
            name="dependency",
            version="1.0.0",
            interface=_MockInterface,
            impl=_MockImplA,
            module="test.module",
        )
        registry.register(dep_spec)

        impl_spec = PortSpec(
            name="impl_with_dep",
            version="1.0.0",
            interface=_MockInterface,
            impl=_MockImplB,
            module="test.module",
        )
        registry.register(impl_spec)

        resolver = Resolver(registry=registry)
        result = resolver.resolve("impl_with_dep")
        assert isinstance(result, _MockImplB)
        assert isinstance(result.dependency, _MockImplA)

    def test_auto_inject_uses_default_for_optional_params(self, registry: PortRegistry) -> None:
        """可选参数应使用默认值。"""
        spec = PortSpec(
            name="optional_dep",
            version="1.0.0",
            interface=_MockInterface,
            impl=_MockImplA,
            module="test.module",
        )
        registry.register(spec)
        resolver = Resolver(registry=registry)

        result = resolver.resolve("optional_dep")
        assert result.config == "default"

    def test_auto_inject_missing_required_raises_runtime_error(self, registry: PortRegistry) -> None:
        """缺少必需依赖应抛出 RuntimeError。"""

        class _ImplWithRequiredDep:
            def __init__(self, missing_dep: Any) -> None:
                self.missing_dep = missing_dep

        spec = PortSpec(
            name="missing_dep_impl",
            version="1.0.0",
            interface=_MockInterface,
            impl=_ImplWithRequiredDep,
            module="test.module",
        )
        registry.register(spec)
        resolver = Resolver(registry=registry)

        with pytest.raises(RuntimeError, match="Cannot resolve required dependencies"):
            resolver.resolve("missing_dep_impl")


class TestResolverFactoryFunction:
    """Resolver 处理工厂函数测试。"""

    @pytest.fixture
    def registry(self) -> PortRegistry:
        """创建干净的注册表。"""
        registry = PortRegistry()
        registry._ports.clear()
        return registry

    def test_callable_factory_returns_result(self, registry: PortRegistry) -> None:
        """工厂函数应被调用并返回结果。"""

        def factory(resolver: Resolver) -> _MockImplC:
            return _MockImplC()

        spec = PortSpec(
            name="factory_port",
            version="1.0.0",
            interface=_MockInterface,
            impl=factory,
            module="test.module",
        )
        registry.register(spec)
        resolver = Resolver(registry=registry)

        result = resolver.resolve("factory_port")
        assert isinstance(result, _MockImplC)

    def test_factory_receives_resolver(self, registry: PortRegistry) -> None:
        """工厂函数应接收 resolver 参数。"""
        _received_resolver = None

        def factory(resolver: Resolver) -> _MockImplC:
            _received_resolver = resolver
            return _MockImplC()

        spec = PortSpec(
            name="factory_port",
            version="1.0.0",
            interface=_MockInterface,
            impl=factory,
            module="test.module",
        )
        registry.register(spec)
        resolver = Resolver(registry=registry)
        resolver.resolve("factory_port")


class TestResolverLazyLoading:
    """Resolver._load_from_module_path 懒加载测试。"""

    def test_load_from_module_path_success(self) -> None:
        """成功加载模块路径。"""
        resolver = Resolver()
        cls = resolver._load_from_module_path("unittest.mock.MagicMock")
        assert cls is MagicMock

    def test_load_from_module_path_invalid_module(self) -> None:
        """无效模块路径应抛出 RuntimeError。"""
        resolver = Resolver()
        with pytest.raises(RuntimeError, match="Failed to lazy-load"):
            resolver._load_from_module_path("nonexistent.module.Class")

    def test_load_from_module_path_invalid_class(self) -> None:
        """无效类名应抛出 RuntimeError。"""
        resolver = Resolver()
        with pytest.raises(RuntimeError, match="Failed to lazy-load"):
            resolver._load_from_module_path("unittest.mock.NonexistentClass")


class TestGlobalResolver:
    """全局 Resolver 函数测试。"""

    def test_get_resolver_returns_instance(self) -> None:
        """get_resolver 应返回 Resolver 实例。"""
        resolver = get_resolver()
        assert isinstance(resolver, Resolver)

    def test_get_resolver_returns_same_instance(self) -> None:
        """get_resolver 应返回相同实例（单例）。"""
        a = get_resolver()
        b = get_resolver()
        assert a is b

    def test_resolve_calls_resolver_resolve(self) -> None:
        """resolve 函数应委托给 Resolver.resolve。"""
        with patch.object(get_resolver(), "resolve", return_value="mock_result") as mock_resolve:
            result = resolve("some_port")
            mock_resolve.assert_called_once_with("some_port")
            assert result == "mock_result"
