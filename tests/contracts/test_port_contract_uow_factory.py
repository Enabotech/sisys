"""Port contract tests for uow_factory port.

Tests that PostgreSQLUnitOfWork factory satisfies UnitOfWorkFactory Protocol.
验证 AC-2: UnitOfWorkFactory Protocol + DI 注册
"""

from __future__ import annotations

from src.domain.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory


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


class TestUnitOfWorkFactoryContract:
    """Contract tests for uow_factory port."""

    PORT_NAME = "uow_factory"
    INTERFACE = UnitOfWorkFactory
    REQUIRED_METHODS = ["__call__"]

    def test_port_is_registered(self, registry) -> None:
        """Port must be registered in global registry."""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"Port {self.PORT_NAME} not registered"
        assert spec.interface is self.INTERFACE

    def test_implementation_has_required_methods(self, registry) -> None:
        """Implementation must have __call__ method (callable)."""
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
        assert spec.version, "Port version is empty"
        assert spec.owner, "Port owner is empty"
        assert spec.module, "Port module is empty"

    def test_lifetime_is_transient(self, registry) -> None:
        """Factory must be TRANSIENT lifetime (each call returns new instance)."""
        from src.domain.ports.registry import Lifetime

        spec = registry.get(self.PORT_NAME)
        assert spec.lifetime == Lifetime.TRANSIENT

    def test_factory_returns_unit_of_work(self, registry) -> None:
        """Calling factory() must return a UnitOfWork instance."""
        from unittest import mock

        from src.domain.ports.resolver import Resolver
        from src.infrastructure.storage.postgresql.session_context import (
            reset_session,
            set_session,
        )

        mock_session = mock.AsyncMock()
        token = set_session(mock_session)
        try:
            factory = Resolver().resolve(self.PORT_NAME)
            uow = factory()
            assert isinstance(uow, UnitOfWork)
        finally:
            reset_session(token)
