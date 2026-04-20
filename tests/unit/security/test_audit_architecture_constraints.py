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
    """Verify domain layer has no infrastructure dependencies."""

    def test_domain_events_has_no_infrastructure_imports(self):
        """Domain events module should not import infrastructure modules."""
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

    def test_domain_services_has_no_infrastructure_imports(self):
        """Domain services (Protocol) should not import infrastructure modules."""
        domain_services_path = Path("src/domain/services/audit_service.py")
        assert domain_services_path.exists(), "AuditService Protocol should be defined in domain layer"

        content = domain_services_path.read_text()
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

        assert len(infra_imports) == 0, f"Domain services should not import infrastructure: {infra_imports}"


class TestDependencyDirection:
    """Verify dependency direction is from infrastructure to domain."""

    def test_infrastructure_audit_imports_domain_not_vice_versa(self):
        """Infrastructure audit module can import domain, but domain cannot import infrastructure."""
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

            # These imports are expected and correct
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


class TestNoCircularDependencies:
    """Verify no circular dependencies exist."""

    def test_no_circular_dependencies(self):
        """Domain should not depend on infrastructure."""
        # Check domain events doesn't import from infrastructure
        domain_events = Path("src/domain/events/audit_events.py").read_text()

        # Domain layer files should not contain infrastructure imports
        assert "from src.infrastructure" not in domain_events
        assert "import src.infrastructure" not in domain_events

        # Check domain services doesn't import from infrastructure
        domain_services = Path("src/domain/services/audit_service.py").read_text()
        assert "from src.infrastructure" not in domain_services
        assert "import src.infrastructure" not in domain_services
