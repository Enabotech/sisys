"""SISYS 领域层端口解析器模块

提供 Resolver 类，从注册中心解析端口实现并管理其生命周期（瞬态、作用域、单例）

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
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
    """依赖注入端口解析器，从注册中心解析端口实现并管理生命周期

    Attributes:
        _registry: 端口注册中心实例
        _overrides: 端口覆盖映射（用于测试）
        _instances: 单例实例缓存
        _scoped_context: 作用域实例缓存
    """

    def __init__(
        self,
        registry: PortRegistry | None = None,
        overrides: dict[str, Any] | None = None,
    ):
        """初始化解析器

        Args:
            registry: 端口注册中心（默认使用全局注册中心）
            overrides: 端口名到实例的映射（用于测试）
        """
        self._registry = registry or _global_registry
        self._overrides = overrides or {}
        self._instances: dict[str, Any] = {}
        self._scoped_context: dict[str, Any] = {}

    def resolve(self, port_name: str) -> Any:
        """通过名称解析端口并返回实例

        Args:
            port_name: 待解析的端口名称

        Returns:
            端口实现实例

        Raises:
            KeyError: 端口未注册时抛出
            RuntimeError: 端口已废弃时抛出
        """
        if port_name in self._overrides:
            return self._overrides[port_name]

        spec = self._registry.get(port_name)
        if spec is None:
            raise KeyError(f"Port not registered: {port_name}")

        if spec.deprecated:
            logger.warning("Using deprecated port: %s", port_name)

        return self._create_instance(spec)

    def resolve_by_interface(self, interface: Type[T] | str) -> Any:
        """通过接口类型解析端口

        Args:
            interface: 接口类型

        Returns:
            端口实现实例

        Raises:
            KeyError: 未找到匹配接口的端口时抛出
        """
        if isinstance(interface, str):
            raise KeyError(f"Cannot resolve forward-reference annotation: {interface}")
        spec = self._registry.get_by_interface(interface)
        if spec is None:
            raise KeyError(f"Port not found for interface: {interface.__name__}")
        return self._create_instance(spec)

    def _create_instance(self, spec: PortSpec) -> Any:
        """根据生命周期策略创建实例"""
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
        """实例化端口实现"""
        if callable(spec.impl) and not isinstance(spec.impl, type):
            return spec.impl(resolver=self)
        if isinstance(spec.impl, str):
            cls = self._load_from_module_path(spec.impl)
            return self._auto_inject(cls)
        return self._auto_inject(spec.impl)

    def _load_from_module_path(self, module_path: str) -> Any:
        """从模块路径字符串延迟加载类

        Args:
            module_path: 完全限定路径，如 'module.ClassName'

        Returns:
            加载的类或实例
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
        """自动注入构造函数依赖"""
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
        """清除作用域实例（请求结束时调用）"""
        self._scoped_context.clear()

    def clear_singleton(self) -> None:
        """清除单例实例"""
        self._instances.clear()


# Default global resolver
_default_resolver: Resolver | None = None


def get_resolver() -> Resolver:
    """获取全局解析器实例"""
    global _default_resolver
    if _default_resolver is None:
        _default_resolver = Resolver()
    return _default_resolver


def resolve(port_name: str) -> Any:
    """全局解析函数

    Args:
        port_name: 待解析的端口名称

    Returns:
        端口实现实例
    """
    return get_resolver().resolve(port_name)
