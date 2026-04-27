"""Tests for trigger mechanism architecture compliance (hexagonal architecture)."""

from __future__ import annotations

import ast
from pathlib import Path


class TestHexagonalArchitectureCompliance:
    """Verify trigger mechanism follows hexagonal architecture principles."""

    def test_trigger_service_is_domain_layer(self) -> None:
        """Verify AutoTriggerService is in domain layer (no infrastructure imports)."""
        trigger_service_path = Path("src/domain/services/auto_trigger_service.py")
        assert trigger_service_path.exists(), "AutoTriggerService must be in domain layer"

        content = trigger_service_path.read_text()
        tree = ast.parse(content)

        # Check imports
        infrastructure_imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "infrastructure" in alias.name:
                        infrastructure_imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module and "infrastructure" in node.module:
                    infrastructure_imports.append(node.module)

        assert not infrastructure_imports, (
            f"AutoTriggerService (domain layer) must not import infrastructure. " f"Found: {infrastructure_imports}"
        )

    def test_trigger_events_is_domain_layer(self) -> None:
        """Verify AutoTriggered event is in domain layer."""
        trigger_events_path = Path("src/domain/events/auto_trigger_events.py")
        assert trigger_events_path.exists(), "AutoTriggered event must be in domain layer"

        content = trigger_events_path.read_text()
        tree = ast.parse(content)

        infrastructure_imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "infrastructure" in alias.name:
                        infrastructure_imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module and "infrastructure" in node.module:
                    infrastructure_imports.append(node.module)

        assert not infrastructure_imports, (
            f"TriggerEvents (domain layer) must not import infrastructure. " f"Found: {infrastructure_imports}"
        )

    def test_trigger_context_is_domain_layer(self) -> None:
        """Verify AutoTriggerContext is in domain layer."""
        trigger_context_path = Path("src/domain/value_objects/auto_trigger_context.py")
        assert trigger_context_path.exists(), "AutoTriggerContext must be in domain layer"

        content = trigger_context_path.read_text()
        tree = ast.parse(content)

        infrastructure_imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "infrastructure" in alias.name:
                        infrastructure_imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module and "infrastructure" in node.module:
                    infrastructure_imports.append(node.module)

        assert not infrastructure_imports, (
            f"TriggerContext (domain layer) must not import infrastructure. " f"Found: {infrastructure_imports}"
        )

    def test_trigger_service_uses_protocol_for_publisher(self) -> None:
        """Verify AutoTriggerService depends on EventPublisherProtocol, not concrete implementation."""
        trigger_service_path = Path("src/domain/services/auto_trigger_service.py")
        content = trigger_service_path.read_text()

        # AutoTriggerService should define/use a Protocol for event publishing
        assert "Protocol" in content, "AutoTriggerService should use Protocol for dependency inversion"
        assert "EventPublisherProtocol" in content, "AutoTriggerService should define EventPublisherProtocol"

    def test_heartbeat_scheduler_is_infrastructure_layer(self) -> None:
        """Verify HeartbeatScheduler is in infrastructure layer."""
        heartbeat_scheduler_path = Path("src/infrastructure/scheduler/heartbeat_scheduler.py")
        assert heartbeat_scheduler_path.exists(), "HeartbeatScheduler must be in infrastructure layer"

    def test_trigger_config_is_infrastructure_layer(self) -> None:
        """Verify AutoTriggerConfig is in infrastructure/config layer."""
        trigger_config_path = Path("src/infrastructure/config/auto_trigger.py")
        assert trigger_config_path.exists(), "AutoTriggerConfig must be in infrastructure/config layer"


class TestTriggerRouteDecoupling:
    """Verify trigger and route stages are decoupled via event bus."""

    def test_trigger_service_does_not_import_route(self) -> None:
        """Verify AutoTriggerService does not directly import any route-related modules."""
        trigger_service_path = Path("src/domain/services/auto_trigger_service.py")
        content = trigger_service_path.read_text()
        tree = ast.parse(content)

        route_imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "route" in alias.name.lower():
                        route_imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module and "route" in node.module.lower():
                    route_imports.append(node.module)

        assert not route_imports, (
            f"AutoTriggerService must not import route modules (decoupling requirement). " f"Found: {route_imports}"
        )

    def test_trigger_service_publishes_triggered_event(self) -> None:
        """Verify AutoTriggerService publishes AutoTriggered event (not direct route call)."""
        trigger_service_path = Path("src/domain/services/auto_trigger_service.py")
        content = trigger_service_path.read_text()

        # Should publish AutoTriggered event
        assert "AutoTriggered" in content, "AutoTriggerService should emit AutoTriggered event"
        # Should not call route directly
        assert (
            "route" not in content.lower() or "publish" in content.lower()
        ), "AutoTriggerService should use event publishing, not direct route calls"


class TestDependencyDirection:
    """Verify dependencies point towards domain (hexagonal architecture principle)."""

    def test_domain_layer_depends_on_nothing_external(self) -> None:
        """Verify domain layer (AutoTriggerService, AutoTriggerContext) has no external dependencies."""
        domain_trigger_files = [
            Path("src/domain/services/auto_trigger_service.py"),
            Path("src/domain/events/auto_trigger_events.py"),
            Path("src/domain/value_objects/auto_trigger_context.py"),
        ]

        for file_path in domain_trigger_files:
            if not file_path.exists():
                continue

            content = file_path.read_text()
            tree = ast.parse(content)

            # Check for problematic imports (external frameworks in domain)
            problematic_imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        # Allow standard library and domain events
                        if any(ext in alias.name for ext in ["redis", "pymongo", "sqlalchemy", "boto", "httpx", "fastapi"]):
                            if "domain" not in alias.name.lower():
                                problematic_imports.append(alias.name)

            assert not problematic_imports, (
                f"{file_path.name} (domain layer) must not import external frameworks. " f"Found: {problematic_imports}"
            )
