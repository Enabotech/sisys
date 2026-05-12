"""Contract gate — port compatibility checking and contract testing.

This module provides the ContractGate class for checking port compatibility
and the PortContractTest base class for contract testing.
"""

from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass
from typing import Any, Type

from src.domain.ports.registry import PortSpec

logger = logging.getLogger(__name__)


@dataclass
class CompatibilityResult:
    """Result of compatibility check between two port versions."""

    port_name: str
    old_version: str
    new_version: str
    is_compatible: bool
    breaking_changes: list[str]
    warnings: list[str]


class ContractGate:
    """Contract compatibility checker.

    Checks port changes for compatibility to ensure upgrades don't break
    existing functionality.
    """

    def check_compatibility(
        self,
        old_spec: PortSpec,
        new_spec: PortSpec,
    ) -> CompatibilityResult:
        """Check compatibility between old and new port specifications.

        Args:
            old_spec: Previous version specification
            new_spec: New version specification

        Returns:
            Compatibility result with breaking changes and warnings
        """
        breaking_changes = []
        warnings = []

        # Check interface changes
        if old_spec.interface is not new_spec.interface:
            old_methods = self._get_methods(old_spec.interface)
            new_methods = self._get_methods(new_spec.interface)

            # Check for removed methods
            for method in old_methods:
                if method not in new_methods:
                    breaking_changes.append(f"Removed method: {method}")

            # Check for changed signatures
            for method in new_methods:
                if method in old_methods:
                    old_sig = old_methods[method]
                    new_sig = new_methods[method]
                    if old_sig != new_sig:
                        breaking_changes.append(f"Changed signature: {method} ({old_sig} -> {new_sig})")

        # Check lifecycle changes
        if old_spec.lifetime != new_spec.lifetime:
            warnings.append(f"Lifetime changed: {old_spec.lifetime.value} -> {new_spec.lifetime.value}")

        return CompatibilityResult(
            port_name=old_spec.name,
            old_version=old_spec.version,
            new_version=new_spec.version,
            is_compatible=len(breaking_changes) == 0,
            breaking_changes=breaking_changes,
            warnings=warnings,
        )

    def _get_methods(self, interface: Type) -> dict[str, str]:
        """Get all methods and their signatures from an interface."""
        methods = {}
        for name in dir(interface):
            if name.startswith("_"):
                continue
            obj = getattr(interface, name)
            if callable(obj) or isinstance(obj, property):
                try:
                    sig = inspect.signature(obj)
                    methods[name] = str(sig)
                except (ValueError, TypeError):
                    pass
        return methods


class PortContractTest:
    """Base class for port contract tests.

    All port implementations must inherit from this and implement contract tests.
    """

    @classmethod
    def get_port_name(cls) -> str:
        """Return the port name being tested."""
        raise NotImplementedError

    @classmethod
    def get_implementation(cls) -> Any:
        """Return the implementation instance to test."""
        raise NotImplementedError

    def run_contract_tests(self) -> None:
        """Run all contract tests.

        Called by CI to verify implementation matches contract.
        """
        port_name = self.get_port_name()
        impl = self.get_implementation()

        logger.info("Running contract tests for: %s", port_name)

        # Verify implementation exists in registry
        from src.domain.ports.registry import _global_registry

        spec = _global_registry.get(port_name)
        if spec is None:
            raise RuntimeError(f"Port not registered: {port_name}")

        # Verify implementation matches interface
        self._verify_implements_interface(impl, spec.interface)

        # Run concrete contract tests
        self.test_contract()

    def _verify_implements_interface(
        self,
        impl: Any,
        interface: Type,
    ) -> None:
        """Verify that implementation actually implements the interface."""
        if not isinstance(impl, interface) and not issubclass(type(impl), interface):
            raise AssertionError(f"Implementation {type(impl)} does not implement {interface}")

    def test_contract(self) -> None:
        """Implement specific contract tests in subclass."""
        raise NotImplementedError
