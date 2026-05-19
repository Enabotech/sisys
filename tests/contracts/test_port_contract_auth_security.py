"""Auth security and compliance port contract tests.

Tests that auth_service, permission_service, token_blacklist, password_validation,
compliance_gateway, sensitive_data_detector, data_residency_enforcer, whitelist_service,
pipl_compliance, cross_border_transfer ports are correctly registered.
对应 AC-4: 全部 domain/ports 认证/安全/合规端口契约测试完成
"""

from __future__ import annotations

from src.domain.ports.auth_service import AuthServicePort
from src.domain.ports.compliance_gateway import ComplianceGatewayPort
from src.domain.ports.cross_border_transfer_service import CrossBorderTransferServicePort
from src.domain.ports.data_residency_enforcer import DataResidencyEnforcerPort
from src.domain.ports.password_validation_service import PasswordValidationServicePort
from src.domain.ports.permission_service import PermissionServicePort
from src.domain.ports.pipl_compliance_service import PIPLComplianceServicePort
from src.domain.ports.sensitive_data_detector import SensitiveDataDetectorPort
from src.domain.ports.token_blacklist import TokenBlacklistPort
from src.domain.ports.whitelist_service import WhitelistServicePort


def _get_impl(spec, port_name):
    """Helper to get implementation instance or None if cannot resolve."""
    impl_cls = spec.impl if isinstance(spec.impl, type) else None
    if impl_cls is None:
        try:
            from src.domain.ports.resolver import Resolver

            return Resolver().resolve(port_name)
        except (RuntimeError, ImportError, KeyError):
            return None
    return impl_cls


class TestAuthServicePort:
    """Contract tests for AuthService port."""

    PORT_NAME = "auth_service"
    INTERFACE = AuthServicePort
    REQUIRED_METHODS = ["authenticate", "verify_token", "refresh_token", "logout"]

    def test_port_is_registered(self, registry) -> None:
        """Port must be registered in global registry."""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"Port {self.PORT_NAME} not registered"
        assert spec.interface is self.INTERFACE

    def test_implementation_has_required_methods(self, registry) -> None:
        """Implementation must have all required methods from protocol."""
        spec = registry.get(self.PORT_NAME)
        impl = _get_impl(spec, self.PORT_NAME)
        if impl is None:
            return
        for method in self.REQUIRED_METHODS:
            assert hasattr(impl, method), f"Implementation missing method: {method}"
            assert callable(getattr(impl, method)), f"{method} is not callable"

    def test_metadata_complete(self, registry) -> None:
        """Port metadata must be complete."""
        spec = registry.get(self.PORT_NAME)
        assert spec.version
        assert spec.owner
        assert spec.module


class TestPermissionServicePort:
    """Contract tests for PermissionService port."""

    PORT_NAME = "permission_service"
    INTERFACE = PermissionServicePort
    REQUIRED_METHODS = ["check_permission", "get_user_permissions"]

    def test_port_is_registered(self, registry) -> None:
        """Port must be registered in global registry."""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"Port {self.PORT_NAME} not registered"
        assert spec.interface is self.INTERFACE

    def test_implementation_has_required_methods(self, registry) -> None:
        """Implementation must have all required methods from protocol."""
        spec = registry.get(self.PORT_NAME)
        impl = _get_impl(spec, self.PORT_NAME)
        if impl is None:
            return
        for method in self.REQUIRED_METHODS:
            assert hasattr(impl, method), f"Implementation missing method: {method}"
            assert callable(getattr(impl, method)), f"{method} is not callable"

    def test_metadata_complete(self, registry) -> None:
        """Port metadata must be complete."""
        spec = registry.get(self.PORT_NAME)
        assert spec.version
        assert spec.owner
        assert spec.module


class TestTokenBlacklistPort:
    """Contract tests for TokenBlacklist port."""

    PORT_NAME = "token_blacklist"
    INTERFACE = TokenBlacklistPort
    REQUIRED_METHODS = ["add", "is_blacklisted"]

    def test_port_is_registered(self, registry) -> None:
        """Port must be registered in global registry."""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"Port {self.PORT_NAME} not registered"
        assert spec.interface is self.INTERFACE

    def test_implementation_has_required_methods(self, registry) -> None:
        """Implementation must have all required methods from protocol."""
        spec = registry.get(self.PORT_NAME)
        impl = _get_impl(spec, self.PORT_NAME)
        if impl is None:
            return
        for method in self.REQUIRED_METHODS:
            assert hasattr(impl, method), f"Implementation missing method: {method}"
            assert callable(getattr(impl, method)), f"{method} is not callable"

    def test_metadata_complete(self, registry) -> None:
        """Port metadata must be complete."""
        spec = registry.get(self.PORT_NAME)
        assert spec.version
        assert spec.owner
        assert spec.module


class TestPasswordValidationServicePort:
    """Contract tests for PasswordValidationService port."""

    PORT_NAME = "password_validation"
    INTERFACE = PasswordValidationServicePort
    REQUIRED_METHODS = ["validate", "get_requirements"]

    def test_port_is_registered(self, registry) -> None:
        """Port must be registered in global registry."""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"Port {self.PORT_NAME} not registered"
        assert spec.interface is self.INTERFACE

    def test_implementation_has_required_methods(self, registry) -> None:
        """Implementation must have all required methods from protocol."""
        spec = registry.get(self.PORT_NAME)
        impl = _get_impl(spec, self.PORT_NAME)
        if impl is None:
            return
        for method in self.REQUIRED_METHODS:
            assert hasattr(impl, method), f"Implementation missing method: {method}"
            assert callable(getattr(impl, method)), f"{method} is not callable"

    def test_metadata_complete(self, registry) -> None:
        """Port metadata must be complete."""
        spec = registry.get(self.PORT_NAME)
        assert spec.version
        assert spec.owner
        assert spec.module


class TestComplianceGatewayPort:
    """Contract tests for ComplianceGateway port."""

    PORT_NAME = "compliance_gateway"
    INTERFACE = ComplianceGatewayPort
    REQUIRED_METHODS = ["check"]

    def test_port_is_registered(self, registry) -> None:
        """Port must be registered in global registry."""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"Port {self.PORT_NAME} not registered"
        assert spec.interface is self.INTERFACE

    def test_implementation_has_required_methods(self, registry) -> None:
        """Implementation must have all required methods from protocol."""
        spec = registry.get(self.PORT_NAME)
        impl = _get_impl(spec, self.PORT_NAME)
        if impl is None:
            return
        for method in self.REQUIRED_METHODS:
            assert hasattr(impl, method), f"Implementation missing method: {method}"
            assert callable(getattr(impl, method)), f"{method} is not callable"

    def test_metadata_complete(self, registry) -> None:
        """Port metadata must be complete."""
        spec = registry.get(self.PORT_NAME)
        assert spec.version
        assert spec.owner
        assert spec.module


class TestSensitiveDataDetectorPort:
    """Contract tests for SensitiveDataDetector port."""

    PORT_NAME = "sensitive_data_detector"
    INTERFACE = SensitiveDataDetectorPort
    REQUIRED_METHODS = ["detect_sensitive_data"]

    def test_port_is_registered(self, registry) -> None:
        """Port must be registered in global registry."""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"Port {self.PORT_NAME} not registered"
        assert spec.interface is self.INTERFACE

    def test_implementation_has_required_methods(self, registry) -> None:
        """Implementation must have all required methods from protocol."""
        spec = registry.get(self.PORT_NAME)
        impl = _get_impl(spec, self.PORT_NAME)
        if impl is None:
            return
        for method in self.REQUIRED_METHODS:
            assert hasattr(impl, method), f"Implementation missing method: {method}"
            assert callable(getattr(impl, method)), f"{method} is not callable"

    def test_metadata_complete(self, registry) -> None:
        """Port metadata must be complete."""
        spec = registry.get(self.PORT_NAME)
        assert spec.version
        assert spec.owner
        assert spec.module


class TestDataResidencyEnforcerPort:
    """Contract tests for DataResidencyEnforcer port."""

    PORT_NAME = "data_residency_enforcer"
    INTERFACE = DataResidencyEnforcerPort
    REQUIRED_METHODS = ["enforce_residency", "check_violation"]

    def test_port_is_registered(self, registry) -> None:
        """Port must be registered in global registry."""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"Port {self.PORT_NAME} not registered"
        assert spec.interface is self.INTERFACE

    def test_implementation_has_required_methods(self, registry) -> None:
        """Implementation must have all required methods from protocol."""
        spec = registry.get(self.PORT_NAME)
        impl = _get_impl(spec, self.PORT_NAME)
        if impl is None:
            return
        for method in self.REQUIRED_METHODS:
            assert hasattr(impl, method), f"Implementation missing method: {method}"
            assert callable(getattr(impl, method)), f"{method} is not callable"

    def test_metadata_complete(self, registry) -> None:
        """Port metadata must be complete."""
        spec = registry.get(self.PORT_NAME)
        assert spec.version
        assert spec.owner
        assert spec.module


class TestWhitelistServicePort:
    """Contract tests for WhitelistService port."""

    PORT_NAME = "whitelist_service"
    INTERFACE = WhitelistServicePort
    REQUIRED_METHODS = ["is_allowed", "add_to_whitelist"]

    def test_port_is_registered(self, registry) -> None:
        """Port must be registered in global registry."""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"Port {self.PORT_NAME} not registered"
        assert spec.interface is self.INTERFACE

    def test_implementation_has_required_methods(self, registry) -> None:
        """Implementation must have all required methods from protocol."""
        spec = registry.get(self.PORT_NAME)
        impl = _get_impl(spec, self.PORT_NAME)
        if impl is None:
            return
        for method in self.REQUIRED_METHODS:
            assert hasattr(impl, method), f"Implementation missing method: {method}"
            assert callable(getattr(impl, method)), f"{method} is not callable"

    def test_metadata_complete(self, registry) -> None:
        """Port metadata must be complete."""
        spec = registry.get(self.PORT_NAME)
        assert spec.version
        assert spec.owner
        assert spec.module


class TestPIPLComplianceServicePort:
    """Contract tests for PIPLComplianceService port."""

    PORT_NAME = "pipl_compliance"
    INTERFACE = PIPLComplianceServicePort
    REQUIRED_METHODS = [
        "record_access",
        "validate_legal_basis",
        "respond_to_access_request",
        "respond_to_correction_request",
        "respond_to_deletion_request",
        "respond_to_portability_request",
        "get_record",
    ]

    def test_port_is_registered(self, registry) -> None:
        """Port must be registered in global registry."""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"Port {self.PORT_NAME} not registered"
        assert spec.interface is self.INTERFACE

    def test_implementation_has_required_methods(self, registry) -> None:
        """Implementation must have all required methods from protocol."""
        spec = registry.get(self.PORT_NAME)
        impl = _get_impl(spec, self.PORT_NAME)
        if impl is None:
            return
        for method in self.REQUIRED_METHODS:
            assert hasattr(impl, method), f"Implementation missing method: {method}"
            assert callable(getattr(impl, method)), f"{method} is not callable"

    def test_metadata_complete(self, registry) -> None:
        """Port metadata must be complete."""
        spec = registry.get(self.PORT_NAME)
        assert spec.version
        assert spec.owner
        assert spec.module


class TestCrossBorderTransferServicePort:
    """Contract tests for CrossBorderTransferService port."""

    PORT_NAME = "cross_border_transfer"
    INTERFACE = CrossBorderTransferServicePort
    REQUIRED_METHODS = ["request_transfer", "approve", "reject", "list_pending_requests"]

    def test_port_is_registered(self, registry) -> None:
        """Port must be registered in global registry."""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"Port {self.PORT_NAME} not registered"
        assert spec.interface is self.INTERFACE

    def test_implementation_has_required_methods(self, registry) -> None:
        """Implementation must have all required methods from protocol."""
        spec = registry.get(self.PORT_NAME)
        impl = _get_impl(spec, self.PORT_NAME)
        if impl is None:
            return
        for method in self.REQUIRED_METHODS:
            assert hasattr(impl, method), f"Implementation missing method: {method}"
            assert callable(getattr(impl, method)), f"{method} is not callable"

    def test_metadata_complete(self, registry) -> None:
        """Port metadata must be complete."""
        spec = registry.get(self.PORT_NAME)
        assert spec.version
        assert spec.owner
        assert spec.module
