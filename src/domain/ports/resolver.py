"""Port resolver — dependency injection container for port resolution.

This module provides the Resolver class for resolving port implementations
from the registry and managing their lifecycle.
"""

from __future__ import annotations

import importlib
import inspect
import logging
from typing import Any, Type, TypeVar

from src.domain.ports.registry import Lifetime, PortRegistry, PortSpec, _global_registry

logger = logging.getLogger(__name__)

T = TypeVar("T")


class Resolver:
    """Dependency injection resolver for ports.

    Resolves port implementations from the registry and manages their lifecycle
    (transient, scoped, singleton).
    """

    def __init__(
        self,
        registry: PortRegistry | None = None,
        overrides: dict[str, Any] | None = None,
    ):
        """Initialize resolver.

        Args:
            registry: Port registry to use (defaults to global registry)
            overrides: Port name to instance mapping for testing
        """
        self._registry = registry or _global_registry
        self._overrides = overrides or {}
        self._instances: dict[str, Any] = {}
        self._scoped_context: dict[str, Any] = {}

    def resolve(self, port_name: str) -> Any:
        """Resolve a port by name and return an instance.

        Args:
            port_name: Name of the port to resolve

        Returns:
            Port implementation instance

        Raises:
            KeyError: If port is not registered
            RuntimeError: If port is deprecated
        """
        if port_name in self._overrides:
            return self._overrides[port_name]

        spec = self._registry.get(port_name)
        if spec is None:
            raise KeyError(f"Port not registered: {port_name}")

        if spec.deprecated:
            logger.warning("Using deprecated port: %s", port_name)

        return self._create_instance(spec)

    def resolve_by_interface(self, interface: Type[T]) -> Any:
        """Resolve a port by its interface type.

        Args:
            interface: Interface type to resolve

        Returns:
            Port implementation instance

        Raises:
            KeyError: If no port found for interface
        """
        spec = self._registry.get_by_interface(interface)
        if spec is None:
            raise KeyError(f"Port not found for interface: {interface.__name__}")
        return self._create_instance(spec)

    def _create_instance(self, spec: PortSpec) -> Any:
        """Create an instance based on lifecycle."""
        if spec.lifetime == Lifetime.SINGLETON:
            if spec.name not in self._instances:
                self._instances[spec.name] = self._instantiate(spec)
            return self._instances[spec.name]

        if spec.lifetime == Lifetime.SCOPED:
            if spec.name not in self._scoped_context:
                self._scoped_context[spec.name] = self._instantiate(spec)
            return self._scoped_context[spec.name]

        # TRANSIENT
        return self._instantiate(spec)

    def _instantiate(self, spec: PortSpec) -> Any:
        """Instantiate a port implementation."""
        if callable(spec.impl) and not isinstance(spec.impl, type):
            return spec.impl(resolver=self)
        if isinstance(spec.impl, str):
            return self._load_from_module_path(spec.impl)
        return self._auto_inject(spec.impl)

    def _load_from_module_path(self, module_path: str) -> Any:
        """Load class from module path string (lazy loading).

        Args:
            module_path: Fully qualified path like 'module.ClassName'

        Returns:
            Loaded class or instance
        """
        try:
            module_name, class_name = module_path.rsplit(".", 1)
            module = importlib.import_module(module_name)
            cls = getattr(module, class_name)
            # Return the class itself (not an instance) for auto_inject to handle
            return cls
        except (ImportError, AttributeError) as e:
            raise RuntimeError(f"Failed to lazy-load {module_path}: {e}") from e

    def _auto_inject(self, cls: Type[T]) -> T:
        """Auto-inject constructor dependencies."""
        sig = inspect.signature(cls.__init__)
        kwargs = {}
        failures = []

        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue
            if param.annotation is inspect.Parameter.empty:
                continue

            param_type = param.annotation

            try:
                instance = self.resolve(param_name)
                kwargs[param_name] = instance
            except KeyError:
                try:
                    instance = self.resolve_by_interface(param_type)
                    kwargs[param_name] = instance
                except KeyError:
                    if param.default is inspect.Parameter.empty:
                        failures.append(param_name)
                    else:
                        kwargs[param_name] = param.default

        if failures:
            raise RuntimeError(f"Cannot resolve required dependencies for {cls.__name__}: {failures}")

        return cls(**kwargs)

    def clear_scoped(self) -> None:
        """Clear scoped instances (call at request end)."""
        self._scoped_context.clear()

    def clear_singleton(self) -> None:
        """Clear singleton instances."""
        self._instances.clear()


# Default global resolver
_default_resolver: Resolver | None = None


def get_resolver() -> Resolver:
    """Get the global resolver instance."""
    global _default_resolver
    if _default_resolver is None:
        _default_resolver = Resolver()
    return _default_resolver


def resolve(port_name: str) -> Any:
    """Global resolve function.

    Args:
        port_name: Name of the port to resolve

    Returns:
        Port implementation instance
    """
    return get_resolver().resolve(port_name)
