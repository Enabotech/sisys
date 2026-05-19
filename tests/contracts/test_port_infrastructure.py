"""Port infrastructure contract tests.

Tests that PortRegistry, Resolver, and ContractGate core functionality is correct.
对应 AC-1: 端口基础设施测试完成
"""

from __future__ import annotations

import pytest

from src.domain.ports.contract_gate import CompatibilityResult, ContractGate
from src.domain.ports.registry import PortRegistry, PortSpec
from src.domain.ports.resolver import Resolver


class TestPortRegistry:
    """Contract tests for PortRegistry."""

    @pytest.fixture
    def fresh_registry(self) -> PortRegistry:
        """提供一个新的空注册中心用于测试."""
        return PortRegistry()

    def test_register_adds_port_spec(self, fresh_registry: PortRegistry) -> None:
        """register() should add a PortSpec to the registry."""
        from src.domain.ports.connection_manager import ConnectionManager

        spec = PortSpec(
            name="test_port",
            version="v1.0.0",
            interface=ConnectionManager,
            impl=ConnectionManager,
            module="test_module",
        )
        fresh_registry.register(spec)
        retrieved = fresh_registry.get("test_port")
        assert retrieved is not None
        assert retrieved.name == "test_port"

    def test_get_returns_none_for_unregistered(self, fresh_registry: PortRegistry) -> None:
        """get() should return None for unregistered port."""
        result = fresh_registry.get("nonexistent_port")
        assert result is None

    def test_list_all_returns_all_registered_ports(self, fresh_registry: PortRegistry) -> None:
        """list_all() should return all registered port specs."""
        from src.domain.ports.connection_manager import ConnectionManager

        spec1 = PortSpec(
            name="port_a_fresh",
            version="v1.0.0",
            interface=ConnectionManager,
            impl=ConnectionManager,
            module="test",
        )
        spec2 = PortSpec(
            name="port_b_fresh",
            version="v1.0.0",
            interface=ConnectionManager,
            impl=ConnectionManager,
            module="test",
        )
        fresh_registry.register(spec1)
        fresh_registry.register(spec2)
        all_ports = fresh_registry.list_all()
        # Verify the two ports we just registered are in the list
        port_names = [p.name for p in all_ports]
        assert "port_a_fresh" in port_names
        assert "port_b_fresh" in port_names

    def test_unregister_removes_port(self, fresh_registry: PortRegistry) -> None:
        """unregister() should remove a port from the registry."""
        from src.domain.ports.connection_manager import ConnectionManager

        spec = PortSpec(
            name="to_remove",
            version="v1.0.0",
            interface=ConnectionManager,
            impl=ConnectionManager,
            module="test",
        )
        fresh_registry.register(spec)
        fresh_registry.unregister("to_remove")
        assert fresh_registry.get("to_remove") is None


class TestResolver:
    """Contract tests for Resolver."""

    @pytest.fixture
    def resolver(self) -> Resolver:
        """提供 Resolver 实例."""
        return Resolver()

    def test_resolve_returns_instance(self, resolver: Resolver) -> None:
        """resolve() should return an instance for registered port."""
        impl = resolver.resolve("hash_router")
        assert impl is not None

    def test_resolve_by_interface(self, resolver: Resolver) -> None:
        """resolve_by_interface() should return instance matching interface."""
        from src.domain.ports.hash_router_protocol import HashRouterProtocol

        impl = resolver.resolve_by_interface(HashRouterProtocol)
        assert impl is not None

    def test_clear_singleton_clears_cached_instances(self, resolver: Resolver) -> None:
        """clear_singleton() should clear singleton cache."""
        # First resolve to cache
        resolver.resolve("hash_router")
        # Clear should not raise
        resolver.clear_singleton()
        # Resolving again should still work
        impl = resolver.resolve("hash_router")
        assert impl is not None


class TestContractGate:
    """Contract tests for ContractGate."""

    def test_check_compatibility_returns_result(self, registry) -> None:
        """check_compatibility() should return CompatibilityResult."""
        gate = ContractGate()
        redis_spec = registry.get("redis_connection_manager")
        assert redis_spec is not None
        result = gate.check_compatibility(redis_spec, redis_spec)
        assert isinstance(result, CompatibilityResult)

    def test_compatibility_result_has_required_fields(self, registry) -> None:
        """CompatibilityResult must have required fields."""
        gate = ContractGate()
        redis_spec = registry.get("redis_connection_manager")
        assert redis_spec is not None
        result = gate.check_compatibility(redis_spec, redis_spec)
        assert hasattr(result, "is_compatible")
        assert hasattr(result, "breaking_changes")
        assert hasattr(result, "warnings")
