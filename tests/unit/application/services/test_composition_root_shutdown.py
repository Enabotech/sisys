"""composition_root.shutdown() 数据源适配器清理测试（Story 4.1b R2-2-B1 / G6）

验证 shutdown() 对 7 个 data_source_* 端口 httpx 连接池的清理语义：
- 已实例化的单例适配器 → close() 被调用
- 已注册但未实例化的端口 → 不触发懒实例化（peek_singleton 零副作用，
  resolve() 会在 shutdown 路径现场创建实例——含读 env 构造，属危险副作用）
- 未注册端口（条件注册的 newsapi/tavily Key 缺失场景）→ 跳过不报错
- 单端口 close() 失败 → 不阻断其余端口清理（异常隔离）

测试模式：真实 Resolver + 独立注册中心实例（object.__new__ 绕过全局单例，
对齐 tests/unit/domain/ports/test_resolver.py 既有先例；单元测试 Mock 端口）。
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.composition_root import shutdown
from src.domain.ports.registry import Lifetime, PortRegistry, PortSpec
from src.domain.ports.resolver import Resolver


class _FakeAdapter:
    """假数据源适配器（close 计数 + 可编程失败）。"""

    def __init__(self, fail_on_close: bool = False) -> None:
        self.close_calls = 0
        self._fail = fail_on_close

    async def close(self) -> None:
        self.close_calls += 1
        if self._fail:
            raise ConnectionError("close failed")


def _fresh_registry() -> PortRegistry:
    """创建独立的注册中心实例（不污染全局单例，对齐 test_resolver.py 先例）。"""
    registry = object.__new__(PortRegistry)
    registry._ports = {}
    return registry


def _make_resolver(
    used: tuple[str, ...] = (),
    unused: tuple[str, ...] = (),
    fail_close: tuple[str, ...] = (),
) -> tuple[Resolver, dict[str, _FakeAdapter]]:
    """构建真实 Resolver：used/fail_close 端口预实例化，unused 仅注册不实例化。"""
    registry = _fresh_registry()
    adapters: dict[str, _FakeAdapter] = {}
    for name in (*used, *unused, *fail_close):
        adapter = _FakeAdapter(fail_on_close=name in fail_close)
        adapters[name] = adapter
        registry.register(
            PortSpec(
                name=name,
                version="v1.0.0",
                interface=object,
                impl=lambda *, resolver, _name=name: adapters[_name],  # 工厂签名对齐 Resolver._instantiate 契约
                module="tests.fake",
                lifetime=Lifetime.SINGLETON,
            )
        )
    resolver = Resolver(registry=registry)
    for name in (*used, *fail_close):
        resolver.resolve(name)  # 触发懒实例化（模拟生产已使用）
    return resolver, adapters


async def _run_shutdown(resolver: Resolver) -> None:
    with patch("src.domain.ports.resolver.get_resolver", return_value=resolver):
        await shutdown()


class TestShutdownDataSourceCleanup:
    @pytest.mark.asyncio
    async def test_instantiated_adapter_closed(self) -> None:
        """已使用的适配器（已实例化单例）→ shutdown 时 close() 被调用。"""
        resolver, adapters = _make_resolver(used=("data_source_worldbank",))
        await _run_shutdown(resolver)
        assert adapters["data_source_worldbank"].close_calls == 1

    @pytest.mark.asyncio
    async def test_uninstantiated_port_not_lazy_created(self) -> None:
        """已注册未使用的端口 → shutdown 不触发懒实例化、不调用 close。"""
        resolver, adapters = _make_resolver(unused=("data_source_newsapi",))
        await _run_shutdown(resolver)
        assert adapters["data_source_newsapi"].close_calls == 0
        assert resolver.peek_singleton("data_source_newsapi") is None  # 仍未实例化

    @pytest.mark.asyncio
    async def test_unregistered_port_skipped(self) -> None:
        """无任何 data_source_* 注册 → shutdown 正常完成不报错。"""
        resolver, _ = _make_resolver()
        await _run_shutdown(resolver)  # 不抛异常即通过

    @pytest.mark.asyncio
    async def test_close_failure_does_not_block_others(self) -> None:
        """单端口 close 失败 → 其余端口仍被清理（异常隔离）。"""
        resolver, adapters = _make_resolver(
            used=("data_source_imf",),
            fail_close=("data_source_worldbank",),
        )
        await _run_shutdown(resolver)
        assert adapters["data_source_worldbank"].close_calls == 1  # 已尝试（失败）
        assert adapters["data_source_imf"].close_calls == 1  # 未被阻断


class TestPeekSingleton:
    """Resolver.peek_singleton 四类 None 语义（domain 层新增方法）。"""

    def test_unregistered_returns_none(self) -> None:
        resolver, _ = _make_resolver()
        assert resolver.peek_singleton("data_source_tavily") is None

    def test_registered_but_not_instantiated_returns_none(self) -> None:
        resolver, _ = _make_resolver(unused=("data_source_tavily",))
        assert resolver.peek_singleton("data_source_tavily") is None

    def test_instantiated_returns_instance(self) -> None:
        resolver, adapters = _make_resolver(used=("data_source_tavily",))
        assert resolver.peek_singleton("data_source_tavily") is adapters["data_source_tavily"]

    def test_override_not_visible(self) -> None:
        """override 注入实例对 peek 不可见（overrides 仅测试路径，文档化语义）。"""
        registry = _fresh_registry()
        resolver = Resolver(registry=registry, overrides={"data_source_tavily": _FakeAdapter()})
        assert resolver.peek_singleton("data_source_tavily") is None
