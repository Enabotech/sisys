"""Tests for SDD Architecture Constraints.

Verifies that architecture constraints are respected:
- Domain layer has zero dependencies on external frameworks
- No circular dependencies
- Security services are in infrastructure layer only

Reference: Story 1.11 Data Sovereignty Isolation - Task 7.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


def _has_cycle(
    node: str,
    dependencies: dict[str, set[str]],
    visited: set[str],
    rec_stack: set[str],
) -> bool:
    """Check for cycle using DFS. Extracted to module level to satisfy mypy."""
    visited.add(node)
    rec_stack.add(node)

    for neighbor in dependencies.get(node, set()):
        if neighbor not in visited:
            if _has_cycle(neighbor, dependencies, visited, rec_stack):
                return True
        elif neighbor in rec_stack:
            return True

    rec_stack.remove(node)
    return False


class TestArchitectureConstraints:
    """Architecture constraint validation tests."""

    @pytest.fixture
    def src_root(self) -> Path:
        """Get src directory path."""
        return Path(__file__).parents[3] / "src"

    def test_domain_events_no_pydantic(self, src_root):
        """Domain events should not import pydantic."""
        domain_events_path = src_root / "domain" / "events"

        if not domain_events_path.exists():
            pytest.skip("Domain events directory not found")

        violations = []
        for py_file in domain_events_path.rglob("*.py"):
            with open(py_file, encoding="utf-8") as f:
                content = f.read()
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if "pydantic" in alias.name:
                                violations.append(f"{py_file.name}: imports pydantic")
                    elif isinstance(node, ast.ImportFrom):
                        if node.module and "pydantic" in node.module:
                            violations.append(f"{py_file.name}: from pydantic import")

        assert violations == [], f"Pydantic imports found in domain layer: {violations}"

    def test_domain_events_no_external_dependencies(self, src_root):
        """Domain events should only use Python standard library."""
        domain_events_path = src_root / "domain" / "events"

        if not domain_events_path.exists():
            pytest.skip("Domain events directory not found")

        violations = []
        external_modules = {"fastapi", "sqlalchemy", "redis", "pydantic", "numpy", "pandas"}

        for py_file in domain_events_path.rglob("*.py"):
            with open(py_file, encoding="utf-8") as f:
                content = f.read()
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            module_name = alias.name.split(".")[0]
                            if module_name in external_modules:
                                violations.append(f"{py_file.name}: imports {module_name}")
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            module_name = node.module.split(".")[0]
                            if module_name in external_modules:
                                violations.append(f"{py_file.name}: from {module_name} import")

        assert violations == [], f"External dependencies in domain layer: {violations}"

    def test_security_services_in_infrastructure_only(self, src_root):
        """Security services must be in infrastructure layer."""
        # Security-related files should be in infrastructure/security/
        domain_services_path = src_root / "domain" / "services"
        infrastructure_security_path = src_root / "infrastructure" / "security"

        if not infrastructure_security_path.exists():
            pytest.skip("Infrastructure security directory not found")

        # Check that sensitive data detector, whitelist service, etc. are NOT in domain
        forbidden_in_domain = [
            "sensitive_data_detector",
            "whitelist_service",
            "approval_workflow",
            "pipl_compliance",
            "data_sovereignty_service",
        ]

        violations = []
        if domain_services_path.exists():
            for py_file in domain_services_path.rglob("*.py"):
                for forbidden in forbidden_in_domain:
                    if forbidden in py_file.name:
                        violations.append(f"{py_file.name} should not be in domain/services")

        assert violations == [], f"Security services found in domain layer: {violations}"

    def test_no_circular_dependencies_in_security(self, src_root) -> None:
        """Security module should not have circular dependencies."""
        infrastructure_security_path = src_root / "infrastructure" / "security"

        if not infrastructure_security_path.exists():
            pytest.skip("Infrastructure security directory not found")

        # Build dependency graph
        dependencies: dict[str, set[str]] = {}

        for py_file in infrastructure_security_path.rglob("*.py"):
            if py_file.name.startswith("__"):
                continue

            module_name = py_file.stem
            dependencies[module_name] = set()

            with open(py_file, encoding="utf-8") as f:
                content = f.read()
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom):
                        if node.module:
                            # Check if it's a local import
                            if "infrastructure.security" in node.module or node.module.startswith("."):
                                for alias in node.names:
                                    dep_name = alias.name
                                    if dep_name in dependencies:
                                        dependencies[module_name].add(dep_name)

        visited: set[str] = set()
        for module in dependencies:
            if module not in visited:
                if _has_cycle(module, dependencies, visited, set()):
                    pytest.fail(f"Circular dependency detected involving {module}")

    def test_infrastructure_security_imports(self, src_root):
        """Infrastructure security should not import from interfaces layer."""
        infrastructure_security_path = src_root / "infrastructure" / "security"

        if not infrastructure_security_path.exists():
            pytest.skip("Infrastructure security directory not found")

        violations = []
        for py_file in infrastructure_security_path.rglob("*.py"):
            if py_file.name.startswith("__"):
                continue

            with open(py_file, encoding="utf-8") as f:
                content = f.read()
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom):
                        if node.module and "interfaces" in node.module:
                            violations.append(f"{py_file.name}: imports from {node.module}")

        assert violations == [], f"Infrastructure security should not import from interfaces: {violations}"

    def test_compliance_events_uses_domain_base(self, src_root):
        """Compliance events should inherit from domain base."""
        compliance_events_path = src_root / "domain" / "events" / "compliance_events.py"

        if not compliance_events_path.exists():
            pytest.skip("compliance_events.py not found")

        with open(compliance_events_path, encoding="utf-8") as f:
            content = f.read()

        # Should import from base
        assert "from .base import DomainEvent" in content or "from domain.events.base import DomainEvent" in content

        # Should inherit from DomainEvent
        assert "DomainEvent" in content


class TestComplianceEventsSchema:
    """Tests for compliance events schema validation."""

    def test_sensitive_data_detected_event_fields(self):
        """SensitiveDataDetected event should have required fields."""
        from src.domain.events.base import DomainEvent
        from src.domain.events.compliance_events import SensitiveDataDetected, SensitiveType

        event = SensitiveDataDetected(
            data_id=__import__("uuid").uuid4(),
            sensitive_type=SensitiveType.PII,
            confidence=0.95,
        )

        # Should inherit from DomainEvent
        assert isinstance(event, DomainEvent)

        # Should have required fields
        assert hasattr(event, "data_id")
        assert hasattr(event, "sensitive_type")
        assert hasattr(event, "confidence")
        assert hasattr(event, "event_type")

    def test_cross_border_transfer_requested_event_fields(self):
        """CrossBorderTransferRequested event should have required fields."""
        from src.domain.events.base import DomainEvent
        from src.domain.events.compliance_events import CrossBorderTransferRequested

        event = CrossBorderTransferRequested(
            request_id=__import__("uuid").uuid4(),
            data_id=__import__("uuid").uuid4(),
            destination="US",
            purpose="International collaboration",
        )

        # Should inherit from DomainEvent
        assert isinstance(event, DomainEvent)

        # Should have required fields
        assert hasattr(event, "request_id")
        assert hasattr(event, "data_id")
        assert hasattr(event, "destination")
        assert hasattr(event, "purpose")
        assert hasattr(event, "status")

    def test_data_sovereignty_violation_event_fields(self):
        """DataSovereigntyViolation event should have required fields."""
        from src.domain.events.base import DomainEvent
        from src.domain.events.compliance_events import DataSovereigntyViolation

        event = DataSovereigntyViolation(
            violation_id=__import__("uuid").uuid4(),
            data_id=__import__("uuid").uuid4(),
            violation_type="unauthorized_transfer",
            severity="high",
        )

        # Should inherit from DomainEvent
        assert isinstance(event, DomainEvent)

        # Should have required fields
        assert hasattr(event, "violation_id")
        assert hasattr(event, "data_id")
        assert hasattr(event, "violation_type")
        assert hasattr(event, "severity")

    def test_pipl_data_access_requested_event_fields(self):
        """PIPLDataAccessRequested event should have required fields."""
        from src.domain.events.base import DomainEvent
        from src.domain.events.compliance_events import PIPLDataAccessRequested

        event = PIPLDataAccessRequested(
            access_id=__import__("uuid").uuid4(),
            personal_data_id=__import__("uuid").uuid4(),
            purpose="user_authentication",
            legal_basis="consent",
        )

        # Should inherit from DomainEvent
        assert isinstance(event, DomainEvent)

        # Should have required fields
        assert hasattr(event, "access_id")
        assert hasattr(event, "personal_data_id")
        assert hasattr(event, "purpose")
        assert hasattr(event, "legal_basis")
        assert hasattr(event, "data_subject_consent")
