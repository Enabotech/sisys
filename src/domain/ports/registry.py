"""Port registry — unified port management for hexagonal architecture.

This module provides the central registry for all port contracts in the system.
Ports are registered with metadata (name, version, interface, implementation, module).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Type

logger = logging.getLogger(__name__)


class Lifetime(Enum):
    """Port lifecycle management."""

    TRANSIENT = "transient"  # New instance per request
    SCOPED = "scoped"  # Single instance per scope
    SINGLETON = "singleton"  # Global single instance


@dataclass(frozen=True)
class PortSpec:
    """Port specification metadata.

    Attributes:
        name: Unique port name
        version: Semantic version (semver)
        interface: Protocol interface type
        impl: Implementation type, factory function, or module path string
        module: Module path where implementation is located
        lifetime: Instance lifecycle (default: SCOPED)
        owner: Team or individual responsible
        compatibility: Tuple of compatible versions
        tags: Tags for scenario/environment selection
        deprecated: Whether port is deprecated
    """

    name: str
    version: str
    interface: Type
    impl: Type | Callable[..., Any] | str
    module: str
    lifetime: Lifetime = Lifetime.SCOPED
    owner: str = ""
    compatibility: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    deprecated: bool = False


class PortRegistry:
    """Central port registry.

    Singleton pattern ensures a single source of truth for all port registrations.
    """

    _instance: PortRegistry | None = None
    _ports: dict[str, PortSpec] = field(default_factory=dict)

    def __new__(cls) -> PortRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._ports = {}
        return cls._instance

    def register(self, spec: PortSpec) -> None:
        """Register a port.

        Args:
            spec: Port specification to register

        Raises:
            ValueError: If port name already exists
        """
        if spec.name in self._ports:
            raise ValueError(f"Port already registered: {spec.name}")
        logger.info("Registering port: %s (%s)", spec.name, spec.version)
        self._ports[spec.name] = spec

    def get(self, name: str) -> PortSpec | None:
        """Get port specification by name."""
        return self._ports.get(name)

    def get_by_interface(self, interface: Type) -> PortSpec | None:
        """Get port specification by interface type."""
        for spec in self._ports.values():
            if spec.interface is interface:
                return spec
            if isinstance(interface, type) and isinstance(spec.interface, type):
                if issubclass(spec.interface, interface):
                    return spec
        return None

    def list_all(self) -> list[PortSpec]:
        """List all registered port specifications."""
        return list(self._ports.values())

    def list_by_tag(self, tag: str) -> list[PortSpec]:
        """List port specifications filtered by tag."""
        return [spec for spec in self._ports.values() if tag in spec.tags]

    def unregister(self, name: str) -> None:
        """Unregister a port by name."""
        if name in self._ports:
            del self._ports[name]
            logger.info("Unregistered port: %s", name)

    def __contains__(self, name: str) -> bool:
        return name in self._ports

    def __len__(self) -> int:
        return len(self._ports)


# Global registry instance
_global_registry = PortRegistry()


def register_port(
    name: str,
    version: str,
    interface: Type,
    impl: Type | Callable[..., Any] | str,
    module: str,
    **kwargs: Any,
) -> None:
    """Convenient port registration function.

    Args:
        name: Unique port name
        version: Semantic version
        interface: Protocol interface type
        impl: Implementation type, factory, or module path string (for lazy loading)
        module: Module path
        **kwargs: Additional PortSpec fields (lifetime, owner, tags, etc.)
    """
    spec = PortSpec(
        name=name,
        version=version,
        interface=interface,
        impl=impl,
        module=module,
        **kwargs,
    )
    _global_registry.register(spec)
