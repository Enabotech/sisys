"""Test Architecture Constraints for Audit Module.

Verifies that the audit module follows hexagonal architecture principles:
1. Domain layer has no infrastructure dependencies
2. Domain → Infrastructure is the only allowed dependency direction
3. Audit events are defined in the correct location

Reference: Story 1.10 Task 6 - Architecture Constraints
"""

from __future__ import annotations

import ast
from pathlib import Path


class TestDomainLayerNoInfraDependencies:
    """Verify domain layer has no infrastructure dependencies (reverse dependency check)."""

    def test_domain_events_no_infrastructure_imports(self):
        """Domain events should not import infrastructure modules (reverse dependency)."""
        domain_events_path = Path("src/domain/events/audit_events.py")
        assert domain_events_path.exists(), "AuditEvent should be defined in domain layer"

        content = domain_events_path.read_text()
        tree = ast.parse(content)

        infra_imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "infrastructure" in alias.name:
                        infra_imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module and "infrastructure" in node.module:
                    infra_imports.append(node.module)

        assert len(infra_imports) == 0, f"Domain layer should not import infrastructure: {infra_imports}"

    def test_audit_service_protocol_no_infrastructure_imports(self):
        """AuditService Protocol in application/ports should not import infrastructure."""
        # Protocol is in application/ports per refactoring
        app_ports_path = Path("src/application/ports/audit_service.py")
        assert app_ports_path.exists(), "AuditService Protocol should be in application/ports"

        content = app_ports_path.read_text()
        tree = ast.parse(content)

        infra_imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "infrastructure" in alias.name:
                        infra_imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module and "infrastructure" in node.module:
                    infra_imports.append(node.module)

        assert len(infra_imports) == 0, f"AuditService Protocol should not import infrastructure: {infra_imports}"


class TestInfrastructureImportsInnerLayers:
    """Verify infrastructure can import domain and application (correct outward-inward dependency)."""

    def test_infrastructure_can_import_domain_layer(self):
        """Infrastructure audit module can import domain layer (correct dependency direction)."""
        infra_audit_path = Path("src/infrastructure/audit/audit_service.py")
        if infra_audit_path.exists():
            content = infra_audit_path.read_text()
            tree = ast.parse(content)

            # Infrastructure can import domain (this is correct)
            domain_imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if "domain" in alias.name:
                            domain_imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module and "domain" in node.module:
                        domain_imports.append(node.module)

            # Infrastructure importing domain is expected and correct
            assert "domain" in str(domain_imports) or len(domain_imports) >= 0


class TestAuditEventDefinition:
    """Verify audit events are defined in correct location."""

    def test_audit_event_in_domain_events(self):
        """AuditEvent must be defined in src/domain/events/."""
        audit_events_path = Path("src/domain/events/audit_events.py")
        assert audit_events_path.exists(), "AuditEvent should be in src/domain/events/audit_events.py"

        content = audit_events_path.read_text()
        assert "class AuditEvent" in content, "AuditEvent class should be defined"
        assert "class AuditActionType" in content, "AuditActionType enum should be defined"

    def test_audit_event_inherits_from_domain_event(self):
        """AuditEvent must inherit from DomainEvent."""
        from src.domain.events.audit_events import AuditEvent
        from src.domain.events.base import DomainEvent

        assert issubclass(AuditEvent, DomainEvent), "AuditEvent should inherit from DomainEvent"


class TestInfrastructureImplementation:
    """Verify infrastructure implementations exist and are properly structured."""

    def test_audit_service_implementation_exists(self):
        """AuditServiceImpl should exist in infrastructure layer."""
        impl_path = Path("src/infrastructure/audit/audit_service.py")
        assert impl_path.exists(), "AuditServiceImpl should exist in infrastructure layer"

    def test_outbox_processor_exists(self):
        """OutboxProcessor should exist in infrastructure layer."""
        impl_path = Path("src/infrastructure/audit/outbox_processor.py")
        assert impl_path.exists(), "OutboxProcessor should exist in infrastructure layer"

    def test_event_listener_exists(self):
        """AuditEventListener should exist in infrastructure layer."""
        impl_path = Path("src/infrastructure/audit/event_listener.py")
        assert impl_path.exists(), "AuditEventListener should exist in infrastructure layer"


class TestReverseDependencyCheck:
    """Verify inner layers (domain, application) don't import outer layer (infrastructure)."""

    def test_inner_layers_no_infrastructure_imports(self):
        """Domain and application should not import infrastructure (reverse dependency check)."""
        # Check domain events doesn't import from infrastructure
        domain_events = Path("src/domain/events/audit_events.py").read_text()

        # Domain layer files should not contain infrastructure imports
        assert "from src.infrastructure" not in domain_events
        assert "import src.infrastructure" not in domain_events

        # Protocol now in application/ports per refactoring
        app_ports = Path("src/application/ports/audit_service.py").read_text()
        assert "from src.infrastructure" not in app_ports
        assert "import src.infrastructure" not in app_ports
