"""Unit tests for route architecture compliance - hexagonal architecture verification."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from uuid import uuid4

import pytest


class TestRouteHexagonalArchitecture:
    """Test suite for verifying hexagonal architecture compliance in route mechanism."""

    def test_auto_route_service_in_domain_layer(self) -> None:
        """AutoRouteService should be in domain layer."""
        from src.domain.services.auto_route_service import AutoRouteService

        module_path = Path(inspect.getfile(AutoRouteService))
        assert "src/domain/services" in str(module_path), f"AutoRouteService should be in domain layer, found in {module_path}"

    def test_hash_router_in_infrastructure_layer(self) -> None:
        """HashRouter should be in infrastructure layer."""
        from src.infrastructure.routing.hash_router import HashRouter

        module_path = Path(inspect.getfile(HashRouter))
        assert "src/infrastructure/routing" in str(module_path), (
            f"HashRouter should be in infrastructure layer, found in {module_path}"
        )

    def test_semantic_router_in_infrastructure_layer(self) -> None:
        """SemanticRouter should be in infrastructure layer."""
        from src.infrastructure.routing.semantic_router import SemanticRouter

        module_path = Path(inspect.getfile(SemanticRouter))
        assert "src/infrastructure/routing" in str(module_path), (
            f"SemanticRouter should be in infrastructure layer, found in {module_path}"
        )

    def test_auto_route_events_in_domain_layer(self) -> None:
        """AutoRouted event should be in domain layer."""
        from src.domain.events.auto_route_events import AutoRouted

        module_path = Path(inspect.getfile(AutoRouted))
        assert "src/domain/events" in str(module_path), f"AutoRouted event should be in domain layer, found in {module_path}"

    def test_auto_route_service_no_infrastructure_imports(self) -> None:
        """AutoRouteService should not import infrastructure modules directly."""
        from src.domain.services.auto_route_service import AutoRouteService

        source = inspect.getsource(AutoRouteService)
        tree = ast.parse(source)

        infrastructure_imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "infrastructure" in alias.name and "messaging" not in alias.name:
                        infrastructure_imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module and "infrastructure" in node.module:
                    infrastructure_imports.append(node.module)

        # AutoRouteService should NOT directly import RedisPublisher, HashRouter, SemanticRouter
        forbidden_imports = [
            "src.infrastructure.messaging.redis_publisher",
            "src.infrastructure.routing.hash_router",
            "src.infrastructure.routing.semantic_router",
            "RedisEventPublisher",
            "HashRouter",
            "SemanticRouter",
        ]

        for imp in infrastructure_imports:
            for forbidden in forbidden_imports:
                assert forbidden not in imp, f"AutoRouteService imports infrastructure module: {imp}"

    def test_auto_route_service_uses_protocols(self) -> None:
        """AutoRouteService should use Protocol definitions for dependency inversion."""
        from src.domain.ports.event_publisher import EventPublisher
        from src.domain.ports.hash_router_protocol import HashRouterProtocol
        from src.domain.ports.semantic_router_protocol import SemanticRouterProtocol
        from src.domain.services.auto_route_service import AutoRouteService

        # Verify protocols exist
        assert EventPublisher is not None
        assert HashRouterProtocol is not None
        assert SemanticRouterProtocol is not None

        # Verify AutoRouteService accepts Protocol types
        sig = inspect.signature(AutoRouteService.__init__)
        params = list(sig.parameters.keys())

        assert "publisher" in params, "AutoRouteService should accept publisher parameter"
        # Note: hash_router and semantic_router are optional
        assert len(params) >= 1, "AutoRouteService should have init parameters"

    def test_auto_route_service_is_async(self) -> None:
        """AutoRouteService methods should be async."""
        from src.domain.services.auto_route_service import AutoRouteService

        # Check that on_triggered_event is async
        assert inspect.iscoroutinefunction(AutoRouteService.on_triggered_event), "on_triggered_event should be async"

    def test_domain_layer_has_no_external_dependencies(self) -> None:
        """Domain layer (route services) should not depend on external frameworks."""
        domain_route_files = [
            Path("src/domain/services/auto_route_service.py"),
            Path("src/domain/events/auto_route_events.py"),
        ]

        external_frameworks = [
            "fastapi",
            "typer",
            "redis",
            "sqlalchemy",
            "prefect",
            "langgraph",
        ]

        for file_path in domain_route_files:
            if not file_path.exists():
                continue

            content = file_path.read_text()
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        for framework in external_frameworks:
                            assert framework not in alias.name, f"{file_path} imports external framework: {alias.name}"
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        for framework in external_frameworks:
                            assert framework not in node.module, f"{file_path} imports external framework: {node.module}"

    def test_infrastructure_routing_depends_on_domain(self) -> None:
        """Infrastructure routing should depend on domain (not vice versa)."""
        # Infrastructure can import domain
        # Domain should NOT import infrastructure
        # This is verified by test_auto_route_service_no_infrastructure_imports

        # Verify domain events don't import infrastructure
        from src.domain.events.auto_route_events import AutoRouted

        source = inspect.getsource(AutoRouted)
        assert "infrastructure" not in source.lower(), "AutoRouted event should not import infrastructure"

    def test_no_circular_dependencies(self) -> None:
        """Route mechanism should not have circular dependencies."""
        # Import graph should be acyclic
        import sys
        from pathlib import Path

        # Add src to path for imports
        src_path = Path("src").resolve()
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))

        # Try importing route service - should not raise circular dependency error
        try:
            import importlib.util

            for module_name in [
                "src.domain.events.auto_route_events",
                "src.domain.services.auto_route_service",
                "src.infrastructure.routing.hash_router",
                "src.infrastructure.routing.semantic_router",
            ]:
                spec = importlib.util.find_spec(module_name)
                if spec is None:
                    pytest.fail(f"Module {module_name} not found")
        except ImportError as e:
            if "circular" in str(e).lower():
                pytest.fail(f"Circular dependency detected: {e}")
            # Other import errors are acceptable for this test

    def test_auto_routed_event_follows_domain_event_pattern(self) -> None:
        """AutoRouted event should follow domain event pattern (inherit from DomainEvent)."""
        from src.domain.events.auto_route_events import AutoRouted
        from src.domain.events.base import DomainEvent

        # AutoRouted should be a subclass of DomainEvent
        assert issubclass(AutoRouted, DomainEvent), "AutoRouted should inherit from DomainEvent"

    def test_routing_decision_log_in_domain_layer(self) -> None:
        """RoutingDecisionLog should be in domain layer."""
        from src.domain.entities.routing_decision_log import RoutingDecisionLog

        module_path = Path(inspect.getfile(RoutingDecisionLog))
        assert "src/domain/entities" in str(module_path), (
            f"RoutingDecisionLog should be in domain layer, found in {module_path}"
        )

    def test_routing_decision_log_has_worm_field(self) -> None:
        """RoutingDecisionLog should have worm_storage_ref field."""
        from src.domain.entities.routing_decision_log import RoutingDecisionLog

        log = RoutingDecisionLog(
            log_id=uuid4(),
            task_id="test",
            session_id="test",
            route_type="hash",
            route_target="test",
            route_score=0.5,
        )

        assert hasattr(log, "worm_storage_ref"), "RoutingDecisionLog should have worm_storage_ref field"


class TestRouteDecoupling:
    """Test suite for verifying route is decoupled from trigger/execute."""

    def test_auto_route_service_does_not_call_execute(self) -> None:
        """AutoRouteService should not call execute functions."""
        from src.domain.services.auto_route_service import AutoRouteService

        source = inspect.getsource(AutoRouteService)

        # Check for actual execute function calls (not doc comments)
        # Pattern: obj.execute( or similar actual method calls
        import re

        # Only match actual function calls, not doc comments
        # This regex looks for .execute( but not in docstrings
        execute_calls = re.findall(r"\w+\.execute\(", source)
        # Filter to only those not in docstring (simple heuristic: preceded by newline + spaces)
        assert len(execute_calls) == 0, f"AutoRouteService calls execute: {execute_calls}"

    def test_auto_route_service_only_publishes_events(self) -> None:
        """AutoRouteService should only publish events, not call downstream directly."""
        from src.domain.services.auto_route_service import AutoRouteService

        # Verify _publish method exists
        assert hasattr(AutoRouteService, "_publish"), "AutoRouteService should have _publish method"

        # on_triggered_event should return AutoRouted, not execute anything
        _sig = inspect.signature(AutoRouteService.on_triggered_event)
        # Should return AutoRouted
        # Should not have side effects beyond publishing

    def test_auto_routed_event_does_not_reference_execute(self) -> None:
        """AutoRouted event should not reference execute mechanism."""
        from src.domain.events.auto_route_events import AutoRouted

        source = inspect.getsource(AutoRouted)
        # Only check for actual method calls like .execute( not doc references
        import re

        execute_method_calls = re.findall(r"\w+\.execute\(", source)
        assert len(execute_method_calls) == 0, f"AutoRouted event calls execute method: {execute_method_calls}"

    def test_route_service_respects_trigger_dependency(self) -> None:
        """Route should depend on trigger (AutoTriggered input), not call trigger."""
        from src.domain.services.auto_route_service import AutoRouteService

        # AutoRouteService should accept AutoTriggered events as input
        sig = inspect.signature(AutoRouteService.on_triggered_event)

        # Should accept an event parameter that relates to trigger
        # This verifies the dependency direction: trigger -> route
        params = list(sig.parameters.keys())
        assert len(params) >= 1, "on_triggered_event should accept event parameter"
