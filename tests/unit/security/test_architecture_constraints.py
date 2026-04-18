"""Tests for Architecture Constraints - Domain layer zero external dependencies.

Verifies that the domain layer has no imports from infrastructure or external packages.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path


class TestArchitectureConstraints:
    """Architecture constraint tests for RBAC implementation."""

    def test_domain_services_no_infrastructure_imports(self):
        """Domain services should not import from infrastructure layer."""
        domain_services_path = Path("src/domain/services")

        forbidden_imports = [
            "src.infrastructure",
            "src.interfaces",
            "infrastructure",
            "interfaces",
        ]

        violations = []

        for py_file in domain_services_path.glob("*.py"):
            if py_file.name == "__init__.py":
                continue

            content = py_file.read_text()
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        for forbidden in forbidden_imports:
                            if alias.name.startswith(forbidden):
                                violations.append(f"{py_file.name}: imports {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        for forbidden in forbidden_imports:
                            if node.module.startswith(forbidden):
                                violations.append(f"{py_file.name}: from {node.module} import ...")

        assert len(violations) == 0, f"Domain layer has infrastructure imports: {violations}"

    def test_domain_services_no_external_dependencies(self):
        """Domain services should only use Python standard library."""
        domain_services_path = Path("src/domain/services")

        forbidden_patterns = [
            "src.infrastructure",
            "src.interfaces",
            "passlib",
            "bcrypt",
            "jwt",
            "jose",
            "fastapi",
            "sqlalchemy",
            "asyncpg",
        ]

        violations = []

        for py_file in domain_services_path.glob("*.py"):
            if py_file.name == "__init__.py":
                continue

            content = py_file.read_text()

            for pattern in forbidden_patterns:
                if pattern in content:
                    violations.append(f"{py_file.name}: contains '{pattern}'")

        assert len(violations) == 0, f"Domain layer has external dependencies: {violations}"

    def test_security_models_in_infrastructure_layer(self):
        """Security models (Role, Permission, User) should be in infrastructure layer."""
        # Check that security models are NOT in domain layer
        domain_models_path = Path("src/domain")

        # These should NOT exist in domain layer
        forbidden_files = [
            "role.py",
            "permission.py",
            "user.py",
        ]

        violations = []

        for root, dirs, files in os.walk(domain_models_path):
            for file in files:
                if file in forbidden_files:
                    violations.append(str(Path(root) / file))

        assert len(violations) == 0, f"Security models found in domain layer: {violations}"

    def test_security_services_protocol_in_domain(self):
        """AuthService and PermissionService protocols should be in domain layer."""
        auth_service_path = Path("src/domain/services/auth_service.py")
        permission_service_path = Path("src/domain/services/permission_service.py")

        assert auth_service_path.exists(), "auth_service.py should exist in domain services"
        assert permission_service_path.exists(), "permission_service.py should exist in domain services"

        # Check they define Protocol classes
        auth_content = auth_service_path.read_text()
        permission_content = permission_service_path.read_text()

        assert "Protocol" in auth_content, "auth_service.py should define Protocol"
        assert "Protocol" in permission_content, "permission_service.py should define Protocol"

    def test_security_implementations_in_infrastructure(self):
        """Security implementations should be in infrastructure layer."""
        security_path = Path("src/infrastructure/security")

        assert security_path.exists(), "Security implementations should be in infrastructure/security"

        # Check for expected implementation files
        expected_files = [
            "auth_service.py",
            "jwt_service.py",
            "role_service.py",
            "permission_service.py",
            "permission_middleware.py",
            "encryption_service.py",
        ]

        for filename in expected_files:
            file_path = security_path / filename
            assert file_path.exists(), f"{filename} should exist in infrastructure/security"


class TestRBACModels:
    """Test RBAC model relationships."""

    def test_permission_string_format(self):
        """Permission should follow resource:action format."""
        from src.infrastructure.security.models import Permission

        perm = Permission.from_string("document:read")

        assert perm.resource == "document"
        assert perm.action == "read"
        assert perm.permission_string == "document:read"

    def test_role_wildcard_permission(self):
        """Role with *:* should match any permission."""
        from src.infrastructure.security.models import Role

        role = Role(id=None, name="admin", permissions=["*:*"])

        assert role.has_permission("anything", "any_action") is True

    def test_role_resource_wildcard(self):
        """Role with resource:* should match any action on that resource."""
        from src.infrastructure.security.models import Role

        role = Role(id=None, name="doc_admin", permissions=["document:*"])

        assert role.has_permission("document", "read") is True
        assert role.has_permission("document", "write") is True
        assert role.has_permission("document", "delete") is True
        assert role.has_permission("other", "read") is False

    def test_user_account_locking(self):
        """User should be lockable after failed login attempts."""
        from src.infrastructure.security.models import User

        user = User(id=None, username="test", email="test@test.com")

        assert user.is_locked() is False

        user.lock_account(30)

        assert user.is_locked() is True
